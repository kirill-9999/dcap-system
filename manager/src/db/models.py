# manager/src/db/models.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Resource(Base):
    __tablename__ = "resources"

    # Существующие поля
    id = Column(Integer, primary_key=True)
    path = Column(String(500), nullable=False, unique=True)
    type = Column(String(50), default="FILESYSTEM")
    status = Column(String(20), default="ACTIVE")
    last_scanned_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scan_config = Column(JSON, nullable=True)
    scan_interval = Column(Integer, default=3600)
    schedule_enabled = Column(Boolean, default=False)
    cron_expression = Column(String(100), nullable=True)

    # 🆕 НОВЫЕ ПОЛЯ ДЛЯ УПРАВЛЕНИЯ ДОСТУПОМ (День 9)
    # Владелец ресурса
    owner = Column(String(200), nullable=True)  # DOMAIN\User или LOCAL\User
    owner_sid = Column(String(100), nullable=True)  # SID владельца

    # Права доступа в упрощенном формате
    permissions = Column(JSON, default={})  # {"user": "read", "group": "write"}

    # Время последней синхронизации прав
    permission_last_synced = Column(DateTime, nullable=True)

    # Классификация ресурса по чувствительности
    is_sensitive = Column(Boolean, default=False)  # Флаг чувствительности
    classification_level = Column(
        String(20), default="public"
    )  # public, internal, confidential, restricted

    # Источник прав доступа
    permission_source = Column(String(50), default="local")  # local, ad, custom

    # Домен (для будущей AD интеграции)
    domain = Column(String(100), nullable=True)

    # 🆕 СВЯЗИ (День 9)
    access_entries = relationship(
        "AccessEntry", back_populates="resource", cascade="all, delete-orphan", lazy="select"
    )
    permission_changes = relationship(
        "PermissionChange", back_populates="resource", cascade="all, delete-orphan", lazy="select"
    )
    access_alerts = relationship(
        "AccessAlert", back_populates="resource", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self):
        return f"<Resource(id={self.id}, path='{self.path}', owner='{self.owner}')>"


class Scanner(Base):
    __tablename__ = "scanners"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    status = Column(String(20), default="offline")
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    hostname = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    scan_interval = Column(Integer, default=10)

    def __repr__(self):
        return f"<Scanner(id={self.id}, name='{self.name}', status='{self.status}')>"


class ScanTask(Base):
    __tablename__ = "scan_tasks"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=True)
    source_path = Column(String(500), nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    files_scanned = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    progress = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ScanTask(id={self.id}, resource_id={self.resource_id}, status='{self.status}')>"


class Finding(Base):
    """Находка = конкретное совпадение (строка/фрагмент), а не файл.

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


class CatalogEntry(Base):
    __tablename__ = "catalog_entries"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=True)
    path = Column(String(500), nullable=False, unique=True, index=True)
    entry_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CatalogEntry(id={self.id}, path='{self.path}')>"


class FailedFile(Base):
    __tablename__ = "failed_files"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"))
    resource_id = Column(Integer, ForeignKey("resources.id"))
    file_path = Column(String(500), nullable=False)
    error_type = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FailedFile(id={self.id}, file='{self.file_path}', error='{self.error_type}')>"


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), unique=True)
    cron_expression = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Schedule(id={self.id}, resource_id={self.resource_id}, cron='{self.cron_expression}')>"


# 🆕 НОВЫЕ МОДЕЛИ ДЛЯ УПРАВЛЕНИЯ ДОСТУПОМ (День 9)


class AccessEntry(Base):
    """
    Модель для хранения информации о правах доступа к ресурсу.
    Поддерживает локальных пользователей/группы и будущую AD интеграцию.
    """

    __tablename__ = "access_entries"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)

    # Субъект доступа
    principal_type = Column(
        String(20), nullable=False
    )  # user, group, local_user, ad_user, ad_group, system
    principal_name = Column(String(200), nullable=False)  # DOMAIN\User или GROUP_NAME
    principal_sid = Column(String(100), nullable=True)  # SID субъекта

    # Для будущей AD интеграции
    principal_domain = Column(String(100), nullable=True)  # Домен субъекта
    principal_upn = Column(String(200), nullable=True)  # User Principal Name (user@domain.com)

    # Права
    permission_type = Column(
        String(50), nullable=False
    )  # read, write, delete, modify, full_control
    permission_source = Column(String(50), default="direct")  # direct, inherited, group_membership

    # Наследование
    inherited_from = Column(String(500), nullable=True)  # Путь или группа-источник
    is_inherited = Column(Boolean, default=False)

    # Аудит
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(String(200), nullable=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Источник коллектора
    collector_source = Column(String(50), default="local")  # local, ad, custom

    # Связь с ресурсом
    resource = relationship("Resource", back_populates="access_entries")

    def __repr__(self):
        return (
            f"<AccessEntry(id={self.id}, resource_id={self.resource_id}, "
            f"principal='{self.principal_name}', permission='{self.permission_type}')>"
        )

    def to_dict(self):
        """Удобный метод для сериализации"""
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "principal_type": self.principal_type,
            "principal_name": self.principal_name,
            "principal_sid": self.principal_sid,
            "principal_domain": self.principal_domain,
            "principal_upn": self.principal_upn,
            "permission_type": self.permission_type,
            "permission_source": self.permission_source,
            "inherited_from": self.inherited_from,
            "is_inherited": self.is_inherited,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "granted_by": self.granted_by,
            "last_verified_at": (
                self.last_verified_at.isoformat() if self.last_verified_at else None
            ),
            "is_active": self.is_active,
            "collector_source": self.collector_source,
        }


class PermissionChange(Base):
    """
    Модель для хранения истории изменений прав доступа.
    Позволяет отслеживать кто, когда и что изменил.
    """

    __tablename__ = "permission_changes"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)

    # Что изменилось
    change_type = Column(String(50), nullable=False)  # grant, revoke, modify
    principal_name = Column(String(200), nullable=False)
    permission_type = Column(String(50), nullable=False)

    # Старое и новое состояние
    old_value = Column(String(50), nullable=True)
    new_value = Column(String(50), nullable=True)

    # Кто изменил
    changed_by = Column(String(200), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)

    # Источник изменения
    change_source = Column(String(50), default="manual")  # manual, ad_sync, api, system

    # Связь с ресурсом
    resource = relationship("Resource", back_populates="permission_changes")

    def __repr__(self):
        return (
            f"<PermissionChange(id={self.id}, resource_id={self.resource_id}, "
            f"type='{self.change_type}', principal='{self.principal_name}')>"
        )

    def to_dict(self):
        """Удобный метод для сериализации"""
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "change_type": self.change_type,
            "principal_name": self.principal_name,
            "permission_type": self.permission_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "change_source": self.change_source,
        }


class AccessAlert(Base):
    """
    Модель для хранения алертов по доступам.
    Помогает выявлять проблемы безопасности: избыточные права, опасные наследования и т.д.
    """

    __tablename__ = "access_alerts"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True)

    # Тип и важность
    alert_type = Column(
        String(50), nullable=False
    )  # excessive_permissions, inherited_risk, orphaned, sensitive_access
    severity = Column(String(20), default="warning")  # critical, warning, info

    # Детали
    principal_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)

    # Статус обработки
    status = Column(String(20), default="open")  # open, acknowledged, resolved, ignored

    # Аудит
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(200), nullable=True)

    # Связь с ресурсом
    resource = relationship("Resource", back_populates="access_alerts")

    def __repr__(self):
        return (
            f"<AccessAlert(id={self.id}, type='{self.alert_type}', "
            f"severity='{self.severity}', status='{self.status}')>"
        )

    def to_dict(self):
        """Удобный метод для сериализации"""
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "principal_name": self.principal_name,
            "description": self.description,
            "recommendation": self.recommendation,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


class AuditAgent(Base):
    __tablename__ = "audit_agents"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)  # например: server01-audit
    hostname = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    status = Column(String(20), default="offline")  # offline, online, error, updating

    version = Column(String(20), default="1.0.0")

    # Конфигурация агента (передается из Manager)
    config = Column(
        JSON,
        default={
            "read_interval": 60,  # секунд между чтением Security Log
            "batch_size": 100,  # сколько событий за раз
            "buffer_size": 10000,  # сколько хранить локально при потере связи
            "event_filters": [],  # список Event ID для сбора
            "paths": [],  # какие папки аудировать (SACL)
        },
    )

    # Мониторинг
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_error = Column(Text, nullable=True)

    # Статистика
    events_sent = Column(Integer, default=0)
    events_failed = Column(Integer, default=0)
    last_event_at = Column(DateTime, nullable=True)

    # Связи
    audit_logs = relationship("AuditLog", back_populates="agent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AuditAgent(id={self.id}, name='{self.name}', status='{self.status}')>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    # Индексы для поиска. Партиционирование audit_logs по месяцам выполняется
    # на PostgreSQL через Alembic-миграцию (001_initial_postgres.py):
    # на SQLite DDL PARTITION OF не применяется, поэтому здесь только индексы.
    __table_args__ = (
        Index("idx_audit_source_created", "event_source", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("audit_agents.id"), nullable=True, index=True)

    event_type = Column(String(50), nullable=False)  # read, write, delete, move, rename
    event_source = Column(String(50), default="agent")  # agent, scanner, api, system
    user = Column(String(200), nullable=True)
    user_sid = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500), nullable=True)  # для move/rename
    source_host = Column(String(100), nullable=True)  # откуда пришло событие

    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связи
    agent = relationship("AuditAgent", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event_type='{self.event_type}', file='{self.file_path}')>"


# 🆕 АРХИВНЫЕ МОДЕЛИ (День 35)
class AuditLogArchive(Base):
    """Архивная таблица для аудит-событий"""

    __tablename__ = "audit_logs_archive"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    event_source = Column(String(50), default="agent")
    user = Column(String(200), nullable=True)
    user_sid = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500), nullable=True)
    source_host = Column(String(100), nullable=True)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    archived_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Удобный метод для сериализации"""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "event_source": self.event_source,
            "user": self.user,
            "user_sid": self.user_sid,
            "file_path": self.file_path,
            "old_path": self.old_path,
            "source_host": self.source_host,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


class FindingArchive(Base):
    """Архивная таблица для находок"""

    __tablename__ = "findings_archive"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, nullable=True, index=True)
    resource_id = Column(Integer, nullable=True, index=True)
    file_path = Column(String(500), nullable=False)
    line_number = Column(Integer, default=0)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=True)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    archived_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Удобный метод для сериализации"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "category": self.category,
            "subcategory": self.subcategory,
            "value": self.value,
            "confidence": self.confidence,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


# Словарь для удобного импорта всех моделей
__all__ = [
    "Base",
    "Resource",
    "Scanner",
    "ScanTask",
    "Finding",
    "CatalogEntry",
    "FailedFile",
    "Schedule",
    "AccessEntry",
    "PermissionChange",
    "AccessAlert",
    "AuditAgent",
    "AuditLog",
    "AuditLogArchive",
    "FindingArchive",
]


def create_monthly_partition(engine, year: int, month: int) -> str:
    """Создание партиции audit_logs для указанного месяца (PostgreSQL).

    Возвращает имя созданной партиции. На SQLite — no-op.
    """
    if engine.dialect.name != "postgresql":
        return ""
    from sqlalchemy import text

    partition_name = f"audit_logs_{year}_{month:02d}"
    start_date = f"{year}-{month:02d}-01"
    end_month = month + 1
    end_year = year
    if end_month > 12:
        end_month = 1
        end_year = year + 1
    end_date = f"{end_year}-{end_month:02d}-01"

    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF audit_logs
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
                """
            )
        )
    return partition_name


def ensure_audit_log_partitions(engine, months_ahead: int = 12) -> list:
    """Создание партиций аудита на текущий месяц + N вперёд (PostgreSQL).

    SQLite — возвращает пустой список (партиционирование недоступно).
    """
    if engine.dialect.name != "postgresql":
        return []
    from datetime import date
    from sqlalchemy import text

    # Проверяем, что audit_logs — партиционированная таблица
    # (иначе DDL «PARTITION OF» упадёт).
    with engine.connect() as conn:
        is_partitioned = conn.execute(
            text(
                "SELECT 1 FROM pg_partitioned_table "
                "WHERE partrelid = to_regclass('audit_logs')"
            )
        ).fetchone()
    if not is_partitioned:
        return []

    created = []
    today = date.today()
    year, month = today.year, today.month
    for i in range(months_ahead + 1):
        y = year + (month - 1 + i) // 12
        m = (month - 1 + i) % 12 + 1
        created.append(create_monthly_partition(engine, y, m))
    return created
