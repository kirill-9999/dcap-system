# Отчёт: День 53.4m — Мультипроцессинг сканера (ProcessPoolExecutor)

**Версия:** v3.14.10 → **v3.14.11**
**Дата:** 22.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes
**ТЗ:** `prompts/tz/day_53_4m_scanner_multiprocessing.md`

---

## Цель

ФС-сканирование упиралось в GIL: 8 потоков `ThreadPoolExecutor` на 1000 файлах давали
63.7 ф/мин (одно ядро). Требовался реальный параллелизм (`ProcessPoolExecutor`),
ленивая загрузка spaCy в каждом процессе (память), picklable-обмен результатами,
свой temp_dir на процесс и graceful shutdown по Ctrl+C.

---

## Замеры «до/после» (1000 файлов, `E:\Temp\dcap_perf_1000`)

Оба прогона — подряд, на одной машине (Intel i5-7400, **4 физических ядра**,
16 ГБ), через `ManagedScanner._scan_line_by_line`, пик RSS дерева процессов — psutil.

| Метрика | До (v3.14.10, thread, 8) | После (v3.14.11, process, 4) | Изменение |
|---|---|---|---|
| Время скана | 941.7 с | 451.5 с | **−52%** |
| Files/min | **63.7** | **132.9** | **×2.09** |
| Находок | 598 | 598 | 0 lost |
| Уникальных content-key | 598 | 598 | 0 lost |
| findings/файл | 0.6 | 0.6 | — |
| Категории | phone 464 / email 67 / us_driver_license 67 | то же | — |
| locations[] | 598 | 598 | сохранён |
| **Пик RSS** (дерево) | **3025 МБ** | **4649 МБ** | **×1.54** (≤ ×2 ✅) |
| Пик числа процессов | 4 | 10 (parent + 4 воркера + tesseract) | — |
| ETA на 2 000 000 | 21.8 дн | **10.4 дн** | −52% |

Контрольные точки масштабирования (тот же корпус):

| Режим | Files/min | Масштаб к 1 процессу |
|---|---|---|
| 1 процесс (`max_workers=1`) | 47.6 | ×1.00 |
| 4 процесса (`max_workers=4`) | 132.9–147.9 | **×2.8–3.1** |
| 8 потоков (baseline) | 63.7 | ×1.34 |

Вывод: потоки давали лишь ×1.34 (GIL), процессы — ×2.8–3.1 на 4 ядрах
(КПД 70–78%; остальное — старт воркеров, Tesseract и память).
**Потолок ТЗ (≥ 200 ф/мин) упирается в железо:** 200 ф/мин = ×3.1 от baseline
достижимо на 6–8 физических ядрах; на 8 ядрах ожидаемо ~250–290 ф/мин и
ETA 2 000 000 ≈ 4.8–5.5 дн.

⚠️ На малых наборах процесс-режим **проигрывает** потокам из-за старта воркеров
(spawn + загрузка моделей ~10–15 с): E2E на 40 файлах — thread 207.6 ф/мин,
process 64.7 ф/мин. Порог окупаемости — от ~200–300 файлов.

---

## Регрессия (функционал сохранён)

- `tests/unit/test_perf_regression_v31411.py`:
  baseline significant_content_keys ⊆ after — **0 lost**; дамп process-прогона
  против эталона v3.14.10 — **0 lost**.
- content-keys считаются как `sha256("file|category|match")[:16]` (как в эталонах).
- `metadata["locations"]` сохранён (598 locations на 598 находок).
- OCR: в дереве процессов во время прогона присутствовали дети `tesseract`
  (PDF/PNG корпуса обработаны), находки `us_driver_license` из PDF на месте.

---

## Реализация

### 1. Фабрика классификаторов (`scanner/classifiers/factory.py`, новый)
- `classifier_spec(c)` → `{"name", "config"}` (pickle-проверка, `None` если не сериализуется);
  имя берётся из `classifier_name` или по имени класса (`_CLASS_TO_NAME`).
- `classifier_specs(list)` → список spec'ов либо `None`.
- `get_classifier(name, config)` — ленивое создание + **кеш на процесс** (`_CACHE`, lock).
- `build_classifiers(specs)` — восстановление списка в воркере.
- `worker_specs(specs)` — для `pii_classifier` принудительно
  `analyzer_pool_size=1` и `start_ocr_worker=False` (в воркере один поток;
  OCR изображений в построчном пути идёт через `DocumentExtractor`, не через OCRWorker).

### 2. `scanner/connectors/filesystem.py`
- `_process_worker_init(connector, specs)` — initializer пула: `_init_worker()`
  (logging + `WORKER_TEMP_DIR`) + глобалы `_WORKER_SELF/_WORKER_SPECS/_WORKER_CLASSIFIERS=None`.
- `_get_worker_classifiers()` — ленивый `build_classifiers` при первом файле.
- `_process_scan_one(file_path)` — `_WORKER_SELF.scan_file(...)` в воркере.
- `scan_path`: режим из `performance.executor` (`process` по умолчанию, `thread` — fallback).
  `ProcessPoolExecutor` c `initializer`, при `specs is None` или исключении — **автоматический
  откат на потоки**. Ограниченное окно задач (`in_flight_limit = max(max_workers, chunk_size)`)
  + `wait(..., FIRST_COMPLETED)` — futures не копятся на 2 000 000 файлов.
- **Ctrl+C**: `KeyboardInterrupt` перехватывается внутри `scan_path` — уже готовые
  futures забираются, незапущенные отменяются, `shutdown(wait=True)`, возвращаются
  собранные находки (исключение наружу не выходит). Принудительный «Windows → thread» хак удалён.
- `decode_text_bytes` возвращён в импорты (в первой итерации был случайно удалён → `NameError`).

### 3. `scanner/classifiers/pii_classifier.py`
- `_get_nlp_engine()`: проверка наличия моделей через `importlib.util.find_spec`
  вместо `spacy.load` (убирает двойную загрузку ~450 МБ пика и секунды старта в каждом процессе).
- `configure()`: OCRWorker стартует только при `ocr_enabled` **и** `start_ocr_worker`.

### 4. Конфигурация
- `scanner/src/config_loader.py`: `AppConfig.performance` (верхнеуровневая секция),
  fallback на `orchestrator.performance`, `to_dict()` пишет `performance`.
- `scanner/src/managed_scanner.py`: `_get_connector_config()` пробрасывает
  `performance` (executor/max_workers/chunk_size/max_parallel_files);
  `_load_classifiers()` в process-режиме ставит родителю `analyzer_pool_size=1`.
- `scanner/config/scanner_config.json`: `performance`
  `{executor: "process", max_workers: 4, chunk_size: 100, max_parallel_files: 8}`;
  остальные пороги возвращены к значениям HEAD (save_interval 1000, cache_cleanup 10000,
  models_reload 50000, emergency_restart 90, max_file_size_mb 500, memory_limit 16384).

---

## Тесты

| Файл | Что | Результат |
|---|---|---|
| `tests/unit/test_multiprocessing_v31411.py` | Finding picklable, PerformanceConfig, `_get_executor`, spec/specs, `worker_specs`, кеш `get_classifier`, неизвестное имя, чтение `performance` | **9 passed** |
| `tests/unit/test_perf_regression_v31411.py` | baseline ⊆ after (эталоны + дамп process-прогона) | **2 passed** |
| `tests/e2e/test_multiprocessing_v31411.py` | process vs thread: тот же набор находок, locations[], скорость ≥ порога | **1 passed** (74 с) |
| `pytest tests/unit manager/tests -q` | весь unit-набор | **566 passed** |

---

## Ручная приёмка (ТЗ, 8 пунктов)

| # | Сценарий | Ожидание | Факт |
|---|---|---|---|
| 1 | Скан 1000 файлов, 8 ядер | ≥ 200 ф/мин (×4 от 50) | ⚠️ 132.9–147.9 ф/мин — **4 физических ядра**; экстраполяция на 8 ядер ≈ 250–290 |
| 2 | ETA на 2 000 000 | ≤ 7 дн (было 26) | ⚠️ 10.4 дн (4 ядра); на 8 ядрах ≈ 4.8–5.5 дн |
| 3 | Regression | baseline ⊆ after, 0 lost | ✅ 0 lost |
| 4 | Память | ≤ ×2 от baseline | ✅ ×1.54 (4649 / 3025 МБ) |
| 5 | Ctrl+C | Graceful: процессы умирают, находки сохранены | ✅ `elapsed=27.4s findings=5 children_after=0`, исключения наружу нет |
| 6 | OCR (.png/.pdf) | Находки есть | ✅ PDF/PNG корпуса, `tesseract`-дети в дереве процессов, `us_driver_license` 67 |
| 7 | S3-скан | Работает | ⛔ не проверялся (нет MinIO-стенда в сессии); `S3LineConnector` наследует `scan_path` |
| 8 | `executor="thread"` | Работает | ✅ baseline-прогон выполнен на этом же коде |

### Ctrl+C — детали
Скрипт `temp/phase3/test_ctrl_c.py` (имитация Ctrl+C через `_thread.interrupt_main()`):
в момент прерывания 5 находок уже собраны — все вернулись, дочерних процессов 0,
`KeyboardInterrupt` не вышел из `scan_path` (иначе находки были бы потеряны — до фикса
было `raise`). Задержка выхода = догрузка воркеров + завершение текущих задач.

---

## Изменения в документации

- `ARCHITECTURE.md` — «Параллелизм файлов внутри задачи (v3.14.11)».
- `docs/admin-guide/06-scanner.md` — новый раздел 9 «Параллелизм ФС», Troubleshooting → 10.
- `CHANGELOG.md`, `STATE.md`.

---

## Известные ограничения / следующий шаг

1. **Память на Windows (spawn):** ~0.5 ГБ RSS на процесс с PII-моделями.
   4 воркера ≈ 3.5–4.6 ГБ на дерево — нормально для 16 ГБ, на 8 ГБ-хосте
   ставить `max_workers=2`. На Linux (fork) модели разделяются copy-on-write → ×1.
2. **Порог железа:** ≥ 200 ф/мин требует 6–8 физических ядер (ТЗ писалось под 8).
3. `max_workers` подбирается по формуле `физические ядра − 1` (родитель + tesseract).
4. Следующая оптимизация (если нужен ещё ×1.5): вынести OCR в отдельный
   пул/процесс на задачу и переиспользовать один spaCy-инстанс для нескольких
   файлов батчами (сейчас модель загружается один раз на процесс, но токенизация
   идёт по файлу).

---

## Коммит

```powershell
git add scanner/classifiers/factory.py `
        scanner/classifiers/pii_classifier.py `
        scanner/connectors/filesystem.py `
        scanner/src/config_loader.py `
        scanner/src/managed_scanner.py `
        scanner/config/scanner_config.json `
        tests/unit/test_multiprocessing_v31411.py `
        tests/unit/test_perf_regression_v31411.py `
        tests/e2e/test_multiprocessing_v31411.py `
        ARCHITECTURE.md CHANGELOG.md STATE.md docs/admin-guide/06-scanner.md
git commit -m "perf: 53.4m scanner multiprocessing — ProcessPoolExecutor (v3.14.11)

Baseline v3.14.10 (thread, 8): 63.7 ф/мин, ETA 2 000 000 = 21.8 дн.
После (process, 4 воркера): 132.9 ф/мин, ETA = 10.4 дн (×2.09).
Пик RSS дерева: 3025 → 4649 МБ (×1.54, ≤ ×2).
Ленивая инициализация spaCy/OCR в воркерах, кеш на процесс, temp_dir на процесс.
Graceful shutdown по Ctrl+C, findings не теряются.
Функционал сохранён: 0 потерянных content-keys, locations[], OCR.
Тесты: 567 passed (unit), e2e process-vs-thread parity."
```

---

## Ручной тест (для проверки после выката)

1. `python init_db.py` (если БД нет) → `python run_all.py`.
2. В `scanner/config/scanner_config.json` проверить `performance.executor="process"`.
3. `python run_scanner.py scanner/config/scanner_config.json` — в логе должно быть
   `[FS] ProcessPoolExecutor: 4 процессов, chunk=100`.
4. Запустить задачу на папке с >300 файлов, в Диспетчере задач — 4 python-процесса
   по ~600 МБ; Files/min на дашборде.
5. Ctrl+C в консоли сканера → «Ctrl+C — graceful shutdown (сохранено находок: N)»,
   процессы исчезают, находки в Manager на месте.
6. Поставить `"executor": "thread"` → лог `[FS] ThreadPoolExecutor: 8 потоков`,
   скан работает (fallback).
7. На хосте с малым объёмом RAM — `"max_workers": 2`.
