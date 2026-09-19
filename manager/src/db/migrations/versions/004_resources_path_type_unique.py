"""BUG-059: уникальность ресурсов (path, type) вместо (path).

Revision ID: 004_resources_path_type_unique
Revises: 003_findings_refactor
Create Date: 2026-09-19

Проблема: POST /api/tasks/create отправляет type='FILESYSTEM', БД хранит
'filesystem' — query по (type, path) не находил строку, INSERT падал с
UniqueViolation на resources_path_key (unique только по path). BUG-059.

Решение:
  1) Нормализация существующих значений resources.type в lowercase (все БД);
  2) PostgreSQL: замена уникальности `resources_path_key` (path) на
     `uq_resources_path_type` (path, type);
  3) SQLite (dev): индекс остаётся прежним (SQLite не умеет ALTER-констрейнты),
     проблема решена на уровне кода (нормализация type + fallback без type).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "004_resources_path_type_unique"
down_revision = "003_findings_refactor"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _index_exists(bind, table: str, index: str) -> bool:
    idx = [i["name"] for i in inspect(bind).get_indexes(table)]
    return index in idx


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _table_exists(bind, "resources"):
        return

    # 1. Нормализуем type в lowercase (иначе (path,type)-уникальность ломается
    #    на старых данных с 'FILESYSTEM').
    op.execute(
        sa.text(
            "UPDATE resources SET type = LOWER(type) "
            "WHERE type IS NOT NULL AND type <> LOWER(type)"
        )
    )

    if dialect != "postgresql":
        # SQLite: индекс по path остаётся (не могу дропнуть его через ALTER),
        # код уже нормализует type при создании. Возвращаемся.
        return

    # 2. PostgreSQL: дроп старого unique-индекса по path (если есть).
    if _index_exists(bind, "resources", "resources_path_key"):
        try:
            op.drop_constraint("resources_path_key", "resources", type_="unique")
        except Exception:  # noqa: BLE001
            op.execute(sa.text('DROP INDEX IF EXISTS "resources_path_key"'))

    # 3. Создаём уникальный индекс по (path, type), если его нет.
    if not _index_exists(bind, "resources", "uq_resources_path_type"):
        op.create_unique_constraint(
            "uq_resources_path_type", "resources", ["path", "type"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if not _table_exists(bind, "resources"):
        return
    try:
        op.drop_constraint("uq_resources_path_type", "resources", type_="unique")
    except Exception:  # noqa: BLE001
        op.execute(sa.text('DROP INDEX IF EXISTS "uq_resources_path_type"'))
    if not _index_exists(bind, "resources", "resources_path_key"):
        op.create_unique_constraint("resources_path_key", "resources", ["path"])