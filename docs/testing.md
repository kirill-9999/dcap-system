# Тестирование DCAP (День 40-41)

Проект использует **pytest** как основу тестирования (внедрён в v3.8.0).

## Требования

- Python 3.10+ и зависимости: `pip install -r requirements.txt -r requirements-dev.txt`
- **E2E / Chaos / Load** требуют запущенного тестового стека:
  `docker compose -f docker-compose.test.yml up -d --build` (или `scripts/test-up.sh`)
- **E2E со сканером** требуют реально запущенного сканера на хосте
  (`python run_scanner.py scanner/config/scanner_config.json`) и его регистрации в Manager.

Тестовый стек изолирован: БД `dcap_test` (PostgreSQL :15432, tmpfs), Redis :16379,
Manager на **:18000**, WebUI на **:18001**, сеть `dcap-test-network`.
Прод-данные не затрагиваются.

## Быстрый старт

```bash
scripts/test-up.sh            # поднять стек (build + wait health)
pytest tests/                 # все тесты
scripts/run-tests.sh e2e      # только E2E
scripts/run-tests.sh chaos    # только Chaos (-m chaos)
scripts/run-tests.sh load     # только Load (-m load)
scripts/run-tests.sh quick    # E2E без slow-тестов
scripts/test-down.sh          # остановить стек
```

Если стек не запущен — тесты с `requires_manager`/`requires_docker` будут
**skip** (не fail), так как у них есть соответствующие маркеры и проверки.

## Структура

```
tests/
├── conftest.py                # общие фикстуры: api_client, anon_client, cleanup_tasks
├── e2e/                       # сквозные сценарии (задание → сканирование → находки)
│   ├── conftest.py            # фикстуры сканеров (first_active_scanner)
│   ├── test_full_scan_cycle.py
│   ├── test_auth_flow.py
│   ├── test_scanner_heartbeat.py
│   ├── test_agents_flow.py
│   ├── test_webui_proxy.py
│   └── test_retention.py
├── chaos/                     # отказоустойчивость (Manager/Redis/PG/Scanner/сеть)
│   ├── conftest.py            # ComposeService + compose_stack фикстура
│   ├── test_manager_down.py
│   ├── test_redis_down.py
│   ├── test_postgres_down.py
│   ├── test_scanner_crash.py
│   └── test_network_partition.py
├── load/                      # базовые нагрузочные (глубокие — в v3.1.0)
│   ├── test_api_load.py
│   ├── test_agents_load.py
│   └── test_concurrent_scanners.py
└── fixtures/                  # переиспользуемые хелперы (модули, не pytest-фикстуры)
    ├── auth.py                # login/token
    ├── manager.py             # create/get/wait task
    ├── scanner.py             # list/get/register/heartbeat scanner
    ├── db.py                  # cleanup задач
    └── test_files.py          # генерация тестовых файлов (PII/creds/code)
```

## Фикстуры

| Фикстура | Назначение |
|----------|------------|
| `manager_url` / `webui_url` / `scanner_url` | Адреса компонентов (env `MANAGER_URL`/`WEBUI_URL`/`SCANNER_URL`, по умолчанию :18000/:18001/:9101) |
| `api_client` | `requests.Session` с Bearer-токеном admin (логин admin/admin123) |
| `anon_client` | Анонимни session без токена |
| `test_files_dir` | Временная папка с pii.txt / creds.env / code.py / clean.txt |
| `cleanup_tasks` | Удаление созданных заданий после теста |
| `compose_stack` (chaos) | Обёртка над `docker compose -f docker-compose.test.yml` |

## Маркеры pytest

| Маркер | Назначение |
|--------|------------|
| `e2e` | Сквозные сценарии |
| `chaos` | Отказоустойчивость |
| `load` | Нагрузочные |
| `slow` | Дольше 30 сек |
| `requires_manager` | Нужен запущенный Manager |
| `requires_docker` | Нужен Docker + тестовый стек |
| `requires_scanner` | Нужен запущенный и зарегистрированный Scanner |

`--strict-markers` регистрация маркеров — в `pyproject.toml` `[tool.pytest.ini_options]`.
`--timeout=300` (в `pytest`-опциях и `scripts/run-tests.sh`) защищает от зависаний.

## Как добавить тест

1. Определи группу: `tests/e2e/`, `tests/chaos/`, `tests/load/`.
2. Подключи нужные маркеры (`@pytest.mark.e2e`, `@pytest.mark.requires_manager`, ...).
3. Используй готовые фикстуры из `tests/conftest.py`.
4. Вспомогательные функции — в `tests/fixtures/*.py` (импорт: `from fixtures.auth import ...`
   работает автоматически, `tests/` добавляется в `sys.path` в корневом conftest).
5. Добавь фикстуру/маркер в conftest и, если нужен новый маркер, — в pyproject.toml.

## Известные ограничения

- Chaos-тесты: `test_scanner_inactive_alert` — **skip** с причиной (требует ручной
  остановки сканера; автоматизация — в v3.1.0).
- Load-тесты: rate-limit Manager (300 req/min по IP) может отдавать 429 — это не 5xx
  и в ошибки не попадает; фактическое число созданных заданий в отчёте теста.
- `/api/findings` поддерживает фильтр `task_id` (добавлен в v3.8.0).

## CI-интеграция

Полноценный GitHub Actions pipeline — в **Дне 42**. Рекомендуемая схема:

```yaml
- run: pip install -r requirements-dev.txt
- run: scripts/test-up.sh
- run: pytest tests/ -m "e2e and not requires_scanner"
- run: pytest tests/chaos -m chaos
- run: scripts/test-down.sh
```