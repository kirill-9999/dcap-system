# Отчет: День 21 — Интеграционное тестирование

**Дата:** 25.08.2026
**ТЗ:** `prompts/tz/day_21_integration_testing.md`
**Статус:** Выполнено, 47/48 пройдено

---

## Результат

```
47 passed, 1 skipped in 134.39s
```

| Модуль | Файлов | Тестов | Passed | Failed | Skipped |
|--------|--------|--------|--------|--------|---------|
| test_api.py | 1 | 12 | 12 | 0 | 0 |
| test_audit.py | 1 | 7 | 7 | 0 | 0 |
| test_scanner.py | 1 | 6 | 5 | 0 | 1 |
| test_webui.py | 1 | 21 | 21 | 0 | 0 |
| test_e2e.py | 1 | 2 | 2 | 0 | 0 |
| **Итого** | **5** | **48** | **47** | **0** | **1** |

Skip: `test_submit_results` — нет активного задания для сканера (нет незавершённых задач).

---

## Структура файлов

```
tests/
├── __init__.py
└── integration/
    ├── __init__.py
    ├── conftest.py          # Фикстуры: manager_url, webui_url, db_conn, test_resource, test_agent
    ├── test_api.py          # Manager API: health, redirect, resources CRUD, tasks, findings, catalog, permissions, audit
    ├── test_scanner.py      # Scanner: register, duplicate, heartbeat, db update, pending tasks, results
    ├── test_audit.py        # Audit Agent: register, heartbeat, db check, ingest events, API visibility, stats
    ├── test_webui.py        # WebUI: homepage, no-cache, dashboard elements, 4 pages, 13 API endpoints, 3 vendor assets
    ├── test_e2e.py          # E2E: полный цикл (health→agent→event→API→report) + DB consistency
    └── README.md            # Инструкция по запуску
```

---

## Что проверяется

### Manager API (12 тестов)
- Health check (`/api/health`)
- Root redirect (`/` → `:8001`)
- Resources: list, create/delete, scan
- Tasks: list
- Findings: list
- Catalog: list, tree
- Permissions: mode
- Audit: stats, events

### Audit Agent (7 тестов)
- Register → agent_id
- Heartbeat → 200
- Heartbeat → last_heartbeat updated in DB
- Ingest events → saved count
- Events visible in API
- Audit stats
- Events stored in DB (>0)

### Scanner (6 тестов)
- Register → scanner_id
- Duplicate register → idempotent
- Heartbeat → 200
- Heartbeat → last_heartbeat in DB
- Pending tasks → 200/404
- Submit results → SKIPPED (no task)

### WebUI (21 тест)
- Homepage: 200, "DCAP", no-cache
- Dashboard: elements (total-findings, active-scanners, dashboard-audit-agents)
- Pages: /findings, /tasks, /scanners, /resources
- APIs: stats, findings, tasks, scanners, resources, audit, audit/stats, audit/agents
- Reports: preview, Excel export, PDF export
- Vendor: bootstrap.css, fontawesome.css, chart.js

### E2E (2 теста)
- Полный цикл: Manager health → WebUI → redirect → agent register → event → audit API → stats → report preview → Excel → PDF
- DB consistency: все 6 таблиц существуют, агенты >0, события >0

---

## Исправления во время тестирования

1. `test_api.py`: `create_resource` принимает query params, не JSON body
2. `test_audit.py`: Manager `/api/audit/stats` не содержит `agents_total`
3. `test_scanner.py`: Scanner register возвращает `scanner_id`, не `id`
4. `test_e2e.py`: Redirect test проверял `webui_url` вместо `manager_url`

---

## Команда для коммита

```bash
git add tests/
git commit -m "test: День 21 — интеграционное тестирование Windows-стека (47 passed)"
```
