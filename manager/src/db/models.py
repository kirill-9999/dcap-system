from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

Base = declarative_base()

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(500), nullable=False, unique=True, index=True)
    type = Column(String(50), default="FILESYSTEM")
    status = Column(String(20), default="ACTIVE")
    last_scanned_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # НОВЫЕ ПОЛЯ ДЛЯ КОНФИГУРАЦИИ
    scan_config = Column(JSON, nullable=True)
    scan_interval = Column(Integer, default=3600)
    schedule_enabled = Column(Boolean, default=False)
    cron_expression = Column(String(100), nullable=True)


class ScanTask(Base):
    __tablename__ = "scan_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    status = Column(String(20), default="pending")
    assigned_to = Column(Integer, ForeignKey("scanners.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    findings_count = Column(Integer, default=0)
    files_scanned = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)


class Scanner(Base):
    __tablename__ = "scanners"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    manager_url = Column(String(200), nullable=False)
    status = Column(String(20), default="active")
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class Finding(Base):
    __tablename__ = "findings"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    line_number = Column(Integer, default=0)
    category = Column(String(50), nullable=False, index=True)
    subcategory = Column(String(50), nullable=True)
    value = Column(Text, nullable=False)
    confidence = Column(Integer, default=100)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CatalogEntry(Base):
    __tablename__ = "catalog_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(500), nullable=False, unique=True, index=True)  # Путь к папке
    entry_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FailedFile(Base):
    __tablename__ = "failed_files"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    error_message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)