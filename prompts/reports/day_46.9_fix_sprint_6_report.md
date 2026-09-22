# Отчёт: День 46.9 — Fix-спринт №6 (TZ_FIX_SPRINT_6.md) — v3.13.15

**Дата:** 22.09.2026
**Версия:** v3.13.14 → **v3.13.15**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_SPRINT_6.md` (перенесён в `prompts/archive/` после выполнения)

---

## Что сделано

Все правки — в одном файле `scanner/classifiers/pii_classifier.py` (+ smoke-тесты).

### TASK-037 (BUG-071 + BUG-074) — `_filter_url_over_email_finding` переписан

Проблема: старый фильтр работал по спанам (`start_pos`/`end_pos`), но Presidio
обрезает url по `@` (`http://bob.new` для `http://bob.new@test.example/x`) или
отрезает логин (`example.org/path`) — спаны url и email НЕ пересекались, фильтр
не срабатывал. Плюс не было межклассификаторной координации: email из URL-логина
(`postgresql://user:pass@host:port/db`) проходил.

Fix (по ТЗ): работа по `line_text`. Если строка содержит URL-схему (`://`) И
email-признак (`@` или email-паттерн) — отбрасываются все url/email-findings этой
строки. Обычный email без `://` (`contact: user@example.com`) сохраняется.

### TASK-038 (BUG-072) — аббревиатуры в spaCy noise

Проблема: `organization = "INN"` (3 заглавные латинские) из `en`-прохода —
текущий фильтр не отбрасывал (нет `_:=`, 0% цифр, len=3 не <3).

Fix: в `_filter_spacy_noise` и `_filter_spacy_noise_classification` добавлено
условие — `len(val) <= 5 and val.isupper() and val.isascii() and val.isalpha()`
(INN/SSN/DOB/URL/API и т.п.).

### TASK-039 (BUG-073) — `_filter_uk_nhs_with_phone`

Проблема: `UkNhsRecognizer` ловил 10 цифр — US-телефон `+1 415 555 0199` проходил
как UK NHS.

Fix: новая функция `_filter_uk_nhs_with_phone` — отбрасывает `uk_nhs`, если в той
же строке (по `line_number`/`fragment_path`) уже есть `phone`. Подключена в
`scan_line` и `scan_text` после `_filter_spacy_noise` и перед дедупликацией.

---

## Проверка

- `python -m py_compile scanner/classifiers/pii_classifier.py` → OK
- `python -m pytest tests/unit/test_pii_filters_v31315.py -v` → **7 passed**
  (url-over-email removed, credentials-url email removed, plain email kept,
  INN removed, Apple Inc kept, uk_nhs removed with phone, uk_nhs kept without)
- `python -m pytest tests/unit/ -q` → **135 passed** (регрессий нет)

## Коммиты

```
6a19597 fix: fix-спринт №6 — BUG-071..074 (TASK-037..039), v3.13.15
```

## Пересборка контейнеров

```
$env:VERSION="3.13.15"; docker compose build
$env:VERSION="3.13.15"; docker compose up -d
docker compose ps → manager/webui/celery_worker/celery_beat (healthy), images dcap/manager|webui:3.13.15
GET http://127.0.0.1:8000/api/health → {"status":"healthy","version":"3.13.15"}
```

## Критерии приёмки ТЗ №6

| Критерий | Статус |
|----------|--------|
| pytest tests/unit/test_pii_filters_v31315.py — все зелёные | ✅ 7 passed |
| python -m py_compile pii_classifier.py — OK | ✅ |
| task 33 completed, критерии приёмки | ⏳ live-прогон на C:\test\scanner_clean (нужен пользователь) |
| Обновлён STATE.md (v3.13.15, Блок 3 — 100%) | ✅ |
| Обновлён ROADMAP.md (BUG-071…074 → ✅) | ✅ |
| Обновлён STATE_TEST_SESSION.md (Блок 3 → ✅) | ✅ |

## Последние использованные файлы

- `scanner/classifiers/pii_classifier.py` — TASK-037/038/039
- `tests/unit/test_pii_filters_v31315.py` — новые smoke-тесты (7)
- `docker-compose.yml`, `.env.example` — VERSION → 3.13.15
- `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md`, `CHANGELOG.md` — обновлены