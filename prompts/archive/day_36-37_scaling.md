📋 ТЗ — ДЕНЬ 36-37: МАСШТАБИРОВАНИЕ (АДАПТИРОВАННОЕ)
Файл: prompts/tz/day_36-37_scaling.md
Дата: 10.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
PostgreSQL — миграция с SQLite, партиционирование, Alembic

Redis — кэширование, rate limiting, брокер

Celery — внедрение с нуля, замена фоновых потоков

Docker Compose — единый production-стек

Миграция данных — SQLite → PostgreSQL

📁 КЛЮЧЕВЫЕ ФАЙЛЫ
Файл	Действие
manager/src/db/session.py	ОБНОВИТЬ: PostgreSQL + пул
manager/src/db/migrations/	СОЗДАТЬ: Alembic (env.py, versions/)
manager/src/cache/redis_client.py	СОЗДАТЬ
manager/src/workers/celery_app.py	СОЗДАТЬ
manager/src/workers/tasks.py	СОЗДАТЬ
manager/src/workers/beat_schedule.py	СОЗДАТЬ
manager/src/retention/scheduler.py	УДАЛИТЬ (замена на Celery Beat)
manager/src/main.py	ОБНОВИТЬ: убрать start_scheduler
scripts/migrate_sqlite_to_postgres.py	СОЗДАТЬ
docker-compose.yml	ОБНОВИТЬ: + postgres, redis, celery
requirements.txt	+ celery, redis, psycopg2-binary, alembic
alembic.ini	СОЗДАТЬ
🔧 ЭТАП 1: POSTGRESQL
1.1. docker-compose.yml
yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-dcap}
      POSTGRES_USER: ${POSTGRES_USER:-dcap}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dcap123}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dcap"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dcap-network
1.2. session.py (обновление)
python
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://dcap:dcap123@localhost:5432/dcap")

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
1.3. Alembic
bash
alembic init manager/src/db/migrations
alembic revision --autogenerate -m "initial"
alembic upgrade head
1.4. Миграция данных
Скрипт scripts/migrate_sqlite_to_postgres.py — перенос всех таблиц (audit_logs, findings, users, roles, resources, access_entries, catalog_entries, scan_tasks, audit_logs_archive, findings_archive).

🔴 ЭТАП 2: REDIS
2.1. docker-compose.yml
yaml
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis123} --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
2.2. redis_client.py
python
class RedisCache:
    def __init__(self, redis_url: str):
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
    
    # Кэш
    def get(self, key, default=None): ...
    def set(self, key, value, ttl=300): ...
    
    # Rate limiting
    def check_rate_limit(self, key, limit=100, window=60): ...
    
    # Сессии
    def set_session(self, session_id, data): ...
📦 ЭТАП 3: CELERY (С НУЛЯ)
3.1. celery_app.py
python
from celery import Celery

celery_app = Celery(
    "dcap",
    broker=os.environ.get("REDIS_URL"),
    backend=os.environ.get("REDIS_URL"),
    include=["manager.src.workers.tasks", "manager.src.workers.beat_schedule"]
)

celery_app.conf.update(
    task_serializer="json",
    timezone="UTC",
    task_queues={
        "audit_events": {"exchange": "audit"},
        "scanner_tasks": {"exchange": "scanner"},
        "retention": {"exchange": "retention"},
        "reports": {"exchange": "reports"},
    }
)
3.2. tasks.py
python
@celery_app.task(queue="audit_events")
def process_audit_event(event_data: dict):
    """Асинхронная обработка аудита"""
    ...

@celery_app.task(queue="retention")
def run_retention_task(dry_run: bool = False):
    """Архивация (замена фонового потока)"""
    return run_retention(dry_run)
3.3. beat_schedule.py
python
celery_app.conf.beat_schedule = {
    "retention-task": {
        "task": "manager.src.workers.tasks.run_retention_task",
        "schedule": 24 * 3600,  # каждые 24 часа
    },
    "cleanup-sessions": {
        "task": "...cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=0),
    },
}
3.4. Удалить старый scheduler
python
# manager/src/retention/scheduler.py — УДАЛИТЬ
# manager/src/main.py — убрать start_scheduler()
🐳 ЭТАП 4: DOCKER COMPOSE (ПОЛНЫЙ СТЕК)
yaml
services:
  postgres: ...
  redis: ...
  manager: ...
  celery_worker:
    command: celery -A manager.src.workers.celery_app worker -Q audit_events,scanner_tasks,retention,reports -c 4
  celery_beat:
    command: celery -A manager.src.workers.celery_app beat
  celery_flower:
    image: mher/flower:latest
    ports: ["5555:5555"]
  webui: ...
✅ КРИТЕРИИ ПРИЕМКИ
PostgreSQL
□ PostgreSQL в Docker
□ Alembic миграции работают
□ Данные из SQLite мигрированы
□ Пул соединений
□ Партиционирование audit_logs (по месяцам)
Redis
□ Redis в Docker
□ Кэширование прав/AD/сессий
□ Rate limiting
□ Брокер для Celery
Celery
□ Celery worker запускается
□ Celery beat запускается
□ Retention переведён на Celery Beat
□ Старый scheduler.py удалён
□ Flower доступен на :5555
Docker Compose
□ Весь стек поднимается одной командой
□ Healthchecks работают
□ Volumes персистентны
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запуск стека
docker-compose up -d

# 2. Миграция
python scripts/migrate_sqlite_to_postgres.py

# 3. Alembic
alembic upgrade head

# 4. Проверка Celery
docker-compose logs celery_worker
docker-compose logs celery_beat

# 5. Flower
open http://localhost:5555

# 6. Проверка retention через Celery
docker-compose exec manager python -c "from manager.src.workers.tasks import run_retention_task; run_retention_task.delay()"
💾 КОММИТ
bash
git checkout -b feature/day_36-37_scaling
git commit -m "feat: День 36-37 — Масштабирование (PostgreSQL, Redis, Celery)

PostgreSQL:
- Docker контейнер PostgreSQL 16
- Alembic миграции (init + initial)
- Миграция данных из SQLite
- Пул соединений (10+20)
- Партиционирование audit_logs

Redis:
- Docker контейнер Redis 7
- RedisCache (кэш, сессии, rate limit)
- Брокер для Celery

Celery:
- Внедрение с нуля
- Задачи: audit_events, scanner_tasks, retention, reports
- Beat: retention, cleanup
- Замена фонового scheduler.py
- Flower :5555

Docker Compose:
- Полный стек
- Healthchecks
- Volumes"
📊 ОБНОВЛЕНИЕ ПЛАНА
День	Задача	Статус
36-37	Масштабирование (PostgreSQL, Redis, Celery)	🔄 В РАЗРАБОТКЕ
38	Контейнеризация и деплой	📋
39	Мониторинг (Prometheus/Grafana)	📋
40-41	Тестирование (E2E + Chaos)	📋
42	Публикация на GitHub	📋
43	Релиз v3.0.0	📋