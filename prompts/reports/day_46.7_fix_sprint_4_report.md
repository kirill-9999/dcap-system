# Отчёт: День 46.7 — Fix-спринт №4 (TZ_FIX_SPRINT_4.md) — v3.13.13

**Дата:** 21.09.2026
**Версия:** v3.13.13
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_SPRINT_4.md` (архив после выполнения)

---

## Что сделано

### TASK-029 (BUG-067c) — OCR-ключ из правильной секции (`scanner/src/managed_scanner.py`)

Проблема: `_get_connector_config()` возвращает только connector-секцию конфига, ключа
`ocr_enabled` в ней нет → `FilesystemConnector` читал `self.config.get("ocr_enabled", False)`
и OCR всегда был ВЫКЛЮЧЕН, несмотря на `classifiers.pii.ocr_enabled: true` в конфиге.

Решение: в `_init_line_pipeline` (после `connector_cfg = self._get_connector_config()`)
прокинут ключ из PII-секции:

```python
connector_cfg = self._get_connector_config()
# TASK-029 (BUG-067c): OCR-ключ берём из classifiers.pii.ocr_enabled,
# потому что в connector-секции его нет (день 46.7).
pii_cfg = None
if self.config is not None and self.config.classifiers is not None:
    pii_cfg = getattr(self.config.classifiers, "pii", None)
ocr_enabled = bool(
    getattr(pii_cfg, "ocr_enabled", True)
    if pii_cfg is not None
    else True
)
connector_cfg["ocr_enabled"] = ocr_enabled
self._connector = FilesystemConnector(connector_cfg)
```

### TASK-030 (BUG-063) — двухпроходный Presidio ru+en (`scanner/classifiers/pii_classifier.py`)

Проблема: все вызовы `analyzer.analyze(text=..., language="ru")` — только один проход.
Presidio регистрирует `CREDIT_CARD` и US-сущности (банки, водительские права, SSN)
ИСКЛЮЧИТЕЛЬНО для `language="en", а телефон/паспорт/СНИЛС/ИНН — для `"ru"`.
В одном `ru`-проходе кредитки не детектировались вообще (Luhn-фильтр из fix-спринта №3
стал бесполезным — до него ничего не доходило).

Решение: **двухпроходный анализ (ru+en) + дедуп по span `(entity_type, start, end)`**,
сохраняется наибольший score. Применено во **всех трёх** местах:

1. `scan_line()` (построчный путь) — L404-409:
```python
with analyzer_lock:
    # TASK-030 (BUG-063): двухпроходный ru+en — Presidio регистрирует
    # CREDIT_CARD и US-паттерны только для en; кредитки в ru-тексте
    # без en-пасса не детектируются.
    results_ru = analyzer.analyze(text=line, language="ru")
    results_en = analyzer.analyze(text=line, language="en")
    results = list({
        (r.entity_type, r.start, r.end): r
        for r in (results_ru + results_en)
    }.values())
```

2. `scan_text()` (файловый путь, Presidio по всему тексту) — L487-492 (тот же дедуп).

3. `classify()` (main-путь конвейера) — L800-809 + фикс итерации по `results.values()`:
```python
# Двухпроходный анализ (TASK-030, BUG-063): ... делаем оба и дедуплицируем.
results = {}
for lang in ("ru", "en"):
    with analyzer_lock:
        pass_results = self._analyzer.analyze(
            text=text,
            language=lang,
        )
    for r in pass_results:
        key = (r.entity_type, r.start, r.end)
        if key not in results or r.score > results[key].score:
            results[key] = r

for result in results.values():
```

Важно: в `classify()` переменная `results` изначально была списком от Presidio; при
переходе на дедуп-словарь итерация идёт по `results.values()` (иначе дедупликация
вернула бы ключи-кортежи и `result.entity_type` упал бы).

### TASK-031 (BUG-066) / TASK-032 (BUG-065)

Уже закрыты на день 46.5/46.7:
- `_filter_url_over_email` — единственный корректный (ClassificationFinding, position/len), L600.
- credentials — дедупликация по `(subcategory, value)` с `CATEGORY_PRIORITY`.
Изменений не потребовалось.

---

## Проверка

- `python -m py_compile scanner/src/managed_scanner.py scanner/classifiers/pii_classifier.py` → OK
- grep по `analyze(`: подтверждены все 3 двухпроходных пути (L404-405, L487-488, L803)

---

## Коммит

```
d1c9ccc fix: OCR-секция + двухпроходный Presidio ru+en (TASK-029/030) — ТЗ4, v3.13.13
```

## Пересборка контейнеров

```
$env:VERSION="3.13.13"; docker compose build
$env:VERSION="3.13.13"; docker compose up -d --build   # (после rm -f застрявших worker/beat/manager)
docker compose ps → manager/webui/celery_worker/celery_beat (healthy), images dcap/manager|webui:3.13.13
GET http://127.0.0.1:8000/api/health → {"status":"healthy","version":"3.13.13"}
```

> Примечание: celery_worker при `up -d --build` не останавливался (контейнер завис на kill) —
> помог `docker rm -f` проблемных контейнеров и повторный `up -d`. Дальнейший апдейт стека — штатно.

## Последние использованные файлы

- `scanner/src/managed_scanner.py` — TASK-029 (OCR-секция, L600-612)
- `scanner/classifiers/pii_classifier.py` — TASK-030 (двухпроходный ru+en, L404/487/800)
- `prompts/tz/TZ_FIX_SPRINT_4.md` → `prompts/archive/`
- `docker-compose.yml`, `.env.example` — VERSION → 3.13.13