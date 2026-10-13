"""Add ON DELETE CASCADE to foreign keys referencing resources and scan_tasks

Revision ID: 007_add_cascade_deletes
Revises: 006_add_source_type
Create Date: 2026-10-12

BUG-150 (v3.13.41): DELETE /api/resources/{id} падал с 500
sqlalchemy.exc.IntegrityError: failed_files_task_id_fkey — 9+ FK с
NO ACTION не позволяли удалить ресурс/задание. Миграция пересоздаёт FK
с ondelete='CASCADE': при удалении ресурса/задания каскадно удаляются
findings, scan_tasks, catalog_entries, access_entries, access_alerts,
permission_changes, failed_files, schedules.

НЕ трогаются: audit_logs (партиционированная), findings_old (legacy),
findings.reviewed_by (FK -> users.id), scan_tasks.scanner_id (-> scanners.id).

Внимание: имена constraint'ов НЕ захардкожены — реальные имена в БД могут
иметь суффикс '1' (findings_resource_id_fkey1, findings_task_id_fkey1 —
пересоздание FK в 003_findings_refactor). Имя FK ищется по
(table, column, referred_table) в pg_constraint — надёжно для свежих БД
(001_initial_postgres) и мигрированных.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_add_cascade_deletes"
down_revision = "006_add_source_type"
branch_labels = None
depends_on = None

# (table, column, referred_table) — все FK, которым нужен ON DELETE CASCADE.
# ref_col всегда 'id'.
CASCADE_FKS = [
    ("findings", "resource_id", "resources"),
    ("findings", "task_id", "scan_tasks"),
    ("scan_tasks", "resource_id", "resources"),
    ("catalog_entries", "resource_id", "resources"),
    ("catalog_entries", "task_id", "scan_tasks"),
    ("access_entries", "resource_id", "resources"),
    ("access_alerts", "resource_id", "resources"),
    ("permission_changes", "resource_id", "resources"),
    ("failed_files", "task_id", "scan_tasks"),
    ("failed_files", "resource_id", "resources"),
    ("schedules", "resource_id", "resources"),
]


def _fk_names(bind, table: str, column: str, referred_table: str) -> list:
    """Имена FK по (table, column, referred_table)."""
    inspector = sa.inspect(bind)
    try:
        tables = inspector.get_table_names()
    except Exception:  # noqa: BLE001 — таблица может отсутствовать
        return []
    if table not in tables:
        return []
    names = []
    try:
        fks = inspector.get_foreign_keys(table)
    except Exception:  # noqa: BLE001
        return []
    for fk in fks:
        cols = fk.get("constrained_columns") or []
        ref = fk.get("referred_table") or ""
        if column in cols and ref == referred_table and fk.get("name"):
            names.append(fk["name"])
    return names


def _retarget(table: str, column: str, referred_table: str, ondelete) -> None:
    """Пересоздать FK с ondelete (CASCADE / None)."""
    bind = op.get_bind()
    for name in _fk_names(bind, table, column, referred_table):
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, referred_table, [column], ["id"], ondelete=ondelete
        )


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite dev-режим: внешние ключи не проверяются, каскад не нужен.
        return
    for table, column, referred_table in CASCADE_FKS:
        _retarget(table, column, referred_table, "CASCADE")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column, referred_table in reversed(CASCADE_FKS):
        _retarget(table, column, referred_table, None)