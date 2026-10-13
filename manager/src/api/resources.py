import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..db import models, session
from manager.src.auth.dependencies import require_admin, require_scanner
from manager.src.auth.models import User
from manager.src.api.audit_helper import with_audit

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
    request: Request,
    path: str = Query(..., min_length=1),
    type: str = Query("FILESYSTEM"),  # noqa: A002
    endpoint: Optional[str] = Query(None, description="S3/MinIO endpoint (host:port)"),
    secure: bool = Query(False, description="S3: HTTPS"),
    use_path_style: bool = Query(True, description="S3: path-style addressing"),
    region: str = Query("us-east-1"),
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),
):
    """Создать новый ресурс (только Admin, BUG-046).

    День 53.1a (BACKLOG-097): поддержка S3/MinIO-ресурсов.
    - type нормализуется в lowercase (BUG-059);
    - уникальность по (path, type), а не только по path (uq_resources_path_type);
    - для type in (s3, minio) path = 's3://bucket[/prefix]', добавляется
      scan_config.connector.s3 с endpoint/secure/use_path_style/region;
    - endpoint для S3/MinIO обязателен: query-параметр или ENV
      S3_DEFAULT_ENDPOINT на хосте Manager, иначе 400 (день 53.3, вариант B);
    - секреты S3 в scan_config НЕ пишутся — только ENV на хосте сканера
      (S3_ACCESS_KEY / S3_SECRET_KEY), единая политика TASK-018.
    """
    type = type.lower()  # noqa: A001
    if type not in ("filesystem", "s3", "minio"):
        raise HTTPException(400, f"Unsupported resource type: {type!r}")

    # BUG-059 + uq_resources_path_type: уникальность по (path, type).
    existing = db.query(models.Resource).filter(
        models.Resource.path == path,
        models.Resource.type == type,
    ).first()
    if existing:
        raise HTTPException(
            400,
            f"Resource with path '{path}' and type '{type}' already exists",
        )

    scan_config = get_default_config()

    if type in ("s3", "minio"):
        parsed = urlparse(path)
        if parsed.scheme not in ("s3", "minio") or not parsed.netloc:
            raise HTTPException(400, "S3 path must be 's3://bucket[/prefix]'")
        scan_config["connector"] = scan_config.get("connector", {})
        # День 53.3 (BACKLOG-097, вариант B): убран неявный хардкод
        # host.docker.internal:9000. Endpoint — либо явно в query, либо из
        # ENV S3_DEFAULT_ENDPOINT на хосте Manager; иначе 400.
        resolved_endpoint = endpoint or os.environ.get("S3_DEFAULT_ENDPOINT")
        if not resolved_endpoint:
            raise HTTPException(
                400,
                "endpoint is required for S3/MinIO resources "
                "(or set S3_DEFAULT_ENDPOINT in env)",
            )
        scan_config["connector"]["s3"] = {
            "endpoint": resolved_endpoint,
            "bucket": parsed.netloc,
            "prefix": parsed.path.lstrip("/"),
            "secure": secure,
            "use_path_style": use_path_style,
            "region": region,
        }

    resource = models.Resource(
        path=path,
        type=type,
        status="ACTIVE",
        enabled=True,
        scan_config=scan_config,
        scan_interval=3600,
        schedule_enabled=False,
    )

    # BUG-202 (v3.13.39): создание ресурса + аудит = одна транзакция.
    meta = {"action": "created", "resource_id": None, "path": path, "type": type}
    with with_audit(
        db, "resource_created", request=request, user=user, file_path=path, metadata=meta
    ):
        db.add(resource)
        db.flush()
        meta["resource_id"] = resource.id
    db.refresh(resource)

    return {
        "id": resource.id,
        "path": resource.path,
        "type": resource.type,
        "status": resource.status,
        "message": "Resource created successfully"
    }

@router.delete("/{resource_id}", status_code=204)
def delete_resource(
    resource_id: int,
    request: Request,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),
):
    """Удалить ресурс (только Admin, BUG-046).

    BUG-202 (v3.13.39): удаление + аудит = одна транзакция.
    BUG-150 (v3.13.41): FK с NO ACTION не давали удалить ресурс —
    миграция 007_add_cascade_deletes перевела их на ON DELETE CASCADE;
    теперь DELETE /api/resources/{id} → 204, связанные записи удаляются
    каскадом (findings, scan_tasks, catalog_entries, access_entries,
    access_alerts, permission_changes, failed_files, schedules).
    """
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")

    meta = {
        "action": "deleted",
        "resource_id": resource_id,
        "path": resource.path,
        "type": resource.type,
    }
    with with_audit(
        db, "resource_deleted", request=request, user=user, file_path=resource.path,
        metadata=meta,
    ):
        # Удаляем связанные записи
        db.query(models.CatalogEntry).filter(models.CatalogEntry.resource_id == resource_id).delete()
        db.query(models.Finding).filter(models.Finding.resource_id == resource_id).delete()
        db.query(models.ScanTask).filter(models.ScanTask.resource_id == resource_id).delete()
        db.query(models.FailedFile).filter(models.FailedFile.resource_id == resource_id).delete()
        db.query(models.AccessEntry).filter(models.AccessEntry.resource_id == resource_id).delete()
        db.query(models.AccessAlert).filter(models.AccessAlert.resource_id == resource_id).delete()
        db.query(models.PermissionChange).filter(models.PermissionChange.resource_id == resource_id).delete()
        db.query(models.Schedule).filter(models.Schedule.resource_id == resource_id).delete()

        db.delete(resource)
        db.flush()

    return None

@router.post("/{resource_id}/scan")
def scan_resource(
    resource_id: int,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_scanner),
):
    """Запустить сканирование ресурса (Админ/Сканер, BUG-046)."""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")
    
    if not resource.enabled:
        raise HTTPException(400, "Resource is disabled")
    
    # Создаем задание
    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource.path,
        # День 53.1a: тип источника из ресурса (lowercase — как Resource.type).
        source_type=(resource.type or "filesystem").lower(),
        status="pending",
        created_at=datetime.utcnow(),
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
    request: Request,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),
):
    """Обновить конфигурацию сканирования для ресурса (только Admin, BUG-046).

    BUG-202 (v3.13.39): изменение + аудит = одна транзакция.
    """
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

    meta = {
        "action": "updated",
        "resource_id": resource_id,
        "path": resource.path,
        "changed_fields": sorted(k for k in ("scan_config", "scan_interval", "schedule_enabled", "cron_expression") if k in config_data),
    }
    with with_audit(
        db, "resource_updated", request=request, user=user, file_path=resource.path,
        metadata=meta,
    ):
        db.flush()

    return {
        "status": "updated",
        "id": resource.id,
        "message": "Configuration updated successfully"
    }