# Отчёт: День 53.4l — Оптимизация сканера (фаза 2): дедуп находок + исключение NER-шум

**Версия:** v3.14.9 → v3.14.10  
**Дата:** 22.10.2026  
**Ветка:** feature/day_53_4a_add_webui_fixes  
**Коммит (после фиксации):** будет создан по завершении

## Цель
Оптимизировать сканер на большом наборе файлов (E:\Temp\dcap_perf_1000, 1000 файлов).  
Решение: **3.4.0 — дедуп в рамках файла по (category, match_text)** + **исключение NER-категорий (PERSON/LOCATION/ORGANIZATION/DATE_TIME/NRP)** из анализа Presidio (они не маскируются по решению, составляли 99.9% находок).  
Line-windowed Presidio (3.4) **не потребовался** (Files/min 65.8 ≥ 50).

## Измерения (ManagedScanner, _scan_line_by_line)
| Метрика | baseline v3.14.9 | after v3.14.10 | Изменение |
|---|---|---|---|
| Файлов | 1000 | 1000 | — |
| Files/min | 24.0 | 65.8 | **+174%** |
| Найдено находок (итого) | 666136 | 598 | **−99.91%** |
| Найдено на файл (среднее) | 666.1 | 0.6 | **−99.91%** |
| Уникальных content-key | 288620 | 598 | — |
| Категории | person/location/date_time/org/nrp/phone/email/us_driver_license | **phone/email/us_driver_license** | NER-шум убран |
| Значимых находок (не NER) | 598 | 598 | **0 потеряно, 0 новых** |
| Время скана | 2503 с | 913 с | **−63.5%** |
| ETA на 22500 файлов | 15.6 ч | 5.7 ч | **−63.5%** |

## Регрессия (значимые находки)
- **Проверка:** `tests/unit/test_perf_regression_v31410.py` — baseline significant_content_keys ⊆ after: **0 lost, 0 new**.
- **Fingerprint:** после дедупа одна находка на уникальное совпадение (line = первое вхождение) — корректно сравнивать по **content-key** `file_path|category|match_text` (согласно ТЗ).
- **Дедуп:** 100 повторений email+phone в одном файле → **2 находки**, каждая с **locations[]=100** вхождений.

## Реализация

### 1) Дедуп в рамках файла (scan_text)
**Файл:** `scanner/connectors/_text_scanner.py`
- Добавлен `dedup_findings_by_file(findings)` — группировка по `(category, match_text)`, первое вхождение по `(line_number, start_pos)`, `metadata["locations"] = [{line, context_before, context_after, start_pos, end_pos}]`, сортировка по строке, `metadata["locations_count"]`.
- Применяется в `scan_text()` после построчного сканирования (включает находки PII, credentials, code).
- `__all__` дополнен `dedup_findings_by_file`.

### 2) Исключение NER-категорий Presidio
**Файл:** `scanner/classifiers/pii_classifier.py`
- `NER_ENTITY_TYPES = ("PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "NRP")`
- В `configure()` чтение `ner_enabled` (по умолчанию **false**), `excluded_entities`.
- `_apply_entity_filter()` — вычисляет `self._analyze_entities` (список entity без NER), при `ner_enabled=False` **отключает spaCy компоненты `parser`, `ner`** в каждом `nlp`.
- `analyze()` во всех путях (`scan_line`, `scan_text`, `classify`) вызывается с `entities=self._analyze_entities`.
- Лог при старте: `[PII] [OK] NER-категории отключены (исключены: ...) , spaCy parser/ner off`

### 3) Конфигурация
- **`scanner/src/config_loader.py`**: `PiiConfig` — `ner_enabled: bool = False`, `excluded_entities` (по умолчанию NER-набор). `AppConfig.to_dict()` сохраняет поля.
- **`scanner/src/managed_scanner.py`**: проброс `ner_enabled`/`excluded_entities` в `pii_config_dict`.
- **`scanner/config/scanner_config.json`**: `classifiers.pii_classifier.ner_enabled=false`, `excluded_entities` добавлены.

### 4) Модель Finding + сериализация
- **`scanner/src/finding.py`**: добавлено поле `metadata: Dict[str, Any] = field(default_factory=dict)`, включено в `to_dict()`.
- **`scanner/src/managed_scanner.py`**: в `_serialize_finding` пробрасывается `d["metadata"]` при наличии.

## Пример locations[]
```json
{
  "category": "email",
  "line_number": 1,
  "match_text": "test@example.com",
  "metadata": {
    "locations_count": 100,
    "locations_head": [
      {"line": 1, "context_before": "", "context_after": "...", "start_pos": 20, "end_pos": 36},
      {"line": 2, "context_before": "...", "context_after": "...", "start_pos": 20, "end_pos": 36}
    ]
  }
}
```
(Демо: 100 повторений одного email → **1 находка**, **locations[]=100**)

## Тесты
| Тест | Результат |
|---|---|
| `tests/unit/test_dedup_v31410.py` | **12 passed** |
| `tests/unit/test_perf_regression_v31410.py` | **6 passed** |
| `tests/unit/test_perf_v3149.py` | **4 passed** |
| `tests/unit/test_dedup_v31410.py tests/unit/test_perf_regression_v31410.py tests/unit/test_perf_v3149.py` | **22 passed** |
| `pytest tests/unit -q` | **504 passed, 1175 warnings** |

## Фикстуры регрессии
- `tests/fixtures/perf_baseline_1000.json` — baseline v3.14.9 (24.0 f/min, 666136 findings)
- `tests/fixtures/perf_after_1000.json` — after v3.14.10 (65.8 f/min, 598 findings)
(Полные дампы `*_findings.jsonl.gz` в `temp/phase3/` — gitignored, не добавлены в репозиторий.)

## Изменённые файлы
- `scanner/connectors/_text_scanner.py` — дедуп в рамках файла
- `scanner/classifiers/pii_classifier.py` — NER-исключение, entities-фильтр, подрезка spaCy
- `scanner/src/finding.py` — `metadata`
- `scanner/src/managed_scanner.py` — прокидка metadata + ner_enabled
- `scanner/src/config_loader.py` — `PiiConfig.ner_enabled/excluded_entities`
- `scanner/config/scanner_config.json` — конфиг NER-фильтра
- `tests/unit/test_dedup_v31410.py` — обновлён под новый API
- `tests/unit/test_perf_regression_v31410.py` — регрессия
- `tests/fixtures/perf_baseline_1000.json`, `tests/fixtures/perf_after_1000.json` — фикстуры
- `CHANGELOG.md`, `STATE.md`, `ARCHITECTURE.md`, `docs/admin-guide/06-scanner.md` — обновлены

## Ручной тест
```powershell
# 1) Быстрая проверка
$env:PYTHONIOENCODING="utf-8"
python -c "
# файл с повторами PII
pass
"

# 2) Единичный прогон
python -m pytest tests/unit/test_dedup_v31410.py tests/unit/test_perf_regression_v31410.py -v

# 3) Замер на 1000 файлов (опц.)
python -u temp/phase3/measure_1000.py E:\Temp\dcap_perf_1000 temp\phase3\fp_check.json check 8
```

**Результат приёмки:** Files/min 65.8 ≥ 50, findings/файл 0.6 ≤ 30, regression 0 lost. Line-windowed Presidio **не применялся**.
