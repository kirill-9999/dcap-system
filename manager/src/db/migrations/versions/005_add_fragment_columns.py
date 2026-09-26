"""BACKLOG-086 (TASK-049): колонки встроенного фрагмента в findings.

Revision ID: 005_add_fragment_columns
Revises: 004_resources_path_type_unique
Create Date: 2026-09-26

Назначение: встраивание OCR-фрагментов (доказательная база) в findings.
Сканер (host) отправляет base64-фрагмент; Manager хранит байты прямо в БД,
чтобы доказательство переживало удаление/изменение исходного файла.

Колонки:
  fragment_data         LargeBinary  — декодированные байты PNG/JPEG
  fragment_mime         String(50)   — image/png, image/jpeg
  fragment_hash         String(64)   — SHA-256 целостности
  fragment_size         Integer      — размер в байтах
  fragment_embedded_at  DateTime     — когда встроен

Замечание: только image_region (OCR). text_line — данные в line_text_encrypted.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "005_add_fragment_columns"
down_revision = "004_resources_path_type_unique"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("fragment_data", sa.LargeBinary()),
    ("fragment_mime", sa.String(50)),
    ("fragment_hash", sa.String(64)),
    ("fragment_size", sa.Integer()),
    ("fragment_embedded_at", sa.DateTime()),
)


def _table_columns(bind, table: str):
    return set(c["name"] for c in inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "findings" not in tables:
        return
    existing = _table_columns(bind, "findings")
    for name, col in _COLUMNS:
        if name not in existing:
            op.add_column("findings", sa.Column(name, col, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "findings" not in tables:
        return
    existing = _table_columns(bind, "findings")
    for name, _col in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("findings", name)