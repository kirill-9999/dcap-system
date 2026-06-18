# -*- coding: utf-8 -*-
"""
Database session management for SQLite (разработка)
"""

from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from manager.src.db.models import Base

# SQLite для разработки
DB_PATH = Path(__file__).parent / "dcap.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

print(f"[DB] Используется SQLite: {DB_PATH}")

# Создание engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # SQL логи в консоль (полезно для отладки)
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db() -> None:
    """Инициализация БД — создание таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"[DB] Инициализирована SQLite: {DB_PATH}")


async def close_db() -> None:
    """Закрытие соединения"""
    await engine.dispose()
    print("[DB] Соединение закрыто")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Получение сессии БД"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()