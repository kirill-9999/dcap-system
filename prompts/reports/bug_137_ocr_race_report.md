# Отчёт — BUG-137: гонка temp-файлов `OCREngine` при параллельном сканировании (v3.13.36)

**Дата:** 09.10.2026
**Приоритет:** 🔴 критично (блокер релиза v3.0.0; тихая потеря OCR-находок)
**Родитель:** 53.3-fs-regress-ocr-diag
**Ветка:** feature/day_53_3_s3_e2e_webui

---

## TASK-BUG137-1 — Диагностика: корень найден

### Где потеря: гонка temp-файлов `OCREngine` (НЕ очередь OCRWorker)

В linewise-пути `FilesystemConnector.scan_file` (`scanner/connectors/filesystem.py:316-339`)
для каждого файла вызывается `extract_document_text` (`scanner/connectors/_text_scanner.py`,
день 53.1b) → `DocumentExtractor` → **новый `OCREngine` на каждый файл** с общим
`tempfile.gettempdir()`.

**Ключевой фрагмент `scanner/utils/ocr_engine.py` (БЫЛО, до фикса):**

```python
class OCREngine:
    def __init__(self, ...):
        self.temp_dir = Path(tempfile.gettempdir())
        self._cleanup_temp_files()          # ← УДАЛЯЛ ВСЁ tmp*/ocr_* в системном temp
```

`_cleanup_temp_files()` сканировала (glob `tmp*`, `ocr_*`) **весь системный temp** и удаляла
файлы старше критичного возраста. При параллельных файлах (max_parallel_files=8,
analyzer_pool_size=4): поток A обрабатывает `.png` через tesseract (создал `tmp*.png`,
ждёт `tmp*.txt`), поток B в это время обрабатывает `.pdf`/`.docx`/`.xlsx`, создаёт свой
`OCREngine` → `_cleanup_temp_files()` удаляет temp-файлы tesseract потока A →
в `ocr_image` (`ocr_engine.py`):

```python
if not os.path.exists(temp_txt):      # ← ФАЙЛ УДАЛЁН ДРУГИМ ПОТОКОМ
    self._log = "Tesseract did not produce output"
    return ""
```

→ пустой результат → находки PNG молча пропадают. Одиночный прогон — один движок,
cleanup безвреден (поэтому D2/D4 = 4, D3 параллель = 0).

**Почему не OCRWorker:** QR/Worker-очередь (`ocr_worker.py`) — классический путь
`scan_text` с пулом процессов; в linewise-пути сканер идёт через `_text_scanner`
(`scan_file`), и `OCRWorker` там не участвует. Поэтому фикс нужен в `OCREngine`,
а не в `ocr_worker.py` (вместе с WARNING-логами в `pii_classifier._call_ocr_worker`).

**Фраза-корень:** «Общий системный temp + глобальный `_cleanup_temp_files()` при каждом
`OCREngine` — один поток удаляет работающие temp-файлы tesseract другого потока».

---

## TASK-BUG137-2 — Фикс

### `scanner/utils/ocr_engine.py`

1. У каждого `OCREngine` — **своя уникальная подпапка**:
   `self._work_dir = self.temp_dir / f"ocr_{uuid.uuid4().hex[:12]}"` (создаётся в `__init__`).
2. `_cleanup_temp_files()` чистит **только свою подпапку** `self._work_dir`
   (`glob("tmp*")` + `glob("ocr_*")` внутри неё), никогда не трогая temp других движков.
3. `ocr_image` создаёт temp-файлы через `NamedTemporaryFile(dir=str(self._work_dir), ...)`.

Одиночный прогон: подпапка одна, cleanup своей же подпапки безвреден — регресс D2/D4 исключён.

### `scanner/classifiers/pii_classifier.py`

Никакой тихой потери — WARNING вместо тихого `return None`/`print`:

```python
logger.warning("OCR потерян: request %s вернул success=False (%s)", ...)   # success=False
logger.warning("OCR потерян: таймаут ожидания ответа от OCRWorker ...")    # timeout
```

### `scanner/connectors/_text_scanner.py`

WARNING при пустом результате документ-OCR:

```python
# extract_document_text: если OCR включён и результат пуст, но был error —
logger.warning("extract_document_text: документ-OCR вернул пусто при error")
```

### Соответствие требованиям ТЗ
- ✅ Никакой тихой потери (WARNING в `pii_classifier.py` + `_text_scanner.py`).
- ✅ Одиночный прогон не сломан (live задача 12: 4 находки).
- ✅ Публичный интерфейс `PiiClassifier.scan_text / scan_line` не менялся.

---

## TASK-BUG137-3 — Воспроизводимый юнит-тест

Файл: `tests/unit/test_ocr_worker_race_v31336.py` (NEW).

- Одиночный прогон PNG (Pillow, Phone/Email/Passport/Name) → **4 находки** `image_region`/`ocr`.
- Параллельный (ThreadPoolExecutor, 8 потоков): PNG + 10 txt → все PNG дают находки.
- Регресс на стабильность: **3 повтора подряд — результат одинаков**.

```
tests/unit/test_ocr_worker_race_v31336.py ... 3 passed in 7.38s
```

Если Tesseract недоступен в окружении — тест skip с явной причиной.

---

## TASK-BUG137-4 — Live-проверка

Живой стенд: Manager :8000 (PID 15840, не перезапускался) + Scanner на хосте
(PID 14196, с фиксом, legacy-режим, `temp/ocr_fix_scanner_{out,err}.log`).

| Прогон | task | Корпус | files | findings | image_region/ocr | Источник |
|--------|------|--------|-------|----------|------------------|----------|
| D3 #1 | 5 | `temp/fs-regress-d3` (png+10txt, 8 потоков) | 11 | **4** | **4** | pii_screenshot.png |
| D3 #2 | 9 | `temp/fs-regress-d3/r1` (11 файлов) | 11 | **4** | **4** | pii_screenshot.png |
| D3 #3 | 10 | `temp/fs-regress-d3/r2` | 11 | **4** | **4** | pii_screenshot.png |
| D3 #4 | 11 | `temp/fs-regress-d3/r3` | 11 | **4** | **4** | pii_screenshot.png |
| D2/D4 solo | 12 | `temp/fs-regress-d3/single` (png one) | 1 | **4** | **4** | pii_screenshot.png |

**Регресс D2/D4 (критерий 2):** одиночный PNG → 4 находки, фикс не сломал.
**Параллель D3 (критерий 3):** 4 чистых прогона подряд → стабильно 4 находки
(`email`, `phone`, `passport`, `person`; все `image_region`, `detector=ocr`).

> Примечание: задачи 6–8 (повторы 2–4 на том же каталоге `fs-regress-d3`) сканер
> находил по 4 находки (см. `ocr_fix_scanner_err.log`: «Total findings: 4»), но в БД
> `[SubmitResults] 0 findings saved` — это **дедупликация по fingerprint** Manager'а
> (тот же путь+значение, день 40.2), а не потеря OCR. Для чистоты 4 повторов с
> фактической записью в БД использованы каталоги r1/r2/r3 и single (уникальные пути).

---

## ✅ Критерии приёмки

| # | Критерий | Результат |
|---|----------|-----------|
| 1 | Корень найден и описан | ✅ TASK-BUG137-1 (гонка temp-файлов OCREngine) |
| 2 | Одиночный прогон не сломан | ✅ live D2/D4 (task 12): 4 находки |
| 3 | Параллельный прогон даёт 4 находки | ✅ live D3: 4 прогона подряд, стабильно 4 |
| 4 | WARNING при потере OCR | ✅ `grep "OCR потерян" scanner/classifiers/pii_classifier.py` + WARNING в `_text_scanner.py` |
| 5 | Юнит-тест создан | ✅ `tests/unit/test_ocr_worker_race_v31336.py` — 3 passed |
| 6 | Полный unit-набор | ✅ **433 passed** (было 430; +3) |
| 7 | E2E | ⚠️ 53 passed, 7 skipped (эталон); 4 теста флакают из-за окружения (нет живого сканера на :18000) — падают и без фикса (проверено `git stash`) |

> ⚠️ ЧТО НЕ ДЕЛАЛИ (по ТЗ): OCR-пайплайн не переписан, Tesseract/Presidio не менялись,
> S3-коннектор и WebUI-редизайн не тронуты, `max_parallel_files` не уменьшался.

---

## Изменённые файлы

```
scanner/utils/ocr_engine.py                      # ФИКС: изоляция temp (_work_dir)
scanner/classifiers/pii_classifier.py            # WARNING при потере OCR-ответа
scanner/connectors/_text_scanner.py              # WARNING при пустом документ-OCR
tests/unit/test_ocr_worker_race_v31336.py        # NEW: воспроизводимый тест BUG-137
ROADMAP.md                                       # BUG-137 закрыт, v3.13.36
STATE.md                                         # версия v3.13.36, день, отчёт
CHANGELOG.md                                     # секция [3.13.36]
prompts/reports/bug_137_ocr_race_report.md       # этот отчёт
prompts/tz/bug_137_ocr_race.md -> prompts/archive/
```

---

## Команда для коммита

```bash
git add scanner/utils/ocr_engine.py \
        scanner/classifiers/pii_classifier.py \
        scanner/connectors/_text_scanner.py \
        tests/unit/test_ocr_worker_race_v31336.py \
        ROADMAP.md STATE.md CHANGELOG.md \
        prompts/reports/bug_137_ocr_race_report.md
git mv prompts/tz/bug_137_ocr_race.md prompts/archive/bug_137_ocr_race.md

git commit -m "fix: BUG-137 — гонка temp-файлов OCREngine при параллельном сканировании (v3.13.36)

- scanner/utils/ocr_engine.py — каждый OCREngine в своей уникальной подпапке
  ocr_<uuid>; _cleanup_temp_files чистит только свою подпапку; temp-файлы
  через NamedTemporaryFile(dir=_work_dir) — один поток больше не удаляет
  работающие temp-файлы tesseract другого потока
- scanner/classifiers/pii_classifier.py — WARNING при потере OCR-ответа
  (success=False и timeout) вместо тихого return/print
- scanner/connectors/_text_scanner.py — WARNING при пустом документ-OCR
- tests/unit/test_ocr_worker_race_v31336.py — воспроизводимый тест
  (single 4 находки; parallel 8 потоков; 3 повтора стабильно равны)

BUG-137 (блокер v3.0.0; воспроизведён в 53.3-fs-regress-ocr-diag)
docs: обновлены STATE.md (v3.13.36), CHANGELOG.md, ROADMAP.md"
```

---

## Инструкция по ручному тестированию

1. Запустить Manager: `python run_manager.py` (:8000).
2. Запустить сканер с фиксом: `python run_scanner.py scanner/config/scanner_config.json`
   (виден в логе: heartbeat, legacy-режим при `DCAP_ALLOW_LEGACY_SCANNER=true`).
3. Создать задачу на каталог с PNG + 10 txt (8 потоков) через WebUI :8001
   (Ресурсы → Добавить) или `POST /api/tasks/create` с `resource_path`.
4. Дождаться завершения → PNG должен давать 4 находки (`image_region`, `detector=ocr`)
   стабильно при повторах.
5. Одиночный PNG (только png) → тоже 4 находки (регресс).
6. При неудаче OCR (например, битый файл) в `scanner`-логе — WARNING
   «OCR потерян: …», а не тихое молчание.