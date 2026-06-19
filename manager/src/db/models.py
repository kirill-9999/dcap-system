# -*- coding: utf-8 -*-
"""
DCAP Manager - Database Models (SQLite compatible)
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, DateTime, Integer, Boolean, 
    JSON, Enum as SQLEnum, BigInteger, ForeignKey,
    Text, Float, Index
)
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
import enum

Base = declarative_base()


def generate_uuid() -> str:
    """Генерация UUID строки"""
    return str(uuid.uuid4())


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


class Scanner(Base):
    """Модель агента сканирования"""
    __tablename__ = "scanners"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
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
    findings: Mapped[List["Finding"]] = relationship("Finding", back_populates="scanner")
    catalog_entries: Mapped[List["CatalogEntry"]] = relationship("CatalogEntry", back_populates="scanner")
    failed_files: Mapped[List["FailedFile"]] = relationship("FailedFile", back_populates="scanner")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
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
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    
    credentials_encrypted: Mapped[Optional[bytes]] = mapped_column(JSON, nullable=True)
    credentials_nonce: Mapped[Optional[bytes]] = mapped_column(JSON, nullable=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    last_scan_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_scan_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="resource")
    tasks: Mapped[List["ScanTask"]] = relationship("ScanTask", back_populates="resource")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "path": self.path,
            "enabled": self.enabled,
            "config": self.config or {},
            "last_scan_start": self.last_scan_start.isoformat() if self.last_scan_start else None,
            "last_scan_end": self.last_scan_end.isoformat() if self.last_scan_end else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def get_full_path(self) -> str:
        if self.type in ("S3", "MINIO"):
            return f"{self.type.lower()}://{self.path}"
        return self.path


class Schedule(Base):
    """Модель расписания сканирования"""
    __tablename__ = "schedules"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("resources.id"), nullable=False)
    
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
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
    
    resource: Mapped[Resource] = relationship("Resource", back_populates="schedules")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "cron_expression": self.cron_expression,
            "priority": self.priority,
            "max_files_per_batch": self.max_files_per_batch,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }


class ScanTask(Base):
    """Модель задания на сканирование"""
    __tablename__ = "scan_tasks"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("resources.id"), nullable=False)
    scanner_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("scanners.id"), nullable=True)
    
    path_filter: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    
    files_total: Mapped[int] = mapped_column(Integer, default=0)
    files_scanned: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    resource: Mapped[Resource] = relationship("Resource", back_populates="tasks")
    scanner: Mapped[Optional[Scanner]] = relationship("Scanner", back_populates="tasks")
    findings: Mapped[List["Finding"]] = relationship("Finding", back_populates="task")
    failed_files: Mapped[List["FailedFile"]] = relationship("FailedFile", back_populates="task")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "scanner_id": self.scanner_id,
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


class Finding(Base):
    """Находка (результат сканирования)"""
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    scanner_id: Mapped[str] = mapped_column(String(36), ForeignKey("scanners.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("scan_tasks.id"), nullable=False)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    classifier_name: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scanner: Mapped[Scanner] = relationship("Scanner", back_populates="findings")
    task: Mapped[ScanTask] = relationship("ScanTask", back_populates="findings")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scanner_id": self.scanner_id,
            "task_id": self.task_id,
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "file_modified": self.file_modified.isoformat() if self.file_modified else None,
            "classifier_name": self.classifier_name,
            "category": self.category,
            "subcategory": self.subcategory,
            "value": self.value,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CatalogEntry(Base):
    """Запись каталога (папка с находками)"""
    __tablename__ = "catalog_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    scanner_id: Mapped[str] = mapped_column(String(36), ForeignKey("scanners.id"), nullable=False)

    folder_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    classifiers: Mapped[List[str]] = mapped_column(JSON, default=list)
    subcategories: Mapped[List[str]] = mapped_column(JSON, default=list)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)

    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scanner: Mapped[Scanner] = relationship("Scanner", back_populates="catalog_entries")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scanner_id": self.scanner_id,
            "folder_path": self.folder_path,
            "source_type": self.source_type,
            "classifiers": self.classifiers,
            "subcategories": self.subcategories,
            "findings_count": self.findings_count,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class FailedFile(Base):
    """Файлы, которые не удалось обработать"""
    __tablename__ = "failed_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    scanner_id: Mapped[str] = mapped_column(String(36), ForeignKey("scanners.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("scan_tasks.id"), nullable=False)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scanner: Mapped[Scanner] = relationship("Scanner", back_populates="failed_files")
    task: Mapped[ScanTask] = relationship("ScanTask", back_populates="failed_files")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scanner_id": self.scanner_id,
            "task_id": self.task_id,
            "file_path": self.file_path,
            "error": self.error,
            "error_type": self.error_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Индексы
Index("idx_scanners_status", Scanner.status)
Index("idx_scanners_last_heartbeat", Scanner.last_heartbeat)
Index("idx_resources_enabled", Resource.enabled)
Index("idx_resources_type", Resource.type)
Index("idx_schedules_next_run", Schedule.next_run)
Index("idx_schedules_enabled", Schedule.enabled)
Index("idx_tasks_status", ScanTask.status)
Index("idx_tasks_assigned_at", ScanTask.assigned_at)
Index("idx_findings_file_path", Finding.file_path)
Index("idx_findings_category", Finding.category)
Index("idx_catalog_folder_path", CatalogEntry.folder_path)