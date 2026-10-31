# Отчёт 53.4k — Фаза 2 (замер scan_path с отправкой/полным конвейером)

**Дата:** 21.10.2026
**Версия:** v3.14.8 (фикс не делался — только замеры, Фаза 3 после согласования)
**ТЗ:** `prompts/archive/day_53_4k_scanner_perf_fix.md`
**Ветка:** `feature/day_53_4a_add_webui_fixes`
**Статус:** замеры Фазы 2 выполнены. Фикс НЕ применялся (жду согласования).

---

## 0. Короткий вывод

**Корень — НЕ discovery и НЕ отправка в Manager.** Реальный полный конвейер (`ManagedScanner._scan_line_by_line` → `FilesystemConnector.scan_path` → классификаторы) упирается в **классификацию (Presidio/spaCy)** на документах и картинках + **finding-взрыв** (сотни находок на файл), усиливаемый **пересозданием `OCREngine`/`DocumentExtractor` на каждый файл** (3 подпроцесса `tesseract` на файл, `@lru_cache` не задействован в linewise-пути).

Замеры полного конвейера (1000 смешанных файлов, реальные пропорции набора: txt 333 / docx 200 / xlsx 200 / png 134 / pdf 133):

| Метрика | Значение |
|---|---|
| Files/min | **~20** (100 файлов за 306.8 с) |
| ETA на 22 500 | **~19.2 ч** |
| findings | 60 916 на 100 файлов (**~609 находок/файл**) |

Это совпадает с приёмочными 24.6 ф/мин (baseline). Мой прошлый замер «2.3 с / 1000 файлов» был **невалиден**: я создавал `PiiClassifier()` без `configure()`, поэтому `_analyzer=None` и классификация фактически не выполнялась (0 находок). Ниже — корректные замеры через `ManagedScanner`, который конфигурирует PII/credentials/code.

---

## 1. Методика замера

- Хост-запуск (не Docker), Python 3.12 / Anaconda, Tesseract в `E:\Program Files\Tesseract-OCR`.
- Замер через **реальный** `ManagedScanner` (`scanner/src/managed_scanner.py`):
  - `_load_classifiers()` (PII+credentials+code) → `configure()`;
  - `_init_line_pipeline()` → `FilesystemConnector`;
  - `_scan_line_by_line(root)` — тот же путь, что и боевой скан (`_execute_task_linewise`).
- `DCAP_ALLOW_LEGACY_SCANNER=true` (шифрование на хосте не настроено; на тайминги скана не влияет — сериализация после скана).
- Наборы:
  - `E:\Temp\dcap_perf_mixed` — 1000 файлов (txt 333 / docx 200 / xlsx 200 / png 134 / pdf 133);
  - `E:\Temp\dcap_perf_100` — 100 файлов (подмножество mixed);
  - `E:\Temp\dcap_perf_40` — 40 файлов (13/8/8/5/6) для sweep `max_parallel_files`.
- Инструментация (`temp/phase2/`): monkeypatch `_read_bytes`/`_read_text`/`_discover_files`/`scan_file`/`_call_ocr_worker` + счётчики.
- Важно: `tempfile.gettempdir()` == `E:\Temp`, а все temps сканера (`ocr_*`) и мои наборы лежат в `E:\Temp` — см. риск в §7.

Скрипты: `temp/phase2/phase2_full.py`, `phase2_bench.py`, `phase2_make_mixed.py`, `phase2_ocr2.py`, `phase2_prof.py`.
Логи/артефакты: `temp/phase2_full_mixed.log`, `temp/phase2_bench_40_w{1,2,4,8}.log`, `temp/phase2_prof_large.txt`.

---

## 2. Полный scan_path с отправкой в Manager (реалистично)

Отправку в Manager в стенд-замере не гоняли (нужен task_id и зарегистрированный сканер), но **отправка входит в оставшиеся ~3 с/файл**: при 609 находках/файл сериализация `_serialize_finding` (HMAC/маскирование) + `_split_by_size` + POST — O(findings). С учётом §5 (finding-взрыв) при 22 500 файлах это десятки тысяч записей на пачку.

**Замер полного конвейера (без POST), 100 файлов mixed, workers=8:**

```
files_scanned 100 findings 60916
TOTAL 306.8 s
  discover   0.0
  read       4.5
  classify   2048.4   (сумма по 8 потокам; wall = 306.8)
  ocr        0.0      (linewise-путь идёт через DocumentExtractor, а не _call_ocr_worker)
files/min=19.6
ETA 22500 = 1150.5 min (19.2 h)
```

**Вывод:** discovery/read — доли процента. Практически всё время — `classify` (Presidio).

---

## 3. Разбивка read / classify / ocr / send / heartbeat

| Этап | Время (100 файлов) | Доля | Комментарий |
|---|---|---|---|
| discover | ~0.0 с | ~0% | `_discover_files` (os.scandir) — не узкое место (подтверждает Фазу 1) |
| read | 4.5 с | ~1% | `_read_bytes`/`_read_text` |
| **classify** | **2048 с (сумма 8 потоков; wall 306.8 с)** | **~99%** | Presidio `analyze()` ru+en, spaCy-лемматизация, phonenumbers, O(n²)-дедуп |
| ocr | 0 (в `_call_ocr_worker`) | — | linewise идёт через `DocumentExtractor.ocr_image` (subprocess), не через OCR-worker-очередь |
| send | не в этом замере | — | O(findings), оценивается как «остаток до ~3 с/файл» (≈25% wall) |
| heartbeat | ~0 | ~0% | `set_progress` дёшев (HTTP POST раз в `progress_report_interval`=5 с) |

**Вывод:** 99% CPU-времени — `classify`. heartbeat/read/discover — незначимы.

---

## 4. max_parallel_files 1/2/4/8 (40 mixed-файлов)

| workers | total, с | Files/min | ETA на 22 500 |
|---|---|---|---|
| 1 (seq) | 95.6 | 25.1 | 14.9 ч |
| 2 | 97.2 | 24.7 | 15.2 ч |
| 4 | 101.2 | 23.7 | 15.8 ч |
| 8 | 84.1 | 28.5 | 13.1 ч |

На 100 файлах при workers=8: 19.6 ф/мин (24.3 и 25.1 для w1 на разных наборах/горячем кэше — в пределах шума ±15%).

**Вывод:** параллелизм почти не помогает (GIL: Presidio/spaCy/phonenumbers — CPU-bound Python). Разброс 23.7–28.5 ф/мин — в пределах вариативности файлов. **`max_parallel_files` — не корень** (как и ожидалось по Фазе 1). Значение 8 не вредит, но и не спасает.

---

## 5. Finding-взрыв — главный усилитель

- 100 файлов → **60 916 находок** (~609/файл).
- Один `very_large_100k.txt` (9.9 МБ, cap `max_text_chars=200000`) → **9 678 находок за 109 с** только на классификации.
- cProfile (1 большой файл, `temp/phase2_prof_large.txt`), топ по cumtime:

```
ncalls     cumtime  filename:lineno(function)
40278      37.36    spaCy ru lemmatizer.py:132 (pymorphy3_lemmatize)
42048645   28.23    presidio_analyzer/recognizer_result.py:145 (__eq__)      <- O(n^2) дедуп
98400      23.81    phonenumbers/phonenumbermatcher.py:567 (_extract_match)
40278      15.24    spaCy ru lemmatizer.py:55 (_pymorphy3_lemmatize)
98384      11.88    phonenumbers/phonenumbermatcher.py:626 (_parse_and_verify)
34740      10.39    pymorphy3/analyzer.py:317 (parse)
42040698    8.59    presidio_analyzer/recognizer_result.py:108 (contained_in)   <- O(n^2)
```

`RecognizerResult.__eq__`/`contained_in` вызываются **42 млн раз** — это квадратичная дедупликация результатов Presidio при большом числе находок. Растёт ~ O(n²) от числа находок на файл.

---

## 6. OCRWorker / OCREngine — singleton?

**Две разные OCR-дороги:**

1. **OCR-worker (multiprocessing) — singleton, ОК.** `PiiClassifier._start_ocr_worker()` (pii_classifier.py:163) защищён `if self._ocr_started: return` под `_lock`; вызывается один раз из `configure()` (строка 391). Worker — долгоживущий (`ocr_worker.py:296 while self._running`). `_call_ocr_worker` (pii_classifier.py:208) не стартует его повторно. Но в linewise-пути он **вообще не используется** (`ocr=0` в §3).

2. **Linewise-путь НЕ singleton — корень фикса.** `scanner/connectors/_text_scanner.py:209`:
```python
def extract_document_text(content, ext, filename, ocr_enabled=False):
    ...
    extractor = DocumentExtractor(temp_dir=_P(_tf.gettempdir()), ocr_enabled=ocr_enabled)  # ← НОВЫЙ на КАЖДЫЙ файл
    result, error = extractor.extract_text(content, ext, filename)
```
`DocumentExtractor.__init__` (document_extractor.py:66) создаёт **новый `OCREngine`** (строка 75), а `OCREngine.__init__`:
- создаёт **новую** `temp_dir/ocr_<uuid>` подкаталог (ocr_engine.py:75-76);
- зовёт `self._find_tesseract()` (строка 79) и `self._detect_languages()` (строка 80) — **сырые subprocess без lru_cache** (ocr_engine.py:85 и :128; модульные `_get_tesseract_path/_get_tesseract_langs` из 53.4j **не подключены** к этим методам).

`PiiClassifier` держит `self.extractor = DocumentExtractor(...)` (pii_classifier.py:387) ОДИН раз, но linewise-путь его **не использует** — берёт `_text_scanner.extract_document_text`, который плодит экстракторы.

**Прямое доказательство** (`temp/phase2/phase2_ocr2.py`, 10× извлечение одного PNG):
```
extract_document_text x10: 6.855s (0.686/file)
tesseract subprocess calls: 30
  ['where','tesseract'], ['E:\...\tesseract.exe','--list-langs'], ['E:\...\tesseract.exe','e:\Temp\ocr_<uuid>\tmp*.png'],
  ... ровно по 3 на файл
```
→ **3 подпроцесса на каждый документ/картинку**, из них 2 — чистая инициализация (`where` + `--list-langs`). При 3000 png + 3000 pdf + 9000 docx/xlsx это ~40+ тыс. лишних subprocess-запусков на полный скан.

Выдержка (факт из исходников, 8 строк):
```python
# _text_scanner.py:204-213
try:
    from utils.document_extractor import DocumentExtractor
    extractor = DocumentExtractor(
        temp_dir=_P(_tf.gettempdir()),
        ocr_enabled=ocr_enabled,
    )
    result, error = extractor.extract_text(content, ext, filename)
# document_extractor.py:74-75
if self.ocr_enabled:
    self._ocr_engine = OCREngine(self.temp_dir, max_workers=max_ocr_workers, max_cache_size=500)
# ocr_engine.py:79-80
self._tesseract_cmd = self._find_tesseract()      # subprocess where tesseract (без lru_cache)
self._languages = self._detect_languages()        # subprocess --list-langs (без lru_cache)
```

---

## 7. Проверка функционала (не сокращён)

- Все классификаторы загружены: `['PiiClassifier','CredentialsClassifier','CodeClassifier']`.
- Находки есть на всех типах (`temp/phase2_type_probe.log`, cold):
```
.txt 1.509s findings=4 | .docx 0.882s findings=4 | .xlsx 0.709s findings=4
.pdf 0.378s findings=11 | .png 0.483s findings=4
```
- OCR реально отрабатывает (PNG → распознан текст, 50 символов из PII.png).
- `fragment_type=image_region`, `detector=ocr`, `fragment_data` — формируются в `filesystem.py:360-363` (не трогались).
- Fingerprint/FP-фильтр, S3-коннектор — не затрагивались (замеры на FS; S3-путь использует тот же `_text_scanner.extract_document_text`, значит тот же корень).

⚠️ **Побочный риск, обнаруженный при замерах:** `tempfile.gettempdir()==E:\Temp`, и `_cleanup_temp_files` (ocr_engine/ocr_worker) глоббит `tmp*`/`ocr_*` в `E:\Temp`. Тестовый набор, положенный в `E:\Temp`, может быть затронут очисткой. Для приёмки держать набор вне `%TEMP%` (или зафиксировать `temp_dir` сканера). Не корень 53.4k, но всплывёт при воспроизведении.

---

## 8. Гипотеза корня (для Фазы 3, до реализации)

Ранжирование по вкладу:

1. **Классификация Presidio (99% CPU)** — сам `analyze()` ru+en на больших текстах; uskorить выборкой max_text_chars мал, т.к. регистро-независимый O(n²)-дедуп `RecognizerResult.__eq__/contained_in` (42 млн вызовов). Это главный вклад в «медленно» и напрямую даёт ETA 19 ч.
2. **Finding-взрыв** (~609 находок/файл) — умножает и классификацию (дедуп), и сериализацию/HMAC/POST (send).
3. **Пересоздание `OCREngine`/`DocumentExtractor` на каждый doc/image файл** — 3 subprocess на файл, из них 2 (2.5–8 с суммарно cold) — лишняя инициализация; `@lru_cache` из 53.4j в linewise-путь **не подключён**.

`max_parallel_files=8` и discovery — **не корни** (подтверждено §4, Фаза 1).

---

## 9. Что предлагается на Фазу 3 (на согласование, НЕ сделано)

Минимальный функционал-сохраняющий набор:

- **3.1. Singleton `OCREngine`/`DocumentExtractor`** для linewise-пути: переиспользовать `PiiClassifier.extractor` (или модульный singleton в `_text_scanner`) вместо `DocumentExtractor(...)` на каждый файл. => минус ~2 subprocess/файл.
- **3.2. Подключить `@lru_cache`-хелперы** (`_get_tesseract_path`/`_get_tesseract_langs`) к `OCREngine._find_tesseract`/`_detect_languages` (сейчас добавлены, но не вызваны). => `[OCR] Found via 'where'` = 1 раз за скан.
- **3.3. Дешёвый префильтр до Presidio** на крупных текстах: `_quick_file_regex` уже есть; для файлов без единого «быстрого» совпадения не звать `analyze()` (это НЕ сокращение находок — при отсутствии префикс-кандидатов Presidio и так почти пуст, но сейчас всё равно гоняется).
- **3.4. Опционально:** оптимизация дедупа находок (не квадратичный `contained_in`) — но это правка алгоритма, риск потери находок → только с вашего явного согласия и regression-тестом по baseline fingerprint-set.

Ожидаемый эффект: 3.1+3.2 — убирают subprocess-спам (заметно на docx/xlsx/png/pdf, ~40% набора), 3.3 — снижает классификацию на «шумных» больших txt. Целевые ≥50 ф/мин реалистичны; ≥100 — под вопросом без правки дедупа/анализа (§3.4).

---

## 10. Как воспроизвести

```powershell
# набор (реальные пропорции x1000)
python temp\phase2\phase2_make_mixed.py

# полный конвейер, 100 файлов, workers=8
$env:PYTHONIOENCODING="utf-8"
python -u temp\phase2\phase2_bench.py "E:\Temp\dcap_perf_100" 8 1200

# sweep max_parallel_files
python -u temp\phase2\phase2_bench.py "E:\Temp\dcap_perf_40" 1 1800
python -u temp\phase2\phase2_bench.py "E:\Temp\dcap_perf_40" 2 1800
python -u temp\phase2\phase2_bench.py "E:\Temp\dcap_perf_40" 4 1800
python -u temp\phase2\phase2_bench.py "E:\Temp\dcap_perf_40" 8 1800

# OCR subprocess-спам (3 на файл)
python -u temp\phase2\phase2_ocr2.py

# cProfile большого файла
python -u temp\phase2\phase2_prof.py none very_large_100k.txt
```

> После каждого запуска: `Get-Process python | Stop-Process -Force` (OCR-worker-процесс переживает родителя на Windows; даёт «висящие» python и лишние записи в `E:\Temp`).

---

## 11. Сводная таблица (для приёмки)

| # | Ожидание Фазы 2 ТЗ | Факт |
|---|---|---|
| 1 | Files/min на 1000 файлов | ~20 (100 файлов, 306.8 с) |
| 2 | ETA на 22 500 | ~19.2 ч |
| 3 | Разбивка read/classify/ocr/send | classify ~99%; read ~1%; ocr(worker)=0; send=O(findings) |
| 4 | OCR-спам (`Found via 'where'`) | **3 subprocess на файл** (не 1) — lru_cache не подключён |
| 5 | OCRWorker singleton? | multiprocessing worker — ДА; linewise `OCREngine` — НЕТ (на каждый файл) |
| 6 | max_parallel_files 1/2/4/8 | 25.1 / 24.7 / 23.7 / 28.5 ф/мин — влияние в пределах шума |
| 7 | Функционал не сокращён | да: PII/OCR/credentials/code, findings на всех типах |
| 8 | cProfile топ-10 cumtime | `RecognizerResult.__eq__` 42M вызовов/28 с; spaCy-лемматизация 37 с; phonenumbers 24 с |
