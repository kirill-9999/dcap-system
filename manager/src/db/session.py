import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _default_sqlite_path() -> str:
    """Путь к файлу SQLite по умолчанию (manager/dcap.db)."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dcap.db"
    )


def _resolve_database_url() -> str:
    """Определение URL БД.

    Приоритет: env DATABASE_URL -> manager/config/config.json (database.url)
    -> sqlite:///manager/dcap.db.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        from manager.src.config import get_config

        url = get_config().get("database", {}).get("url")
        if url:
            return url
    except Exception:
        pass
    return f"sqlite:///{_default_sqlite_path()}"


def _normalize_url(url: str) -> str:
    """Явно фиксирует DBAPI-драйвер в схеме URL.

    Проект ставит psycopg2-binary (requirements.txt), но SQLAlchemy >= 2.1
    для голой схемы "postgresql://" по умолчанию пытается импортировать
    psycopg (v3) и падает с ModuleNotFoundError. Явная схема
    "postgresql+psycopg2://" работает одинаково во всех версиях
    SQLAlchemy 2.x. Явно указанные драйверы (+psycopg, +pg8000, ...)
    не трогаем.
    """
    if not url.startswith("postgresql://"):
        return url
    return "postgresql+psycopg2://" + url[len("postgresql://"):]


DATABASE_URL = _normalize_url(_resolve_database_url())

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

if _IS_SQLITE:
    # SQLite: только check_same_thread, пул не настраиваем.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Для SQLite
    )
else:
    # PostgreSQL: пул соединений (пул 10 + overflow 20).
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Генератор для получения сессии базы данных."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация базы данных (создание таблиц)."""
    from . import models

    # Импорт auth-моделей регистрирует users/roles/user_roles в Base.metadata
    from manager.src.auth import models as auth_models  # noqa: F401
    from manager.src.auth.models import User, Role  # noqa: F401

    models.Base.metadata.create_all(bind=engine)

    # Партиционирование audit_logs по месяцам (PostgreSQL) — создаём
    # партиции на текущий месяц + 12 вперёд.
    try:
        created = models.ensure_audit_log_partitions(engine, months_ahead=12)
        if created:
            import logging

            logging.getLogger(__name__).info(
                "Audit log partitions ensured: %s", created
            )
    except Exception:
        pass


def get_pool_stats() -> dict:
    """Статистика пула соединений (для PostgreSQL)."""
    pool = engine.pool
    stats = {}
    for attr in ("size", "checkedin", "overflow", "total"):
        method = getattr(pool, attr, None)
        if callable(method):
            try:
                stats[attr] = method()
            except Exception:
                stats[attr] = None
    return stats