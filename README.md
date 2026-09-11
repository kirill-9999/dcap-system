# DCAP System

Система сканирования и аудита данных (PII/credentials/code) для Windows и Linux.

## Компоненты

| Компонент | Описание | Порт |
|-----------|----------|------|
| `manager/` | FastAPI control-plane | :8000 |
| `webui/` | Дашборд (Jinja2, прокси API на Manager) | :8001 |
| `scanner/` | Агент сканирования | — |
| `audit-agent-windows/` | Windows-агент аудита (wevtutil) | — |
| `audit-agent-linux/` | Linux-агент аудита (watchdog) | — |
| `audit-agent-s3/` | S3/MinIO агент аудита (polling) | — |
| `shared/` | Единая схема событий (UnifiedEvent) | — |

## Запуск

```bash
# Инициализация БД
python init_db.py

# Единый запуск Manager + WebUI (порты из конфигов)
python run_all.py

# или по отдельности:
python run_manager.py        # Manager API (порт из manager/config/config.json, :8000)
python run_webui.py          # WebUI (порт из webui/config/config.json, :8001)

# Сканер
python run_scanner.py scanner/config/scanner_config.json

# Windows-агент аудита
cd audit-agent-windows && python main.py config.json

# Linux-агент аудита
cd audit-agent-linux && ./start.sh --daemon

# S3/MinIO агент аудита
cd audit-agent-s3 && python -m src.main --config config/config.json
```

## Масштабирование (День 36-37): PostgreSQL + Redis + Celery

Production-стек поднимается одной командой:

```bash
docker compose up -d     # postgres(5432) + redis(6379) + manager(8000) + webui(8001) + celery worker/beat + flower(5555)
```

- **PostgreSQL 16** — основная БД (`postgres:16-alpine`). Миграции — Alembic:
  ```bash
  alembic upgrade head
  python scripts/migrate_sqlite_to_postgres.py  # перенос данных из SQLite (все таблицы + архивы)
  ```
- **Партиционирование** `audit_logs` по месяцам (RANGE on `created_at`), создаётся миграцией `001_initial_postgres` для PostgreSQL; SQLite-режим не затронут.
- **Redis 7** — брокер Celery + кэш + rate-limit. При недоступности Redis Manager работает в no-op режиме (rate-limit fail-open в памяти).
- **Celery** — очереди: `audit_events`, `scanner_tasks`, `retention`, `reports`. Периодическая архивация — Celery Beat (заменила фоновый поток дня 35).
  ```bash
  celery -A manager.src.workers.celery_app:app worker --queues=audit_events,scanner_tasks,retention,reports
  celery -A manager.src.workers.celery_app:app beat
  ```
- **Flower** — мониторинг задач на :5555.

Локальный запуск (без Docker) остаётся прежним: SQLite + без RabbitMQ/Celery (асинхронные задачи опциональны).

## Контейнеризация и деплой (День 38)

Полная контейнеризация всех компонентов — одна команда поднимает весь стек.

```bash
cp .env.example .env    # настроить пароли и ключи
./scripts/deploy.sh     # сборка образов + запуск всех сервисов + healthcheck
```

- **Dockerfile** (multi-stage, непривилегированный пользователь, healthcheck): `manager/` (Manager + Celery worker/beat), `webui/`, `audit-agent-s3/`, `audit-agent-linux/`; `.dockerignore` для каждого (build-контекст Manager/S3 — корень репо; webui — `./webui`).
- **docker-compose.yml** — полный стек: postgres(5432) + redis(6379) + manager(8000) + webui(8001) + celery worker/beat + flower(5555). Агенты — profile: `--profile agents` (S3).
- **Scanner — НЕ в Docker** (в контейнере нельзя динамически примонтировать папки из заданий): запускается на хосте через `python run_scanner.py scanner/config/scanner_config.json` и видит любые пути напрямую (см. `docs/deployment.md`).
- **docker-compose.prod.yml** — production overrides (лимиты CPU/RAM, mTLS, репликация worker).
- **Скрипты**: `scripts/deploy.sh`, `stop.sh`, `logs.sh`, `status.sh`, `healthcheck.sh`.
- **Документация**: `docs/deployment.md`.

## Тестирование (День 40-41): E2E + Chaos + Load

Тесты построены на **pytest** (изолированный тестовый стек `docker-compose.test.yml`,
Manager :18000, WebUI :18001, БД `dcap_test`, tmpfs). Полная инструкция —
**`docs/testing.md`**.

```bash
pip install -r requirements-dev.txt
./scripts/test-up.sh        # поднять изолированный тестовый стек
pytest tests/               # все тесты
./scripts/run-tests.sh e2e  # только E2E (или chaos / load / quick / all)
./scripts/test-down.sh      # остановить стек
```

- **E2E** — `tests/e2e/`: полный цикл (задание → сканирование → находки), auth, heartbeat сканера, агенты, WebUI-прокси, retention
- **Chaos** — `tests/chaos/`: падение Manager / Redis (fail-open) / PostgreSQL / Scanner, обрыв сети
- **Load** — `tests/load/`: 1000 заданий, 10 000 событий, конкурентные сканеры (базовые; глубокие — в v3.1.0)

## Мониторинг (День 39): Prometheus + Grafana + Alertmanager

Стек мониторинга поднимается вместе с docker-compose:

```bash
docker compose up -d prometheus grafana alertmanager \
  postgres_exporter redis_exporter celery_exporter
```

- **Grafana** — http://localhost:3000 (`admin` / `${GRAFANA_PASSWORD}`, дефолт `admin`); provisioning дашбордов из `monitoring/grafana/provisioning/`
- **Prometheus** — http://localhost:9090; таргеты в `monitoring/prometheus/prometheus.yml`
- **Alertmanager** — http://localhost:9093; уведомления (webhook/email/Slack/Telegram)
- **Алерты** — `monitoring/prometheus/alerts.yml` (ScannerInactive, TaskFailed, HighErrorRate, CeleryQueueBacklog)
- **Метрики**:
  - Manager — `GET /metrics` (HTTP, tasks, findings, scanner heartbeat age, celery queues)
  - Scanner (хост, :9101) — files/findings/duration/errors, собирается через `host.docker.internal`
  - Linux-агент (:9102), S3-агент (:9103), экспортеры Celery/PostgreSQL/Redis
- **Heartbeat-тред сканера**: фоновый поток шлёт heartbeat каждые 30 с (в т.ч. прогресс длинных заданий) — сканер больше не помечается "inactive" во время сканирования
- **Статус**: `./scripts/monitoring-status.sh` (полный) и `-q` (только проблемы)
- **Документация**: `docs/monitoring.md`

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ audit-agent │────▶│   Manager   │◀────│ audit-agent │
│  (Windows)  │     │   :8000     │     │   (Linux)   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │    WebUI    │
                    │   :8001     │
                    └─────────────┘
```

- **Manager** — REST API, прием событий от агентов, хранение в PostgreSQL (или SQLite в dev-режиме)
- **WebUI** — дашборд с фильтрацией по источнику (Windows/Linux), удаление агентов/сканеров. Все `/api/*` запросы проксируются в Manager (нет прямого доступа к БД)
- **Агенты** — легкие компоненты, буферизуют события в SQLite, отправляют батчами

## Единый формат событий

Все агенты (Windows, Linux, S3, scanner) используют формат `UnifiedEvent`:

- `event_type`: read, write, delete, move, rename
- `event_source`: windows_agent, linux_agent, scanner, s3_agent
- `user`, `user_sid`, `file_path`, `source_host`, `metadata`

## Версии

| Версия | Описание |
|--------|----------|
| v1.0.0 | Базовый функционал (обнаружение + классификация + каталог) |
| v2.0.0 | Управление доступом + Аудит Windows (ядро) |
| v2.0.1 | Windows-стек полностью готов |
| v2.1.0 | Linux-агент + унифицированный формат + WebUI фильтр |
| v3.0.0 | Унификация Manager и WebUI: WebUI — Jinja2 + прокси API на Manager, конфиги портов, run_all.py |
| v3.1.0 | Гибридная аутентификация (JWT+Bcrypt/SPNEGO) + роли; S3/MinIO агент аудита (polling, буфер, heartbeat, JWT); Windows + Linux аудит |
| v3.2.0 | Безопасность: mTLS (relaxed/strict), CertificateManager, SecretsManager, CRL, generate_certs.py/rotate_certs.py |
| v3.3.0 | Архивация данных: retention, политики хранения, экспорт JSON/CSV, WebUI настройки хранения |
| v3.4.0 | Интеграция Secret Scanner (FP-фильтры, префильтр, буферизация, расширенные типы, лог-отчёт) |
| v3.5.0 | Масштабирование: PostgreSQL + Alembic, партиционирование audit_logs, Redis (кэш/брокер/rate-limit), Celery worker/beat + Flower, docker-compose полный стек |
| v3.6.0 | Контейнеризация и деплой: multi-stage Dockerfile для Manager/WebUI/S3/Linux-агент, .dockerignore, docker-compose полный стек + prod overrides, скрипты deploy/stop/logs/status/healthcheck, docs/deployment.md |
| v3.6.1 (день 38.5) | Scanner в Docker: scanner/Dockerfile (multi-stage, Tesseract + spaCy + Presidio), profile `scanner` в compose, монтирование SCAN_PATH:/scanned:ro, лимиты CPU/RAM в prod-override |
| v3.6.2 (день 38.5+) | Scanner возвращён на хост (Docker-контейнер не может динамически монтировать папки из заданий): `python run_scanner.py scanner/config/scanner_config.json`, фикс сохранения `failed_files.error_type` (500 при отправке результатов) |
| v3.7.0 (день 39) | Мониторинг: heartbeat-тред сканера (не "inactive" при длинных заданиях), прогресс заданий из heartbeat (`scan_tasks.progress`), метрики Manager (HTTP/tasks/findings/celery) и агентов, Prometheus + Grafana (provisioning) + Alertmanager + экспортеры (celery/postgres/redis), docs/monitoring.md, scripts/monitoring-status.sh |

## Требования

- Python 3.8+
- Windows: wevtutil (встроен), права администратора для аудита
- Linux: watchdog, optional: paramiko (SSH-мониторинг)
- Production: Docker (PostgreSQL 16, Redis 7)
