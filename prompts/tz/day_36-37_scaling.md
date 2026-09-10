📋 ТЗ — ДЕНЬ 36-37: МАСШТАБИРОВАНИЕ (POSTGRESQL + REDIS + CELERY)
Файл: prompts/tz/day_36-37_scaling.md
Дата: 09.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Подготовить DCAP к промышленной нагрузке через масштабирование:

PostgreSQL — миграция с SQLite, партиционирование, индексы, пул соединений

Redis — кэширование (сессии, права доступа, AD), rate limiting, брокер для Celery

Celery — очередь задач (аудит, сканирование, архивация, отчеты)

Docker Compose — единый стек для production

Миграция данных — перенос существующих данных из SQLite в PostgreSQL

📁 СТРУКТУРА ИЗМЕНЕНИЙ
text
manager/src/
├── db/
│   ├── session.py           # ОБНОВЛЕН: поддержка PostgreSQL
│   ├── models.py            # ОБНОВЛЕН: + партицирование
│   └── migrations/          # НОВЫЙ: Alembic миграции
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 001_initial_postgres.py
├── cache/
│   └── redis_client.py      # НОВЫЙ: Redis клиент (кэш, сессии, rate limit)
├── workers/
│   ├── celery_app.py        # НОВЫЙ: Celery приложение
│   ├── tasks.py             # НОВЫЙ: все задачи (аудит, сканирование, архивация)
│   └── beat_schedule.py     # НОВЫЙ: расписание периодических задач
├── core/
│   └── rate_limit.py        # НОВЫЙ: Rate limiting через Redis
└── config/
    └── config.json          # ОБНОВЛЕН: + DATABASE_URL, REDIS_URL

scripts/
└── migrate_sqlite_to_postgres.py  # НОВЫЙ: миграция данных

docker-compose.yml           # ОБНОВЛЕН: + postgres, redis, celery
.env.example                 # ОБНОВЛЕН: + DATABASE_URL, REDIS_URL
requirements.txt             # ОБНОВЛЕН: + asyncpg, psycopg2-binary, redis, celery
🗄️ 1. POSTGRESQL
1.1. docker-compose.yml — PostgreSQL
yaml
# docker-compose.yml (дополнение)

services:
  postgres:
    image: postgres:16-alpine
    container_name: dcap-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-dcap}
      POSTGRES_USER: ${POSTGRES_USER:-dcap}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dcap123}
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-dcap}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dcap-network
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
1.2. Модели с партиционированием
python
# manager/src/db/models.py (дополнение)

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index, BigInteger

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        # Партиционирование по месяцам
        {
            "postgresql_partition_by": "RANGE (created_at)",
        }
    )
    
    id = Column(BigInteger, primary_key=True)
    agent_id = Column(Integer, ForeignKey("audit_agents.id"), index=True)
    event_type = Column(String(50), nullable=False)
    event_source = Column(String(50), nullable=False)
    user = Column(String(200))
    user_sid = Column(String(100))
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500))
    source_host = Column(String(100))
    metadata = Column(JSONB)  # JSONB для индексации
    created_at = Column(DateTime, nullable=False, index=True)
    
    # Индексы для поиска
    __table_args__ = (
        Index("idx_audit_source_created", "event_source", "created_at"),
        Index("idx_audit_file_path", "file_path", postgresql_ops={"file_path": "gin_trgm_ops"}),
    )

# Функция для создания партиций
def create_monthly_partition(db, year: int, month: int):
    """Создание партиции для указанного месяца"""
    partition_name = f"audit_logs_{year}_{month:02d}"
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF audit_logs
        FOR VALUES FROM ('{start_date}') TO ('{end_date}')
    """)
1.3. session.py — PostgreSQL подключение
python
# manager/src/db/session.py (ОБНОВЛЕННЫЙ)

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://dcap:dcap123@localhost:5432/dcap"
)

# Создание engine с пулом соединений
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Session:
    """Получение сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Инициализация БД (создание таблиц)"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")

def get_pool_stats():
    """Статистика пула соединений"""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "overflow": pool.overflow(),
        "total": pool.total()
    }
1.4. Alembic миграции
python
# manager/src/db/migrations/env.py

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

from manager.src.db.models import Base
from manager.src.auth.models import Base as AuthBase

target_metadata = [Base.metadata, AuthBase.metadata]

def run_migrations_offline():
    url = os.environ.get("DATABASE_URL")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
1.5. Миграция данных из SQLite
python
# scripts/migrate_sqlite_to_postgres.py

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLITE_PATH = os.environ.get("SQLITE_PATH", "dcap.db")
POSTGRES_URL = os.environ.get("DATABASE_URL")

def migrate():
    """Миграция данных из SQLite в PostgreSQL"""
    
    logger.info("Starting migration from SQLite to PostgreSQL...")
    
    # 1. Подключение к SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    
    # 2. Подключение к PostgreSQL
    pg_conn = psycopg2.connect(POSTGRES_URL)
    cur = pg_conn.cursor()
    
    # 3. Список таблиц для миграции (в порядке зависимостей)
    tables = [
        ("roles", "SELECT * FROM roles ORDER BY id"),
        ("users", "SELECT * FROM users ORDER BY id"),
        ("user_roles", "SELECT * FROM user_roles ORDER BY user_id"),
        ("audit_agents", "SELECT * FROM audit_agents ORDER BY id"),
        ("resources", "SELECT * FROM resources ORDER BY id"),
        ("access_entries", "SELECT * FROM access_entries ORDER BY id"),
        ("audit_logs", "SELECT * FROM audit_logs ORDER BY created_at"),
        ("findings", "SELECT * FROM findings ORDER BY id"),
        ("scan_tasks", "SELECT * FROM scan_tasks ORDER BY id"),
        ("catalog_entries", "SELECT * FROM catalog_entries ORDER BY id"),
    ]
    
    total_migrated = 0
    
    for table_name, query in tables:
        logger.info(f"Migrating {table_name}...")
        
        rows = sqlite_conn.execute(query).fetchall()
        if not rows:
            logger.info(f"  No rows in {table_name}")
            continue
        
        # Получение колонок
        columns = [desc[0] for desc in sqlite_conn.execute(f"PRAGMA table_info({table_name})")]
        placeholders = ",".join(["%s"] * len(columns))
        
        # Подготовка данных
        data = []
        for row in rows:
            data.append([row[col] for col in columns])
        
        # Пакетная вставка
        batch_size = 1000
        for i in tqdm(range(0, len(data), batch_size), desc=f"  Migrating {table_name}"):
            batch = data[i:i+batch_size]
            execute_values(
                cur,
                f"INSERT INTO {table_name} ({','.join(columns)}) VALUES %s",
                batch
            )
            pg_conn.commit()
            total_migrated += len(batch)
        
        logger.info(f"  Migrated {len(data)} rows")
    
    sqlite_conn.close()
    pg_conn.close()
    
    logger.info(f"Migration complete! Total rows migrated: {total_migrated}")

if __name__ == "__main__":
    migrate()
🔴 2. REDIS
2.1. docker-compose.yml — Redis
yaml
# docker-compose.yml (дополнение)

services:
  redis:
    image: redis:7-alpine
    container_name: dcap-redis
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis123} --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dcap-network
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
2.2. Redis клиент
python
# manager/src/cache/redis_client.py

import redis
import json
import logging
from typing import Optional, Any, Dict, List
from datetime import timedelta

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis клиент для кэширования, сессий, rate limiting"""
    
    def __init__(self, redis_url: str):
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._test_connection()
    
    def _test_connection(self):
        """Проверка подключения"""
        try:
            self.redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    # ===== КЭШИРОВАНИЕ =====
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.debug(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Сохранение в кэш с TTL (сек)"""
        try:
            self.redis.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    def delete(self, key: str):
        """Удаление из кэша"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def invalidate_pattern(self, pattern: str):
        """Инвалидация по шаблону"""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis invalidate_pattern error: {e}")
            return False
    
    # ===== СЕССИИ =====
    
    def set_session(self, session_id: str, data: dict, ttl: int = 86400):
        """Сохранение сессии (TTL 24 часа)"""
        return self.set(f"session:{session_id}", data, ttl)
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Получение сессии"""
        return self.get(f"session:{session_id}")
    
    def delete_session(self, session_id: str):
        """Удаление сессии"""
        return self.delete(f"session:{session_id}")
    
    # ===== RATE LIMITING =====
    
    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """
        Проверка rate limit (скользящее окно)
        key: идентификатор (ip, user_id)
        limit: максимальное количество запросов
        window: окно в секундах
        """
        try:
            current = self.redis.get(key)
            if current and int(current) >= limit:
                return False
            
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            pipe.execute()
            return True
            
        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            return True  # Пропускаем при ошибке (fail-open)
    
    # ===== ПРАВА ДОСТУПА (кэш) =====
    
    def cache_permissions(self, resource_path: str, entries: List[dict], ttl: int = 300):
        """Кэширование прав доступа"""
        return self.set(f"perms:{resource_path}", entries, ttl)
    
    def get_cached_permissions(self, resource_path: str) -> Optional[List[dict]]:
        """Получение кэшированных прав"""
        return self.get(f"perms:{resource_path}")
    
    # ===== AD КЭШ =====
    
    def cache_ad_user(self, sid: str, username: str, ttl: int = 3600):
        """Кэширование AD пользователя"""
        return self.set(f"ad:user:{sid}", username, ttl)
    
    def get_cached_ad_user(self, sid: str) -> Optional[str]:
        """Получение кэшированного AD пользователя"""
        return self.get(f"ad:user:{sid}")
    
    def cache_ad_groups(self, username: str, groups: List[str], ttl: int = 3600):
        """Кэширование AD групп"""
        return self.set(f"ad:groups:{username}", groups, ttl)
    
    def get_cached_ad_groups(self, username: str) -> Optional[List[str]]:
        """Получение кэшированных AD групп"""
        return self.get(f"ad:groups:{username}")
    
    # ===== СТАТИСТИКА =====
    
    def get_stats(self) -> dict:
        """Статистика Redis"""
        try:
            info = self.redis.info()
            return {
                "used_memory": info.get("used_memory_human", "0"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keys": self.redis.dbsize()
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {}
📦 3. CELERY
3.1. requirements.txt
txt
# requirements.txt (дополнение)
celery>=5.3.0
redis>=5.0.0
asyncpg>=0.29.0
psycopg2-binary>=2.9.0
3.2. celery_app.py
python
# manager/src/workers/celery_app.py

from celery import Celery
import os
import logging

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Создание Celery приложения
celery_app = Celery(
    "dcap",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "manager.src.workers.tasks",
        "manager.src.workers.beat_schedule"
    ]
)

# Конфигурация
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    task_queues={
        "audit_events": {"exchange": "audit", "routing_key": "audit.event"},
        "scanner_tasks": {"exchange": "scanner", "routing_key": "scanner.task"},
        "retention": {"exchange": "retention", "routing_key": "retention.task"},
        "reports": {"exchange": "reports", "routing_key": "report.generate"},
        "maintenance": {"exchange": "maintenance", "routing_key": "maintenance.task"},
    },
    task_default_queue="audit_events",
    result_expires=60 * 60 * 24,  # 24 часа
)

logger.info(f"Celery app initialized with broker: {REDIS_URL}")
3.3. tasks.py
python
# manager/src/workers/tasks.py

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from .celery_app import celery_app
from ..db.session import get_db
from ..db.models import AuditLog, AuditAgent, Finding, ScanTask
from ..cache.redis_client import RedisCache
from ..retention.runtime import run_retention
from ..core.secrets import get_secrets_manager

logger = logging.getLogger(__name__)

# ===== АУДИТ =====

@celery_app.task(queue="audit_events", bind=True, max_retries=3)
def process_audit_event(self, event_data: dict):
    """Асинхронная обработка аудит-события"""
    try:
        with next(get_db()) as db:
            # 1. Дедупликация (Redis)
            cache = RedisCache(os.environ.get("REDIS_URL"))
            event_id = f"audit:{event_data.get('event_source')}:{event_data.get('created_at')}:{event_data.get('file_path')}"
            if cache.get(event_id):
                logger.debug(f"Duplicate event: {event_id}")
                return
            
            # 2. Сохранение в БД
            log = AuditLog(**event_data)
            db.add(log)
            db.commit()
            
            # 3. Отметка в кэше (24 часа)
            cache.set(event_id, "processed", 86400)
            
            # 4. Обновление статистики агента
            if event_data.get("agent_id"):
                update_agent_stats.delay(event_data["agent_id"])
            
            logger.debug(f"Event processed: {event_id}")
            
    except Exception as e:
        logger.error(f"Error processing audit event: {e}")
        self.retry(exc=e, countdown=60)

@celery_app.task(queue="audit_events")
def update_agent_stats(agent_id: int):
    """Обновление статистики агента"""
    with next(get_db()) as db:
        agent = db.query(AuditAgent).filter(AuditAgent.id == agent_id).first()
        if agent:
            agent.events_sent += 1
            agent.last_event_at = datetime.utcnow()
            db.commit()

# ===== СКАНИРОВАНИЕ =====

@celery_app.task(queue="scanner_tasks", bind=True, max_retries=3)
def process_scan_task(self, task_id: int):
    """Обработка задачи сканирования"""
    with next(get_db()) as db:
        task = db.query(ScanTask).filter(ScanTask.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found")
            return
        
        # Обновление статуса
        task.status = "running"
        task.started_at = datetime.utcnow()
        db.commit()
        
        try:
            # Поиск доступного сканера
            scanner = db.query(Scanner).filter(
                Scanner.status == "online"
            ).first()
            
            if not scanner:
                task.status = "failed"
                task.error = "No online scanner available"
                db.commit()
                return
            
            task.scanner_id = scanner.id
            db.commit()
            
            # Отправка задания сканеру (через heartbeat)
            # (реализация через REST API)
            # ...
            
        except Exception as e:
            logger.error(f"Error processing scan task {task_id}: {e}")
            task.status = "failed"
            task.error = str(e)
            db.commit()
            self.retry(exc=e, countdown=60)

# ===== АРХИВАЦИЯ =====

@celery_app.task(queue="retention")
def run_retention_task(dry_run: bool = False):
    """Периодическая архивация данных"""
    logger.info(f"Running retention task (dry_run={dry_run})")
    return run_retention(dry_run)

# ===== ОТЧЕТЫ =====

@celery_app.task(queue="reports")
def generate_report(report_type: str, params: dict):
    """Генерация отчета"""
    logger.info(f"Generating report: {report_type}")
    # ... реализация ...

# ===== МАИНТЕНАНС =====

@celery_app.task(queue="maintenance")
def cleanup_expired_sessions():
    """Очистка истекших сессий"""
    cache = RedisCache(os.environ.get("REDIS_URL"))
    # ... реализация ...
3.4. beat_schedule.py
python
# manager/src/workers/beat_schedule.py

from celery.schedules import crontab
from .celery_app import celery_app
from ..config import config

# Настройка расписания из конфига
retention_interval = config.get("retention", {}).get("interval_hours", 24)

celery_app.conf.beat_schedule = {
    # Архивация
    "retention-task": {
        "task": "manager.src.workers.tasks.run_retention_task",
        "schedule": retention_interval * 3600,  # в секундах
        "args": (False,),
    },
    # Очистка сессий
    "cleanup-sessions": {
        "task": "manager.src.workers.tasks.cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=0),  # каждую ночь в 3:00
    },
    # Обновление статусов агентов
    "update-agent-statuses": {
        "task": "manager.src.workers.tasks.update_agent_statuses",
        "schedule": 60,  # каждую минуту
    },
}

logger.info("Beat schedule configured")
3.5. docker-compose.yml — Celery
yaml
# docker-compose.yml (дополнение)

services:
  celery_worker:
    build:
      context: ./manager
      dockerfile: Dockerfile
    container_name: dcap-celery-worker
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-dcap}:${POSTGRES_PASSWORD:-dcap123}@postgres:5432/${POSTGRES_DB:-dcap}
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    volumes:
      - ./manager/certs:/app/certs:ro
      - ./manager/logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A manager.src.workers.celery_app worker -Q audit_events,scanner_tasks,retention,reports,maintenance -c 4 --loglevel=info
    networks:
      - dcap-network
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  celery_beat:
    build:
      context: ./manager
      dockerfile: Dockerfile
    container_name: dcap-celery-beat
    environment:
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      - redis
    command: celery -A manager.src.workers.celery_app beat --loglevel=info
    networks:
      - dcap-network
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  celery_flower:
    image: mher/flower:latest
    container_name: dcap-celery-flower
    environment:
      CELERY_BROKER_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      FLOWER_PORT: 5555
    ports:
      - "${FLOWER_PORT:-5555}:5555"
    depends_on:
      - redis
    networks:
      - dcap-network
    restart: unless-stopped
🔧 4. ОБНОВЛЕНИЕ MANAGER
4.1. main.py — интеграция
python
# manager/src/main.py (ОБНОВЛЕННЫЙ)

from .workers.celery_app import celery_app
from .cache.redis_client import RedisCache
from .core.rate_limit import RateLimiter

app = FastAPI(title="DCAP Manager", version="3.0.0")

# Инициализация Redis
redis_cache = RedisCache(os.environ.get("REDIS_URL"))

# Инициализация Rate Limiter
rate_limiter = RateLimiter(redis_cache)

# Добавление rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    if not rate_limiter.check(client_ip, limit=100, window=60):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"}
        )
    return await call_next(request)
4.2. Rate Limiter
python
# manager/src/core/rate_limit.py

from ..cache.redis_client import RedisCache

class RateLimiter:
    """Rate limiting через Redis"""
    
    def __init__(self, cache: RedisCache):
        self.cache = cache
    
    def check(self, key: str, limit: int = 100, window: int = 60) -> bool:
        """Проверка лимита (по умолчанию 100 запросов в минуту)"""
        return self.cache.check_rate_limit(
            f"ratelimit:{key}",
            limit,
            window
        )
✅ КРИТЕРИИ ПРИЕМКИ
PostgreSQL
□ PostgreSQL запускается в Docker
□ Миграция данных из SQLite работает
□ Партиционирование AuditLog по месяцам
□ Индексы созданы
□ Пул соединений работает
Redis
□ Redis запускается в Docker
□ Кэширование прав доступа
□ Кэширование AD пользователей
□ Rate limiting
□ Сессии
Celery
□ Celery worker запускается
□ Celery beat запускается
□ Задачи обработки аудита работают
□ Задачи архивации работают
□ Flower для мониторинга
Документация
□ AGENTS.md обновлена
□ README.md обновлена
□ project_plan.md обновлен
□ project_context.md обновлен
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запуск стека
docker-compose up -d

# 2. Миграция данных
python scripts/migrate_sqlite_to_postgres.py

# 3. Проверка подключения
python -c "from manager.src.db.session import get_db; next(get_db()).execute('SELECT 1')"

# 4. Проверка Redis
python -c "from manager.src.cache.redis_client import RedisCache; c=RedisCache('redis://localhost:6379/0'); print(c.redis.ping())"

# 5. Проверка Celery
celery -A manager.src.workers.celery_app worker --loglevel=info

# 6. Отправка тестовой задачи
python -c "from manager.src.workers.tasks import process_audit_event; process_audit_event.delay({'test': 'data'})"

# 7. Проверка Flower
open http://localhost:5555
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_36-37_scaling
git add .
git commit -m "feat: День 36-37 — Масштабирование (PostgreSQL, Redis, Celery)

PostgreSQL:
- Docker контейнер с PostgreSQL 16
- Миграция данных из SQLite (скрипт migrate_sqlite_to_postgres.py)
- Партиционирование AuditLog по месяцам
- Индексы для поиска
- Пул соединений (10+20)

Redis:
- Docker контейнер с Redis 7
- Кэширование (права доступа, AD, сессии)
- Rate limiting (скользящее окно)
- Брокер для Celery

Celery:
- Celery приложение (manager/src/workers/)
- Задачи: аудит, сканирование, архивация, отчеты
- Beat расписание (архивация, очистка сессий)
- Flower мониторинг (:5555)

Docker Compose:
- Полный стек: postgres, redis, manager, celery_worker, celery_beat, celery_flower, webui
- Healthchecks для всех сервисов
- Volumes для персистентности"
