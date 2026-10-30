# Отчёт: День 56 — BUG-117 Manager маскирует контексты findings

**Версия:** v3.14.16 → v3.14.17
**Дата:** 29.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes

---

## Кратко

Manager теперь маскирует `context_before`/`context_after`/`match_text`/`line_text` через `mask_context` (22 паттерна, specific → generic). Добавлены 8 новых категорий в `MASK_RULES` (всего 19). Двойная маскировка на чтении (`findings.py`) и записи (`scanner.py`).

---

## Изменённые файлы

- `manager/src/core/encryption.py` — `MASK_RULES` 11→19, `_mask_database_url`, `_CONTEXT_PATTERNS`, `mask_context`.
- `manager/src/api/scanner.py` — `mask_context(...)` при создании Finding.
- `manager/src/api/findings.py` — `mask_context(...)` при ответе.
- `manager/tests/test_bug117_masking.py` — 16 тестов.

---

## Тесты

- `manager/tests/test_bug117_masking.py` — 16 passed.
- `manager/tests` — 67 passed.

---

## Артефакты

- Образ `dcap/manager:3.14.17`.
- Коммит `021b5c6`.

---

## Коммит

```powershell
git commit -m "fix: BUG-117 — Manager маскирует контексты findings (mask_context, 19 правил)"
```
