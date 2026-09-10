"""День 36-37: начальная схема для PostgreSQL + партиционирование audit_logs.

Revision ID: 001_initial_postgres
Revises:
Create Date: 2026-09-10

Таблицы создаются через metadata (Manager + auth) с учётом партиционирования:
- audit_logs  — партиционированная по RANGE(created_at) (месячные партиции),
  с default-партицией; НЕ создаётся через metadata.create_all (партиционированная).
  Для PostgreSQL-схемы, создаваемой этой миграцией, обязательно применение
  Alembic ДО старта Manager (init_db.create_all пропускает уже существующие).
- Остальные таблицы (users, roles, resources, findings, archives и пр.) —
  создаются Alembic'ом автономно из metadata при наличии (иначе создаются
  Manager'ом через create_all на старте).
"""
import datetime

import sqlalchemy as sa
from alembic import op

from manager.src.db.models import Base

# revision identifiers, used by Alembic.
revision = "001_initial_postgres"
down_revision = None
branch_labels = None
depends_on = None


AUDIT_PARTITIONS_HEAD = 3  # текущий месяц + 3 вперёд


def _create_audit_partitioned_table(bind) -> None:
    """Создание партиционированной audit_logs (+ партиции) для PostgreSQL."""
    bind.execute(
        sa.text(
            """
            CREATE SEQUENCE IF NOT EXISTS audit_logs_id_seq
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE TABLE audit_logs (
                id BIGINT NOT NULL DEFAULT nextval('audit_logs_id_seq'),
                agent_id INTEGER,
                event_type VARCHAR(50) NOT NULL,
                event_source VARCHAR(50) NOT NULL,
                "user" VARCHAR(200),
                user_sid VARCHAR(100),
                file_path VARCHAR(500) NOT NULL,
                old_path VARCHAR(500),
                source_host VARCHAR(100),
                metadata JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                PRIMARY KEY (created_at, id)
            ) PARTITION BY RANGE (created_at)
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_source_created
            ON audit_logs (event_source, created_at)
            """
        )
    )
    bind.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs (created_at)"
        )
    )
    # default-партиция + месячные партиции
    bind.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS audit_logs_default PARTITION OF audit_logs DEFAULT"
        )
    )
    today = datetime.date.today()
    year, month = today.year, today.month
    for i in range(AUDIT_PARTITIONS_HEAD + 1):
        y = year + (month - 1 + i) // 12
        m = (month - 1 + i) % 12 + 1
        name = f"audit_logs_{y}_{m:02d}"
        start = f"{y}-{m:02d}-01"
        end_y, end_m = (y + 1, 1) if m == 12 else (y, m + 1)
        end = f"{end_y}-{end_m:02d}-01"
        bind.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS %(name)s PARTITION OF audit_logs "
                "FOR VALUES FROM ('%(start)s') TO ('%(end)s')"
                % {"name": name, "start": start, "end": end}
            )
        )


def _drop_audit_partitions(bind) -> None:
    """Удаление партиционированной audit_logs (включая партиции)."""
    rows = bind.execute(
        sa.text(
            "SELECT inhrelid::regclass AS name FROM pg_inherits "
            "WHERE inhparent = 'audit_logs'::regclass"
        )
    ).fetchall()
    for row in rows:
        bind.execute(sa.text(f'DROP TABLE IF EXISTS "{row.name}"'))
    bind.execute(sa.text("DROP TABLE IF EXISTS audit_logs"))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Партиционированный audit_logs создаём вручную; остальные таблицы —
        # через metadata (skip уже созданных Manager'ом таблиц не требуется:
        # эта миграция выполняется первой, но create_all уже мог создать
        # обычные таблицы при предыдущем старте — используем checkfirst).
        tables = list(Base.metadata.sorted_tables)
        # Создаём партиционированную audit_logs ДО metadata.create_all,
        # чтобы create_all её пропустил (проверка существования).
        _create_audit_partitioned_table(bind)
        # Остальные таблицы
        for table in tables:
            if table.name == "audit_logs":
                continue
            table.create(bind=bind, checkfirst=True)
    # Для не-PostgreSQL (SQLite) схема создаётся Manager'ом на старте (create_all).


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = list(reversed(Base.metadata.sorted_tables))
    for table in tables:
        if table.name == "audit_logs":
            continue
        table.drop(bind=bind, checkfirst=True)
    _drop_audit_partitions(bind)
    bind.execute(sa.text("DROP SEQUENCE IF EXISTS audit_logs_id_seq"))