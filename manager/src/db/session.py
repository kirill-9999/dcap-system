from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os

# Создаем директорию для базы данных, если её нет
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dcap.db")
# Или используем относительный путь
# db_path = "dcap.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Для SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Генератор для получения сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Инициализация базы данных (создание таблиц)"""
    from . import models
    # Импорт auth-моделей регистрирует users/roles/user_roles в Base.metadata
    from manager.src.auth import models as auth_models  # noqa: F401
    from manager.src.auth.models import User, Role  # noqa: F401
    models.Base.metadata.create_all(bind=engine)