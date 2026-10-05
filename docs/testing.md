# Тестирование DCAP (День 40-41)

Проект использует **pytest** как основу тестирования (внедрён в v3.8.0).

## Требования

- Python 3.10+ и зависимости: `pip install -r requirements.txt -r requirements-dev.txt`
- Docker + Docker Compose v2 (поддерживается `up --wait`).
- **E2E / Chaos / Load** требуют запущенного тестового стека:
  `docker compose -f docker-compose.test.yml up -d --build --wait` (или `scripts/test-up.sh`).
  Ручные `restart`/`down -v` **не нужны** — `scripts/run-tests.sh all` сам делает
  чистый пересозданный запуск (см. «Автоматический запуск стенда»).
- **E2E со сканером** требуют реально запущенного сканера на хосте и его регистрации
  в Manager. Сканер требует ключи шифрования находок (иначе fail-fast):

  ```powershell
  # PowerShell
  $env:FINDINGS_ENCRYPTION_KEY = "<base64 32 bytes>"
  $env:FINDINGS_HMAC_KEY       = "<base64 32 bytes>"
  $env:MANAGER_URL             = "http://127.0.0.1:18000"   # тестовый Manager
  python run_scanner.py scanner/config/scanner_config.json
  ```

  Либо, для локальной разработки, `DCAP_ALLOW_LEGACY_SCANNER=true` — только в dev,
  в prod сканер без ключей не стартует (см. `docs/admin-guide/05-security.md`).

Тестовый стек изолирован: БД `dcap_test` (PostgreSQL :15432, tmpfs), Redis :16379,
Manager на **:18000**, WebUI на **:18001**, сеть `dcap-test-network`.
Прод-данные не затрагиваются.

## Быстрый старт

```bash
scripts/test-up.sh            # поднять стек (build + wait health)
scripts/run-tests.sh all      # чистый стенд + все тесты (рекомендуется)
scripts/run-tests.sh e2e      # только E2E
scripts/run-tests.sh chaos    # только Chaos (-m chaos)
scripts/run-tests.sh load     # только Load (-m load)
scripts/run-tests.sh quick    # E2E без slow-тестов
scripts/test-down.sh          # остановить стек
```

Если стек не запущен — тесты с `requires_manager`/`requires_docker` будут
**skip** (не fail), так как у них есть соответствующие маркеры и проверки.

## Автоматический запуск стенда

`scripts/run-tests.sh all` выполняет полный цикл без ручных шагов:

1. `docker compose -f docker-compose.test.yml down -v --remove-orphans` — остановка
   и **удаление томов** (гарантирует чистую БД: нет pending-заданий и находок от
   прошлых прогонов — TEST-NOTE-10.7).
2. `docker compose -f docker-compose.test.yml up -d [--build] --wait` — запуск и
   ожидание healthcheck всех сервисов (TEST-NOTE-10.6).
3. `pytest` — прогон тестов.

Healthcheck в `docker-compose.test.yml`: `manager_test` ждёт `GET /api/health`,
`webui_test` — `GET /health`; `webui_test` стартует только после
`service_healthy` Manager, поэтому `--wait` гарантирует готовность обоих.

Остальные режимы (`e2e`, `quick`, `load`, `chaos`) **не трогают стенд** — они
предполагают, что он уже поднят.

## Известные ограничения стенда

- Тома PostgreSQL/Redis **пересоздаются** при `run-tests.sh all`: данные между
  прогонами не сохраняются.
- Нужен Docker Compose с поддержкой `--wait`; при более старой версии скрипт
  использует fallback (`up -d` + проверка health через HTTP).
- Docker Desktop на Windows: если опубликованный порт перестал отвечать при
  живых контейнерах (healthcheck зелёный, HTTP не отвечает) — прокси портов
  «залип». Помогает пересоздание контейнеров:
  `docker compose -f docker-compose.test.yml up -d --force-recreate manager_test webui_test`.
- 2 legacy-теста WebUI (`test_webui_block5_v31322.py`) требуют **непустую** таблицу
  findings (`X-Total-Count != "0"`). На полностью чистом стенде без находок они
  падают — это TEST-NOTE-10.8, отдельная задача, не регрессия стенда.

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
- S3/MinIO E2E (`test_s3_e2e.py`) требуют доступного MinIO (env `S3_DEFAULT_ENDPOINT`,
  по умолчанию `host.docker.internal:9000`) и креды `S3_ACCESS_KEY`/`S3_SECRET_KEY`;
  без них тесты **skip**.

## CI-интеграция

Полноценный GitHub Actions pipeline — в **Дне 42**. Рекомендуемая схема:

```yaml
- run: pip install -r requirements-dev.txt
- run: scripts/run-tests.sh all     # чистый стенд + все тесты
- run: scripts/test-down.sh
```