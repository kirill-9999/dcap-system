"""День 39: колонка scan_tasks.progress (JSON) — прогресс заданий из heartbeat.

Revision ID: 002_scanner_progress
Revises: 001_initial_postgres
Create Date: 2026-09-11

Добавляет scan_tasks.progress (files_scanned, total, percent), который
HeartbeatThread сканера передаёт в POST /api/scanner/heartbeat.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "002_scanner_progress"
down_revision = "001_initial_postgres"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    """Колонка уже существует (001 создаёт scan_tasks из текущих моделей)."""
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "scan_tasks", "progress"):
        op.add_column("scan_tasks", sa.Column("progress", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "scan_tasks", "progress"):
        op.drop_column("scan_tasks", "progress")