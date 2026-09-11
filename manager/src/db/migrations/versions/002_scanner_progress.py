"""День 39: колонка scan_tasks.progress (JSON) — прогресс заданий из heartbeat.

Revision ID: 002_scanner_progress
Revises: 001_initial_postgres
Create Date: 2026-09-11

Добавляет scan_tasks.progress (files_scanned, total, percent), который
HeartbeatThread сканера передаёт в POST /api/scanner/heartbeat.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002_scanner_progress"
down_revision = "001_initial_postgres"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column("scan_tasks", sa.Column("progress", sa.JSON(), nullable=True))
    else:
        # SQLite: SQLAlchemy 2.0 поддерживает ALTER TABLE ADD COLUMN.
        try:
            op.add_column("scan_tasks", sa.Column("progress", sa.JSON(), nullable=True))
        except Exception:
            pass  # колонка может уже существовать (create_all)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_column("scan_tasks", "progress")
    else:
        # SQLite ALTER TABLE DROP COLUMN поддерживается с 3.35; пробуем, иначе пропускаем.
        try:
            op.drop_column("scan_tasks", "progress")
        except Exception:
            pass