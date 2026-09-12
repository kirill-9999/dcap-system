"""День 40.1: Findings refactor — строка/фрагмент + шифрование + fingerprint.

Revision ID: 003_findings_refactor
Revises: 002_scanner_progress
Create Date: 2026-09-12

Заменяет таблицу findings (находка = файл) на находку = строку/фрагмент:
- гибридное хранение (masked + encrypted AES-256-GCM),
- HMAC-SHA256 fingerprint (дедупликация),
- статусы new/confirmed/false_positive/archived.

Старые данные переносятся как «одна находка на файл» (legacy fingerprint),
старая таблица сохраняется как findings_old для отката.

Для SQLite (dev): упрощённая миграция — создание новой таблицы;
перенос данных не выполняется (dev-БД), находки остаются в findings_old.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "003_findings_refactor"
down_revision = "002_scanner_progress"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    """Таблица существует в текущей БД."""
    return name in inspect(bind).get_table_names()


def _column_exists(bind, table: str, column: str) -> bool:
    """Колонка уже существует (для идемпотентности)."""
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def _create_new_findings_table() -> None:
    """Создаёт новую таблицу findings (схема refactor)."""
    op.create_table(
        "findings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("resource_id", sa.Integer, sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("scan_tasks.id"), nullable=True),

        # Классификация
        sa.Column("finding_type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium"),

        # Где найдено
        sa.Column("fragment_type", sa.String(20), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=True),
        sa.Column("line_text_masked", sa.Text, nullable=True),
        sa.Column("line_text_encrypted", sa.Text, nullable=True),
        sa.Column("match_text_masked", sa.Text, nullable=True),
        sa.Column("match_text_encrypted", sa.Text, nullable=True),
        sa.Column("context_before_masked", sa.Text, nullable=True),
        sa.Column("context_after_masked", sa.Text, nullable=True),

        # Не-текстовые
        sa.Column("fragment_path", sa.String(500), nullable=True),
        sa.Column("bounding_box", sa.JSON, nullable=True),
        sa.Column("byte_offset", sa.Integer, nullable=True),
        sa.Column("byte_length", sa.Integer, nullable=True),
        sa.Column("hex_preview", sa.Text, nullable=True),

        # Дедупликация
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("encryption_key_id", sa.String(50), nullable=False),

        # Время
        sa.Column("first_seen_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime, server_default=sa.func.now()),

        # Статус
        sa.Column("status", sa.String(20), server_default="new"),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),

        # Метаданные
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("detector", sa.String(50), nullable=True),
    )

    op.create_index("ix_findings_resource_id", "findings", ["resource_id"])
    op.create_index("ix_findings_task_id", "findings", ["task_id"])
    op.create_index("ix_findings_finding_type", "findings", ["finding_type"])
    op.create_index("ix_findings_category", "findings", ["category"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_resource_status", "findings", ["resource_id", "status"])
    op.create_index("ix_findings_type_category", "findings", ["finding_type", "category"])
    op.create_index("ix_findings_status_first_seen", "findings", ["status", "first_seen_at"])


def _migrate_legacy_data(bind) -> None:
    """Переносит данные из findings_old в новую findings (PostgreSQL)."""
    op.execute(
        """
        INSERT INTO findings (
            resource_id, task_id, finding_type, category, severity,
            fragment_type, fragment_path, line_number,
            fingerprint, encryption_key_id,
            first_seen_at, last_seen_at, status, detector,
            confidence
        )
        SELECT
            resource_id, task_id,
            COALESCE(category, 'unknown'),
            COALESCE(subcategory, 'unknown'),
            'medium',
            'text_line',
            file_path,
            COALESCE(line_number, 0),
            md5(random()::text || resource_id::text),
            'legacy',
            COALESCE(created_at, NOW()),
            COALESCE(created_at, NOW()),
            'new',
            'legacy',
            confidence
        FROM findings_old
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Идемпотентность: если новой схемы уже нет, но колонки refactor уже есть
    # (например, таблица создана через create_all) — ничего не делаем.
    if _table_exists(bind, "findings") and _column_exists(bind, "findings", "fingerprint"):
        return

    has_old = _table_exists(bind, "findings") and not _column_exists(
        bind, "findings", "fingerprint"
    )

    if has_old:
        op.rename_table("findings", "findings_old")

    _create_new_findings_table()

    # Перенос данных — только PostgreSQL. SQLite (dev): не переносим
    # (старые данные остаются в findings_old для ручного разбора).
    if has_old and dialect == "postgresql":
        _migrate_legacy_data(bind)


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, "findings", "fingerprint"):
        op.drop_index("ix_findings_status_first_seen", "findings")
        op.drop_index("ix_findings_type_category", "findings")
        op.drop_index("ix_findings_resource_status", "findings")
        op.drop_index("ix_findings_status", "findings")
        op.drop_index("ix_findings_fingerprint", "findings")
        op.drop_index("ix_findings_category", "findings")
        op.drop_index("ix_findings_finding_type", "findings")
        op.drop_index("ix_findings_task_id", "findings")
        op.drop_index("ix_findings_resource_id", "findings")
        op.drop_table("findings")

    if _table_exists(bind, "findings_old"):
        op.rename_table("findings_old", "findings")