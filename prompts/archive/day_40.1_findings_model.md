📋 ТЗ: День 40.1 — Findings Refactor: модель + шифрование + API
Дата: 12.09.2026
Роль: Кодер
Версия (целевая): v3.9.0
Ветка: feature/day_40.1_findings_model
Предыдущая версия: v3.8.0
Этап: 1 из 4 (Findings Refactor)

🎯 Цель дня
Подготовить фундамент для новой модели находок:

Модель Finding — строка/фрагмент вместо файла

Шифрование — AES-256-GCM + маскирование + HMAC-fingerprint

API находок — CRUD, reveal, bulk, stats, FP

Аудит расшифровок — каждая reveal логируется

Docker Secrets — ключи шифрования

ВАЖНО: сканер и WebUI ещё не трогаем — они продолжат слать старое. API должен принимать оба формата (backward compatibility) и новый формат (для Этапа 2).

📦 Часть 1. Модель данных
1.1. Модель Finding
MODIFIED: manager/src/db/models.py — заменить существующую модель Finding (или создать новую, если её нет).

python
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from manager.src.db.session import Base


class Finding(Base):
    """
    Находка = конкретное совпадение (строка/фрагмент), а не файл.

    Хранение: гибрид — маскированное (по умолчанию) + зашифрованное (AES-256-GCM).
    Расшифровка — только Auditor, с аудитом.
    """
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True)

    # Связи
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=True, index=True)

    # Классификация
    finding_type = Column(String(50), nullable=False, index=True)   # pii, credentials, code
    category = Column(String(100), nullable=False, index=True)      # phone, email, api_key
    severity = Column(String(20), default="medium")                 # low, medium, high, critical

    # Где найдено
    fragment_type = Column(String(20), nullable=False)
    # text_line | text_context | image_region | byte_range

    line_number = Column(Integer, nullable=True)
    line_text_masked = Column(Text, nullable=True)
    line_text_encrypted = Column(Text, nullable=True)
    match_text_masked = Column(Text, nullable=True)
    match_text_encrypted = Column(Text, nullable=True)
    context_before_masked = Column(Text, nullable=True)
    context_after_masked = Column(Text, nullable=True)

    # Не-текстовые
    fragment_path = Column(String(500), nullable=True)     # путь к вырезанному фрагменту
    bounding_box = Column(JSON, nullable=True)             # {x, y, width, height}
    byte_offset = Column(Integer, nullable=True)
    byte_length = Column(Integer, nullable=True)
    hex_preview = Column(Text, nullable=True)

    # Дедупликация
    fingerprint = Column(String(64), nullable=False, index=True)   # HMAC-SHA256
    encryption_key_id = Column(String(50), nullable=False)

    # Время
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    # Статус
    status = Column(String(20), default="new", index=True)
    # new | confirmed | false_positive | archived

    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    comment = Column(Text, nullable=True)

    # Метаданные
    confidence = Column(Float, nullable=True)
    detector = Column(String(50), nullable=True)           # presidio, regex, entropy, ocr

    # Связи (relationships)
    resource = relationship("Resource", backref="findings")
    task = relationship("ScanTask", backref="findings")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    # Индексы
    __table_args__ = (
        Index("ix_findings_resource_status", "resource_id", "status"),
        Index("ix_findings_type_category", "finding_type", "category"),
        Index("ix_findings_status_first_seen", "status", "first_seen_at"),
    )

    def __repr__(self):
        return f"<Finding(id={self.id}, type={self.finding_type}, category={self.category}, line={self.line_number})>"
Важно:

Если старая модель Finding существует — заменить (миграция перенесёт данные).

Если есть findings_archive — не трогать (архивная таблица, отдельная).

1.2. Alembic-миграция 003_findings_refactor
NEW: manager/src/db/migrations/versions/003_findings_refactor.py

python
"""Findings refactor: строка/фрагмент + шифрование + fingerprint

Revision ID: 003_findings_refactor
Revises: 002_scanner_progress
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_findings_refactor"
down_revision = "002_scanner_progress"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    # 1. Проверяем, есть ли старая таблица findings
    inspector = sa.inspect(conn)
    has_old = "findings" in inspector.get_table_names()

    if has_old:
        # 2. Переименовываем старую → findings_old
        op.rename_table("findings", "findings_old")

    # 3. Создаём новую таблицу
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

    # 4. Индексы
    op.create_index("ix_findings_resource_id", "findings", ["resource_id"])
    op.create_index("ix_findings_task_id", "findings", ["task_id"])
    op.create_index("ix_findings_finding_type", "findings", ["finding_type"])
    op.create_index("ix_findings_category", "findings", ["category"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_resource_status", "findings", ["resource_id", "status"])
    op.create_index("ix_findings_type_category", "findings", ["finding_type", "category"])
    op.create_index("ix_findings_status_first_seen", "findings", ["status", "first_seen_at"])

    # 5. Миграция данных из старой таблицы (если есть)
    if has_old:
        # Старая модель: находка = файл. Переносим как одну находку на файл.
        # fingerprint = HMAC от resource_id + "legacy" + type + category
        # (после первого скана в Этапе 2 — заменятся на реальные)
        op.execute("""
            INSERT INTO findings (
                resource_id, task_id, finding_type, category, severity,
                fragment_type, fingerprint, encryption_key_id,
                first_seen_at, last_seen_at, status, detector
            )
            SELECT
                resource_id, task_id,
                COALESCE(finding_type, 'unknown'),
                COALESCE(category, 'unknown'),
                COALESCE(severity, 'medium'),
                'text_line',
                COALESCE(fingerprint, md5(random()::text || resource_id::text)),
                'legacy',
                COALESCE(first_seen_at, NOW()),
                COALESCE(last_seen_at, NOW()),
                COALESCE(status, 'new'),
                'legacy'
            FROM findings_old
        """)

        # Не удаляем findings_old сразу — оставляем для отката
        # (удалить вручную после проверки)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    has_old = "findings_old" in inspector.get_table_names()

    # Удаляем новую
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

    # Восстанавливаем старую
    if has_old:
        op.rename_table("findings_old", "findings")
Особенности:

SQLite не поддерживает md5(random()) — в миграции для SQLite используем Python-fallback (см. ниже).

Для PostgreSQL — оставляем как есть.

Для SQLite — упрощённая миграция (только создание таблицы, без переноса данных, т.к. dev-БД).

Дополнительно в миграции (для SQLite):

python
if dialect == "sqlite":
    # SQLite: без переноса данных (dev-БД)
    # Только создание новой таблицы
    pass
1.3. Проверка модели в init_db.py
MODIFIED: init_db.py — убедиться, что Finding импортируется (для create_all).

python
from manager.src.db.models import Finding, Resource, ScanTask  # noqa
📦 Часть 2. Шифрование и маскирование
2.1. Модуль manager/src/core/encryption.py
NEW: manager/src/core/encryption.py

python
"""
Шифрование и маскирование находок.

- AES-256-GCM для зашифрованного хранения.
- HMAC-SHA256 для fingerprint (защита от brute-force).
- Маскирование по категориям.
"""
import os
import re
import hmac
import hashlib
import base64
import logging
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


# ========== КЛЮЧИ ==========

def _read_secret(name: str, default: Optional[bytes] = None) -> bytes:
    """Читает секрет из Docker Secrets → env → default."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read().strip()

    env_val = os.getenv(name.upper())
    if env_val:
        return env_val.encode()

    if default is not None:
        return default

    raise RuntimeError(
        f"Secret '{name}' not found. "
        f"Set Docker Secret /run/secrets/{name} or env {name.upper()}."
    )


# ========== МАСКИРОВАНИЕ ==========

MASK_RULES = {
    "phone": lambda s: re.sub(
        r"(\+\d)\d{3}(\d{3})(\d{2})(\d{2})", r"\1***\2-\3-\4", s
    ),
    "email": lambda s: re.sub(r"(\w{2})\w+@", r"\1***@", s),
    "api_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "aws_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "password": lambda s: "***",
    "token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "passport": lambda s: (s[:2] + "** ******") if len(s) >= 2 else "***",
    "snils": lambda s: "***-***-*** **",
    "inn": lambda s: (s[:2] + "**********") if len(s) >= 2 else "***",
    "credit_card": lambda s: "**** **** **** " + s[-4:] if len(s) >= 4 else "***",
    # Имена НЕ маскируются (по решению)
    "person": lambda s: s,
}


def mask(value: str, category: str) -> str:
    """Маскирует значение по категории."""
    if not value:
        return value
    fn = MASK_RULES.get(category)
    if fn is None:
        # По умолчанию — полная маска
        return "***"
    try:
        return fn(value)
    except Exception as e:
        logger.warning("Mask failed for category=%s: %s", category, e)
        return "***"


def mask_line(line: str, matches: list[tuple[int, int, str]]) -> str:
    """
    Маскирует строку по списку совпадений.

    matches: [(start, end, category), ...]
    """
    if not matches:
        return line

    # Сортируем по убыванию start (чтобы не сбить индексы)
    sorted_matches = sorted(matches, key=lambda m: m[0], reverse=True)

    result = line
    for start, end, category in sorted_matches:
        original = result[start:end]
        masked = mask(original, category)
        result = result[:start] + masked + result[end:]

    return result


# ========== ШИФРОВАНИЕ ==========

class FindingEncryption:
    """
    AES-256-GCM для находок + HMAC-fingerprint.

    Ключи — Docker Secrets:
      /run/secrets/findings_encryption_key (32 байта)
      /run/secrets/findings_hmac_key        (32 байта)
      /run/secrets/findings_key_id          (строка, напр. "key-2026-09")
    """

    def __init__(self, key: bytes, hmac_key: bytes, key_id: str):
        if len(key) != 32:
            raise ValueError(f"Encryption key must be 32 bytes, got {len(key)}")
        if len(hmac_key) < 32:
            raise ValueError(f"HMAC key must be >= 32 bytes, got {len(hmac_key)}")

        self.aes = AESGCM(key)
        self.hmac_key = hmac_key
        self.key_id = key_id

    @classmethod
    def from_secrets(cls) -> "FindingEncryption":
        key = _read_secret("findings_encryption_key")
        hmac_key = _read_secret("findings_hmac_key")
        key_id_bytes = _read_secret("findings_key_id", default=b"key-2026-09")
        key_id = key_id_bytes.decode() if isinstance(key_id_bytes, bytes) else key_id_bytes

        return cls(key=key, hmac_key=hmac_key, key_id=key_id)

    @classmethod
    def from_env_or_default(cls) -> "FindingEncryption":
        """
        Fallback для dev: генерирует ключи, если не заданы.
        В production — Docker Secrets обязательны.
        """
        if os.path.exists("/run/secrets/findings_encryption_key"):
            return cls.from_secrets()

        if os.getenv("FINDINGS_ENCRYPTION_KEY"):
            key = base64.b64decode(os.getenv("FINDINGS_ENCRYPTION_KEY"))
            hmac_key = base64.b64decode(os.getenv("FINDINGS_HMAC_KEY"))
            key_id = os.getenv("FINDINGS_KEY_ID", "key-dev")
            return cls(key, hmac_key, key_id)

        # Dev: генерируем ephemeral (предупреждение!)
        logger.warning(
            "⚠️ Findings keys not configured! Using ephemeral keys. "
            "Data encrypted with them will be LOST on restart. "
            "Set Docker Secrets or FINDINGS_ENCRYPTION_KEY env."
        )
        return cls(
            key=os.urandom(32),
            hmac_key=os.urandom(32),
            key_id="key-ephemeral",
        )

    def encrypt(self, plaintext: str) -> str:
        """Шифрует строку → base64(nonce + ciphertext)."""
        if not plaintext:
            return ""
        nonce = os.urandom(12)
        ct = self.aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Расшифровывает base64(nonce + ciphertext) → строка."""
        if not ciphertext:
            return ""
        try:
            data = base64.b64decode(ciphertext)
            nonce, ct = data[:12], data[12:]
            return self.aes.decrypt(nonce, ct, None).decode("utf-8")
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            raise ValueError("Decryption failed") from e

    def fingerprint(self, file_path: str, line: int, match: str, category: str) -> str:
        """
        HMAC-SHA256 от (file_path, line, match, category).
        Защита от brute-force по fingerprint.
        """
        msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
        return hmac.new(self.hmac_key, msg, hashlib.sha256).hexdigest()


# ========== СИНГЛТОН ==========

_encryption_instance: Optional[FindingEncryption] = None


def get_encryption() -> FindingEncryption:
    """Синглтон для доступа к шифрованию."""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = FindingEncryption.from_env_or_default()
    return _encryption_instance


def reset_encryption():
    """Сброс синглтона (для тестов)."""
    global _encryption_instance
    _encryption_instance = None
2.2. Обновление manager/src/core/secrets.py (если есть)
MODIFIED: manager/src/core/secrets.py — добавить чтение ключей находок (если используется SecretsManager).

python
# Добавить в список секретов:
FINDINGS_KEYS = [
    "findings_encryption_key",
    "findings_hmac_key",
    "findings_key_id",
]
2.3. Генерация ключей
NEW: scripts/generate_findings_keys.py

python
"""
Генерация ключей для шифрования находок.

Использование:
    python scripts/generate_findings_keys.py

Создаёт:
    secrets/findings_encryption_key   (32 байта, base64)
    secrets/findings_hmac_key         (32 байта, base64)
    secrets/findings_key_id           (key-YYYY-MM)
"""
import os
import base64
from datetime import datetime
from pathlib import Path


def main():
    secrets_dir = Path("secrets")
    secrets_dir.mkdir(exist_ok=True)

    # 32 байта для AES-256
    encryption_key = os.urandom(32)
    hmac_key = os.urandom(32)
    key_id = f"key-{datetime.utcnow().strftime('%Y-%m')}"

    (secrets_dir / "findings_encryption_key").write_bytes(
        base64.b64encode(encryption_key)
    )
    (secrets_dir / "findings_hmac_key").write_bytes(
        base64.b64encode(hmac_key)
    )
    (secrets_dir / "findings_key_id").write_text(key_id)

    print(f"✅ Keys generated in {secrets_dir}/")
    print(f"   - findings_encryption_key ({len(encryption_key)} bytes)")
    print(f"   - findings_hmac_key ({len(hmac_key)} bytes)")
    print(f"   - findings_key_id = {key_id}")
    print()
    print("⚠️  НЕ КОММИТИТЬ В GIT! Добавьте secrets/ в .gitignore")


if __name__ == "__main__":
    main()
Проверить: secrets/ уже в .gitignore (должно быть с Дня 34).

📦 Часть 3. Схемы Pydantic
3.1. Схемы для API
NEW: manager/src/api/schemas_findings.py

python
"""Pydantic-схемы для API находок."""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


FindingStatus = Literal["new", "confirmed", "false_positive", "archived"]
FragmentType = Literal["text_line", "text_context", "image_region", "byte_range"]


class FindingResponse(BaseModel):
    """Находка в ответе API (маскированное)."""
    id: int
    resource_id: int
    task_id: Optional[int] = None

    finding_type: str
    category: str
    severity: str

    fragment_type: str
    line_number: Optional[int] = None
    match_text: Optional[str] = None          # masked
    line_text: Optional[str] = None           # masked
    context_before: Optional[str] = None
    context_after: Optional[str] = None

    # Не-текстовые
    has_fragment: bool = False
    bounding_box: Optional[dict] = None
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None

    # Статус
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    comment: Optional[str] = None

    # Метаданные
    confidence: Optional[float] = None
    detector: Optional[str] = None

    first_seen_at: datetime
    last_seen_at: datetime

    # Возможности
    has_encrypted: bool = False
    can_reveal: bool = False

    class Config:
        from_attributes = True


class FindingRevealResponse(BaseModel):
    """Ответ на reveal (расшифровка)."""
    id: int
    match_text: str
    line_text: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    revealed_at: datetime
    revealed_by: str


class FindingUpdateRequest(BaseModel):
    """Обновление статуса находки."""
    status: FindingStatus
    comment: Optional[str] = None


class FindingBulkUpdateRequest(BaseModel):
    """Массовое обновление."""
    finding_ids: list[int] = Field(..., min_length=1, max_length=1000)
    status: FindingStatus
    comment: Optional[str] = None


class FindingBulkUpdateResponse(BaseModel):
    updated: int
    skipped: int
    errors: list[str] = []


class FindingStatsResponse(BaseModel):
    """Статистика по находкам."""
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]


class FalsePositiveResponse(BaseModel):
    """Ложное срабатывание (для аудита)."""
    id: int
    resource_id: int
    line_number: Optional[int] = None
    match_text_masked: Optional[str] = None
    category: str
    finding_type: str
    comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class CheckFingerprintsRequest(BaseModel):
    """Проверка fingerprints (для сканера)."""
    fingerprints: list[str] = Field(..., max_length=10000)


class CheckFingerprintsResponse(BaseModel):
    """Результат проверки."""
    false_positives: list[str] = []
    confirmed: list[str] = []
    new: list[str] = []
📦 Часть 4. API находок
4.1. Роутер manager/src/api/findings.py
MODIFIED (полная переработка): manager/src/api/findings.py

python
"""
API находок: список, детали, reveal, bulk, stats, FP.

Хранение: гибрид (masked + encrypted).
Расшифровка — только Auditor, с аудитом.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from manager.src.db.session import get_db
from manager.src.db.models import Finding, Resource, ScanTask
from manager.src.auth.models import User
from manager.src.auth.dependencies import (
    require_auth, require_auditor, require_admin
)
from manager.src.core.encryption import get_encryption
from manager.src.api.schemas_findings import (
    FindingResponse, FindingRevealResponse, FindingUpdateRequest,
    FindingBulkUpdateRequest, FindingBulkUpdateResponse,
    FindingStatsResponse, FalsePositiveResponse,
    CheckFingerprintsRequest, CheckFingerprintsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/findings", tags=["findings"])


# ========== ВСПОМОГАТЕЛЬНЫЕ ==========

def _finding_to_response(
    finding: Finding,
    user: Optional[User] = None,
    reveal: bool = False,
) -> dict:
    """Преобразует Finding в ответ (masked или revealed)."""
    enc = get_encryption()

    can_reveal = bool(user and user.has_role("auditor") or user and user.has_role("admin"))

    data = {
        "id": finding.id,
        "resource_id": finding.resource_id,
        "task_id": finding.task_id,
        "finding_type": finding.finding_type,
        "category": finding.category,
        "severity": finding.severity,
        "fragment_type": finding.fragment_type,
        "line_number": finding.line_number,
        "match_text": finding.match_text_masked,
        "line_text": finding.line_text_masked,
        "context_before": finding.context_before_masked,
        "context_after": finding.context_after_masked,
        "has_fragment": bool(finding.fragment_path),
        "bounding_box": finding.bounding_box,
        "byte_offset": finding.byte_offset,
        "byte_length": finding.byte_length,
        "status": finding.status,
        "reviewed_by": finding.reviewed_by,
        "reviewed_at": finding.reviewed_at,
        "comment": finding.comment,
        "confidence": finding.confidence,
        "detector": finding.detector,
        "first_seen_at": finding.first_seen_at,
        "last_seen_at": finding.last_seen_at,
        "has_encrypted": bool(finding.match_text_encrypted),
        "can_reveal": can_reveal,
    }

    # Reveal (только если явно запрошен и есть права)
    if reveal and can_reveal:
        if finding.match_text_encrypted:
            data["match_text"] = enc.decrypt(finding.match_text_encrypted)
        if finding.line_text_encrypted:
            data["line_text"] = enc.decrypt(finding.line_text_encrypted)

    return data


# ========== LIST / GET ==========

@router.get("", response_model=list[FindingResponse])
def list_findings(
    resource_id: Optional[int] = None,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    order_by: str = Query("first_seen_at", regex="^(first_seen_at|last_seen_at|severity|line_number)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Список находок (маскированное)."""
    q = db.query(Finding)

    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if status:
        q = q.filter(Finding.status == status)
    if finding_type:
        q = q.filter(Finding.finding_type == finding_type)
    if category:
        q = q.filter(Finding.category == category)
    if severity:
        q = q.filter(Finding.severity == severity)

    col = getattr(Finding, order_by)
    q = q.order_by(desc(col) if order == "desc" else col)

    findings = q.offset(offset).limit(limit).all()
    return [_finding_to_response(f, user) for f in findings]


@router.get("/stats", response_model=FindingStatsResponse)
def get_stats(
    task_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Статистика по находкам."""
    q = db.query(Finding)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)

    total = q.count()

    by_status = dict(
        db.query(Finding.status, func.count(Finding.id))
        .filter(*q.whereclause.clause_expr if hasattr(q, "whereclause") else [])
        .group_by(Finding.status)
        .all()
    )
    by_type = dict(
        db.query(Finding.finding_type, func.count(Finding.id))
        .group_by(Finding.finding_type).all()
    )
    by_category = dict(
        db.query(Finding.category, func.count(Finding.id))
        .group_by(Finding.category).all()
    )
    by_severity = dict(
        db.query(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity).all()
    )

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_category": by_category,
        "by_severity": by_severity,
    }


@router.get("/false-positives", response_model=list[FalsePositiveResponse])
def list_false_positives(
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Список ложных срабатываний (для аудита)."""
    findings = (
        db.query(Finding)
        .filter(Finding.status == "false_positive")
        .order_by(desc(Finding.reviewed_at))
        .offset(offset).limit(limit).all()
    )
    return [
        {
            "id": f.id,
            "resource_id": f.resource_id,
            "line_number": f.line_number,
            "match_text_masked": f.match_text_masked,
            "category": f.category,
            "finding_type": f.finding_type,
            "comment": f.comment,
            "reviewed_by": f.reviewed_by,
            "reviewed_at": f.reviewed_at,
        }
        for f in findings
    ]


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Детали находки (маскированное)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    return _finding_to_response(finding, user)


# ========== REVEAL ==========

@router.post("/{finding_id}/reveal", response_model=FindingRevealResponse)
def reveal_finding(
    finding_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """
    Расшифровка находки. Только Auditor+. Логируется в audit_logs.
    """
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    enc = get_encryption()

    try:
        match_text = enc.decrypt(finding.match_text_encrypted) if finding.match_text_encrypted else None
        line_text = enc.decrypt(finding.line_text_encrypted) if finding.line_text_encrypted else None
    except ValueError:
        raise HTTPException(500, "Decryption failed")

    revealed_at = datetime.utcnow()

    # Аудит
    _log_reveal(db, user, finding, revealed_at, request)

    return {
        "id": finding.id,
        "match_text": match_text or "",
        "line_text": line_text,
        "context_before": finding.context_before_masked,  # контекст только masked
        "context_after": finding.context_after_masked,
        "revealed_at": revealed_at,
        "revealed_by": user.username,
    }


def _log_reveal(db, user, finding, revealed_at, request):
    """Пишет запись в audit_logs."""
    try:
        from manager.src.db.models import AuditLog
        log = AuditLog(
            action="finding_revealed",
            user_id=user.id,
            username=user.username,
            resource_id=finding.resource_id,
            details={
                "finding_id": finding.id,
                "category": finding.category,
                "finding_type": finding.finding_type,
            },
            ip_address=request.client.host if request.client else None,
            created_at=revealed_at,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log reveal: %s", e)
        db.rollback()


# ========== UPDATE ==========

@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: int,
    body: FindingUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Обновить статус находки (confirmed / false_positive)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    finding.status = body.status
    finding.comment = body.comment
    finding.reviewed_by = user.id
    finding.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(finding)

    return _finding_to_response(finding, user)


@router.post("/bulk", response_model=FindingBulkUpdateResponse)
def bulk_update(
    body: FindingBulkUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Массовое обновление статуса."""
    updated = 0
    skipped = 0
    errors = []

    findings = db.query(Finding).filter(Finding.id.in_(body.finding_ids)).all()
    found_ids = {f.id for f in findings}
    missing = set(body.finding_ids) - found_ids

    for f in findings:
        try:
            f.status = body.status
            f.comment = body.comment
            f.reviewed_by = user.id
            f.reviewed_at = datetime.utcnow()
            updated += 1
        except Exception as e:
            errors.append(f"Finding {f.id}: {e}")

    skipped = len(missing)
    for mid in missing:
        errors.append(f"Finding {mid}: not found")

    db.commit()
    return {"updated": updated, "skipped": skipped, "errors": errors}


# ========== DELETE ==========

@router.delete("/{finding_id}")
def delete_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Удалить находку (только Admin)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    # Удалить фрагмент (если есть)
    if finding.fragment_path:
        try:
            import os
            if os.path.exists(finding.fragment_path):
                os.remove(finding.fragment_path)
        except Exception as e:
            logger.warning("Failed to remove fragment: %s", e)

    db.delete(finding)
    db.commit()
    return {"deleted": finding_id}


# ========== CHECK FINGERPRINTS (для сканера) ==========

@router.post("/check-fingerprints", response_model=CheckFingerprintsResponse)
def check_fingerprints(
    body: CheckFingerprintsRequest,
    db: Session = Depends(get_db),
):
    """
    Проверка fingerprints перед отправкой находок (для сканера).
    Публичный (machine-эндпоинт, без JWT).
    """
    if not body.fingerprints:
        return {"false_positives": [], "confirmed": [], "new": []}

    existing = (
        db.query(Finding.fingerprint, Finding.status)
        .filter(Finding.fingerprint.in_(body.fingerprints))
        .all()
    )

    status_map = {fp: st for fp, st in existing}

    false_positives = [fp for fp in body.fingerprints if status_map.get(fp) == "false_positive"]
    confirmed = [fp for fp in body.fingerprints if status_map.get(fp) == "confirmed"]
    new = [fp for fp in body.fingerprints if fp not in status_map]

    return {
        "false_positives": false_positives,
        "confirmed": confirmed,
        "new": new,
    }
ВАЖНО:

AuditLog — модель может отличаться. Проверить существующую модель в manager/src/db/models.py. Если поля другие — адаптировать _log_reveal.

user.has_role("auditor") — метод должен существовать. Если нет — добавить в User (см. ниже).

4.2. Метод has_role в User
MODIFIED: manager/src/auth/models.py — добавить (если нет):

python
def has_role(self, role_name: str) -> bool:
    """Проверяет, есть ли у пользователя роль."""
    return any(r.name == role_name for r in self.roles)
4.3. Регистрация роутера
MODIFIED: manager/src/main.py — убедиться, что findings роутер подключён:

python
from manager.src.api import findings as findings_api
app.include_router(findings_api.router)
Проверить: в main.py уже есть app.include_router(...) для findings — заменить/дополнить.

4.4. Обновление middleware
MODIFIED: manager/src/auth/middleware.py — добавить /api/findings/check-fingerprints в публичные machine-эндпоинты (без JWT).

python
MACHINE_ENDPOINTS = [
    # ... существующие
    "/api/findings/check-fingerprints",
]
📦 Часть 5. Docker Secrets
5.1. docker-compose.yml
MODIFIED: docker-compose.yml — добавить secrets для Manager:

yaml
services:
  manager:
    # ...
    secrets:
      - findings_encryption_key
      - findings_hmac_key
      - findings_key_id
    environment:
      # Fallback для dev (если secrets не заданы)
      FINDINGS_KEY_ID: ${FINDINGS_KEY_ID:-key-2026-09}

secrets:
  findings_encryption_key:
    file: ./secrets/findings_encryption_key
  findings_hmac_key:
    file: ./secrets/findings_hmac_key
  findings_key_id:
    file: ./secrets/findings_key_id
5.2. .env.example
MODIFIED: .env.example — добавить:

env
# ===== FINDINGS ENCRYPTION =====
# Ключи генерируются: python scripts/generate_findings_keys.py
# В production — через Docker Secrets (папка secrets/)
FINDINGS_KEY_ID=key-2026-09
# FINDINGS_ENCRYPTION_KEY=<base64 32 bytes>  # для dev без Docker
# FINDINGS_HMAC_KEY=<base64 32 bytes>
5.3. .gitignore
Проверить: secrets/ в .gitignore.

gitignore
secrets/
📦 Часть 6. Тесты
6.1. Unit-тесты шифрования
NEW: tests/unit/test_encryption.py

python
"""Unit-тесты шифрования и маскирования."""
import os
import pytest
from manager.src.core.encryption import (
    FindingEncryption, mask, mask_line
)


@pytest.fixture
def enc():
    return FindingEncryption(
        key=os.urandom(32),
        hmac_key=os.urandom(32),
        key_id="test-key",
    )


def test_encrypt_decrypt_roundtrip(enc):
    plain = "Иван Иванов, +7-999-123-45-67"
    cipher = enc.encrypt(plain)
    assert cipher != plain
    assert enc.decrypt(cipher) == plain


def test_encrypt_empty(enc):
    assert enc.encrypt("") == ""
    assert enc.decrypt("") == ""


def test_decrypt_invalid(enc):
    with pytest.raises(ValueError):
        enc.decrypt("not-valid-base64!!!")


def test_fingerprint_deterministic(enc):
    fp1 = enc.fingerprint("/path/file.txt", 42, "+7-999-123-45-67", "phone")
    fp2 = enc.fingerprint("/path/file.txt", 42, "+7-999-123-45-67", "phone")
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA256 hex


def test_fingerprint_different(enc):
    fp1 = enc.fingerprint("/path/file.txt", 42, "+7-999-123-45-67", "phone")
    fp2 = enc.fingerprint("/path/file.txt", 43, "+7-999-123-45-67", "phone")
    assert fp1 != fp2


def test_mask_phone():
    assert mask("+7-999-123-45-67", "phone") == "+7***123-45-67"


def test_mask_email():
    assert mask("ivan@example.com", "email") == "iv***@example.com"


def test_mask_password():
    assert mask("secret123", "password") == "***"


def test_mask_api_key():
    assert mask("AKIAIOSFODNN7EXAMPLE", "api_key") == "AKIA***"


def test_mask_person_not_masked():
    """Имена НЕ маскируются (по решению)."""
    assert mask("Иван Иванов", "person") == "Иван Иванов"


def test_mask_line_multiple():
    line = "Иван Иванов, +7-999-123-45-67, ivan@example.com"
    matches = [
        (13, 29, "phone"),
        (31, 47, "email"),
    ]
    result = mask_line(line, matches)
    assert "+7-999-123-45-67" not in result
    assert "ivan@example.com" not in result


def test_key_id():
    enc = FindingEncryption(os.urandom(32), os.urandom(32), "key-2026-09")
    assert enc.key_id == "key-2026-09"


def test_invalid_key_size():
    with pytest.raises(ValueError):
        FindingEncryption(key=b"short", hmac_key=os.urandom(32), key_id="x")
6.2. E2E-тесты API находок
NEW: tests/e2e/test_findings_api.py

python
"""E2E-тесты API находок."""
import os
import pytest
import requests
from datetime import datetime


@pytest.fixture
def auditor_token(manager_url):
    """Логин auditor."""
    r = requests.post(f"{manager_url}/api/auth/login",
                      json={"username": "auditor", "password": "auditor123"})
    if r.status_code != 200:
        pytest.skip("auditor user not available")
    return r.json()["access_token"]


@pytest.fixture
def viewer_token(manager_url):
    r = requests.post(f"{manager_url}/api/auth/login",
                      json={"username": "viewer", "password": "viewer123"})
    if r.status_code != 200:
        pytest.skip("viewer user not available")
    return r.json()["access_token"]


@pytest.fixture
def sample_finding(manager_url, api_client):
    """Создаёт находку через прямой SQL (для теста)."""
    # Альтернатива: использовать API /api/scanner/tasks/{id}/results
    # Но пока сканер шлёт старое — создадим напрямую
    pytest.skip("Требует прямого доступа к БД или нового API сканера (Этап 2)")


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_list_findings_requires_auth(manager_url, anon_client):
    """Список находок требует JWT."""
    r = anon_client.get(f"{manager_url}/api/findings")
    assert r.status_code == 401


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_list_findings_with_auth(manager_url, api_client):
    """Список находок доступен с JWT."""
    r = api_client.get(f"{manager_url}/api/findings")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_stats(manager_url, api_client):
    """Статистика доступна."""
    r = api_client.get(f"{manager_url}/api/findings/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "by_status" in data


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_reveal_requires_auditor(manager_url, viewer_token):
    """Reveal недоступен Viewer (403)."""
    r = requests.post(f"{manager_url}/api/findings/1/reveal",
                      headers={"Authorization": f"Bearer {viewer_token}"})
    # 403 или 404 (если находки нет)
    assert r.status_code in (403, 404)


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_check_fingerprints_public(manager_url, anon_client):
    """check-fingerprints доступен без JWT (machine endpoint)."""
    r = anon_client.post(f"{manager_url}/api/findings/check-fingerprints",
                         json={"fingerprints": ["abc123", "def456"]})
    assert r.status_code == 200
    data = r.json()
    assert "false_positives" in data
    assert "confirmed" in data
    assert "new" in data


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_check_fingerprints_empty(manager_url, anon_client):
    """Пустой список fingerprints → пустые результаты."""
    r = anon_client.post(f"{manager_url}/api/findings/check-fingerprints",
                         json={"fingerprints": []})
    assert r.status_code == 200
    assert r.json()["new"] == []


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_false_positives_requires_auditor(manager_url, viewer_token):
    """Список FP требует Auditor."""
    r = requests.get(f"{manager_url}/api/findings/false-positives",
                     headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code in (403, 401)
6.3. Маркер unit в pytest
MODIFIED: pyproject.toml — добавить маркер unit:

toml
markers = [
    "unit: Unit-тесты (без стека)",
    "e2e: End-to-end тесты",
    # ... остальные
]
MODIFIED: tests/conftest.py — не скипать unit-тесты:

python
def pytest_runtest_setup(item):
    # unit-тесты не требуют стека
    if item.get_closest_marker("unit"):
        return
    # ... существующая логика skip
📦 Часть 7. Документация
7.1. Обновление docs/deployment.md
MODIFIED: docs/deployment.md — добавить раздел «Ключи шифрования находок»:

markdown
## Ключи шифрования находок

Находки хранятся в гибридном виде: маскированные + зашифрованные (AES-256-GCM).

### Генерация ключей

```bash
python scripts/generate_findings_keys.py
# Создаёт secrets/findings_encryption_key, findings_hmac_key, findings_key_id
Production
Ключи монтируются в Manager через Docker Secrets:

yaml
secrets:
  - findings_encryption_key
  - findings_hmac_key
  - findings_key_id
Dev (без Docker)
Задать env-переменные:

bash
export FINDINGS_ENCRYPTION_KEY=<base64>
export FINDINGS_HMAC_KEY=<base64>
export FINDINGS_KEY_ID=key-2026-09
⚠️ Без ключей Manager сгенерирует ephemeral-ключи (данные потеряются при рестарте).

text

### 7.2. Обновление `STATE.md` (после выполнения)

Кодер обновит в конце дня:
- Версия → v3.9.0
- Текущий день → 40.2
- Последний отчёт → `day_40.1_report.md`

---

## ✅ Критерии приёмки Дня 40.1

1. **Модель `Finding`** — заменена, все поля + индексы
2. **Alembic-миграция `003`** — применяется на SQLite и PostgreSQL
3. **Модуль шифрования** — `encryption.py` с AES-256-GCM + HMAC + маскирование
4. **Скрипт генерации ключей** — `scripts/generate_findings_keys.py`
5. **Docker Secrets** — в `docker-compose.yml`, `.env.example`, `.gitignore`
6. **API находок** — 10 эндпоинтов (list, get, reveal, update, bulk, stats, FP, check-fingerprints, delete)
7. **Аудит reveal** — запись в `audit_logs`
8. **Роли** — reveal только Auditor, delete только Admin
9. **Backward compatibility** — старые находки перенесены (миграция)
10. **Тесты** — unit (шифрование) + e2e (API), все проходят или skip с причиной
11. **`STATE.md` обновлён** (v3.9.0)
12. **`ROADMAP.md`** — День 40.1 ✅

---

## 📁 Артефакты (итог)

**NEW:**
- `manager/src/core/encryption.py`
- `manager/src/api/schemas_findings.py`
- `manager/src/db/migrations/versions/003_findings_refactor.py`
- `scripts/generate_findings_keys.py`
- `tests/unit/__init__.py`
- `tests/unit/test_encryption.py`
- `tests/e2e/test_findings_api.py`
- `prompts/reports/day_40.1_report.md` (после выполнения)

**MODIFIED:**
- `manager/src/db/models.py` (модель `Finding`)
- `manager/src/api/findings.py` (полная переработка)
- `manager/src/auth/models.py` (`has_role`)
- `manager/src/auth/middleware.py` (`check-fingerprints` публичный)
- `manager/src/main.py` (регистрация роутера)
- `manager/src/core/secrets.py` (если используется)
- `docker-compose.yml` (secrets)
- `.env.example` (FINDINGS_*)
- `docs/deployment.md` (ключи шифрования)
- `pyproject.toml` (маркер `unit`)
- `tests/conftest.py` (unit не скипается)
- `STATE.md` (v3.9.0)
- `ROADMAP.md` (День 40.1 ✅)

**DELETED:** —

---

## 🚀 Команда коммита

```bash
git checkout -b feature/day_40.1_findings_model
git add -A
git commit -m "feat: День 40.1 — Findings Refactor: модель + шифрование + API (v3.9.0)

Модель данных:
- Finding: строка/фрагмент вместо файла (BACKLOG-050)
- Поля: line_number, match_text, line_text, context, fragment_type,
  bounding_box, byte_offset, fingerprint, encryption_key_id, status
- Индексы: fingerprint, resource+status, type+category, status+first_seen

Шифрование (BACKLOG-051):
- manager/src/core/encryption.py: AES-256-GCM + HMAC-SHA256 + маскирование
- Ключи — Docker Secrets (findings_encryption_key, findings_hmac_key)
- Маскирование: phone, email, api_key, password, token, passport
- Имена НЕ маскируются (по решению)
- scripts/generate_findings_keys.py

API находок (BACKLOG-052):
- GET /api/findings — список (маскированное, фильтры)
- GET /api/findings/{id} — детали
- POST /api/findings/{id}/reveal — расшифровка (Auditor+, аудит)
- PATCH /api/findings/{id} — статус (confirmed/false_positive)
- POST /api/findings/bulk — массовое обновление
- GET /api/findings/stats — статистика
- GET /api/findings/false-positives — FP (Auditor+)
- POST /api/findings/check-fingerprints — для сканера (публичный)
- DELETE /api/findings/{id} — только Admin

Alembic:
- 003_findings_refactor: новая таблица + миграция старых данных

Безопасность:
- reveal только Auditor, с записью в audit_logs
- delete только Admin
- HMAC-fingerprint (защита от brute-force)
- ephemeral-ключи в dev с предупреждением

Тесты:
- tests/unit/test_encryption.py — шифрование, маскирование, fingerprint
- tests/e2e/test_findings_api.py — API, роли, check-fingerprints

Docs:
- STATE.md → v3.9.0, следующий — День 40.2
- ROADMAP.md: День 40.1 ✅
- docs/deployment.md: раздел «Ключи шифрования»"
📝 Обратная связь архитектору (шаблон)
После выполнения — заполнить:

Что заработало / что нет

Отклонения от ТЗ (схемы API, модели AuditLog)

Проблемы с миграцией (SQLite vs PostgreSQL)

Время выполнения

Готовность к Дню 40.2 (сканер)

⚠️ Важные замечания
Backward compatibility: API принимает старый формат (от сканера v3.8.0) и новый (после Этапа 2). Пока сканер не обновлён — старые находки создаются с fragment_type="text_line", fingerprint=md5.

AuditLog: проверить существующую модель. Если поля другие — адаптировать _log_reveal.

has_role: если метода нет в User — добавить.

Docker Secrets: в dev можно без них (ephemeral), но в production — обязательно.

Не трогать сканер — он продолжит работать как есть. Этап 2 обновит его.