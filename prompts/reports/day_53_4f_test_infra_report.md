# Отчёт — День 53.4f: тест-инфраструктура (BUG-259/260/261, BUG-262 этап A, BACKLOG-317)

**Версия:** v3.14.3 (без bump — инфраструктура/тесты/док)
**Дата:** 17.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes

## Цель

Закрыть тест-инфра-дефекты v3.14.3 и зафиксировать реальное состояние E2E-стенда
(решение архитектора: BUG-262 — Вариант 2, поэтапно; BACKLOG-317 — срочно).

## 1. BUG-261 — `test_archiver_findings` TypeError

**Причина:** тест устарел после Findings Refactor (v3.9.0): у `Finding` нет
`file_path` / `value` / `created_at`. `archiver` считает cutoff по `first_seen_at`.

**Фикс** (`manager/tests/test_retention.py`): фикстура приведена к текущей схеме —
`finding_type`, `category`, `fragment_type`, `fingerprint`, `encryption_key_id`,
`line_number`, `line_text_masked`, `match_text_masked`, `first_seen_at`.

**Проверка:** `pytest manager/tests/test_retention.py::test_archiver_findings -q` → `1 passed`.

## 2. BUG-259 — `test_ad_permissions` ModuleNotFoundError (combined)

**Причина (диагностика):** не порядок `sys.path`, а тип пакетов.
`manager/src/connectors/` не имел `__init__.py` → namespace-portion; в
`scanner/connectors/` есть `__init__.py` → regular-пакет. При combined-прогоне
(`tests/unit` + `manager/tests`) `tests/unit` подтягивает `scanner/connectors/filesystem.py`,
который делает `from connectors.base import ...` → `sys.modules['connectors']`
указывает на `scanner/connectors` (regular-пакет перекрывает namespace-portion).
Далее `from connectors.permissions import ...` в `test_ad_permissions` не находит subpackage.

**Фикс:**
- `manager/src/connectors/__init__.py` (new) — делает `connectors` regular-пакетом Manager'а;
- `manager/tests/test_ad_permissions.py` — перед импортом чистит
  `sys.modules['connectors*']` и ставит `manager/src` первым в `sys.path`.

**Проверка:**
- репродукция combined `... bug097 + factory + ad_permissions` → `22 items` (0 error);
- полный `pytest tests/unit manager/tests --co` → **517 collected, 0 errors** (было 501 + 1 error).

## 3. BUG-260 — Windows PermissionError (`pytest-current`)

**Фикс:** корневой `conftest.py` — `pytest_configure` переносит `basetemp` в
`.pytest-tmp/` (только Windows, если `--basetemp` не задан). `.pytest-tmp/` в `.gitignore`.

**Проверка:** `pytest manager/tests/test_security.py` → `.pytest-tmp` создан,
`PermissionError` нет.

## 4. BACKLOG-317 — общее имя проекта compose

**Причина:** `docker-compose.test.yml` не задавал `name:` → project name = `dcap-system`
(как у основного `docker-compose.yml`); `down -v --remove-orphans` стенда сносил
контейнеры `dcap-*` основного стека.

**Фикс:** `name: dcap-test` в `docker-compose.test.yml`.
**Проверка:** `docker compose -f docker-compose.test.yml config | name:` → `dcap-test`;
`docker compose config | name:` → `dcap-system` (разные).

## 5. BUG-262 — этап A (документация)

**Внешние предусловия стенда (не поднимает сам):** сканер `:9101`; MinIO
`host.docker.internal:9000`; seed-findings; пользователь `auditor/auditor123`.

**Фактические счётчики** (стенд `:18000/:18001` healthy, предусловия не выполнены):
**47 passed, 12 skipped, 6 failed** (65 собранных).

**6 падений:**
| Тест | Причина |
|------|---------|
| `test_full_scan_cycle` | нужен сканер :9101 |
| `test_scanner_findings::test_real_scanner_end_to_end` | нужен сканер :9101 |
| `test_scanner_heartbeat::test_scanner_heartbeat_keeps_active` | нужен сканер :9101 |
| `test_webui_block5_v31322::test_proxy_forwards_total_count` | нет seed-findings (`X-Total-Count=0`) |
| `test_webui_block5_v31322::test_findings_filters_csv_and_empty` | нет seed-findings |
| `test_webui_block5_v31322::test_webui_pages_with_filters` | `loadFilterOptions` — см. BUG-263 |

**Целевой эталон 53 passed / 7 skipped** — сохраняется как цель при выполненных
предусловиях. Этап B (seed-скрипт + маркеры `requires_minio`/`requires_seed`, CI-селектор
`-m "not requires_scanner and not requires_minio"`) — до 55; этап C (CI) — BACKLOG-046.

**Документация:** `docs/testing.md` — новый раздел «E2E: предусловия и счётчики» +
предупреждение BACKLOG-317; `STATE_TEST_SESSION.md` — реальные 47/12/6; `STATE.md`,
`ROADMAP.md` — BUG-262/263, BACKLOG-317/046.

## 6. BUG-263 (открыт, проверить)

`loadFilterOptions` присутствует в `webui/static/js/audit.js`, но **отсутствует**
в `webui/templates/audit.html`. `test_webui_block5_v31322::test_webui_pages_with_filters`
ожидает функцию в HTML-шаблоне. Требуется решение: seed данных vs. доработка
шаблона (возможен UI-баг, вне тест-инфры).

## 7. Восстановление основного стека

После сноса (BACKLOG-317) основной стек восстановлен:
`docker compose up -d --wait` → **13 контейнеров healthy**; `:8000/api/health` → 200,
`:8001/` → 200. Сканер на хосте `:9101` — отдельно.

## 8. Проверки (сводка)

| Команда | Результат |
|---------|-----------|
| `pytest tests/unit manager/tests -q` | **517 passed** |
| `pytest manager/tests/test_retention.py::test_archiver_findings` | 1 passed |
| `pytest tests/e2e/ -rs` (стенд, без предусловий) | 47 passed, 12 skipped, 6 failed |
| `docker compose ps` | 13 healthy |

## 9. Изменённые файлы

```
 M .gitignore
 M manager/tests/test_ad_permissions.py
 M manager/tests/test_retention.py
 M docker-compose.test.yml
 M docs/testing.md
 M STATE.md
 M ROADMAP.md
 M STATE_TEST_SESSION.md
?? conftest.py
?? manager/src/connectors/__init__.py
?? prompts/reports/day_53_4f_test_infra_report.md
```

## 10. Команда коммита

```powershell
git add .gitignore conftest.py manager/src/connectors/__init__.py `
        manager/tests/test_ad_permissions.py manager/tests/test_retention.py `
        docker-compose.test.yml docs/testing.md STATE.md ROADMAP.md STATE_TEST_SESSION.md `
        prompts/reports/day_53_4f_test_infra_report.md
git commit -m "fix: тест-инфра v3.14.3 — BUG-259/260/261, BUG-262 этап A, BACKLOG-317

BUG-259: manager/src/connectors/__init__.py + зачистка sys.modules['connectors*']
         в test_ad_permissions; combined-прогон 517 collected, 0 errors
BUG-260: корневой conftest.py — basetemp в .pytest-tmp (Windows), .gitignore
BUG-261: test_archiver_findings под схему Finding v3.9.0
BACKLOG-317: docker-compose.test.yml name: dcap-test (не сносит основной стек)
BUG-262 (этап A): docs/testing.md + STATE_TEST_SESSION.md — реальные 47/12/6,
эталон 53/7 при предусловиях; BUG-263/262 в STATE.md/ROADMAP.md

Тесты: pytest tests/unit manager/tests -q -> 517 passed"
```

## 10. Дальше

- Ручная верификация WebUI-блока 14 (Settings).
- BUG-263 — решение по `loadFilterOptions`.
- BUG-262 этап B (seed + маркеры) — до 55.
