# Отчёт: День 46.10 — Fix-спринт №7 (TZ_FIX_SPRINT_7.md) — v3.13.16

**Дата:** 22.09.2026
**Версия:** v3.13.15 → **v3.13.16**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_SPRINT_7.md` (перенесён в `prompts/archive/` после выполнения)

---

## Что сделано

### TASK-040 (BUG-075) — `_filter_url_over_email_finding` расширен

Проблема: Presidio URL recognizer ловил доменную часть email-адреса как отдельный
url-finding (`company.example` для `carol.new@company.example`). В таких строках
НЕТ `://`, поэтому условие п.1 (строки с `://`) не срабатывало → task 34 дал
5 url вместо 0 (ids 1328, 1337, 1338, 1339, 1340). Дополнительно ids 1338/1339 —
дубликат url в одной строке (разные start_pos/end_pos → дедупликатор не схлопнул).

Fix (новая реализация функции, 3 случая):

1. **url-over-email** (`http://user@host/path`): строка с `://` + email-признак
   (`@` или email-паттерн) → все url/email этой строки отбрасываются (как в ТЗ №6).
2. **credentials-URL** (`postgresql://user:pass@host:port/db`): email из URL-логина
   отбрасывается (покрыто п.1).
3. **BUG-075**: собраны все email-значения (match_text email-findings + email-паттерны
   из line_text, case-insensitive). url, чей match_text целиком входит в какое-либо
   email-значение → отбрасывается. Работает и для дублей url в одной строке.

---

## Проверка

- `python -m py_compile scanner/classifiers/pii_classifier.py` → OK
- `python -m pytest tests/unit/test_pii_filters_v31316.py -v` → **7 passed**
  (domain of email url removed, multiple urls same line, real url kept,
  email without url kept, + регрессия: scheme url-over-email, credentials-url,
  plain email no scheme)
- `python -m pytest tests/unit/test_pii_filters_v31315.py -v` → **7 passed** (регрессия)
- `python -m pytest tests/unit/ -q` → **142 passed** (135 + 7 новых)

## Коммиты

```
e467a04 fix: fix-спринт №7 — BUG-075 (TASK-040), v3.13.16
```

## Пересборка контейнеров

```
$env:VERSION="3.13.16"; docker compose build
$env:VERSION="3.13.16"; docker compose up -d
docker compose ps → manager/webui/celery_worker/celery_beat (healthy), images dcap/manager|webui:3.13.16
GET http://127.0.0.1:8000/api/health → {"status":"healthy","version":"3.13.16"}
```

## Критерии приёмки ТЗ №7

| Критерий | Статус |
|----------|--------|
| pytest test_pii_filters_v31316.py — 7 passed | ✅ |
| pytest test_pii_filters_v31315.py — 7 passed (регрессия) | ✅ |
| pytest tests/unit/ — 142 passed | ✅ |
| py_compile pii_classifier.py — OK | ✅ |
| Manager /api/health → 3.13.16 | ✅ |
| task 35 completed, findings_count = 29, url = 0 | ⏳ live-прогон (нужен пользователь) |
| STATE.md, ROADMAP.md (BUG-075 → ✅), STATE_TEST_SESSION.md (Блок 3 → ✅) | ✅ |

## Последние использованные файлы

- `scanner/classifiers/pii_classifier.py` — TASK-040 (новая реализация фильтра)
- `tests/unit/test_pii_filters_v31316.py` — новые smoke-тесты (7)
- `docker-compose.yml`, `.env.example` — VERSION → 3.13.16
- `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md`, `CHANGELOG.md` — обновлены