# CHANGELOG

## v3.13.1 (2026-09-13)

### Файловый PII-анализ + остановка по Ctrl+C (день 42.5+, по прямому ТЗ)
- `PiiClassifier.scan_text(text)` — ОДИН вызов Presidio на весь файл (вместо построчного
  `analyze(line)` на каждую прошедшую quick-check строку); номера строк находок
  вычисляются из offset (`_line_starts` + bisect), позиции — относительно строки
- `FilesystemConnector._scan_text`: классификаторы с `scan_text` обрабатываются один раз
  на файл, остальные (Credentials/Code) — построчно `scan_line` как раньше
- `FilesystemConnector.scan_path(..., stop_event)`: сканирование останавливается после
  текущих файлов (seq — break, parallel — воркеры возвращают [])
- `ManagedScanner._stop_event`: `stop()`/Ctrl+C устанавливает событие → задача прерывается,
  результаты НЕ отправляются в Manager (task остаётся assigned, не искажается)
- Итог: Presidio на файле 200 строк — в 1.64x быстрее при идентичных находках (1200=1200);
  seq/par паритет сохранён (30/30, speedup 3.32x); контроль: 20/200 (seq) и 23/200 (par) файлов

## v3.13.0 (2026-09-13)

### Сканер-оптимизация (день 42.5, по прямому ТЗ)
- file-level prefilter: `_file_pass_prefilter` в `FilesystemConnector` — файл пропускается
  целиком, если ни один классификатор не видит признаков (`file_prefilter` у Credentials/PII)
- precompile всех regex: `CredentialsClassifier._compile_all()` (`prefilter_regex`,
  `compiled_patterns`, `_entropy_patterns`), `PiiClassifier` `_quick_line_patterns` + `_quick_file_regex`;
  убран `re.compile` из горячих циклов `scan_line`/`classify`
- ThreadPoolExecutor в `scan_path` (ex.map, монотонный прогресс) —
  `ConnectorConfig.max_parallel_files` (default 1 = seq; конфиг 4)
- `_analyzer_lock` у PiiClassifier (Presidio AnalyzerEngine не потокобезопасен)
- Синтетика: seq vs parallel идентичны (30/30), speedup 3.81x;
  реальный каталог: 27–43 файл/мин (было <25)

## v3.12.0 (2026-09-12)

### Findings Refactor — Этап 4 (финал)
- BACKLOG-058: фрагменты изображений — `GET /api/findings/{id}/fragment` → PNG
  (вырезанный из `fragment_path` или crop по `bounding_box` через Pillow, кэширование)
- BACKLOG-059: hex-дамп бинарных фрагментов — `?format=hex` вокруг `byte_offset`
  (окно ±64 байта, `manager/src/core/hex_dump.py`)
- BACKLOG-060: экспорт CSV/JSON с маскированием + reveal (Auditor+),
  аудит `findings_exported`, CSV injection protection (`csv_utils.py`), BOM для Excel
- BACKLOG-067: `X-Total-Count` в `GET /api/findings`; пагинация с номерами страниц в WebUI
- WebUI: `<img>` для image_region, `<pre>` для byte_range (finding_detail.js),
  кнопка «Экспорт» с диалогом формата/reveal (findings.js), `api.getWithMeta`
- Тесты: `tests/e2e/test_finding_fragments.py`, `tests/e2e/test_findings_export.py`,
  `tests/unit/test_hex_dump.py`, `tests/unit/test_csv_utils.py`