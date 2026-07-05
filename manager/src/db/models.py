# -*- coding: utf-8 -*-
"""
DCAP Manager - Database Models (SQLite compatible)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, 
    JSON, Enum as SQLEnum, BigInteger, ForeignKey,
    Text, Float, Index
)
from sqlalchemy.orm import declarative_base, relationship
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


class Scanner(Base):
    """Модель агента сканирования"""
    __tablename__ = "scanners"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    endpoint = Column(String(255), nullable=False)
    public_cert = Column(Text, nullable=True)
    
    status = Column(SQLEnum(ScannerStatus), default=ScannerStatus.OFFLINE)
    last_heartbeat = Column(DateTime, nullable=True)
    
    total_files_scanned = Column(BigInteger, default=0)
    total_findings = Column(BigInteger, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = relationship("ScanTask", back_populates="scanner")
    findings = relationship("Finding", back_populates="scanner")
    catalog_entries = relationship("CatalogEntry", back_populates="scanner")
    failed_files = relationship("FailedFile", back_populates="scanner")
    
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
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)
    path = Column(String(500), nullable=False)
    
    credentials_encrypted = Column(JSON, nullable=True)
    credentials_nonce = Column(JSON, nullable=True)
    
    enabled = Column(Boolean, default=True)
    config = Column(JSON, nullable=True)
    
    last_scan_start = Column(DateTime, nullable=True)
    last_scan_end = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    schedules = relationship("Schedule", back_populates="resource")
    tasks = relationship("ScanTask", back_populates="resource")
    
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
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    
    cron_expression = Column(String(100), nullable=False)
    priority = Column(Integer, default=0)
    max_files_per_batch = Column(Integer, default=500)
    
    enabled = Column(Boolean, default=True)
    
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    resource = relationship("Resource", back_populates="schedules")
    
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
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=True)
    
    path_filter = Column(String(500), nullable=True)
    
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    
    files_total = Column(Integer, default=0)
    files_scanned = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    
    assigned_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    resource = relationship("Resource", back_populates="tasks")
    scanner = relationship("Scanner", back_populates="tasks")
    findings = relationship("Finding", back_populates="task")
    failed_files = relationship("FailedFile", back_populates="task")
    
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

    id = Column(Integer, primary_key=True, autoincrement=True)
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=False)

    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)
    file_size = Column(BigInteger, nullable=False)
    file_modified = Column(DateTime, nullable=True)

    classifier_name = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=False)
    value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    detection_method = Column(String(50), nullable=False)
    context = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    scanner = relationship("Scanner", back_populates="findings")
    task = relationship("ScanTask", back_populates="findings")

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
    """Запись каталога — одна папка, глобальная для всех сканеров.
    folder_path уникален: при повторном скане запись перезаписывается (UPSERT).
    """
    __tablename__ = "catalog_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Глобальный каталог: folder_path уникален, не привязан к конкретному сканеру.
    # scanner_id — кто последний обновил запись (информационно, nullable).
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=True)
    folder_path = Column(String(500), nullable=False, unique=True)

    # Какие классификаторы нашли что-либо в этой папке, напр. ["pii", "credentials"]
    classifiers = Column(JSON, default=list)

    first_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    scanner = relationship("Scanner", back_populates="catalog_entries")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scanner_id": self.scanner_id,
            "folder_path": self.folder_path,
            "classifiers": self.classifiers,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FailedFile(Base):
    """Файлы, которые не удалось обработать"""
    __tablename__ = "failed_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=False)

    file_path = Column(String(500), nullable=False)
    error = Column(Text, nullable=False)
    error_type = Column(String(50), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    scanner = relationship("Scanner", back_populates="failed_files")
    task = relationship("ScanTask", back_populates="failed_files")

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