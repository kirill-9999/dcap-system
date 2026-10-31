# Отчёт 53.4k Фаза 3 — фикс производительности сканера (v3.14.9)

**Дата:** 2026-10-21  
**Ветка:** feature/day_53_4a_add_webui_fixes  
**Версия:** v3.14.8 → v3.14.9  
**ТЗ:** prompts/archive/day_53_4k_scanner_perf_fix.md (Фаза 3: 3.1 + 3.2 + 3.3)  
**Бейзлайн Фаза 2:** 19.6 ф/мин, ETA ~19.2 ч, classify ~99%, OCR-спам 3 subprocess/файл, findings 60916

## 1. Найденное (подтверждено)
- `DocumentExtractor` + `OCREngine` пересоздавались **на каждый** `extract_document_text` (doc/image) → **3 subprocess/файл** (`where`/`--list-langs` + tesseract).
- `OCREngine._find_tesseract`/`_detect_languages` вызывали `where`/`--list-langs` на **каждый** экземпляр.
- `PiiClassifier` хранит `self.extractor = DocumentExtractor(...)` (dead для linewise), основной путь — `scanner/connectors/_text_scanner.extract_document_text`.
- `@lru_cache`-хелперы в `ocr_worker.py`/`ocr_engine.py` из 53.4j не подключались к основному пути `extract_document_text`.

## 2. Фиксы

### 3.1. Singleton `DocumentExtractor` в `scanner/connectors/_text_scanner.py`
- Добавлены модульные `_EXTRACTOR_CACHE` + `_EXTRACTOR_CACHE_LOCK`.
- Функция `_get_document_extractor(temp_dir, ocr_enabled)` возвращает переиспользуемый `DocumentExtractor` по ключу `(temp_dir, ocr_enabled)`.
- `extract_document_text` использует кэш вместо `DocumentExtractor(...)` на каждый файл.

### 3.2. Кэш детекции Tesseract в `scanner/utils/ocr_engine.py`
- Добавлены модульные `@lru_cache`-функции `_get_tesseract_path()` / `_get_tesseract_langs(cmd)`.
- `OCREngine._find_tesseract()` переведён на `_get_tesseract_path()` (1 раз на процесс).
- `OCREngine._detect_languages()` переведён на `_get_tesseract_langs(cmd)` (1 раз на процесс).
- Убраны дублирующие импорты (`import subprocess` в середине, дубли `import tempfile`).
- Стандартные пути установки добавлены; поиск `where` сохранён (env имеет приоритет).

### 3.3. Дешёвый префильтр до Presidio
- В `PiiClassifier.scan_text` уже присутствовал файл-уровневый негативный фильтр `self._quick_file_regex.search(text)` (стр. ~483) — сохранён как есть (findings-safe).
- Доп. безопасных вариантов, снижающих O(n²) Presidio без потери находок (score_threshold, язык-фильтр), в рамках API не дали измеримого выигрыша.
- Окно-подход (line-windowed анализ) дал `only_in_A=0` (ни одна baseline-находка не потеряна), но добавил +19 граничных находок и потребует отдельного регрессионного прогона → перенесён в **3.4** по требованию приёмки.

## 3. Замеры

### OCR-спам (10 PNG)
Скрипт: `temp/phase2/phase2_ocr2.py`  
До (Фаза 2): **30 subprocess/10 файлов** (3/файл), 0.686 с/файл  
После 3.1+3.2: **2 subprocess/10 файлов** (0.2/файл), **0.280 с/файл** (−59%)  
`OCREngine._find_tesseract calls: 0`, `[OCR] Found via 'where'` 1 раз.

```
extract_document_text x10: 2.801s (0.280/file)
OCREngine._find_tesseract calls: 0
OCREngine._detect_languages calls: 0
tesseract subprocess calls: 2 [...]
```

### Benchmark (100 файлов, workers=8)
До (Фаза 2): **19.6 ф/мин**, 306.8 с, findings 60916, ETA 19.2 ч  
После 3.1+3.2 (полный прогон): **22–25 ф/мин** (вариативность из-за 6 огромных 9.9МБ файлов в подмножестве)  
Кластеризованная скорость на больших файлах выросла за счёт снижения OCR-overhead; доминирует Presidio/classify (~99%) на текстах с массовым совпадением паттернов.

### Regression (fingerprint)
Скрипт: `temp/phase2/phase2_regress.py` (fingerprint = SHA256 `file_path|line|match|finding_type`)  
Набор 40 файлов: **pre 24.8 ф/мин / 20568 findings / 0 lost, post 25.4 ф/мин / 20568 findings / 0 lost** (только post=0, только pre=0).  
**Findings count идентичен до/после.**

## 4. Тесты
Создан `tests/unit/test_perf_v3149.py` (4 теста): кэш путей/языков Tesseract, singleton DocumentExtractor, переиспользование в `extract_document_text`.  
**Результат:** `4 passed`.

## 5. Изменённые файлы
- `scanner/connectors/_text_scanner.py` — singleton-кэш `DocumentExtractor`
- `scanner/utils/ocr_engine.py` — `@lru_cache` для детекции, упрощение `OCREngine._find_tesseract`/`_detect_languages`
- `tests/unit/test_perf_v3149.py` — новые unit-тесты

## 6. Приёмка
- Files/min: **< 50** (текущие 22–25). По условиям ТЗ при < 50 — **обсудить 3.4** (line-windowed Presidio с overlap, `only_in_A=0` подтверждён, +19 граничных находок) или **53.4l**.
- Спам subprocess: **исправлен** (3→0.2/файл) — соответствует цели 3.1+3.2.
- Регрессия находок: **отсутствует**.
- Unit-тесты: **пройдены**.

**Рекомендация:** рассмотреть 3.4 для сокращения O(n²) Presidio на больших текстах с контролируемым regression-тестом (fingerprint set) до применения.
