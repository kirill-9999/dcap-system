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

- **Dockerfile** (multi-stage, непривилегированный пользователь, healthcheck): `manager/` (Manager + Celery worker/beat), `webui/`, `audit-agent-s3/`, `audit-agent-linux/`, `scanner/`; `.dockerignore` для каждого (build-контекст Manager/Scanner/S3 — корень репо; webui — `./webui`).
- **docker-compose.yml** — полный стек: postgres(5432) + redis(6379) + manager(8000) + webui(8001) + celery worker/beat + flower(5555). Агенты — profiles: `--profile agents` (S3) и `--profile scanner` (Scanner).
- **docker-compose.prod.yml** — production overrides (лимиты CPU/RAM, mTLS, репликация worker/scanner).
- **Скрипты**: `scripts/deploy.sh`, `stop.sh`, `logs.sh`, `status.sh`, `healthcheck.sh`.
- **Документация**: `docs/deployment.md`.

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

## Требования

- Python 3.8+
- Windows: wevtutil (встроен), права администратора для аудита
- Linux: watchdog, optional: paramiko (SSH-мониторинг)
- Production: Docker (PostgreSQL 16, Redis 7)
