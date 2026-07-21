# manager/src/api/scanner.py

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import logging

from ..db import models, session
from .resources import get_default_config, deep_merge

logger = logging.getLogger(__name__)

# ============================================================
# ✅ РОУТЕР (ДОЛЖЕН БЫТЬ ПЕРВЫМ)
# ============================================================
router = APIRouter(prefix="/api/scanner", tags=["scanner"])

# ============================================================
# МОДЕЛИ
# ============================================================

class RegisterRequest(BaseModel):
    name: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    scan_interval: Optional[int] = 10

class HeartbeatRequest(BaseModel):
    scanner_id: int
    status: Optional[str] = "idle"
    current_task_id: Optional[int] = None

class ScannerFinding(BaseModel):
    file_path: str
    line_number: Optional[int] = 0
    category: str
    subcategory: Optional[str] = None
    value: str
    confidence: Optional[float] = 1.0
    context: Optional[str] = None
    severity: Optional[str] = None
    rule_id: Optional[str] = None
    column: Optional[int] = None
    matched_text: Optional[str] = None
    finding_id: Optional[str] = None

class FailedFilePayload(BaseModel):
    path: str
    error: str
    error_type: Optional[str] = None

class ScanStats(BaseModel):
    files_scanned: int = 0
    files_failed: int = 0
    files_with_findings: Optional[int] = 0
    total_findings: Optional[int] = 0
    unique_findings: Optional[int] = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    category_stats: Optional[Dict[str, int]] = {}
    error: Optional[str] = None

class ResultsPayload(BaseModel):
    findings: List[ScannerFinding] = []
    failed_files: List[FailedFilePayload] = []
    stats: ScanStats = ScanStats()

# ============================================================
# КОНСТАНТЫ
# ============================================================
TASK_TIMEOUT_MINUTES = 30

# ============================================================
# ЭНДПОИНТЫ
# ============================================================

@router.post("/register")
async def register_scanner(
    request: Request,
    db: Session = Depends(session.get_db)
):
    """Регистрация сканера"""
    try:
        data = await request.json()
    except:
        data = {}
    
    logger.info(f"Register request: {data}")
    
    name = data.get("name")
    hostname = data.get("hostname")
    ip_address = data.get("ip_address")
    scan_interval = data.get("scan_interval", 10)
    
    if not name:
        raise HTTPException(400, "Missing 'name' field")
    
    existing = db.query(models.Scanner).filter(models.Scanner.name == name).first()
    if existing:
        existing.status = "active"
        existing.last_heartbeat = datetime.utcnow()
        if hostname:
            existing.hostname = hostname
        if ip_address:
            existing.ip_address = ip_address
        if scan_interval:
            existing.scan_interval = scan_interval
        db.commit()
        db.refresh(existing)
        return {
            "scanner_id": existing.id,
            "status": "updated",
            "message": f"Scanner '{name}' updated",
            "name": name
        }
    
    scanner = models.Scanner(
        name=name,
        hostname=hostname,
        ip_address=ip_address,
        scan_interval=scan_interval,
        status="active",
        last_heartbeat=datetime.utcnow()
    )
    db.add(scanner)
    db.commit()
    db.refresh(scanner)
    
    return {
        "scanner_id": scanner.id,
        "status": "registered",
        "message": f"Scanner '{name}' registered",
        "name": name
    }


@router.post("/heartbeat")
async def heartbeat(
    request: Request,
    db: Session = Depends(session.get_db)
):
    """Обновление heartbeat сканера"""
    try:
        data = await request.json()
    except:
        data = {}
    
    scanner_id = data.get("scanner_id")
    if not scanner_id:
        raise HTTPException(400, "Missing 'scanner_id'")
    
    scanner = db.query(models.Scanner).filter(models.Scanner.id == int(scanner_id)).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    
    scanner.last_heartbeat = datetime.utcnow()
    scanner.status = "active"
    db.commit()
    
    return {"status": "ok"}


@router.get("/tasks/pending")
def get_pending_task(
    scanner_id: int = Query(..., description="ID сканера"),
    db: Session = Depends(session.get_db)
):
    """Получить следующее задание для сканера"""
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    
    scanner.last_heartbeat = datetime.utcnow()
    db.commit()
    
    # Освобождаем зависшие задания
    timeout_threshold = datetime.utcnow() - timedelta(minutes=TASK_TIMEOUT_MINUTES)
    stale_tasks = db.query(models.ScanTask).filter(
        and_(
            models.ScanTask.status == "assigned",
            models.ScanTask.assigned_at < timeout_threshold
        )
    ).all()
    
    for task in stale_tasks:
        logger.warning(f"[Task] Releasing stale task {task.id}")
        task.status = "pending"
        task.assigned_to = None
        task.assigned_at = None
    db.commit()
    
    task = db.query(models.ScanTask).filter(
        models.ScanTask.status == "pending"
    ).order_by(models.ScanTask.created_at).first()
    
    if not task:
        return {"task": None}
    
    task = db.query(models.ScanTask).filter(
        and_(
            models.ScanTask.id == task.id,
            models.ScanTask.status == "pending"
        )
    ).first()
    
    if not task:
        return {"task": None}
    
    resource = db.query(models.Resource).filter(models.Resource.id == task.resource_id).first()
    if not resource:
        task.status = "failed"
        db.commit()
        raise HTTPException(404, "Resource not found")
    
    default_config = get_default_config()
    scan_config = default_config
    if resource.scan_config:
        scan_config = deep_merge(default_config, resource.scan_config)
    
    task.status = "assigned"
    task.assigned_to = scanner_id
    task.assigned_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"[Task] Task {task.id} assigned to scanner {scanner_id}")
    
    return {
        "task": {
            "id": task.id,
            "resource_id": task.resource_id,
            "path": resource.path,
            "scan_config": scan_config
        }
    }


@router.post("/tasks/{task_id}/results")
async def submit_results(
    task_id: int,
    request: Request,
    db: Session = Depends(session.get_db)
):
    """Принять результаты сканирования"""
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    
    logger.info(f"Results for task {task_id}: {len(payload.get('findings', []))} findings")
    
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    if task.status != "assigned":
        raise HTTPException(400, f"Task status is {task.status}, expected 'assigned'")
    
    # Сохраняем findings
    for finding_data in payload.get("findings", []):
        file_path = finding_data.get("file_path", finding_data.get("filepath", ""))
        line_number = finding_data.get("line_number", finding_data.get("line", 0))
        category = finding_data.get("category", "")
        subcategory = finding_data.get("subcategory", finding_data.get("sub_type", ""))
        value = finding_data.get("value", finding_data.get("matched_text", ""))
        confidence = finding_data.get("confidence", 1.0)
        context = finding_data.get("context", "")
        
        finding = models.Finding(
            task_id=task_id,
            resource_id=task.resource_id,
            file_path=file_path,
            line_number=line_number or 0,
            category=category,
            subcategory=subcategory,
            value=value,
            confidence=int(confidence * 100) if confidence else 100,
            context=context
        )
        db.add(finding)
    
    # Сохраняем catalog_entries
    for entry in payload.get("catalog_entries", []):
        folder_path = entry.get("path", "")
        if not folder_path:
            continue
        
        metadata = entry.get("metadata", {})
        classifiers = metadata.get("classifiers", {})
        total_findings = metadata.get("total_findings", 0)
        file_count = metadata.get("file_count", 0)
        last_scanned = metadata.get("last_scanned", datetime.utcnow().isoformat())
        
        existing = db.query(models.CatalogEntry).filter(
            models.CatalogEntry.path == folder_path
        ).first()
        
        if existing:
            existing_metadata = existing.entry_metadata or {}
            existing_classifiers = existing_metadata.get("classifiers", {})
            for cat, info in classifiers.items():
                if cat in existing_classifiers:
                    existing_classifiers[cat]["count"] += info.get("count", 0)
                    existing_classifiers[cat]["last_detected"] = info.get("last_detected", datetime.utcnow().isoformat())
                else:
                    existing_classifiers[cat] = info
            
            existing_metadata["classifiers"] = existing_classifiers
            existing_metadata["total_findings"] = existing_metadata.get("total_findings", 0) + total_findings
            existing_metadata["file_count"] = existing_metadata.get("file_count", 0) + file_count
            existing_metadata["last_scanned"] = last_scanned
            
            existing.entry_metadata = existing_metadata
            existing.updated_at = datetime.utcnow()
        else:
            catalog_entry = models.CatalogEntry(
                path=folder_path,
                entry_metadata=metadata
            )
            db.add(catalog_entry)
    
    # Сохраняем failed_files
    for failed in payload.get("failed_files", []):
        failed_file = models.FailedFile(
            task_id=task_id,
            file_path=failed.get("path", ""),
            error_message=failed.get("error", "")
        )
        db.add(failed_file)
    
    stats = payload.get("stats", {})
    task.status = "completed"
    task.completed_at = datetime.utcnow()
    task.findings_count = len(payload.get("findings", []))
    task.files_scanned = stats.get("files_scanned", 0)
    task.files_failed = stats.get("files_failed", 0)
    
    resource = db.query(models.Resource).filter(models.Resource.id == task.resource_id).first()
    if resource:
        resource.last_scanned_at = datetime.utcnow()
        resource.status = "ACTIVE"
    
    db.commit()
    
    logger.info(f"[Task] Task {task_id} completed by scanner {task.assigned_to}")
    
    return {
        "status": "accepted",
        "task_id": task_id,
        "findings_count": len(payload.get("findings", [])),
        "catalog_entries_count": len(payload.get("catalog_entries", [])),
        "failed_files_count": len(payload.get("failed_files", []))
    }


@router.get("/{scanner_id}")
def get_scanner_info(
    scanner_id: int,
    db: Session = Depends(session.get_db)
):
    """Получить информацию о сканере"""
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    
    current_task = db.query(models.ScanTask).filter(
        and_(
            models.ScanTask.assigned_to == scanner_id,
            models.ScanTask.status == "assigned"
        )
    ).first()
    
    return {
        "id": scanner.id,
        "name": scanner.name,
        "status": scanner.status,
        "last_heartbeat": scanner.last_heartbeat.isoformat() if scanner.last_heartbeat else None,
        "created_at": scanner.created_at.isoformat() if hasattr(scanner, 'created_at') and scanner.created_at else None,
        "current_task": {
            "id": current_task.id,
            "resource_id": current_task.resource_id,
            "assigned_at": current_task.assigned_at.isoformat() if current_task.assigned_at else None
        } if current_task else None
    }


@router.get("/tasks/assigned")
def get_assigned_tasks(
    db: Session = Depends(session.get_db)
):
    """Получить список всех assigned заданий (для мониторинга)"""
    tasks = db.query(models.ScanTask).filter(
        models.ScanTask.status == "assigned"
    ).order_by(models.ScanTask.assigned_at).all()
    
    return [
        {
            "id": t.id,
            "resource_id": t.resource_id,
            "assigned_to": t.assigned_to,
            "assigned_at": t.assigned_at.isoformat() if t.assigned_at else None,
            "created_at": t.created_at.isoformat()
        }
        for t in tasks
    ]


@router.post("/tasks/{task_id}/release")
def release_task(
    task_id: int,
    db: Session = Depends(session.get_db)
):
    """Принудительно освободить задание (для администратора)"""
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    if task.status != "assigned":
        raise HTTPException(400, f"Task is not assigned (status: {task.status})")
    
    old_scanner_id = task.assigned_to
    
    task.status = "pending"
    task.assigned_to = None
    task.assigned_at = None
    db.commit()
    
    logger.info(f"[Task] Task {task_id} released from scanner {old_scanner_id}")
    
    return {
        "status": "released",
        "task_id": task_id,
        "old_scanner_id": old_scanner_id
    }