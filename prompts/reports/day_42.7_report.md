# Отчёт — День 42.7 — Пул Presidio-движков + мгновенная остановка + батчинг FP-фильтра (v3.13.2)

**Дата:** 14.09.2026
**Версия:** v3.13.2
**Ветка:** `feature/day_42.5_scanner_optimization`
**Предыдущая версия:** v3.13.1
**ТЗ:** прямое задание пользователя (2 пункта, файл не заводился):
1. Сканер не останавливается по Ctrl+C: после FS-остановки продолжается пост-обработка (~5 сек: сериализация 47 545 находок, CheckFingerprints → **422** — лимит эндпоинта 10 000, каталог, метрики).
2. Увеличить скорость сканирования (36 ф/мин, ETA 10ч20м на 22 500 файлов) — узкое место: Presidio-анализ сериализован единым `_analyzer_lock`.

---

## 1. Цель дня

1. **Мгновенная остановка**: Ctrl+C должен останавливать сканер сразу, без пост-обработки результата прерванного задания (сериализация 47 545 находок + FP-фильтр на 47 545 fingerprint'ов → 422).
2. **Ускорение Presidio**: распараллелить анализ через **пул AnalyzerEngine** (по движку на воркер), убрав глобальный лок.
3. **Сопутствующее**: `check-fingerprints` разбивается на чанки (лимит Manager 10 000); завалящая настройка классификаторов из конфига (секции `*_classifier`, а не `pii`) уже применялась — чиним чтение конфига.

---

## 2. Что сделано

### 42.7.1 — Пул AnalyzerEngine в `PiiClassifier` ✅

`scanner/classifiers/pii_classifier.py`:
- новые поля: `self._analyzers: List[Tuple[AnalyzerEngine, Lock]]`, `self._analyzer_next`, `self._thread_analyzers = threading.local()`;
- `_get_analyzer()` → `(analyzer, lock)`: при пуле каждый поток получает свой движок через thread-local (round-robin при первом обращении) вместе с локом движка — воркеры анализируют файлы **параллельно**, глобального лока нет; при пуле < числа воркеров лок движка страхует от гонок; legacy-фолбэк `(self._analyzer, self._analyzer_lock)`;
- `configure(...)`: создаёт пул размером `analyzer_pool_size` (default `max(1, min(config.get("max_parallel_files", 2), 4))`, ограничение `min(pool_size, 8)`);
- `_add_custom_recognizers(analyzer=None)` — кастомные recognizers (PhoneRU/PassportRU/SnilsRU/InnRU/EmailRU) добавляются к **каждому** движку пула через `analyzer.registry.add_recognizer(...)` (исправлены все 5 вызовов с `self._analyzer.registry` → `analyzer.registry`);
- `scan_line`/`scan_text` используют `_get_analyzer()` и лок движка вместо глобального `self._analyzer`/`self._analyzer_lock`;
- лог инициализации: `[PII] ✅ Presidio инициализирован с локальными моделями (пул: N)`.

### 42.7.2 — Мгновенная остановка в `_execute_task_linewise` ✅

`scanner/src/managed_scanner.py`:
- сразу после `_scan_line_by_line`: если `_should_exit or _stop_event.is_set()` → **немедленный return** со `stats["aborted"] = True` (files_scanned из скана), без сериализации находок, без FP-фильтра, без каталога, без метрик. Находки прерванного задания не отправляются (задача остаётся assigned — как день 42.6);
- `run_scanner.py` Ctrl+C → `scanner.stop()` → `_stop_event.set()` → ранний выход из активного `_execute_task_linewise`.

### 42.7.3 — Батчинг `check-fingerprints` (FP_CHUNK = 5000) ✅

`scanner/src/managed_scanner.py` (`ManagerClient.check_fingerprints`):
- эндпоинт Manager принимает `max_length=10000` (manager/src/api/schemas_findings.py:113) — при 47 545 находках запрос падал с **422**, FP-фильтр fail-open возвращал `None` (т.е. не работал);
- fingerprints отправляются чанками по 5000, результаты (`false_positives`/`confirmed`/`new`) объединяются;
- при неудаче любого чанка — return `None` (fail-open, как раньше), лог с номером чанка.

### 42.7.4 — Корректное чтение конфига классификаторов ✅

`scanner/src/config_loader.py`:
- баг: `ClassifiersConfig.from_dict` читал секции `pii`/`credentials`/`code`, а в `scanner_config.json` они называются `pii_classifier`/`credentials_classifier`/`code_classifier` → конфиг классификаторов фактически игнорировался (`min_confidence` был дефолт 0.5, а не 0.3 из файла; `ocr_enabled` и пр. тоже не применялись);
- теперь поддерживаются **оба** варианта имён: `data.get("pii", data.get("pii_classifier", {}))` и аналогично для credentials/code;
- `PiiConfig.analyzer_pool_size: int = 0` (0 = авто по `max_parallel_files`), поле в `to_dict`.

### 42.7.5 — Передача настроек в `_load_classifiers` + shutdown OCRWorker ✅

`scanner/src/managed_scanner.py`:
- `_load_classifiers`: в dict PII добавляются `analyzer_pool_size` (0 = авто) и, если `analyzer_pool_size <= 0`, `max_parallel_files` из `ConnectorConfig` (default 4);
- **осиротевшие OCRWorker**: при остановке сканера `stop_ocr_worker` не вызывался → оставались дочерние `spawn_main`-процессы (найдены сироты PID 5936 и 23976 с мёртвыми родителями 5948/8392). В конце `run_loop` теперь вызывается `shutdown()` у всех классификаторов, у которых он есть (PiiClassifier → `_stop_ocr_worker()`).

### 42.7.6 — Конфиг сканера ✅

`scanner/config/scanner_config.json`:
- `pii_classifier.analyzer_pool_size: 4`,
- `connector.max_parallel_files: 8` (было 4) — до лимита пула Presidio (8).

---

## 3. Полный код (изменённые фрагменты)

### `scanner/classifiers/pii_classifier.py`

Добавлен импорт `Tuple`:
```python
from typing import Dict, Any, List, Optional, Tuple
```

Новые поля в `__init__` + метод `_get_analyzer()`:
```python
        self._analyzer = None
        # Пул AnalyzerEngine (день 40.2+): по движку на рабочий поток,
        # чтобы Presidio-анализ файлов шёл параллельно, а не через один лок.
        self._analyzers: List[Any] = []
        self._analyzer_next = 0
        self._thread_analyzers = threading.local()
        ...
        self._analyzer_lock = threading.Lock()

    def _get_analyzer(self) -> Tuple[Optional[AnalyzerEngine], Optional[threading.Lock]]:
        """Возвращает (движок Presidio, лок) для текущего потока.

        При пуле движков (self._analyzers) каждый поток получает свой движок
        по thread-local (round-robin при первом обращении) вместе с его локом —
        анализ файлов в воркерах идёт параллельно, ожидания на общий лок нет.
        Если же два потока делят один движок (пул меньше числа воркеров),
        лок движка гарантирует безопасность analyze().
        Если пул не создан (legacy) — возвращает (self._analyzer, self._analyzer_lock).
        """
        if self._analyzers:
            entry = getattr(self._thread_analyzers, "entry", None)
            if entry is None:
                with self._analyzer_lock:
                    entry = self._analyzers[self._analyzer_next % len(self._analyzers)]
                    self._analyzer_next += 1
                self._thread_analyzers.entry = entry
            return entry[0], entry[1]
        return self._analyzer, self._analyzer_lock
```

`configure` — создание пула:
```python
        try:
            # Пул движков (день 40.2+): размер — число параллельных воркеров
            # коннектора (или analyzer_pool_size), но не более 4 по умолчанию,
            # чтобы ограничить расход RAM на модели spaCy.
            pool_size = int(config.get(
                "analyzer_pool_size",
                max(1, min(config.get("max_parallel_files", 2), 4)),
            ) or 1)
            pool_size = max(1, min(pool_size, 8))

            self._analyzers = []
            for _ in range(pool_size):
                nlp_engine = self._get_nlp_engine()
                analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine,
                    supported_languages=["ru", "en"]
                )
                self._add_custom_recognizers(analyzer)
                self._analyzers.append((analyzer, threading.Lock()))

            self._analyzer = self._analyzers[0][0]
            print(f"[PII] ✅ Presidio инициализирован с локальными моделями (пул: {pool_size})")
        except Exception as e:
            print(f"[PII] ❌ Ошибка инициализации Presidio: {e}")
```

`scan_line` — через пул:
```python
        analyzer, analyzer_lock = self._get_analyzer()
        if analyzer is not None:
            try:
                with analyzer_lock:
                    results = analyzer.analyze(text=line, language="ru")
                min_confidence = self.config.get("min_confidence", 0.5)
```

`scan_text` — через пул:
```python
        analyzer, analyzer_lock = self._get_analyzer()
        if analyzer is not None:
            try:
                with analyzer_lock:
                    results = analyzer.analyze(text=text, language="ru")
```

`_add_custom_recognizers` — на переданный движок (все 5 вызовов):
```python
    def _add_custom_recognizers(self, analyzer: Optional[AnalyzerEngine] = None):
        """Добавление кастомных распознавателей для РФ"""
        analyzer = analyzer or self._analyzer
        ...
        analyzer.registry.add_recognizer(phone_recognizer)
        ...
        analyzer.registry.add_recognizer(passport_recognizer)
        ...
        analyzer.registry.add_recognizer(snils_recognizer)
        ...
        analyzer.registry.add_recognizer(inn_recognizer)
        ...
        analyzer.registry.add_recognizer(email_recognizer)
```

### `scanner/src/config_loader.py`

```python
class PiiConfig:
    ...
    analyzer_pool_size: int = 0  # 0 = авто (=== max_parallel_files)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PiiConfig':
        return cls(
            ...
            analyzer_pool_size=data.get("analyzer_pool_size", 0),
        )
```

```python
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClassifiersConfig':
        # Поддержка обоих вариантов имён секций: "pii" и "pii_classifier" (день 42)
        return cls(
            pii=PiiConfig.from_dict(data.get("pii", data.get("pii_classifier", {}))),
            credentials=CredentialsConfig.from_dict(
                data.get("credentials", data.get("credentials_classifier", {}))
            ),
            code=CodeConfig.from_dict(data.get("code", data.get("code_classifier", {})))
        )
```

`to_dict` — добавлено `analyzer_pool_size` в секцию `pii`.

### `scanner/src/managed_scanner.py`

Мгновенная остановка в `_execute_task_linewise` (после `scan_result`):
```python
        scan_result = self._scan_line_by_line(resource_path)
        findings_objects = scan_result["findings"]

        # Мгновенная остановка: если stop_event выставлен после скана —
        # НЕ сериализуем/шифруем находки и НЕ шлём FP-фильтр (день 40.2+).
        if self._should_exit or self._stop_event.is_set():
            logger.warning(
                f"[Scanner] Task {task_id} прервана при остановке — "
                f"post-processing пропущен ({len(findings_objects)} находок не сериализованы)"
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

Батчинг FP-фильтра:
```python
        # Чанками по 5000 — эндпоинт Manager принимает не более 10000 за запрос (день 40.2+)
        FP_CHUNK = 5000
        merged: Dict[str, Any] = {"false_positives": [], "confirmed": [], "new": []}
        url = f"{self.base_url}/api/findings/check-fingerprints"
        try:
            for i in range(0, len(fingerprints), FP_CHUNK):
                chunk = fingerprints[i:i + FP_CHUNK]
                response = self.session.post(
                    url, json={"fingerprints": chunk}, timeout=self.timeout,
                )
                if response.status_code == 200:
                    data = response.json()
                    merged["false_positives"].extend(data.get("false_positives", []))
                    merged["confirmed"].extend(data.get("confirmed", []))
                    merged["new"].extend(data.get("new", []))
                else:
                    logger.warning(
                        "[CheckFingerprints] Failed (chunk %d): %s %s",
                        i // FP_CHUNK + 1, response.status_code, response.text[:200],
                    )
                    return None
            return merged
        except Exception as e:
            logger.warning("[CheckFingerprints] Error: %s", e)
            return None
```

`_load_classifiers` — передача настроек в PII:
```python
                    pii_config_dict = {
                        "enabled": pii_config.enabled,
                        "min_confidence": pii_config.min_confidence,
                        "ocr_enabled": pii_config.ocr_enabled,
                        "ocr_psm": pii_config.ocr_psm,
                        "ocr_timeout": pii_config.ocr_timeout,
                        "max_file_size_mb": pii_config.max_file_size_mb,
                        "quick_filter_enabled": pii_config.quick_filter_enabled,
                        "analyzer_pool_size": pii_config.analyzer_pool_size,  # 0 = авто
                    }
                    if self.config and self.config.connector and pii_config.analyzer_pool_size <= 0:
                        pii_config_dict["max_parallel_files"] = (
                            getattr(self.config.connector, "max_parallel_files", None) or 4
                        )
```

`run_loop` — shutdown классификаторов (убийство OCRWorker):
```python
        self.client.heartbeat(status="offline")
        if self.heartbeat_thread is not None:
            self.heartbeat_thread.stop()
        # Корректное завершение классификаторов (OCRWorker и др. процессы) —
        # иначе после остановки сканера остаются осиротевшие дочерние процессы.
        for clf in self.classifiers:
            shutdown = getattr(clf, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as e:
                    logger.debug("Classifier shutdown error %s: %s", getattr(clf, "classifier_name", clf), e)
        logger.info("👋 Сканер остановлен")
```

### `scanner/config/scanner_config.json`

```json
        "pii_classifier": {
            "enabled": true,
            "min_confidence": 0.3,
            "ocr_enabled": true,
            "analyzer_pool_size": 4
        },
        ...
    "connector": {
        ...
        "max_parallel_files": 8,
```

---

## 4. Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `scanner/classifiers/pii_classifier.py` | Пул AnalyzerEngine (`_analyzers`), `_get_analyzer()` (thread-local), recognizers на каждый движок, `scan_line`/`scan_text` через пул |
| `scanner/src/config_loader.py` | `PiiConfig.analyzer_pool_size`, `ClassifiersConfig.from_dict` — поддержка `*_classifier` секций, `to_dict` |
| `scanner/src/managed_scanner.py` | Мгновенная остановка (aborted), FP_CHUNK=5000, передача настроек в `_load_classifiers`, shutdown классификаторов в `run_loop` |
| `scanner/config/scanner_config.json` | `analyzer_pool_size: 4`, `connector.max_parallel_files: 8` |

`run_scanner.py` — без изменений (Ctrl+C уже звал `scanner.stop()`, теперь прерывание мгновенное).

---

## 5. Тесты

- `python -m py_compile` для 3 python-файлов — **OK**;
- `temp/test_pii_pool.py` (удалён после проверки): пул 2 движка, 9 находок из строки с ФИО/телефоном/email/паспортом/ИНН/СНИЛС — **OK**; найден и исправлен баг `_add_custom_recognizers` в одном месте (`phone_recognizer` добавлялся в `self._analyzer.registry` вместо `analyzer.registry` → `AttributeError`);
- `temp/test_scanner_init.py` (удалён): реальный `_load_classifiers` + `run_loop`-подобная инициализация:
  - пул: `[PII] ✅ Пресушио инициализирован ... (пул: 4)` — 4 движка, recognizers у каждого;
  - конфиг: `connector.max_parallel_files: 8`, `pii.min_confidence: 0.3`, `pii.analyzer_pool_size: 4`;
  - `line pipeline ready: True`;
  - OCRWorker запускается (PID 5300) и **корректно останавливается** через `shutdown()` — `[PII] Остановка OCRWorker... → [PII] OCRWorker остановлен`; процесс 5300 завершён.

**Гигиена процессов:** убиты осиротевшие OCRWorker-процессы `spawn_main` PID 5936 и 23976 (родители 5948/8392 мертвы — остались от предыдущих остановок сканера).

**Ограничение тестов:** живой прогон всего конфига (загрузка моделей spaCy ~2 мин) не выполнялся — только init-путь и паритет; полный E2E — на ручном тестировании (раздел 6).

---

## 6. Инструкция по запуску для ручного тестирования

1. Перезапуск сканера (подхват нового кода; единый процесс на хосте):
```powershell
cd E:\projects\dcap-system
Get-Process python* | Where-Object { $_.Path -like "*Anaconda3*" } | Stop-Process
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"
python run_scanner.py scanner/config/scanner_config.json
```
2. **Ctrl+C**: во время активного сканирования нажать Ctrl+C — «Получен сигнал остановки...», затем «Задача прервана пользователем — результаты не отправлены», «Сканер остановлен» — **мгновенно** (раньше +~5 сек на пост-обработку 47 545 находок и 422 от FP-запроса).
3. **Отсутствие осиротевших процессов** после остановки: `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -match 'spawn_main' }` — пусто.
4. **Скорость**: в логе `[ScanProgress] … | скорость N ф/мин | ETA …` — ожидается рост при Presidio-heavy файлах (пул 4 движка, 8 воркеров против единого лока).
5. WebUI `http://localhost:8001` (admin/admin123) → «Сканеры» — прогресс задания; статус сканера после остановки — офлайн.

---

## 7. Примечания

- **Побочный эффект фикса конфига (42.7.4):** `min_confidence` теперь реально читается из файла (**0.3** вместо дефолта 0.5) — чувствительность PII-скана увеличится (больше находок). Это исправление бага, но для аудита означает больше результатов; при желании можно поднять значение в конфиге.
- **GIL:** многопоточный Presidio ограничен GIL; пул движков даёт выигрыш именно за счёт снятия единого лока + локальных движков (spaCy модели переиспользуются). Реальный прирост повторил init-тест; цифры E2E — на ручном прогоне.
- **Black не применён** (как 42.5/42.6) — правки внесены вручную в исходном стиле.
- В diff попали и более ранние правки сессии (scan_text, stop_event, ThreadPoolExecutor) — они уже зафиксированы отчётами 42.5/42.6; в git add для этого коммита включаются и они (уже в рабочем дереве).