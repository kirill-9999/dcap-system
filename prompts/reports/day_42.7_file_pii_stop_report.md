# 📝 Отчёт — День 42.7 — Файловый PII: пул движков + FP-батчинг + мгновенная остановка (v3.13.2)

**Дата:** 14.09.2026
**Версия:** v3.13.2
**Целевая версия:** v3.3.0 (релиз)
**Статус:** 🟢 День 42.7 выполнен
**Предыдущий отчёт:** `day_42.6_file_pii_stop_report.md` (v3.13.1)
**ТЗ:** прямое задание пользователя (2 пункта, файл не заводился — как 42.5/42.6):
1. Сканер не останавливается по Ctrl+C (продолжение 42.6): после остановки `_executor_run_linewise` всё
   ещё ~4-5 сек тратил на пост-обработку — сериализация 47 545 находок, обход `check-fingerprints`
   (422 из-за лимита Manager 10 000), каталог, метрики.
2. Скорость (продолжение 42.6): Presidio-анализ сериализован единым `_analyzer_lock` — воркеры PII ждут
   глобальный лок, файлы сканируются медленнее, чем могли бы.

---

## 1. Что сделано

### 42.7.1 — Пул AnalyzerEngine в `PiiClassifier` (пул движков Presidio) ✅

Классический `_analyzer_lock` сериализовал ВСЕ Presidio-вызовы в воркерах → PII-анализ файлов шёл
последовательно. Решение: **пул независимых AnalyzerEngine** — по движку на поток (thread-local), анализ
файлов идёт параллельно, без общего глобального лока.

`scanner/classifiers/pii_classifier.py`:
```python
        self._analyzer = None
        # Пул AnalyzerEngine (день 42.7): по движку на рабочий поток, чтобы
        # Presidio-анализ файлов шёл параллельно, а не через единый _analyzer_lock.
        self._analyzers: List[Tuple[AnalyzerEngine, threading.Lock]] = []
        self._analyzer_next = 0
        self._thread_analyzer = threading.local()
```

`_get_analyzer()` — thread-local + round-robin при первом обращении:
```python
    def _get_analyzer(self) -> Tuple[Optional[AnalyzerEngine], Optional[threading.Lock]]:
        """Возвращает (движок, лок) для текущего потока.

        При пуле (self._analyzers) каждый поток получает свой движок через thread-local
        (round-robin при первом обращении) вместе с его локом — анализ файлов в воркерах
        идёт параллельно. Если пул меньше числа воркеров, лок движка страхует от гонок.
        Без пула (legacy) — (self._analyzer, self._analyzer_lock).
        """
        if self._analyzers:
            entry = getattr(self._thread_analyzer, "entry", None)
            if entry is None:
                entry = self._analyzers[self._analyzer_next % len(self._analyzers)]
                self._analyzer_next += 1
                self._thread_analyzer.entry = entry
            return entry[0], entry[1]
        return self._analyzer, self._analyzer_lock
```

`_add_custom_recognizers(analyzer=None)` — recognizers добавляются к переданному движку (иначе
`AttributeError: 'NoneType' object has no attribute 'registry'` на телефонном recognizer):
```python
    def _add_custom_recognizers(self, analyzer=None):
        """Добавление кастомных распознавателей для РФ."""
        analyzer = analyzer or self._analyzer

        # 1. Телефоны РФ
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            name="PhoneRU",
            patterns=[...],
            supported_language="ru",
        )
        analyzer.registry.add_recognizer(phone_recognizer)
        ...
        # 2. Паспорт, 3. СНИЛС, 4. ИНН, 5. Email — аналогично
```

`configure()` — создание пула движков:
```python
        pool_size = int(self.config.get("analyzer_pool_size", 0) or 0)
        if pool_size <= 0:
            # авто: === числу параллельных файлов коннектора, но не более 4
            pool_size = max(1, min(int(self.config.get("max_parallel_files", 2) or 2), 4))
        pool_size = max(1, min(pool_size, 8))

        self._analyzers = []
        for _ in range(pool_size):
            nlp_engine = self._get_nlp_engine()
            analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["ru", "en"],
            )
            self._add_custom_recognizers(analyzer)
            self._analyzers.append((analyzer, threading.Lock()))

        print(f"[PII] ✅ Presidio инициализирован с локальными моделями (пул: {pool_size})")
```

Использование в `scan_text`/`scan_line` — движок из пула + лок, а не `self._analyzer`:
```python
        analyzer, analyzer_lock = self._get_analyzer()
        if analyzer is not None:
            try:
                with analyzer_lock:
                    results = analyzer.analyze(text=line, language="ru")
```

### 42.7.2 — Мгновенная остановка по Ctrl+C через `stop_event` (дополнение к 42.6) ✅

`scanner/src/managed_scanner.py` — **ранний выход из `_execute_task_linewise`** при стопе: находки прерванной
задачи НЕ сериализуются, НЕ проходят FP-фильтр, НЕ добавляются в каталог, НЕ отправляются в Manager:

```python
            # Мгновенная остановка: если stop_event установлен после скана —
            # НЕ сериализуем находки, НЕ гоним FP-фильтр/каталог/метрики (день 42.7).
            if self._should_exit or self._stop_event.is_set():
                logger.warning(
                    f"[Scanner] Task {task_id} прервана при остановке — "
                    f"пост-обработка пропущена ({len(findings_objects)} находок не сериализовано)"
                )
                return {
                    "findings": [],
                    "catalog_entries": [],
                    "failed_files": [],
                    "stats": {
                        "files_scanned": int(scan_result.get("files_scanned", 0) or 0),
                        "files_failed": 0,
                        "files_with_findings": 0,
                        "total_findings": 0,
                        "unique_findings": 0,
                        "category_stats": {},
                        "started_at": task.get("assigned_at", datetime.utcnow().isoformat()),
                        "completed_at": datetime.utcnow().isoformat(),
                        "encryption": "enabled" if self._enc else "legacy",
                        "aborted": True,
                    },
                }
```

### 42.7.3 — Батчинг `check-fingerprints` (FP_CHUNK = 5000) ✅

`scanner/src/managed_scanner.py` — Manager лимитирует 10 000 fingerprint'ов за запрос (422 при 47 545):
```python
    FP_CHUNK = 5000
    ...
            fingerprints = [f["fingerprint"] for f in serialized]
            # Батчинг: Manager принимает не более 10 000 за запрос (день 42.7)
            fp_results = self._check_fingerprints_batched(fingerprints)
```

`_check_fingerprints_batched`:
```python
    def _check_fingerprints_batched(self, fingerprints: List[str]) -> Optional[Dict[str, Any]]:
        """Проверка fingerprints батчами по FP_CHUNK (Manager: лимит 10 000/запрос).

        Возвращает объединённый результат (false_positives/confirmed/new) или None (fail-open).
        """
        if not fingerprints:
            return {"false_positives": [], "confirmed": [], "new": []}

        merged = {"false_positives": [], "confirmed": [], "new": []}
        url = f"{self.client.base_url}/api/findings/check-fingerprints"
        try:
            for i in range(0, len(fingerprints), self.FP_CHUNK):
                chunk = fingerprints[i:i + self.FP_CHUNK]
                response = self.client.session.post(
                    url,
                    json={"fingerprints": chunk},
                    timeout=self.client.timeout,
                )
                if response.status_code != 200:
                    logger.warning(
                        "[CheckFingerprints] Batch %d: HTTP %s (%s)",
                        i // self.FP_CHUNK,
                        response.status_code,
                        response.text[:120],
                    )
                    return None  # fail-open: FP-фильтр не применяется
                data = response.json()
                merged["false_positives"].extend(data.get("false_positives", []))
                merged["confirmed"].extend(data.get("confirmed", []))
                merged["new"].extend(data.get("new", []))
            return merged
        except Exception as e:
            logger.warning("[CheckFingerprints] Error: %s", e)
            return None
```

### 42.7.4 — Проброс настроек пула в `_load_classifiers` + корректный выбор движка ✅

`scanner/src/managed_scanner.py`, `_load_classifiers`:
```python
        pii_config_dict = {
            "enabled": pii_config.enabled,
            "min_confidence": pii_config.min_confidence,
            "ocr_enabled": pii_config.ocr_enabled,
            "ocr_psm": pii_config.ocr_psm,
            "ocr_timeout": pii_config.ocr_timeout,
            "analyzer_pool_size": pii_config.analyzer_pool_size,  # 0 = авто
            "max_parallel_files": getattr(
                getattr(self.config, "connector", None), "max_parallel_files", 2
            ),
        }
```

### 42.7.5 — `shutdown()` классификаторов в конце `run_loop` (убийство OCRWorker/осиротевших процессов) ✅

`scanner/src/managed_scanner.py`, конец `run_loop`:
```python
        self.client.heartbeat(status="offline")
        if self.heartbeat_thread is not None:
            self.heartbeat_thread.stop()

        # Корректное завершение классификаторов (PiiClassifier.shutdown
        # останавливает OCRWorker-процесс) — иначе после остановки сканера
        # остаются осиротевшие OCR-воркеры (день 42.7).
        for clf in self.classifiers:
            shutdown = getattr(clf, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as e:
                    logger.debug(
                        "[Scanner] Ошибка shutdown %s: %s",
                        getattr(clf, "classifier_name", type(clf).__name__), e,
                    )
        logger.info("👋 Сканер остановлен")
```

Примечание: в 42.6 OCRWorker запускался с `daemon=False` — при завершении основного процесса
оставался жить (сирота). Теперь `stop()` → `run_loop` завершается → `shutdown()` классификаторов →
`PiiClassifier.shutdown()` → `stop_ocr_worker()` останавливает OCRWorker. Найденные и убитые сироты
(если такие оставались) — вручную через `Stop-Process -Force`.

### 42.7.6 — `config_loader.py`: `analyzer_pool_size` в `PiiConfig` + поддержка обоих имён секций ✅

`scanner/src/config_loader.py`:
```python
@dataclass
class PiiConfig:
    ...
    analyzer_pool_size: int = 0  # 0 = авто (=== max_parallel_files, но ≤ 4)
```

`ClassifiersConfig.from_dict` теперь читает оба варианта имён секций (раньше конфиг классификаторов
фактически игнорировался — `min_confidence` был дефолт 0.5, а не 0.3 из файла):
```python
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClassifiersConfig':
        return cls(
            pii=PiiConfig.from_dict(data.get("pii", data.get("pii_classifier", {}))),
            credentials=CredentialsConfig.from_dict(
                data.get("credentials", data.get("credentials_classifier", {}))
            ),
            code=CodeConfig.from_dict(data.get("code", data.get("code_classifier", {}))),
        )
```

### 42.7.7 — Конфиг ✅

`scanner/config/scanner_config.json`:
- `pii_classifier`: `"analyzer_pool_size": 4`,
- `performance.max_parallel_files`: `8`.

*(редактирование .json/кода — вручную, без black)*

---

## 2. Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `scanner/classifiers/pii_classifier.py` | Пул AnalyzerEngine (`_analyzers` + thread-local + round-robin), `_get_analyzer()`, `_add_custom_recognizers(analyzer)` |
| `scanner/src/config_loader.py` | `PiiConfig.analyzer_pool_size`; `ClassifiersConfig.from_dict` — поддержка `*_classifier` секций |
| `scanner/src/managed_scanner.py` | Ранний aborted-return в `_execute_task_linewise`; FP-батчинг `FP_CHUNK=5000`; проброс пула в `_load_classifiers`; `shutdown()` классификаторов в `run_loop` |
| `scanner/config/scanner_config.json` | `analyzer_pool_size: 4`, `max_parallel_files: 8` |

*(Дифф-fragments полностью: `git diff scanner/classifiers/pii_classifier.py scanner/src/config_loader.py scanner/src/managed_scanner.py scanner/config/scanner_config.json`)*

---

## 3. Тесты

- `python -m py_compile` для `pii_classifier.py`, `config_loader.py`, `managed_scanner.py` — **OK**;
- **init-смоук** (`temp/test_scanner_init.py`, удалён после): загрузка классификаторов через
  `ManagedScanner._load_classifiers` — пул из 4 движков создан, OCRWorker стартует и **корректно
  останавливается** через `shutdown()` (сироты не остаются), конфиг читается корректно
  (`analyzer_pool_size=4`, `max_parallel_files=8`, `min_confidence=0.3`), progress-интервал 5;
- **остановка OCRWorker**: при `shutdown()` OCRWorker-процесс завершается (проверено по PID);
- **осиротевшие процессы до фикса**: найдены OCRWorker-сироты (PID 5936/23976 от мёртвых родителей,
  5300) — убиты вручную; после фикса `run_loop` → shutdown классификаторов — сироты не появляются;
- **чистка мусора**: удалены `temp_par_*` (временные данные параллельного скана) и `-v` (случайный файл).

---

## 4. Команда для коммита

```powershell
cd E:\projects\dcap-system
git add scanner/classifiers/pii_classifier.py scanner/src/config_loader.py scanner/src/managed_scanner.py scanner/config/scanner_config.json STATE.md prompts/reports/day_42.7_file_pii_stop_report.md
git commit -m "feat: День 42.7 — Файловый PII: пул движков + FP-батчинг + мгновенная остановка (v3.13.2)

- PiiClassifier: пул AnalyzerEngine (по движку на поток, thread-local + round-robin)
  вместо единого _analyzer_lock — Presidio-анализ файлов идёт параллельно;
  recognizers РФ добавляются в каждый движок пула (_add_custom_recognizers(analyzer))
- managed_scanner: ранний aborted-return при stop_event — прерванная задача НЕ
  сериализуется/не проходит FP-фильтр/каталог/метрики (мгновенная остановка Ctrl+C)
- check-fingerprints батчами по 5000 (Manager: лимит 10000/запрос) — устранён 422
- shutdown() классификаторов в run_loop — OCRWorker останавливается, нет осиротевших процессов
- config_loader: PiiConfig.analyzer_pool_size; ClassifiersConfig читает *_classifier секции
- config: analyzer_pool_size: 4, connector.max_parallel_files: 8
- CHANGELOG: v3.13.2"
```

---

## 5. Инструкция для ручного тестирования

```powershell
cd E:\projects\dcap-system
# 1) Перезапуск сканера (новый код; единый процесс на хосте)
Get-Process python* | Where-Object { $_.Path -like "*Anaconda3*" } | Stop-Process
$env:PYTHONIOENCODING='utf-8'
python run_scanner.py scanner/config/scanner_config.json
# 2) Ctrl+C во время активного сканирования — мгновенная остановка
#   (без 5-секундной пост-обработки 47 545 находок)
# 3) Скорость: в логе [PII] пул: 4 + ThreadPool 8 файл/мин — находки/presidio параллельно
# 4) После остановки проверить, что нет осиротевших OCR-процессов:
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'spawn_main|OCRWorker' } | Format-Table ProcessId,CommandLine
```
