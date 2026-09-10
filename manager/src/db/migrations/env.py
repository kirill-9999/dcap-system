"""Alembic env — миграции БД DCAP Manager.

URL берётся из env DATABASE_URL (приоритет) либо из config.json (database.url),
либо из sqlalchemy.url (alembic.ini). Metadata подтягивается из моделей Manager.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import create_engine

from alembic import context

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from manager.src.db.models import Base  # noqa: E402
from manager.src.auth.models import User, Role  # noqa: F401,E402  (регистрирует users/roles/user_roles)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        from manager.src.config import get_config

        cfg_url = get_config().get("database", {}).get("url")
        if cfg_url:
            return cfg_url
    except Exception:
        pass
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Запуск миграций в offline-режиме (SQL на stdout)."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в online-режиме."""
    url = _database_url()
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()