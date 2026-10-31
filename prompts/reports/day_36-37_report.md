# Отчёт: Дни 36-37 — Масштабирование (PostgreSQL, Redis, Celery)

**Дата:** 10.09.2026
**ТЗ:** `prompts/tz/day_36-37_scaling.md`
**Роль:** Кодер
**Версия:** v3.5.0
**Ветка:** `feature/day_36-37_scaling`

---

## Резюме

Реализовано **масштабирование Manager** для production-нагрузки: PostgreSQL 16 + Alembic (партиционирование `audit_logs` по месяцам, архивные таблицы, миграция данных SQLite→PG), Redis (кэш/брокер/rate-limit, fail-open), Celery worker/beat + Flower (очерёдность `audit_events`/`scanner_tasks`/`retention`/`reports`), обновлённый полный docker-compose стек. Фоновый поток-планировщик дня 35 (`retention/scheduler.py`) **удалён** — периодическая архивация переведена на **Celery Beat**. Локальный запуск (SQLite, без брокера) сохранился: PostgreSQL и Celery задействуются только если доступны.

> **Ключевая архитектурная предпосылка (из AGENTS.md):** локальный флоу — `run_all.py`/`run_manager.py` на SQLite; docker/Postgres/Celery — production-стек. Поэтому код выдерживает **два режима одновременно**: dev (SQLite, No-op Redis, без Celery) и production (PG, Redis, Celery), не ломает существующий локальный запуск.

---

## Ключевые решения по коду

- **`session.py`** — URL БД по приоритету: `DATABASE_URL` (env) → `config.json database.url` → sqlite-дефолт. Для Postgres — пул (`pool_size=10`, `max_overflow=20`, `pool_pre_ping`, `pool_recycle=3600`) + `get_pool_stats()`; для SQLite — `check_same_thread=False`. `init_db()` вызывает `create_all` + партиционирование (только реально партиционированные таблицы).
- **Партиционирование `audit_logs`** — в модели только индекс `idx_audit_source_created (event_source, created_at)`; DDL `PARTITION BY RANGE (created_at)` оформлен в Alembic-миграции `001_initial_postgres` (PG-only). Хелперы `models.create_monthly_partition`/`ensure_audit_log_partitions` создают партиции на текущий месяц + 12 вперёд и **проверяют через `pg_partitioned_table`, что таблица действительно партиционированная** (иначе no-op). SQLite не затронут.
- **Alembic** — стандартная структура (`alembic.ini`, `migrations/env.py`, `script.py.mako`, `versions/`). URL в `env.py`: env → config → `sqlalchemy.url`. Миграция не выполняет `metadata.drop_for` — до `import manager.src.db.models` приходит `sys.path` корня репо.
- **Redis** (`cache/redis_client.py`) — redis-py, конфиг из секции `redis` (env-подстановки `${REDIS_URL:-...}`), **no-op/fail-open**: недоступность Redis → методы возвращают дефолт, Manager работает. `REDIS_ENABLED` учитывает строковые значения из config-резолвера (`"true"/"false"`).
- **Rate-limit** (`core/rate_limit.py`) — `RateLimitMiddleware` на все `/api/*` (кроме `/api/health`); Redis-счётчики (INCR+EXPIRE) либо in-memory fallback; при превышении — JSON 429.
- **Celery** (`workers/`) — `celery_app.py` (broker=Redis c паролем, `task_routes` на 4 очереди, `include=tasks`), `tasks.py` (10 задач: аудит, сканер, retention, отчёты), `beat_schedule.py` (retention 03:00, sweep сканера */2ч, ротация логов 03:30).
- **Удалён `retention/scheduler.py`** — `start_scheduler()` убран из `main.py`; `POST /api/retention/start` теперь ставит задачу `run_retention` в Celery (503, если брокер недоступен). `run_retention` по-прежнему вызывается синхронно из API `/run`.
- **docker-compose.yml** — полный стек одной командой: postgres (healthcheck) + redis (healthcheck, `--requirepass`) + manager + webui + celery_worker + celery_beat + celery_flower (:5555). Manager/worker получают `DATABASE_URL`/`REDIS_URL` от Postgres/Redis.

---

## Выполненная работа

### 1. PostgreSQL + Alembic

- **`manager/src/db/session.py`** (MODIFIED) — URL-resolver, пул для PG, `init_db()` с партиционированием, `get_pool_stats()`.
- **`manager/src/db/models.py`** (MODIFIED) — индекс `idx_audit_source_created` в `AuditLog`; функции `create_monthly_partition`/`ensure_audit_log_partitions`.
- **`alembic.ini`** (NEW), **`manager/src/db/migrations/env.py`** (NEW), **`script.py.mako`** (NEW), **`versions/001_initial_postgres.py`** (NEW) — начальная PG-схема + партиционирование + архивные таблицы.

### 2. Redis + Rate-limit

- **`manager/src/cache/redis_client.py`** (NEW) — `RedisClient` (get/set/json/increment, fail-open), `get_redis()` синглтон, `reset_redis_client()`.
- **`manager/src/core/rate_limit.py`** (NEW) — `RateLimiter` + `RateLimitMiddleware`.
- **`manager/src/main.py`** (MODIFIED) — регистрация `RateLimitMiddleware`; startup: `init_db` + проверка Redis (печать статуса) вместо `start_scheduler()`.
- **`manager/src/config.py` / `manager/config/config.json`** (MODIFIED) — дефолты/секция `redis` (url, password, enabled, cache_ttl, rate_limit).

### 3. Celery

- **`manager/src/workers/celery_app.py`**, **`tasks.py`**, **`beat_schedule.py`**, **`__init__.py`** (NEW) — 10 задач, 4 очереди, Beat-расписание.
- **`manager/src/api/retention.py`** (MODIFIED) — `/start` → Celery `.delay()` (503 при недоступном брокере); удалён импорт scheduler.
- **`manager/src/retention/scheduler.py`** (DELETED).

### 4. Конфигурация

- **`requirements.txt`** (MODIFIED) — + `celery`, `psycopg2-binary`, `alembic` (redis уже был).
- **`.env.example`** (MODIFIED) — `DATABASE_URL`, `REDIS_URL/PASSWORD/ENABLED`, `CELERY_WORKER_QUEUES`.
- **`docker-compose.yml`** (MODIFIED) — полный стек (см. выше).

### 5. Миграция данных

- **`scripts/migrate_sqlite_to_postgres.py`** (NEW) — перенос ВСЕХ таблиц (включая `audit_logs_archive`, `findings_archive`, auth `users/roles/user_roles`), порядок по зависимостям, `--reset`, FK отключены через `session_replication_role=replica`, нормализация типов (bool из SQLite int → PG bool, datetime → ISO).

### 6. Документация

- **`AGENTS.md`**, **`README.md`**, **`project_plan.md`**, **`project_context.md`** (MODIFIED) — версия v3.5.0, статус, разделы про PostgreSQL/Alembic/Redis/Celery/docker-compose.

---

## Тестирование

### Alembic (offline + реальный PG в Docker)

- `alembic upgrade head --sql` — корректный SQL для SQLite и PostgreSQL (партиционирование, архивные таблицы, индексы).
- Реальный запуск `alembic upgrade head` на `postgres:16-alpine` (порт 55432) — **успешно**: `audit_logs` = partitioned table, 4 месячные + default партиции, 23 таблицы.

### Oчёредь задач (Celery)

- `workers.celery_app` — broker `redis://localhost:6379/0`, 4 очереди, Beat: `retention-daily`, `scanner-sweep`, `log-rotation-daily`.
- `inspect registered`/статическая регистрация — 10 задач.
- E2E: работник с `--queues=...4...` + `.apply_async` retention-задачи → задача выполнена в worker'e (результат-dry-run), бэкенд Redis.

### Миграция данных

- Из `manager/dcap.db` в тестовый PG перенесены все непустые таблицы (roles=4, users=3, user_roles=3, resources=1, access_entries=1, audit_agents=4; 16 строк). Проверен `--reset`.

### Manager + Прovoдник через ORM (партиционированный audit_logs)

- INSERT/SELECT/DELETE через ORM в партиционированную таблицу — работает (строка попадает в месячную партицию).
- Manager стартовал с `DATABASE_URL` на PG и на SQLite — `/api/health` 200, Redis OK (или no-op), без ошибок.

### Проверка сборки

- `py_compile` всех изменённых модулей — OK.
- Импортируется `manager.src.main`, `manager.src.workers` (celery установлен в окружение: `celery 5.6.3`, `flower 2.1.0`).

---

## Файлы

**NEW:**
- `alembic.ini`
- `manager/src/db/migrations/env.py`
- `manager/src/db/migrations/script.py.mako`
- `manager/src/db/migrations/versions/001_initial_postgres.py`
- `manager/src/cache/__init__.py`, `manager/src/cache/redis_client.py`
- `manager/src/core/rate_limit.py`
- `manager/src/workers/__init__.py`, `celery_app.py`, `tasks.py`, `beat_schedule.py`
- `scripts/migrate_sqlite_to_postgres.py`
- `prompts/reports/day_36-37_report.md` (этот отчёт)

**Modified:**
- `manager/src/db/session.py`, `manager/src/db/models.py`
- `manager/src/main.py`, `manager/src/api/retention.py`
- `manager/src/config.py`, `manager/config/config.json`
- `requirements.txt`, `.env.example`, `docker-compose.yml`
- `AGENTS.md`, `README.md`, `project_plan.md`, `project_context.md`
- `prompts/tz/day_36-37_scaling.md` (адаптированное ТЗ)

**Deleted:**
- `manager/src/retention/scheduler.py`

---

## Запуск (ручное тестирование)

### Локальный (dev, без Docker)

```powershell
# установка зависимостей нового стека
python -m pip install -r requirements.txt

# запуск как раньше (SQLite + Redis если есть, otherwise no-op)
python init_db.py
python run_all.py          # Manager (:8000) + WebUI (:8001)
```

### Production-стек (PostgreSQL + Redis + Celery) — Docker

```powershell
docker compose up -d       # postgres + redis + manager + webui + worker + beat + flower
# Flower: http://localhost:5555
```

### Ручная подготовка PG (вне compose)

```powershell
$env:DATABASE_URL="postgresql://dcap:dcap123@localhost:5432/dcap"
alembic upgrade head                          # создание схемы + партиций
python scripts/migrate_sqlite_to_postgres.py  # перенос данных из SQLite
python run_manager.py                         # Manager на PG
```

### Celery вручную

```powershell
celery -A manager.src.workers.celery_app:app worker --queues=audit_events,scanner_tasks,retention,reports
celery -A manager.src.workers.celery_app:app beat
celery -A manager.src.workers.celery_app:app flower --port=5555
```

---

## Команда коммита

На ветке `feature/day_36-37_scaling`:

```powershell
git checkout -b feature/day_36-37_scaling
git add -A
git commit -m "feat: Дни 36-37 — Масштабирование (PostgreSQL, Redis, Celery)

- PostgreSQL 16 + Alembic: alembic.ini, migrations/env.py, 001_initial_postgres (партиционирование audit_logs по месяцам + default, архивные таблицы)
- session.py: пул для PG (10/20, pre_ping, recycle), get_pool_stats, SQLite-fallback
- Redis: cache/redis_client.py (fail-open), core/rate_limit.py + RateLimitMiddleware в main.py
- Celery: workers/ (celery_app, tasks — 10 задач, beat_schedule), очереди audit_events/scanner_tasks/retention/reports
- Удалён retention/scheduler.py; периодика — Celery Beat; POST /api/retention/start → .delay() (503 без брокера)
- scripts/migrate_sqlite_to_postgres.py: перенос всех таблиц (+архивы, auth) с нормализацией типов, --reset
- docker-compose: postgres+redis(healthcheck)+manager+webui+celery_worker/beat+flower(:5555) одной командой
- Конфиги: config.json и дефолты redis, env DATABASE_URL/REDIS_*, requirements (+celery, psycopg2-binary, alembic)
- Docs: AGENTS.md, README.md, project_plan.md, project_context.md (v3.5.0)"
```

---

## Обратная связь архитектору

- **Стек масштабирования полностью рабочий**: Alembic-миграция на реальном PG, партиционирование, миграция данных, Celery worker (очередь+бэкенд), ORM на партиционированной таблице.
- **Партиционирование `audit_logs`** требует составной PK `(created_at, id)` (правило PG: partition key входит в PK). Модель остаётся с одиночным `id` PK — этим гарантируется совместимость с SQLite; для PG партиции создаёт миграция. Autogenerate будет показывать diff PK для `audit_logs` — это ожидаемо и задокументировано в миграции.
- **`POST /api/retention/start`** переведён на Celery (как в ТЗ), при этом `/run?dry_run=` остался синхронным — для локального запуска без Celery.
- **Локальный запуск без Docker** не требует Celery/Postgres: Redis — fail-open, а sync-пути сохранены. В production worker'ы и Beat должны быть запущены (в compose — автоматически).
- **Сканер остаётся pull-based** (агент тянет задания через `/api/scanner/tasks/next`), поэтому Celery-задания по сканеру лишь помечают `ScanTask` и создают задачи по расписанию; реальное исполнение — на сканере.
- **Образ manager в compose** использует существующий `manager/Dockerfile` (день 34); полная пересборка Python-окружения с celery — на этапе контейнеризации (день 38), т.к. докеризация образов в проекте вторична (см. AGENTS.md).