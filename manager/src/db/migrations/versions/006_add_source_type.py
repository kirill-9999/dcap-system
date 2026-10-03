"""Scanner: колонка scan_tasks.source_type (filesystem | s3 | minio).

Revision ID: 006_add_source_type
Revises: 005_add_fragment_columns
Create Date: 2026-10-03

Назначение: явный тип источника в задании — сканер выбирает коннектор
по source_type, не угадывая по префиксу source_path ('s3://...').

Контекст (День 53.1a, BACKLOG-097): оживление S3-коннектора сканера.
  - filesystem — локальный/сетевой путь (как раньше);
  - s3         — s3://bucket[/prefix];
  - minio      — то же, что s3, но endpoint — MinIO.

Идемпотентность: на свежих БД 001_initial_postgres создаёт scan_tasks
из текущих моделей (models.py уже содержит source_type), поэтому колонка
может существовать — пропускаем add_column.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "006_add_source_type"
down_revision = "005_add_fragment_columns"
branch_labels = None
depends_on = None

_DEFAULT = "filesystem"


def _column_exists(bind, table: str, column: str) -> bool:
    try:
        cols = [c["name"] for c in inspect(bind).get_columns(table)]
    except Exception:
        return False
    return column in cols


def _index_exists(bind, table: str, index: str) -> bool:
    try:
        idx = [i["name"] for i in inspect(bind).get_indexes(table)]
    except Exception:
        return False
    return index in idx


def upgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "scan_tasks" not in tables:
        return

    if not _column_exists(bind, "scan_tasks", "source_type"):
        op.add_column(
            "scan_tasks",
            sa.Column(
                "source_type",
                sa.String(20),
                nullable=False,
                server_default=_DEFAULT,
            ),
        )

    if not _index_exists(bind, "scan_tasks", "ix_scan_tasks_source_type"):
        op.create_index(
            "ix_scan_tasks_source_type", "scan_tasks", ["source_type"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "scan_tasks" not in tables:
        return
    if _index_exists(bind, "scan_tasks", "ix_scan_tasks_source_type"):
        op.drop_index("ix_scan_tasks_source_type", "scan_tasks")
    if _column_exists(bind, "scan_tasks", "source_type"):
        op.drop_column("scan_tasks", "source_type")