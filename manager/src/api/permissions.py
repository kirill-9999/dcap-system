# manager/src/api/permissions.py

"""
API для управления доступом к ресурсам

Эндпоинты:
- /api/permissions/mode — управление режимом сбора прав
- /api/permissions/sync — синхронизация прав
- /api/permissions/resources/{id} — получение прав ресурса
- /api/permissions/resources/{id}/effective — эффективные права
- /api/permissions/resources/{id}/excessive — избыточные права
- /api/permissions/resources/{id}/inheritance — анализ наследования
- /api/permissions/resources/{id}/report — полный отчет
- /api/permissions/alerts — управление алертами
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from manager.src.db.session import get_db
from manager.src.db import models
from manager.src.services.access_service import AccessService
from manager.src.services.access_config import get_access_config, AccessConfig

router = APIRouter(
    prefix="/api/permissions",
    tags=["permissions"]
)


# ============================================================
# Pydantic схемы
# ============================================================

class ModeResponse(BaseModel):
    """Ответ с информацией о текущем режиме"""
    current_mode: str
    available_modes: dict
    config: dict


class ModeSwitchRequest(BaseModel):
    """Запрос на переключение режима"""
    mode: str  # local, ad, mixed, remote


class SyncRequest(BaseModel):
    """Запрос на синхронизацию прав"""
    resource_id: int


class EffectivePermissionsResponse(BaseModel):
    """Ответ с эффективными правами"""
    resource_id: int
    principal: str
    permissions: List[str]


class AlertUpdateRequest(BaseModel):
    """Запрос на обновление статуса алерта"""
    status: str  # open, acknowledged, resolved, ignored


# ============================================================
# 1. Управление режимом
# ============================================================

@router.get("/mode", response_model=ModeResponse)
def get_mode(db: Session = Depends(get_db)):
    """Получить текущий режим сбора прав и список доступных коллекторов"""
    service = AccessService(db)
    config = get_access_config()
    
    return ModeResponse(
        current_mode=service.get_current_mode(),
        available_modes=service.get_available_modes(),
        config={
            "mode": config.mode,
            "scanner_endpoint": config.scanner_endpoint,
            "timeout_seconds": config.timeout_seconds,
            "excessive_days_threshold": config.excessive_days_threshold,
            "alerts_enabled": config.alerts_enabled,
            "auto_sync_on_scan": config.auto_sync_on_scan,
        }
    )


@router.post("/mode", response_model=ModeResponse)
def switch_mode(
    request: ModeSwitchRequest,
    db: Session = Depends(get_db)
):
    """Переключить режим сбора прав (local/remote/ad/mixed)"""
    if request.mode not in ["local", "remote", "ad", "mixed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode: {request.mode}. Supported: local, remote, ad, mixed"
        )
    
    service = AccessService(db)
    
    try:
        service.switch_mode(request.mode)
    except RuntimeError as e:
        raise HTTPException(503, f"Failed to switch mode: {str(e)}")
    
    return get_mode(db)


# ============================================================
# 1.5. Разрешение SID → имя (AD)
# ============================================================

@router.get("/resolve/{sid}")
def resolve_sid(
    sid: str,
    db: Session = Depends(get_db)
):
    """Разрешить SID в доменное имя пользователя/группы (AD)"""
    service = AccessService(db)
    collector = service.collector

    if not hasattr(collector, "resolve_principal"):
        raise HTTPException(
            400,
            "Resolve SID is only available for AD/mixed collector. "
            f"Current mode: {service.get_current_mode()}"
        )

    try:
        name = collector.resolve_principal(sid)
    except Exception as e:
        raise HTTPException(503, f"Failed to resolve SID: {str(e)}")

    return {
        "sid": sid,
        "name": name,
        "mode": service.get_current_mode(),
        "resolved": name is not None,
    }


# ============================================================
# 2. Синхронизация прав
# ============================================================

@router.post("/sync")
def sync_permissions(
    resource_id: int = Query(..., description="ID ресурса для синхронизации"),
    force: bool = Query(False, description="Принудительная синхронизация"),
    db: Session = Depends(get_db)
):
    """Синхронизировать права доступа для ресурса"""
    service = AccessService(db)
    
    try:
        result = service.sync_permissions(resource_id, force=force)
        return {
            "status": "success",
            "message": f"Permissions synced for resource {resource_id}",
            "resource_id": resource_id,
            "result": result
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(503, f"Sync failed: {str(e)}")


# ============================================================
# 3. Получение прав
# ============================================================

@router.get("/resources/{resource_id}")
def get_permissions(
    resource_id: int,
    principal: Optional[str] = None,
    principal_type: Optional[str] = None,
    permission_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Получить права доступа для ресурса с фильтрацией и пагинацией
    
    - principal: фильтр по имени субъекта (частичное совпадение)
    - principal_type: user, group, local_user, system, ad_user, ad_group
    - permission_type: read, write, full_control, modify, delete, etc.
    """
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    
    query = db.query(models.AccessEntry).filter(
        models.AccessEntry.resource_id == resource_id,
        models.AccessEntry.is_active == True
    )
    
    if principal:
        query = query.filter(models.AccessEntry.principal_name.ilike(f"%{principal}%"))
    if principal_type:
        query = query.filter(models.AccessEntry.principal_type == principal_type)
    if permission_type:
        query = query.filter(models.AccessEntry.permission_type == permission_type)
    
    total = query.count()
    entries = query.offset(offset).limit(limit).all()
    
    return {
        "resource_id": resource_id,
        "resource_path": resource.path,
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "principal_type": e.principal_type,
                "principal_name": e.principal_name,
                "principal_domain": e.principal_domain,
                "permission_type": e.permission_type,
                "permission_source": e.permission_source,
                "is_inherited": e.is_inherited,
                "inherited_from": e.inherited_from,
                "granted_at": e.granted_at.isoformat() if e.granted_at else None,
                "last_verified_at": e.last_verified_at.isoformat() if e.last_verified_at else None,
                "collector_source": e.collector_source,
            }
            for e in entries
        ]
    }


# ============================================================
# 4. Анализ прав
# ============================================================

@router.get("/resources/{resource_id}/effective")
def get_effective_permissions(
    resource_id: int,
    principal: str = Query(..., description="Пользователь или группа"),
    db: Session = Depends(get_db)
):
    """Получить эффективные права для пользователя/группы с деталями"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    
    service = AccessService(db)
    result = service.get_effective_permissions_detailed(resource_id, principal)
    
    return {
        "resource_id": resource_id,
        "resource_path": resource.path,
        "principal": result.get("principal"),
        "permissions": result.get("permissions", []),
        "sources": result.get("sources", [])
    }


@router.get("/resources/{resource_id}/excessive")
def get_excessive_permissions(
    resource_id: int,
    db: Session = Depends(get_db)
):
    """Найти избыточные права для ресурса"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    
    service = AccessService(db)
    issues = service.find_excessive_permissions(resource_id)
    
    return {
        "resource_id": resource_id,
        "resource_path": resource.path,
        "issues": issues,
        "count": len(issues)
    }


@router.get("/resources/{resource_id}/inheritance")
def analyze_inheritance(
    resource_id: int,
    db: Session = Depends(get_db)
):
    """Проанализировать наследование прав для ресурса"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    
    service = AccessService(db)
    return service.analyze_inheritance(resource_id)


# ============================================================
# 5. Отчеты
# ============================================================

@router.get("/resources/{resource_id}/report")
def get_access_report(
    resource_id: int,
    db: Session = Depends(get_db)
):
    """Получить полный отчет по доступам к ресурсу"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    
    service = AccessService(db)
    return service.get_access_report(resource_id)


@router.get("/resources/{resource_id}/trends")
def get_permission_trends(
    resource_id: int,
    days: int = Query(30, ge=1, le=365, description="Количество дней"),
    db: Session = Depends(get_db)
):
    """Получить тренды изменений прав за период"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    
    service = AccessService(db)
    return service.get_permission_trends(resource_id, days)


# ============================================================
# 6. Управление алертами
# ============================================================

@router.get("/alerts")
def get_alerts(
    resource_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Получить список алертов по доступам с фильтрацией
    
    - severity: critical, warning, info
    - status: open, acknowledged, resolved, ignored
    - alert_type: excessive_permission, sensitive_access, wide_access, etc.
    """
    query = db.query(models.AccessAlert)
    
    if resource_id:
        query = query.filter(models.AccessAlert.resource_id == resource_id)
    if severity:
        query = query.filter(models.AccessAlert.severity == severity)
    if status:
        query = query.filter(models.AccessAlert.status == status)
    if alert_type:
        query = query.filter(models.AccessAlert.alert_type == alert_type)
    
    total = query.count()
    alerts = query.order_by(
        models.AccessAlert.severity.desc(),
        models.AccessAlert.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": [
            {
                "id": a.id,
                "resource_id": a.resource_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "principal_name": a.principal_name,
                "description": a.description,
                "recommendation": a.recommendation,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                "resolved_by": a.resolved_by,
            }
            for a in alerts
        ]
    }


@router.get("/alerts/stats")
def get_alerts_stats(
    db: Session = Depends(get_db)
):
    """Получить статистику по алертам"""
    query = db.query(models.AccessAlert)
    total = query.count()
    
    stats = {
        "total": total,
        "by_severity": {},
        "by_status": {},
        "by_type": {}
    }
    
    # Статистика по важности
    for severity in ["critical", "warning", "info"]:
        stats["by_severity"][severity] = query.filter(
            models.AccessAlert.severity == severity,
            models.AccessAlert.status == "open"
        ).count()
    
    # Статистика по статусам
    for status in ["open", "acknowledged", "resolved", "ignored"]:
        stats["by_status"][status] = query.filter(
            models.AccessAlert.status == status
        ).count()
    
    # Статистика по типам (топ 5)
    from sqlalchemy import func
    type_stats = db.query(
        models.AccessAlert.alert_type,
        func.count(models.AccessAlert.id).label("count")
    ).filter(models.AccessAlert.status == "open").group_by(
        models.AccessAlert.alert_type
    ).order_by(func.count(models.AccessAlert.id).desc()).limit(5).all()
    
    stats["by_type"] = {t[0]: t[1] for t in type_stats}
    
    return stats


@router.put("/alerts/{alert_id}")
def update_alert_status(
    alert_id: int,
    request: AlertUpdateRequest,
    db: Session = Depends(get_db)
):
    """Обновить статус алерта (open → acknowledged/resolved/ignored)"""
    alert = db.query(models.AccessAlert).filter(models.AccessAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")
    
    if request.status not in ["open", "acknowledged", "resolved", "ignored"]:
        raise HTTPException(400, f"Invalid status: {request.status}")
    
    old_status = alert.status
    alert.status = request.status
    
    if request.status in ["resolved", "ignored"]:
        alert.resolved_at = datetime.utcnow()
    elif request.status == "acknowledged" and old_status == "open":
        # Подтверждение - просто меняем статус
        pass
    
    db.commit()
    
    return {
        "status": "updated",
        "alert_id": alert_id,
        "old_status": old_status,
        "new_status": request.status
    }


@router.post("/alerts/{alert_id}/generate")
def generate_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """Принудительно сгенерировать алерты для ресурса"""
    alert = db.query(models.AccessAlert).filter(models.AccessAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")
    
    if alert.resource_id is None:
        raise HTTPException(400, "Alert has no resource_id")
    
    service = AccessService(db)
    count = service.generate_alerts(alert.resource_id)
    
    return {
        "status": "generated",
        "resource_id": alert.resource_id,
        "alerts_count": count
    }