# Отчёт — День 42.6 — Файловый PII-анализ (один Presidio на файл) + остановка сканера по Ctrl+C

**Дата:** 13.09.2026
**Версия:** v3.13.1
**Ветка:** `feature/day_42.5_scanner_optimization`
**Предыдущая версия:** v3.13.0
**ТЗ:** прямое задание пользователя (2 пункта, файл не заводился)

---

## 1. Цель дня

1. **Убрать построчный вызов Presidio**: вместо `analyze(line)` на каждую строку, прошедшую quick-check, — один `analyze(text=весь файл)`, а номер строки/позиции находки вычислять из offset. Это вторая итерация по BACKLOG-063 (первая — день 42.5: prefilter + ThreadPool, узким местом оставался построчный Presidio).
2. **Починить остановку по Ctrl+C**: лог печатал «Получен сигнал остановки...», но сканирование продолжалось до конца задания (ThreadPoolExecutor не проверял флаг `_should_exit`).

---

## 2. Что сделано

### 42.6.1 — `PiiClassifier.scan_text(text)` — файловый PII-анализ ✅

`scanner/classifiers/pii_classifier.py`:
- новый метод `scan_text(text) -> List[Finding]`: **один** вызов `self._analyzer.analyze(text=text, language="ru")` на весь текст (под `_analyzer_lock` — AnalyzerEngine не потокобезопасен);
- `_line_starts(text)` — предвычисленные offset'ы начал строк; `bisect_right` по ним даёт индекс строки (0-based) для любого offset;
- `line_number = idx + 1`; `line_text` — та строка (срез), где лежит находка; `start_pos`/`end_pos` пересчитаны относительно строки (`offset - starts[idx]`) — формат находки не меняется (день 40.2);
- кастомные regex-паттерны прогоняются по всему тексту через `finditer` с тем же пересчётом строк;
- дедупликация по `(line_number, start_pos, end_pos, category)` — позиции теперь локальные относительно строки, поэтому строку включаем в ключ (в `_deduplicate` ключ без строки);
- prefilter уровня файла — `_quick_file_regex.search(text)` (уже был, день 42.5).

### 42.6.2 — `FilesystemConnector._scan_text` — файловый путь для классификаторов ✅

`scanner/connectors/filesystem.py`:
- классификаторы, у которых есть `scan_text` (сейчас PII), обрабатываются **один раз на файл**, дальше находки дополняются контекстом (`context_before/after`, `fragment_path`) по вычисленному `line_number`;
- классификаторы без `scan_text` (Credentials, Code) — построчно `scan_line` как раньше (с `hasattr(classifier, "scan_text")` в guard построчного цикла);
- добавлен module-level `logger = logging.getLogger("dcap-scanner")`.

### 42.6.3 — Остановка сканирования по stop_event ✅

`scanner/connectors/filesystem.py`:
- `scan_path(..., stop_event=None)` — новый параметр (`threading.Event`);
- seq-режим: `if _stopped(): break` в цикле файлов;
- parallel-режим: воркер `_work` проверяет `_stopped()` и возвращает пустой список; главный цикл `ex.map` — `break` после получения результата, если стоп установлен (прогресс не накручивается на остановленных файлах);
- остановленные файлы **не считаются** в `done_counter` и не зовут `progress_callback`.

`scanner/src/managed_scanner.py`:
- `self._stop_event = threading.Event()` в `__init__` (день 42.5+);
- `stop()` → `_should_exit = True` + `self._stop_event.set()` (Ctrl+C и `stop()` прерывают активное сканирование);
- `_scan_line_by_line` → `scan_path(..., stop_event=self._stop_event)`;
- `run_loop`: после `_execute_task` — если стоп установлен, **результаты прерванной задачи НЕ отправляются** в Manager (задача остаётся assigned, данные не искажаются), `break` → heartbeat offline → «Сканер остановлен».

`run_scanner.py` — без изменений: signal_handler уже звал `scanner.stop()`, теперь это реально прерывает активный скан.

### 42.6.4 — Тесты ✅

- `py_compile` 3 изменённых файлов — OK;
- **паритет** `scan_text` vs `scan_line` на многострочном тексте: **7=7 ключей находок** (category/finding_type/line/pos/start/end/match), missing/extra пусты (`e:\Temp\opencode\test_scan_text_stop.py`);
- **номера строк и позиции** из offset сверены с фактическими строками — OK;
- **бенчмарк** (`e:\Temp\opencode\bench_pii.py`), файл 200 строк с PII: line-based **3.04 с** → file-based **1.85 с** (**1.64x**), находки идентичны (1200=1200);
- **stop_event**: на каталоге 200 файлов срабатывает на 20-м — seq 20/200, parallel 23/200 (в полёте были 3) — сканирование останавливается;
- **регрессия seq/par** (`e:\Temp\opencode\test_seq_par.py`): 30/30 идентичных, speedup 3.32x — паритет сохранён.

---

## 3. Полный код (изменённые фрагменты)

### `scanner/classifiers/pii_classifier.py`

Добавлен импорт `bisect`:
```python
import re
import time
import bisect
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
```

Новые методы (после `scan_line`, перед `_quick_line_check`):
```python
    def scan_text(self, text: str) -> List[Finding]:
        """Файловый PII-анализ (день 42.5+): один вызов Presidio на весь текст.

        Номера строк находок вычисляются из offset'ов через предвычисленные
        начала строк (bisect) — построчный вызов analyze() не нужен.
        """
        findings: List[Finding] = []

        # Быстрый негативный фильтр уровня файла (объединённый regex)
        if not text or len(text.strip()) < 5:
            return findings
        if not self._quick_file_regex.search(text):
            return findings

        starts = self._line_starts(text)

        def _line_index(offset: int) -> int:
            i = bisect.bisect_right(starts, offset) - 1
            return i if 0 <= i < len(starts) else 0

        def _line_text(idx: int) -> str:
            s = starts[idx]
            e = starts[idx + 1] if idx + 1 < len(starts) else len(text)
            if e and text[e - 1] == '\n':
                e -= 1
            return text[s:e]

        # 1. Presidio — один вызов на весь текст (под локом, analyzer не потокобезопасен)
        if self._analyzer is not None:
            try:
                with self._analyzer_lock:
                    results = self._analyzer.analyze(text=text, language="ru")
                min_confidence = self.config.get("min_confidence", 0.5)
                for r in results:
                    if r.score < min_confidence:
                        continue
                    match_text = text[r.start:r.end]
                    if not match_text:
                        continue
                    idx = _line_index(r.start)
                    findings.append(Finding(
                        line_number=idx + 1,
                        line_text=_line_text(idx),
                        match_text=match_text,
                        start_pos=max(0, r.start - starts[idx]),
                        end_pos=max(0, r.end - starts[idx]),
                        finding_type="pii",
                        category=self._map_presidio_entity(r.entity_type),
                        severity=self._severity(r.entity_type),
                        confidence=float(r.score),
                        detector="presidio",
                    ))
            except Exception as e:
                logger.warning("Presidio failed on file-level scan: %s", e)
        else:
            logger.debug("Presidio analyzer not initialized, skip file-level scan")

        # 2. Regex-паттерны (кастомные) — по всему тексту, строки из offset
        for pattern, category, severity in self.custom_patterns:
            for m in pattern.finditer(text):
                idx = _line_index(m.start())
                findings.append(Finding(
                    line_number=idx + 1,
                    line_text=_line_text(idx),
                    match_text=m.group(),
                    start_pos=max(0, m.start() - starts[idx]),
                    end_pos=max(0, m.end() - starts[idx]),
                    finding_type="pii",
                    category=category,
                    severity=severity,
                    confidence=0.85,
                    detector="regex",
                ))

        # Дедупликация: ключ по номеру строки и позициям (относительно строки)
        seen = set()
        result = []
        for f in findings:
            key = (f.line_number, f.start_pos, f.end_pos, f.category)
            if key not in seen:
                seen.add(key)
                result.append(f)
        return result

    @staticmethod
    def _line_starts(text: str) -> List[int]:
        """Offset'ы начала каждой строки (0 — первая строка)."""
        starts = [0]
        for i, ch in enumerate(text):
            if ch == '\n':
                starts.append(i + 1)
        return starts
```

### `scanner/connectors/filesystem.py`

Добавлен module-level logger:
```python
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterator, Optional, List, Callable

from core.base import SourceType, FileContext
from connectors.base import BaseConnector

from scanner.src.finding import Finding

logger = logging.getLogger("dcap-scanner")
```

`scan_path` — сигнатура + stop_event:
```python
    def scan_path(
        self,
        path: str,
        classifiers: List[Any],
        progress_callback: Optional[Callable[[int, int, int, str], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> List[Finding]:
        """
        Сканирует папку (или файл). Возвращает список Finding.
        progress_callback(stage, current, total, file_path): stage 0=обход, 1=скан.
        stop_event (день 42.5+): threading.Event — при установке сканирование
        останавливается после текущих файлов (Ctrl+C, scanner.stop()).
        """
        findings: List[Finding] = []
        files = self._discover_files(path)
        if not files:
            if progress_callback:
                progress_callback(1, 0, 0, path)
            return findings

        total = len(files)
        max_workers = self._max_workers

        def _stopped() -> bool:
            return stop_event is not None and stop_event.is_set()

        def _scan_one(file_path: str) -> List[Finding]:
            """Сканирование одного файла (общий код для seq/parallel)."""
            if not self._within_size(file_path):
                return []
            try:
                return self.scan_file(file_path, classifiers)
            except Exception as e:
                print(f"[FS] Ошибка сканирования {file_path}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                return []

        if max_workers <= 1:
            # Последовательный режим (как раньше, день 40.2)
            for i, file_path in enumerate(files, start=1):
                if _stopped():
                    logger.info("[FS] Сканирование остановлено (stop_event) на %d/%d", i, total)
                    break
                if progress_callback:
                    progress_callback(1, i, total, file_path)
                findings.extend(_scan_one(file_path))
            return findings

        # Параллельный режим (день 42): ThreadPoolExecutor.
        # Прогресс — монотонный счётчик; findings собираем в порядке завершения.
        import threading
        from concurrent.futures import ThreadPoolExecutor

        lock = threading.Lock()
        done_counter = [0]

        def _work(file_path: str):
            if _stopped():
                return []
            result = _scan_one(file_path)
            with lock:
                done_counter[0] += 1
                current = done_counter[0]
            if progress_callback:
                progress_callback(1, current, total, file_path)
            return result

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for result in ex.map(_work, files):
                findings.extend(result)
                if _stopped():
                    logger.info("[FS] Сканирование остановлено (stop_event)")
                    break

        return findings
```

`_scan_text` — файловый путь:
```python
    def _scan_text(self, text: str, classifiers: List[Any], file_path: str) -> List[Finding]:
        """Сканирует текст классификаторами.

        Классификаторы с файловым анализом (scan_text) отрабатывают один раз на
        весь текст (день 42.5+); остальные — построчно через scan_line.
        """
        if len(text) > self._max_text_chars:
            text = text[: self._max_text_chars]

        # File-level prefilter (день 42): пропускаем файл целиком, если ни один
        # классификатор не видит быстрых признаков во всём содержимом.
        if not self._file_pass_prefilter(text, classifiers):
            return []

        lines = text.splitlines()
        context_lines = self._context_lines
        line_end = len(lines)
        findings: List[Finding] = []

        # Файловый путь: классификаторы, у которых есть scan_text(text), вызываем
        # один раз (PII — один вызов Presidio на весь файл, строки из offset).
        for classifier in classifiers:
            scan_text = getattr(classifier, "scan_text", None)
            if scan_text is None:
                continue
            try:
                file_findings = scan_text(text)
            except Exception as e:
                func = getattr(classifier, "classifier_name", type(classifier).__name__)
                print(f"[FS] scan_text error {func} at {file_path}: {e}")
                continue

            for finding in file_findings:
                ln = finding.line_number or 1
                idx = max(0, min(ln - 1, line_end - 1)) if line_end else 0
                if not finding.line_text:
                    finding.line_text = lines[idx] if lines else ""
                before_start = max(0, idx - context_lines)
                after_end = min(line_end, idx + context_lines + 1)
                finding.context_before = "\n".join(lines[before_start:idx]) if lines else ""
                finding.context_after = "\n".join(lines[idx + 1:after_end]) if lines else ""
                finding.fragment_path = file_path
                findings.append(finding)

        # Построчный путь: классификаторы без scan_text (Credentials, Code и т.п.)
        for idx in range(line_end):
            line = lines[idx]
            line_num = idx + 1

            # Контекст вокруг строки
            before_start = max(0, idx - context_lines)
            after_end = min(line_end, idx + context_lines + 1)
            context_before = "\n".join(lines[before_start:idx])
            context_after = "\n".join(lines[idx + 1:after_end])

            for classifier in classifiers:
                if hasattr(classifier, "scan_text"):
                    continue
                try:
                    line_findings = classifier.scan_line(line, line_num)
                except Exception as e:
                    func = getattr(classifier, "classifier_name", type(classifier).__name__)
                    print(f"[FS] scan_line error {func} at {file_path}:{line_num}: {e}")
                    continue

                for finding in line_findings:
                    finding.line_text = line
                    finding.context_before = context_before
                    finding.context_after = context_after
                    finding.fragment_path = file_path
                    findings.append(finding)

        return findings
```

### `scanner/src/managed_scanner.py`

`__init__`:
```python
        self.config = config
        self._should_exit = False
        # Событие остановки (день 42.5+): устанавливается из stop()/Ctrl+C,
        # проверяется параллельным scan_path для немедленной остановки.
        self._stop_event = threading.Event()
```

`_scan_line_by_line` (вызов `scan_path`):
```python
        findings = self._connector.scan_path(
            resource_path,
            line_capable,
            progress_callback=_progress,
            stop_event=self._stop_event,
        )
```

`run_loop` (не отправлять прерванную задачу):
```python
                    result = self._execute_task(task)
                    
                    if self._should_exit or self._stop_event.is_set():
                        logger.warning("⏹️ Задача прервана пользователем — результаты не отправлены")
                        break
```

`stop()`:
```python
    def stop(self):
        self._should_exit = True
        self._stop_event.set()
```

---

## 4. Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `scanner/classifiers/pii_classifier.py` | `scan_text()` (один Presidio на файл), `_line_starts()` (offset→строка через bisect), import `bisect` |
| `scanner/connectors/filesystem.py` | `scan_path(..., stop_event)`, файловый путь в `_scan_text` (guard по `hasattr scan_text`), module-level `logger` |
| `scanner/src/managed_scanner.py` | `_stop_event`, `stop()` → событие, проброс в `scan_path`, отказ от отправки прерванной задачи |

`run_scanner.py` — без изменений (signal_handler уже звал `scanner.stop()`, теперь работает).

---

## 5. Команда для коммита

```
git add scanner/classifiers/pii_classifier.py scanner/connectors/filesystem.py scanner/src/managed_scanner.py CHANGELOG.md STATE.md
git commit -m "perf: Файловый PII-анализ (1 Presidio на файл) + остановка Ctrl+C (v3.13.1)

- PiiClassifier.scan_text(): один analyze(text) на файл вместо построчного analyze(line);
  номера строк из offset (line_starts + bisect), позиции относительно строки
- FilesystemConnector._scan_text: scan_text-классификаторы обрабатываются на уровне файла,
  остальные (Credentials/Code) — построчно как раньше
- Контекст находок (context_before/after, fragment_path) восстанавливается по line_number
- FilesystemConnector.scan_path(..., stop_event): остановка после текущих файлов (seq break,
  parallel — воркеры возвращают [])
- ManagedScanner._stop_event: stop()/Ctrl+C прерывает активный скан; прерванная задача НЕ
  отправляется в Manager (остаётся assigned)
- Бенчмарк: файл 200 строк PII — 1.64x (3.04с -> 1.85с), находки идентичны (1200=1200);
  паритет scan_text vs scan_line — 7=7; seq/par регрессия — 30/30, speedup 3.32x
- stop_event: 20/200 (seq) и 23/200 (par) файлов — сканирование останавливается
"
```

---

## 6. Инструкция по запуску для ручного тестирования

1. Перезапуск сканера (для подхвата нового кода; единый процесс на хосте):
```powershell
cd E:\projects\dcap-system
Get-Process python* | Where-Object { $_.Path -like "*Anaconda3*" } | Stop-Process
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING="utf-8"
python run_scanner.py scanner/config/scanner_config.json
```
2. **Проверка Ctrl+C**: во время активного сканирования нажать Ctrl+C — в логе появится
   «Получен сигнал остановки...», затем «Задача прервана пользователем — результаты не отправлены»
   и «Сканер остановлен» (раньше сканирование продолжалось до конца задания).
3. **Скорость**: в логе `[ScanProgress] … | скорость N файл/мин | ETA …` — на Presidio-heavy
   файлах должно быть быстрее (файловый PII 1.64x против построчного).
4. **Паритет и остановка** (синтетика, вне репо):
```powershell
python e:\Temp\opencode\test_scan_text_stop.py
python e:\Temp\opencode\test_seq_par.py
```
5. WebUI `http://localhost:8001` (admin/admin123) → «Сканеры» — прогресс задания.

---

## 7. Примечания

- **Black не применён** (как 42.5) — массовое форматирование раздувает DIFF-ы; правки внесены
  вручную в исходном стиле файлов.
- Presidio-сплит по предложениям на файлах 100k+ строк всё ещё самый тяжелый случай
  (BACKLOG-063) — теперь один вызов на файл + bisect вместо сотен построчных `analyze`.
- Остановленный файл (собственно Presidio-вызов) дорасчитывается до конца — прерывать
  C-extension нельзя; на практике это 1 текущий файл на воркер.
- Прерванная задача остаётся assigned/heartbeat у Manager — повторный запуск сканера
  перевзберёт её (как было с заданием #4). Намеренно НЕ сабмитим частичные результаты,
  чтобы не занижать аудит.