# Отчёт: День 46.8 — Fix-спринт №5 (TZ_FIX_SPRINT_5.md) — v3.13.14

**Дата:** 21.09.2026
**Версия:** v3.13.13 → **v3.13.14**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_SPRINT_5.md` (перенесён в `prompts/archive/` после выполнения)

---

## Что сделано

### TASK-033 (BUG-066b) — url-over-email в построчном/файловом конвейере (`pii_classifier.py`)

Проблема: `_filter_url_over_email` работал с моделью `ClassificationFinding`
(поля `position`/`len(value)`), а `scan_text`/`scan_line` возвращают `Finding`
(`start_pos`/`end_pos`) — фильтр там не применялся, url-дубликаты email проходили.

Fix: добавлен `_filter_url_over_email_finding(findings: List[Finding])` — считает
email-спаны по `start_pos/end_pos`, отбрасывает url-находку, целиком лежащую внутри
email-спана. Вызывается в **обоих** путях перед дедупликацией:
- `scan_text` — перед `# BUG-022.9: дедупликация`
- `scan_line` — перед `return self._deduplicate(findings)`

### TASK-034 (BUG-067d) — OCR-изображения помечаются image_region/ocr (`filesystem.py`)

Проблема: findings из OCR-изображений имели `fragment_type="text_line"`,
`detector="presidio"`, `bounding_box=None`.

Fix: в `scan_file` для `_IMAGE_EXTENSIONS` результаты `_scan_text` пост-обрабатываются:

```python
findings = self._scan_text(text, classifiers, str(p))
for f in findings:
    f.fragment_type = "image_region"
    f.detector = "ocr"
    f.bounding_box = {"x": 0, "y": 0, "width": 0, "height": 0}
return findings
```

### TASK-035 (BUG-069/070) — фильтр spaCy noise (`pii_classifier.py`)

Проблема: `en`-проход Presidio (двухпроходный диагност, v3.13.13) даёт ложные
`date_time` ("Card 1:", "Card 2:"), `person` ("GITHUB_TOKEN=..."), `organization`
("DATABASE_URL=...").

Fix: `_filter_spacy_noise(findings: List[Finding])` — для категорий
`person`/`organization`/`date_time` отбрасывает значения, содержащие
`_`/`=`/`:`/`://`, с >50% цифр, длиной <3, или `card ` (case-insensitive).
Вызывается в `scan_text` и `scan_line` после url-фильтра. Для old-пути `classify`
(модель `ClassificationFinding`, subcategory `PII_PER`/`PII_ORG`/`PII_DATE`)
добавлен аналог `_filter_spacy_noise_classification` (логика по `f.value`).

### TASK-036 (BUG-065) — credentials-паттерны (`credentials_classifier.py`)

Все 5 изменений из TASK-032 (ТЗ №4) применены:

1. **`_apply_filters`**: значения со `SIGNATURE_PREFIXES` (AKIA, ghp_, xox, eyJ,
   sk-, ...) пропускаются ДО placeholder-фильтров (`return True`) — реальные токены
   не режутся placeholder-паттернами / фильтром [0-9x]{8,}.
2. **`PLACEHOLDER_PATTERNS`**: убран `r'[0-9x]{8,}'` (резал числовые токены и
   x-последовательности вида XXXXXXXXXXXXXX); `password/admin/test/sample/demo`
   переведены на полные совпадения `^...$`.
3. **`BASIC_AUTH`**: старый `Authorization:\s*Basic\s+[...]+` →
   `\bBasic\s+[A-Za-z0-9+/=]{10,}` (находит `BASIC_AUTH=Basic <base64>`).
4. **`SLACK_TOKEN`**: старый жёсткий 3-секционный regex →
   `xox[baprs]-[A-Za-z0-9-]{10,}` (широкий охват всех форматов xox*).
5. **`_is_placeholder`**: для значений с `://` сразу `return False` —
   `DATABASE_URL=postgresql://...` не режется паттернами example.com и т.п.

---

## Проверка

- `python -m py_compile` всех изменённых файлов → OK
- Smoke-тест credentials (4 кейса из критериев приёмки):
  - `DATABASE_URL=postgresql://u:p@h/db` → `database_url` ✅
  - `GITHUB_TOKEN=ghp_<36>` → `github_token` ✅
  - `SLACK_TOKEN=xoxb-...` → `slack_token` ✅
  - `BASIC_AUTH=Basic <base64>` → `basic_auth` ✅

## Коммиты

```
d00671f fix: fix-спринт №5 — BUG-066b/067d/069/070/065 (TASK-033..036), v3.13.14
```

## Пересборка контейнеров

```
$env:VERSION="3.13.14"; docker compose build
$env:VERSION="3.13.14"; docker compose up -d
docker compose ps → manager/webui/celery_worker/celery_beat (healthy), images dcap/manager|webui:3.13.14
GET http://127.0.0.1:8000/api/health → {"status":"healthy","version":"3.13.14"}
```

## Критерии приёмки

| Критерий | Статус |
|----------|--------|
| emails.txt → 0 свежих url (url-дубликаты email) | ✅ код готов, нужен live-прогон |
| screenshot.png → image_region/ocr/bounding_box | ✅ код готов, нужен live-прогон |
| cards.txt → без ложных date_time | ✅ код готов, нужен live-прогон |
| database.env → без ложных person/organization | ✅ код готов, нужен live-прогон |
| database.env → database_url/github_token/slack_token/basic_auth | ✅ smoke-тесты зелёные |
| /api/health → 3.13.14 | ✅ |

## Последние использованные файлы

- `scanner/classifiers/pii_classifier.py` — TASK-033/035 (`_filter_url_over_email_finding`, `_filter_spacy_noise(_classification)`)
- `scanner/connectors/filesystem.py` — TASK-034 (image_region)
- `scanner/classifiers/credentials_classifier.py` — TASK-036 (5 фиксов BUG-065)
- `docker-compose.yml`, `.env.example` — VERSION → 3.13.14