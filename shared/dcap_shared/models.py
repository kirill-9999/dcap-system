# -*- coding: utf-8 -*-
"""
DCAP Shared - Database Models
Базовые модели для Manager и Scanner
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, 
    JSON, Enum as SQLEnum, BigInteger, ForeignKey,
    Index, Text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
import enum

Base = declarative_base()


class ScannerStatus(str, enum.Enum):
    """Статус сканера"""
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    ERROR = "error"


class TaskStatus(str, enum.Enum):
    """Статус задания"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResourceType(str, enum.Enum):
    """Тип ресурса"""
    FILESYSTEM = "filesystem"
    S3 = "s3"
    MINIO = "minio"


class Scanner(Base):
    """Модель агента сканирования"""
    __tablename__ = "scanners"
    
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    public_cert: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[ScannerStatus] = mapped_column(
        SQLEnum(ScannerStatus), 
        default=ScannerStatus.OFFLINE
    )
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    total_files_scanned: Mapped[int] = mapped_column(BigInteger, default=0)
    total_findings: Mapped[int] = mapped_column(BigInteger, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    tasks: Mapped[List["ScanTask"]] = relationship("ScanTask", back_populates="scanner")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "endpoint": self.endpoint,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "total_files_scanned": self.total_files_scanned,
            "total_findings": self.total_findings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self) -> str:
        return f"<Scanner(id={self.id}, name={self.name}, status={self.status.value})>"


class Resource(Base):
    """Модель ресурса для сканирования"""
    __tablename__ = "resources"
    
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    type: Mapped[ResourceType] = mapped_column(SQLEnum(ResourceType), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Зашифрованные credentials (AES-256-GCM)
    credentials_encrypted: Mapped[Optional[bytes]] = mapped_column(JSON, nullable=True)
    credentials_nonce: Mapped[Optional[bytes]] = mapped_column(JSON, nullable=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Дополнительные параметры (extensions, max_file_size и т.д.)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    last_scan_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_scan_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="resource")
    tasks: Mapped[List["ScanTask"]] = relationship("ScanTask", back_populates="resource")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "type": self.type.value,
            "path": self.path,
            "enabled": self.enabled,
            "config": self.config or {},
            "last_scan_start": self.last_scan_start.isoformat() if self.last_scan_start else None,
            "last_scan_end": self.last_scan_end.isoformat() if self.last_scan_end else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def get_full_path(self) -> str:
        """Получить полный путь с учётом типа ресурса"""
        if self.type in (ResourceType.S3, ResourceType.MINIO):
            return f"{self.type.value}://{self.path}"
        return self.path
    
    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, type={self.type.value}, path={self.path})>"


class Schedule(Base):
    """Модель расписания сканирования"""
    __tablename__ = "schedules"
    
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    resource_id: Mapped[UUID] = mapped_column(PGUUID, ForeignKey("resources.id"), nullable=False)
    
    # Cron выражение (например, "0 2 * * *" - каждый день в 2 часа)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Приоритет (чем выше, тем раньше выполняется)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    # Максимальное количество файлов за одно задание
    max_files_per_batch: Mapped[int] = mapped_column(Integer, default=500)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    resource: Mapped[Resource] = relationship("Resource", back_populates="schedules")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "resource_id": str(self.resource_id),
            "cron_expression": self.cron_expression,
            "priority": self.priority,
            "max_files_per_batch": self.max_files_per_batch,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }
    
    def __repr__(self) -> str:
        return f"<Schedule(id={self.id}, cron={self.cron_expression})>"


class ScanTask(Base):
    """Модель задания на сканирование"""
    __tablename__ = "scan_tasks"
    
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    resource_id: Mapped[UUID] = mapped_column(PGUUID, ForeignKey("resources.id"), nullable=False)
    scanner_id: Mapped[Optional[UUID]] = mapped_column(PGUUID, ForeignKey("scanners.id"), nullable=True)
    
    # Какую часть ресурса сканировать (например, подпапку или список файлов)
    path_filter: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Статус задания
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    
    # Статистика
    files_total: Mapped[int] = mapped_column(Integer, default=0)
    files_scanned: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Временные метки
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    resource: Mapped[Resource] = relationship("Resource", back_populates="tasks")
    scanner: Mapped[Optional[Scanner]] = relationship("Scanner", back_populates="tasks")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "resource_id": str(self.resource_id),
            "scanner_id": str(self.scanner_id) if self.scanner_id else None,
            "path_filter": self.path_filter,
            "status": self.status.value,
            "files_total": self.files_total,
            "files_scanned": self.files_scanned,
            "findings_count": self.findings_count,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self) -> str:
        return f"<ScanTask(id={self.id}, status={self.status.value})>"


# Индексы для оптимизации запросов
Index("idx_scanners_status", Scanner.status)
Index("idx_scanners_last_heartbeat", Scanner.last_heartbeat)
Index("idx_resources_enabled", Resource.enabled)
Index("idx_resources_type", Resource.type)
Index("idx_schedules_next_run", Schedule.next_run)
Index("idx_schedules_enabled", Schedule.enabled)
Index("idx_tasks_status", ScanTask.status)
Index("idx_tasks_assigned_at", ScanTask.assigned_at)