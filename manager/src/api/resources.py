from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..db import models, session

router = APIRouter(prefix="/api/resources", tags=["resources"])

def get_default_config():
    """Вернуть конфиг сканирования по умолчанию"""
    return {
        "classifiers": {
            "pii": {
                "enabled": True,
                "min_confidence": 0.5,
                "ocr_enabled": True
            },
            "credentials": {
                "enabled": True
            },
            "code": {
                "enabled": True
            }
        },
        "scan": {
            "extensions": ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
            "recursive": True,
            "max_file_size_mb": 50
        },
        "reporting": {
            "collect_catalog": True,
            "include_context": True,
            "context_lines": 3
        }
    }

def deep_merge(base: dict, override: dict) -> dict:
    """Глубокое слияние двух словарей"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

@router.get("")
def list_resources(
    db: Session = Depends(session.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Получить список всех ресурсов"""
    resources = db.query(models.Resource).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "path": r.path,
            "type": r.type,
            "status": r.status,
            "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
            "enabled": r.enabled,
            "scan_interval": r.scan_interval,
            "schedule_enabled": r.schedule_enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in resources
    ]

@router.post("")
def create_resource(
    path: str = Query(..., min_length=1),
    type: str = Query("FILESYSTEM"),
    db: Session = Depends(session.get_db)
):
    """Создать новый ресурс"""
    # Проверяем, не существует ли уже
    existing = db.query(models.Resource).filter(models.Resource.path == path).first()
    if existing:
        raise HTTPException(400, f"Resource with path '{path}' already exists")
    
    resource = models.Resource(
        path=path,
        type=type,
        status="ACTIVE",
        enabled=True,
        scan_config=get_default_config(),
        scan_interval=3600,
        schedule_enabled=False
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    
    return {
        "id": resource.id,
        "path": resource.path,
        "type": resource.type,
        "status": resource.status,
        "message": "Resource created successfully"
    }

@router.delete("/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(session.get_db)):
    """Удалить ресурс"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")
    
    # Удаляем связанные записи
    db.query(models.CatalogEntry).filter(models.CatalogEntry.resource_id == resource_id).delete()
    db.query(models.Finding).filter(models.Finding.resource_id == resource_id).delete()
    db.query(models.ScanTask).filter(models.ScanTask.resource_id == resource_id).delete()
    
    db.delete(resource)
    db.commit()
    
    return {"status": "deleted", "id": resource_id}

@router.post("/{resource_id}/scan")
def scan_resource(resource_id: int, db: Session = Depends(session.get_db)):
    """Запустить сканирование ресурса"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")
    
    if not resource.enabled:
        raise HTTPException(400, "Resource is disabled")
    
    # Создаем задание
    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource.path,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "success": True,
        "task_id": task.id,
        "resource_id": resource_id,
        "status": "pending",
        "message": "Scan task created"
    }

@router.get("/{resource_id}/config")
def get_resource_config(resource_id: int, db: Session = Depends(session.get_db)):
    """Получить конфигурацию сканирования для ресурса"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")
    
    return {
        "id": resource.id,
        "path": resource.path,
        "scan_config": resource.scan_config or get_default_config(),
        "scan_interval": resource.scan_interval or 3600,
        "schedule_enabled": resource.schedule_enabled or False,
        "cron_expression": resource.cron_expression
    }

@router.put("/{resource_id}/config")
def update_resource_config(
    resource_id: int,
    config_data: dict,
    db: Session = Depends(session.get_db)
):
    """Обновить конфигурацию сканирования для ресурса"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")
    
    # Обновляем поля
    if "scan_config" in config_data:
        resource.scan_config = config_data["scan_config"]
    if "scan_interval" in config_data:
        resource.scan_interval = config_data["scan_interval"]
    if "schedule_enabled" in config_data:
        resource.schedule_enabled = config_data["schedule_enabled"]
    if "cron_expression" in config_data:
        resource.cron_expression = config_data["cron_expression"]
    
    resource.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "updated",
        "id": resource.id,
        "message": "Configuration updated successfully"
    }