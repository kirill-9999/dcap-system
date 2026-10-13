# manager/src/api/webui.py
"""
WebUI-совместимые эндпоинты Manager.

Дополняет базовое API Manager недостающими эндпоинтами, которые использует
каноничный WebUI (webui/templates/*.html), чтобы WebUI мог проксировать
свои /api/* запросы в Manager без дублирования чтения из БД.

Эндпоинты (все — аддитивные, не конфликтуют с существующими роутерами):
- GET  /api/stats                   — агрегированная статистика для дашборда
- GET  /api/scanners                — список сканеров (мн.ч., WebUI-формат)
- GET  /api/scanners/{id}           — сканер по id
- DELETE /api/scanners/{id}         — удалить сканер
- POST /api/scanners/{id}/ping      — ping сканера
- GET  /api/classifiers             — список уникальных категорий находок
- GET  /api/findings/count          — количество находок с фильтрацией
- POST /api/tasks/create            — создать ресурс + задание (WebUI-формат)
- POST /api/resources/create        — создать ресурс (WebUI-формат)
- GET  /api/access/resources        — ресурсы с данными о доступах
- GET  /api/access/resources/{id}/entries — права доступа к ресурсу
- GET  /api/access/alerts           — алерты доступа
- GET  /api/access/alerts/stats     — статистика алертов
- PUT  /api/access/alerts/{id}      — обновить статус алерта
- POST /api/audit/report/preview    — предпросмотр отчёта по аудиту
- POST /api/audit/report/export/excel — экспорт отчёта в Excel
- POST /api/audit/report/export/pdf — экспорт отчёта в PDF
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import io
import logging
import os
from urllib.parse import urlparse

from manager.src.db.session import get_db
from manager.src.db import models
from manager.src.auth.dependencies import require_admin, require_scanner, require_auditor
from manager.src.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webui"])


# ============================================================
# СТАТИСТИКА (дашборд)
# ============================================================

@router.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Агрегированная статистика для дашборда WebUI"""
    total_findings = db.query(models.Finding).count()

    active_scanners = db.query(models.Scanner).filter(
        models.Scanner.last_heartbeat >= datetime.utcnow() - timedelta(seconds=60)
    ).count()

    pending_tasks = db.query(models.ScanTask).filter(models.ScanTask.status == "pending").count()
    running_tasks = db.query(models.ScanTask).filter(models.ScanTask.status == "running").count()
    completed_tasks = db.query(models.ScanTask).filter(models.ScanTask.status == "completed").count()
    failed_tasks = db.query(models.ScanTask).filter(models.ScanTask.status == "failed").count()

    total_files_scanned = db.query(
        func.coalesce(func.sum(models.ScanTask.files_scanned), 0)
    ).scalar() or 0

    total_resources = db.query(models.Resource).count()

    findings_by_category = dict(
        db.query(models.Finding.category, func.count(models.Finding.id))
        .group_by(models.Finding.category).all()
    )

    findings_by_scanner = {}
    rows = (
        db.query(models.Scanner.name, func.count(models.Finding.id))
        .join(models.ScanTask, models.ScanTask.scanner_id == models.Scanner.id)
        .join(models.Finding, models.Finding.task_id == models.ScanTask.id)
        .group_by(models.Scanner.name).all()
    )
    for name, cnt in rows:
        if name:
            findings_by_scanner[name] = cnt

    tasks_by_status = {
        "pending": pending_tasks,
        "running": running_tasks,
        "completed": completed_tasks,
        "failed": failed_tasks,
    }

    return {
        "total_findings": total_findings,
        "active_scanners": active_scanners,
        "pending_tasks": pending_tasks,
        "running_tasks": running_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "total_files_scanned": total_files_scanned,
        "total_resources": total_resources,
        "findings_by_category": findings_by_category,
        "findings_by_scanner": findings_by_scanner,
        "tasks_by_status": tasks_by_status,
    }


# ============================================================
# СКАНЕРЫ (WebUI-формат, мн.ч.)
# ============================================================

def _scanner_dict(s, db: Session = None) -> dict:
    current_task = None
    total_files_scanned = 0
    total_findings = 0
    if db is not None:
        # Активное задание (BACKLOG-043): progress из heartbeat (День 39)
        task = (
            db.query(models.ScanTask)
            .filter(
                models.ScanTask.scanner_id == s.id,
                models.ScanTask.status.in_(["assigned", "running"]),
            )
            .order_by(models.ScanTask.id.desc())
            .first()
        )
        if task:
            current_task = {
                "id": task.id,
                "resource_id": task.resource_id,
                "progress": task.progress,
            }
        total_files_scanned = (
            db.query(func.coalesce(func.sum(models.ScanTask.files_scanned), 0))
            .filter(models.ScanTask.scanner_id == s.id)
            .scalar()
            or 0
        )
        total_findings = (
            db.query(func.count(models.Finding.id))
            .join(models.ScanTask, models.ScanTask.id == models.Finding.task_id)
            .filter(models.ScanTask.scanner_id == s.id)
            .scalar()
            or 0
        )
    return {
        "id": s.id,
        "name": s.name,
        "endpoint": None,
        "status": s.status,
        "last_heartbeat": s.last_heartbeat.isoformat() if s.last_heartbeat else None,
        "total_files_scanned": total_files_scanned,
        "total_findings": total_findings,
        "current_task": current_task,
        "created_at": s.registered_at.isoformat() if s.registered_at else None,
    }


@router.get("/api/scanners")
def get_scanners(db: Session = Depends(get_db)):
    """Список всех сканеров (WebUI-формат)"""
    # Помечаем устаревшие как inactive
    stale = db.query(models.Scanner).filter(
        models.Scanner.status.in_(["active", "ACTIVE"]),
        models.Scanner.last_heartbeat < datetime.utcnow() - timedelta(seconds=120),
    ).all()
    for s in stale:
        s.status = "inactive"
    if stale:
        db.commit()

    scanners = db.query(models.Scanner).order_by(models.Scanner.id).all()
    return [_scanner_dict(s, db) for s in scanners]


@router.get("/api/scanners/{scanner_id}")
def get_scanner(scanner_id: int, db: Session = Depends(get_db)):
    """Информация о сканере"""
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    return _scanner_dict(scanner, db)


@router.delete("/api/scanners/{scanner_id}")
def delete_scanner(
    scanner_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Удалить сканер (с опцией force для активных задач). Только Admin (BUG-049)."""
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")

    if not force:
        active = db.query(models.ScanTask).filter(
            models.ScanTask.scanner_id == scanner_id,
            models.ScanTask.status.in_(["pending", "assigned", "running"]),
        ).first()
        if active:
            raise HTTPException(409, "Scanner has active tasks. Use force=true.")

    if force:
        db.query(models.ScanTask).filter(
            models.ScanTask.scanner_id == scanner_id,
            models.ScanTask.status == "assigned",
        ).update({"scanner_id": None, "status": "pending"})

    db.delete(scanner)
    db.commit()
    return {"status": "deleted", "scanner_id": scanner_id}


@router.post("/api/scanners/{scanner_id}/ping")
def ping_scanner(
    scanner_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_scanner),
):
    """Отметить сканер активным (ping). Админ/Сканер (BUG-050)."""
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    scanner.status = "ACTIVE"
    scanner.last_heartbeat = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Scanner pinged"}


# ============================================================
# КЛАССИФИКАТОРЫ
# ============================================================

@router.get("/api/classifiers")
def get_classifiers(db: Session = Depends(get_db)):
    """Список всех уникальных категорий находок"""
    rows = db.query(models.Finding.category).distinct().order_by(models.Finding.category).all()
    return [r[0] for r in rows if r[0]]


# ============================================================
# СОЗДАНИЕ ЗАДАНИЯ / РЕСУРСА (WebUI-формат)
# ============================================================

def _apply_s3_connector(config: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Заполнить scan_config.connector.s3 для s3/minio ресурса (BUG-149).

    Legacy-эндпоинты WebUI (/api/tasks/create, /api/resources/create) не
    получали connector.s3 → S3LineConnector на сканере падал (bucket не
    задан) и задание возвращало 0 files. Здесь собираем connector.s3 из
    path (s3://bucket[/prefix]) аналогично POST /api/resources.
    Endpoint — из ENV S3_DEFAULT_ENDPOINT (как в resources.py) с fallback
    на host.docker.internal:9000 (WebUI-форма не даёт поле endpoint).
    """
    parsed = urlparse(path)
    if parsed.scheme not in ("s3", "minio") or not parsed.netloc:
        raise HTTPException(
            400, "S3 path must be 's3://bucket[/prefix]'"
        )
    config["connector"] = config.get("connector", {})
    config["connector"]["s3"] = {
        "endpoint": os.environ.get("S3_DEFAULT_ENDPOINT") or "host.docker.internal:9000",
        "bucket": parsed.netloc,
        "prefix": parsed.path.lstrip("/"),
        "secure": False,
        "use_path_style": True,
        "region": "us-east-1",
    }
    return config


@router.post("/api/tasks/create")
def create_task(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_scanner),
):
    """Создать ресурс (если нет) + задание (WebUI-формат). Админ/Сканер (BUG-051)."""
    resource_path = str(payload.get("resource_path") or "").strip()
    # BUG-059: нормализуем type (БД хранит lowercase 'filesystem', WebUI шлёт 'FILESYSTEM').
    resource_type = str(payload.get("resource_type") or "FILESYSTEM").lower()
    if not resource_path:
        raise HTTPException(400, "resource_path is required")

    # Путь может существовать только на хосте сканера (сканер НЕ в Docker),
    # а Manager может работать в контейнере. Поэтому проверка `exists()`
    # не является блокирующей — фактическое существование проверит сканер.
    if resource_type in ("filesystem", "FILESYSTEM") and not Path(resource_path).exists():
        logger.warning(f"Resource path not visible from Manager host, "
                       f"will be checked by scanner: {resource_path}")

    extensions = payload.get("extensions") or "txt,pdf,docx,xlsx,png,jpg,jpeg"
    max_file_size_mb = payload.get("max_file_size_mb") or 50
    recursive = bool(payload.get("recursive", True))

    resource = (
        db.query(models.Resource)
        .filter(models.Resource.type == resource_type, models.Resource.path == resource_path)
        .first()
    )
    if resource:
        resource_id = resource.id
    else:
        config = {
            "extensions": [e.strip() for e in extensions.split(",") if e.strip()],
            "max_file_size_mb": max_file_size_mb,
            "recursive": recursive,
        }
        # BUG-149 (v3.13.41): ресурсы s3/minio, созданные через WebUI, не получали
        # connector.s3 → построчный S3-конвейер падал и возвращал 0 files.
        # Собираем connector.s3 из path (аналогично POST /api/resources).
        if resource_type in ("s3", "minio"):
            config = _apply_s3_connector(config, resource_path)
        resource = models.Resource(path=resource_path, type=resource_type,
                                   status="ACTIVE", enabled=True,
                                   scan_config=config)
        db.add(resource)
        try:
            db.flush()
        except IntegrityError:
            # Конкурентное создание ресурса с тем же путём (load/parallel):
            # unique resources_path_key (по старым БД) или (path+type) —
            # переиспользуем существующий. BUG-059: ищем БЕЗ type.
            db.rollback()
            resource = (
                db.query(models.Resource)
                .filter(models.Resource.path == resource_path)
                .first()
            )
            if resource is None:
                raise HTTPException(500, f"Resource creation conflict for {resource_path}")
            resource_id = resource.id
        else:
            resource_id = resource.id

    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource_path,
        # День 53.1a: тип источника из ресурса (lowercase — как Resource.type).
        source_type=(resource.type or "filesystem").lower(),
        status="pending",
        files_scanned=0,
        files_failed=0,
        findings_count=0,
    )
    db.add(task)
    db.flush()
    task_id = task.id
    db.commit()

    return {
        "success": True,
        "task_id": task_id,
        "resource_id": resource_id,
        "resource_path": resource_path,
        "message": f"Задание создано для {resource_path}",
    }


@router.post("/api/resources/create")
def create_resource_webui(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Создать новый ресурс (WebUI-формат). Только Admin (BUG-052)."""
    # BUG-059: нормализуем type (БД хранит lowercase).
    resource_type = str(payload.get("type") or "FILESYSTEM").lower()
    resource_path = str(payload.get("path") or "").strip()
    enabled = bool(payload.get("enabled", True))
    if not resource_path:
        raise HTTPException(400, "path is required")

    existing = (
        db.query(models.Resource)
        .filter(models.Resource.type == resource_type, models.Resource.path == resource_path)
        .first()
    )
    if existing:
        raise HTTPException(400, "Resource already exists")

    extensions = payload.get("extensions") or "txt,pdf,docx,xlsx,png,jpg,jpeg"
    max_file_size_mb = payload.get("max_file_size_mb") or 50
    recursive = bool(payload.get("recursive", True))
    config = {
        "extensions": [e.strip() for e in extensions.split(",") if e.strip()],
        "max_file_size_mb": max_file_size_mb,
        "recursive": recursive,
    }
    # BUG-149 (v3.13.41): connector.s3 для s3/minio ресурсов (см. create_task).
    if resource_type in ("s3", "minio"):
        config = _apply_s3_connector(config, resource_path)

    resource = models.Resource(
        path=resource_path,
        type=resource_type,
        status="ACTIVE",
        enabled=enabled,
        scan_config=config,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    return {
        "success": True,
        "resource_id": resource.id,
        "message": f"Resource {resource_path} created",
    }


# ============================================================
# ДОСТУП / ПРАВА (АЛИАС на /api/permissions/*)
# ============================================================

@router.get("/api/access/resources")
def get_access_resources(db: Session = Depends(get_db)):
    """Ресурсы с информацией о правах доступа"""
    resources = db.query(models.Resource).order_by(models.Resource.path).all()

    result = []
    for r in resources:
        entries_count = db.query(models.AccessEntry).filter(
            models.AccessEntry.resource_id == r.id,
            # BUG-089 (TASK-056, v3.13.22): is_active — Boolean; сравнение с 1
            # работало только на SQLite, на PostgreSQL → 500
            # (operator does not exist: boolean = integer).
            models.AccessEntry.is_active == True,  # noqa: E712
        ).count()
        alerts_count = db.query(models.AccessAlert).filter(
            models.AccessAlert.resource_id == r.id
        ).count()
        open_alerts_count = db.query(models.AccessAlert).filter(
            models.AccessAlert.resource_id == r.id,
            models.AccessAlert.status == "open",
        ).count()
        result.append({
            "id": r.id,
            "type": r.type,
            "path": r.path,
            "enabled": r.enabled,
            "owner": r.owner,
            "owner_sid": r.owner_sid,
            "is_sensitive": r.is_sensitive,
            "classification_level": r.classification_level,
            "permission_source": r.permission_source,
            "permission_last_synced": r.permission_last_synced.isoformat()
                if r.permission_last_synced else None,
            "entries_count": entries_count,
            "alerts_count": alerts_count,
            "open_alerts_count": open_alerts_count,
        })

    return {"total": len(result), "resources": result}


@router.get("/api/access/resources/{resource_id}/entries")
def get_access_entries(
    resource_id: int,
    principal: Optional[str] = None,
    principal_type: Optional[str] = None,
    permission_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Права доступа к ресурсу (WebUI-формат)"""
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found")

    query = db.query(models.AccessEntry).filter(
        models.AccessEntry.resource_id == resource_id,
        # BUG-089 (TASK-056, v3.13.22): Boolean-колонка, не integer.
        models.AccessEntry.is_active == True,  # noqa: E712
    )
    if principal:
        query = query.filter(models.AccessEntry.principal_name.ilike(f"%{principal}%"))
    if principal_type:
        query = query.filter(models.AccessEntry.principal_type == principal_type)
    if permission_type:
        query = query.filter(models.AccessEntry.permission_type == permission_type)

    total = query.count()
    entries = query.order_by(models.AccessEntry.principal_name).offset(offset).limit(limit).all()

    return {
        "resource_id": resource_id,
        "resource_path": resource.path,
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [e.to_dict() for e in entries],
    }


@router.get("/api/access/alerts")
def get_access_alerts(
    resource_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Список алертов по доступам (WebUI-формат)"""
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
        models.AccessAlert.created_at.desc()
    ).offset(offset).limit(limit).all()

    # Подставляем путь ресурса
    result = []
    for a in alerts:
        d = a.to_dict()
        if a.resource_id:
            res = db.query(models.Resource).filter(models.Resource.id == a.resource_id).first()
            d["resource_path"] = res.path if res else None
        else:
            d["resource_path"] = None
        result.append(d)

    return {"total": total, "limit": limit, "offset": offset, "alerts": result}


@router.get("/api/access/alerts/stats")
def get_access_alerts_stats(db: Session = Depends(get_db)):
    """Статистика по алертам доступа (WebUI-формат)"""
    query = db.query(models.AccessAlert)
    total = query.count()

    stats = {"total": total, "by_severity": {}, "by_status": {}, "by_type": {}}
    for severity in ["critical", "warning", "info"]:
        stats["by_severity"][severity] = query.filter(
            models.AccessAlert.severity == severity,
            models.AccessAlert.status == "open",
        ).count()
    for status in ["open", "acknowledged", "resolved", "ignored"]:
        stats["by_status"][status] = query.filter(
            models.AccessAlert.status == status
        ).count()
    type_rows = (
        db.query(models.AccessAlert.alert_type, func.count(models.AccessAlert.id))
        .filter(models.AccessAlert.status == "open")
        .group_by(models.AccessAlert.alert_type)
        .order_by(func.count(models.AccessAlert.id).desc())
        .limit(5).all()
    )
    stats["by_type"] = {t[0]: t[1] for t in type_rows}
    return stats


@router.put("/api/access/alerts/{alert_id}")
def update_access_alert_status(
    alert_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Обновить статус алерта (open/acknowledged/resolved/ignored). Админ/Аудитор (BUG-053)."""
    status = payload.get("status")
    if status not in ["open", "acknowledged", "resolved", "ignored"]:
        raise HTTPException(400, f"Invalid status: {status}")

    alert = db.query(models.AccessAlert).filter(models.AccessAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")

    old_status = alert.status
    alert.status = status
    if status in ["resolved", "ignored"]:
        alert.resolved_at = datetime.utcnow()
    db.commit()

    return {
        "status": "updated",
        "alert_id": alert_id,
        "old_status": old_status,
        "new_status": status,
    }


# ============================================================
# ОТЧЁТЫ ПО АУДИТУ
# ============================================================

def _audit_preview(db: Session, data: Dict[str, Any]) -> dict:
    days = int(data.get("days", 7))
    event_type = data.get("event_type")
    user = data.get("user")
    file_path = data.get("file_path")
    agent_id = data.get("agent_id")

    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(models.AuditLog).filter(models.AuditLog.created_at >= since)
    if event_type:
        query = query.filter(models.AuditLog.event_type == event_type)
    if user:
        query = query.filter(models.AuditLog.user.ilike(f"%{user}%"))
    if file_path:
        query = query.filter(models.AuditLog.file_path.ilike(f"%{file_path}%"))
    if agent_id:
        query = query.filter(models.AuditLog.agent_id == agent_id)

    total = query.count()

    type_rows = (
        db.query(models.AuditLog.event_type, func.count(models.AuditLog.id))
        .filter(models.AuditLog.created_at >= since)
        .group_by(models.AuditLog.event_type)
        .order_by(func.count(models.AuditLog.id).desc())
        .all()
    )
    user_rows = (
        db.query(models.AuditLog.user, func.count(models.AuditLog.id))
        .filter(models.AuditLog.created_at >= since)
        .filter(models.AuditLog.user.isnot(None))
        .filter(models.AuditLog.user != "")
        .group_by(models.AuditLog.user)
        .order_by(func.count(models.AuditLog.id).desc())
        .limit(10).all()
    )
    events = (
        query.order_by(models.AuditLog.created_at.desc()).limit(100).all()
    )

    return {
        "total": total,
        "days": days,
        "type_stats": [{"type": t or "unknown", "count": c} for t, c in type_rows],
        "top_users": [{"user": u, "count": c} for u, c in user_rows],
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "user": e.user,
                "file_path": e.file_path,
                "source_host": e.source_host,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.post("/api/audit/report/preview")
def preview_audit_report(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Предпросмотр данных для отчёта по аудиту. Админ/Аудитор (BUG-054)."""
    return _audit_preview(db, payload)


@router.post("/api/audit/report/export/excel")
def export_audit_report_excel(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Экспорт отчёта по аудиту в Excel. Админ/Аудитор (BUG-054)."""
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook

    preview = _audit_preview(db, payload)

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Сводка"
    ws1.append(["Отчет по аудиту"])
    ws1.append([f"Период: {preview['days']} дней"])
    ws1.append([f"Всего событий: {preview['total']}"])
    ws1.append([])
    ws1.append(["Тип события", "Количество"])
    for stat in preview["type_stats"]:
        ws1.append([stat["type"], stat["count"]])
    ws1.append([])
    ws1.append(["Топ пользователи"])
    ws1.append(["Пользователь", "Событий"])
    for u in preview["top_users"]:
        ws1.append([u["user"], u["count"]])

    ws2 = wb.create_sheet("Детали")
    ws2.append(["ID", "Тип", "Пользователь", "Файл", "Источник", "Время"])
    for e in preview["events"]:
        ws2.append([e["id"], e["event_type"], e["user"], e["file_path"], e["source_host"], e["created_at"]])

    for ws in wb.worksheets:
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            ws.column_dimensions[column].width = min(max_length + 2, 50)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"audit_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/api/audit/report/export/pdf")
def export_audit_report_pdf(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Экспорт отчёта по аудиту в PDF. Админ/Аудитор (BUG-054)."""
    from fastapi.responses import StreamingResponse
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    preview = _audit_preview(db, payload)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Отчет по аудиту", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Period: {preview['days']} days", styles['Normal']))
    story.append(Paragraph(f"Total events: {preview['total']}", styles['Normal']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("Event types", styles['Heading2']))
    table_data = [["Type", "Count"]]
    for stat in preview["type_stats"]:
        table_data.append([str(stat["type"]), str(stat["count"])])
    t = Table(table_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    story.append(Paragraph("Top users", styles['Heading2']))
    table_data = [["User", "Events"]]
    for u in preview["top_users"]:
        table_data.append([str(u["user"]), str(u["count"])])
    t = Table(table_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    story.append(Paragraph(f"Last events (first 50 of {len(preview['events'])})", styles['Heading2']))
    table_data = [["Type", "User", "File", "Time"]]
    for e in preview["events"][:50]:
        fp = str(e["file_path"] or "")
        if len(fp) > 50:
            fp = fp[:50] + "..."
        table_data.append([str(e["event_type"] or ""), str(e["user"] or ""), fp, str(e["created_at"] or "")[:19]])
    t = Table(table_data, colWidths=[60, 80, 200, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)

    filename = f"audit_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
