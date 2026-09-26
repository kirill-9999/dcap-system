# manager/src/api/scanner.py

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import logging
import base64

from ..db import models, session
from .resources import get_default_config, deep_merge
from manager.src.auth.dependencies import require_admin
from manager.src.auth.models import User
from ..metrics import (
    track_task_submitted,
    track_task_completed,
    track_findings,
)

logger = logging.getLogger(__name__)

# ============================================================
# [OK] РОУТЕР (ДОЛЖЕН БЫТЬ ПЕРВЫМ)
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

class HeartbeatProgress(BaseModel):
    files_scanned: int = 0
    total: Optional[int] = None

class HeartbeatRequest(BaseModel):
    scanner_id: int
    status: Optional[str] = "idle"
    current_task_id: Optional[int] = None
    task_id: Optional[int] = None
    progress: Optional[HeartbeatProgress] = None

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
STALE_THRESHOLD_MINUTES = 2


def _mark_stale_scanners(db: Session):  # BUG-034.1 (06045225 R): stale assigned->failed
    """Mark inactive stale scanners; BUG-034.1: failed their assigned tasks."""
    threshold = datetime.utcnow() - timedelta(minutes=STALE_THRESHOLD_MINUTES)
    stale = db.query(models.Scanner).filter(
        models.Scanner.status.in_(["active", "ACTIVE"]),
        models.Scanner.last_heartbeat < threshold
    ).all()
    if not stale:
        return

    for s in stale:
        # BUG-034.1: tasks assigned/running on stale scanner -> failed
        _ids_06045225 = [r[0] for r in db.query(models.ScanTask.id).filter(
            models.ScanTask.scanner_id == s.id,
            models.ScanTask.status.in_(["assigned", "running"])).all()]
        if _ids_06045225:
            db.query(models.ScanTask).filter(
                models.ScanTask.id.in_(_ids_06045225)
            ).update({models.ScanTask.status: "failed",
                       models.ScanTask.completed_at: datetime.utcnow()},
                      synchronize_session=False)
            db.commit()

        s.status = "inactive"
    db.commit()

@router.get("")
def list_scanners(db: Session = Depends(session.get_db)):
    """Список всех сканеров с актуальным статусом"""
    _mark_stale_scanners(db)

    scanners = db.query(models.Scanner).order_by(models.Scanner.id).all()
    result = []
    for s in scanners:
        result.append({
            "id": s.id,
            "name": s.name,
            "hostname": s.hostname,
            "ip_address": s.ip_address,
            "status": s.status,
            "last_heartbeat": s.last_heartbeat.isoformat() if s.last_heartbeat else None,
            "scan_interval": s.scan_interval,
        })
    return result


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
    """Обновление heartbeat сканера (День 39: + task_id и progress)."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    if not isinstance(data, dict):
        raise HTTPException(400, "JSON body must be an object")

    scanner_id = data.get("scanner_id")
    if not scanner_id:
        raise HTTPException(400, "Missing 'scanner_id'")
    try:
        scanner_id_int = int(scanner_id)
    except (TypeError, ValueError):
        raise HTTPException(400, f"Invalid 'scanner_id': {scanner_id!r}")

    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id_int).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    
    scanner.last_heartbeat = datetime.utcnow()
    scanner.status = "active"
    
    # Обновление прогресса задания
    task_id = data.get("task_id") or data.get("current_task_id")
    if task_id:
        try:
            task_id_int = int(task_id)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Invalid 'task_id': {task_id!r}")
        task = db.query(models.ScanTask).filter(
            models.ScanTask.id == task_id_int
        ).first()
        # BUG-027.3: сканер слал heartbeat(status="busy", task_id=...) при
        # живой задаче — переводим назначенную задачу в running.
        hb_status = (data.get("status") or "").strip().lower()
        if task and task.status in ("assigned", "pending", "running") and hb_status == "busy":
            task.status = "running"

        if task and task.status in ("assigned", "running"):
            progress_data = data.get("progress") or {}
            files_scanned = progress_data.get("files_scanned", 0)
            total = progress_data.get("total")
            # BUG-027.1: если total не пришёл с heartbeat — берём из задачи.
            if total is None:
                total = (task.progress or {}).get("total")
            percent = None
            # BUG-027.1: percent только при total > 0 (иначе не 100% на 70%)
            if total and int(total) > 0:
                percent = round((files_scanned / total) * 100, 1)
                if percent > 100:
                    percent = 100.0
            task.progress = {
                "files_scanned": files_scanned,
                "total": total,
                "percent": percent,
            }
            # Скорость и ETA (День 40.x): транзитом из сканера
            speed = progress_data.get("speed_files_per_sec")
            if speed is not None:
                task.progress["speed_files_per_sec"] = speed
            eta = progress_data.get("eta_seconds")
            if eta is not None:
                task.progress["eta_seconds"] = eta
            task.started_at = task.started_at or datetime.utcnow()
    
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
        task.scanner_id = None
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
    task.scanner_id = scanner_id
    task.assigned_at = datetime.utcnow()
    db.commit()
    
    track_task_submitted(status="assigned")
    
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

    try:
        _batch_no_06045225 = int(request.query_params.get("batch", 1) or 1)
        _batch_total_06045225 = int(request.query_params.get("total", 1) or 1)
    except (TypeError, ValueError):
        _batch_no_06045225 = 1
        _batch_total_06045225 = 1
    _is_final_06045225 = _batch_no_06045225 >= _batch_total_06045225

    
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    if task.status not in ("assigned", "pending", "running"):
        raise HTTPException(400, f"Task status is {task.status}, expected assigned/running")
    
    # === Сохраняем findings (день 40.2: новый формат + дедупликация по fingerprint) ===
    from manager.src.core.encryption import get_encryption, mask, mask_line
    _enc = None
    saved_findings = 0
    deduped_findings = 0
    skipped_false_positives = 0

    # BUG-035-marker: findings сохраняются батчами (по 500) чтобы
    # не держать огромный payload в памяти manager'а - защита от
    # гигантских POST по 10k+ findings с одного сканера.
    _bug35_batch_06045225 = 500
    _bug35_cnt_06045225 = 0

    for finding_data in payload.get("findings", []):
        file_path = finding_data.get("file_path", finding_data.get("filepath", ""))
        line_number = finding_data.get("line_number", finding_data.get("line", 0))
        category = finding_data.get("category", "")
        subcategory = finding_data.get("subcategory", finding_data.get("sub_type", ""))
        value = finding_data.get("value", finding_data.get("matched_text", ""))
        confidence = finding_data.get("confidence", 1.0)
        context = finding_data.get("context", "")

        # Ленивая инициализация шифрования
        if _enc is None:
            _enc = get_encryption()

        # New format (день 40.2): finding_type передаётся явно.
        # Backward compat: старый формат категория = pii/credentials/code.
        finding_type = finding_data.get("finding_type")
        if finding_type not in ("pii", "credentials", "code"):
            finding_type = category if category in ("pii", "credentials", "code") else "code"
        detail_category = finding_data.get("category") or "unknown"
        if detail_category in ("pii", "credentials", "code"):
            detail_category = subcategory or "unknown"

        # fingerprint: передан сканером или вычисляем (legacy/старый формат).
        # В старом формате 4-й компонент = finding_type (совместимо с v3.9).
        fingerprint = finding_data.get("fingerprint")
        if not fingerprint:
            fingerprint = _enc.fingerprint(
                file_path, int(line_number or 0), value, finding_type
            )

        # === Дедупликация (день 40.2): не создаём повторно ===
        existing = db.query(models.Finding).filter(
            models.Finding.fingerprint == fingerprint
        ).first()
        if existing:
            if existing.status == "false_positive":
                # Находка отмечена человеком как ложная — пропускаем
                skipped_false_positives += 1
                continue
            # new/confirmed/archived — не создаём повторно, обновляем last_seen_at
            # и замаскированные поля (BUG-022.8): при повторном скане
            # line_text_masked/context_* должны обновляться, а не стареть.
            existing.last_seen_at = datetime.utcnow()
            if finding_data.get("line_text_masked"):
                existing.line_text_masked = finding_data.get("line_text_masked")
            if finding_data.get("line_text_encrypted"):
                existing.line_text_encrypted = finding_data.get("line_text_encrypted")
            elif finding_data.get("line_text") and not existing.line_text_encrypted:
                existing.line_text_encrypted = _enc.encrypt(finding_data.get("line_text"))  # BUG-058
            if finding_data.get("match_text_masked"):
                existing.match_text_masked = finding_data.get("match_text_masked")
            if finding_data.get("match_text_encrypted"):
                existing.match_text_encrypted = finding_data.get("match_text_encrypted")
            if finding_data.get("context_before_masked"):
                existing.context_before_masked = finding_data.get("context_before_masked")
            if finding_data.get("context_after_masked"):
                existing.context_after_masked = finding_data.get("context_after_masked")
            deduped_findings += 1
            continue

        # Шифрование/маскирование: сканер приложил готовые значения —
        # используем их; иначе вычисляем сами (legacy/старый менеджер-клиент).
        if finding_data.get("match_text_encrypted"):
            match_masked = finding_data.get("match_text_masked") or mask(value, detail_category)
            match_enc = finding_data["match_text_encrypted"]
        else:
            match_masked = mask(value, detail_category) if value else None
            match_enc = _enc.encrypt(value) if value else None

        line_text = finding_data.get("line_text", "")
        line_text_masked = finding_data.get("line_text_masked")
        if line_text_masked is None and finding_data.get("start_pos") is not None:
            st, en = finding_data.get("start_pos"), finding_data.get("end_pos")
            line_text_masked = mask_line(line_text, [(st, en, detail_category)])
        elif line_text_masked is None and line_text:
            line_text_masked = line_text

        # BUG-058: fallback line_text_encrypted — если сканер не прислал
        # зашифрованную строку (legacy), шифруем на стороне Manager.
        line_enc = finding_data.get("line_text_encrypted")
        if not line_enc and line_text:
            line_enc = _enc.encrypt(line_text)

        # BACKLOG-086 (TASK-047): встроенный фрагмент (доказательная база).
        # Сканер шлёт base64 для image_region ≤ MAX_FRAGMENT_EMBED_SIZE; здесь декодируем
        # и кладём байты в findings.fragment_data. text_line — не встраивается.
        fragment_b64 = finding_data.get("fragment_base64")
        fragment_data = None
        if fragment_b64:
            try:
                fragment_data = base64.b64decode(fragment_b64)
            except Exception as e:
                logger.warning("Failed to decode fragment for %s: %s", file_path, e)

        finding = models.Finding(
            task_id=task_id,
            resource_id=task.resource_id,
            finding_type=finding_type,
            category=detail_category,
            severity=finding_data.get("severity", "medium"),
            fragment_type=finding_data.get("fragment_type", "text_line"),
            fragment_path=file_path,
            line_number=line_number or 0,
            match_text_masked=match_masked,
            match_text_encrypted=match_enc,
            line_text_masked=line_text_masked,
            line_text_encrypted=line_enc,
            context_before_masked=finding_data.get("context_before_masked") or context or None,
            context_after_masked=finding_data.get("context_after_masked") or None,
            # BUG-077 (TASK-044, v3.13.18): сканер шлёт bounding_box=None для OCR
            # (координаты не вычисляются, Tesseract без tsv). Раньше здесь стоял
            # `or {...default {0,0,0,0}...}`, который перезаписывал None и вводил в
            # заблуждение API/WebUI. Теперь — честный None (до BACKLOG-085, v3.1.0).
            bounding_box=finding_data.get("bounding_box"),
            byte_offset=finding_data.get("byte_offset"),
            byte_length=finding_data.get("byte_length"),
            hex_preview=finding_data.get("hex_preview"),
            fingerprint=fingerprint,
            encryption_key_id=finding_data.get("encryption_key_id") or _enc.key_id,
            status="new",
            confidence=float(confidence) if confidence else None,
            detector=finding_data.get("detector") or "legacy",
            # BACKLOG-086 (TASK-047): встроенный фрагмент
            fragment_data=fragment_data,
            fragment_mime=finding_data.get("fragment_mime"),
            fragment_hash=finding_data.get("fragment_hash"),
            fragment_size=len(fragment_data) if fragment_data else None,
            fragment_embedded_at=datetime.utcnow() if fragment_data else None,
        )
        db.add(finding)
        _bug35_cnt_06045225 += 1
        if _bug35_cnt_06045225 >= _bug35_batch_06045225:
            db.flush()
            _bug35_cnt_06045225 = 0

        saved_findings += 1
    
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
            resource_id=task.resource_id,
            file_path=failed.get("path", ""),
            error_type=failed.get("error_type", failed.get("error_type", "unknown")),
            error_message=failed.get("error", "")
        )
        db.add(failed_file)
    
    stats = payload.get("stats", {})
    task.findings_count = (task.findings_count or 0) + saved_findings

    if _is_final_06045225:
        task.status = "completed"
        task.completed_at = datetime.utcnow()
        # BUG-027.4: при завершении (linewise) финальный heartbeat может не
        # донести progress — заполняем полностью из финальной статистики.
        prev = task.progress or {}
        task_total = prev.get("total")
        if not task_total:
            task_total = int(stats.get("files_scanned", 0) or 0)
        task.progress = {
            "files_scanned": int(stats.get("files_scanned", task.files_scanned or 0)),
            "total": task_total,
            "percent": 100.0,
            "status": "completed",
        }
        task.files_scanned = stats.get("files_scanned", 0)
        task.files_failed = stats.get("files_failed", 0)

        # Prometheus-метрики (День 39)
        track_task_submitted(status="completed")
        if task.assigned_at:
            track_task_completed(
                (task.completed_at - task.assigned_at).total_seconds()
            )
        track_findings(stats.get("category_stats", {}))

        resource = db.query(models.Resource).filter(models.Resource.id == task.resource_id).first()
        if resource:
            resource.last_scanned_at = datetime.utcnow()
            resource.status = "ACTIVE"

    db.commit()
    
    logger.info(f"[Task] Task {task_id}: batch {_batch_no_06045225}/{_batch_total_06045225} accepted")

    return {
        "status": "accepted",
        "task_id": task_id,
        "findings_count": saved_findings,
        "catalog_entries_count": len(payload.get("catalog_entries", [])),
        "failed_files_count": len(payload.get("failed_files", [])),
        "deduped": deduped_findings,
        "skipped_false_positives": skipped_false_positives,
    }


@router.get("/{scanner_id}")
def get_scanner_info(
    scanner_id: int,
    db: Session = Depends(session.get_db)
):
    """Получить информацию о сканере"""
    _mark_stale_scanners(db)

    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")
    
    current_task = db.query(models.ScanTask).filter(
        and_(
            models.ScanTask.scanner_id == scanner_id,
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
            "assigned_to": t.scanner_id,
            "assigned_at": t.assigned_at.isoformat() if t.assigned_at else None,
            "created_at": t.created_at.isoformat()
        }
        for t in tasks
    ]


@router.post("/tasks/{task_id}/fail")
def fail_task(
    task_id: int,
    payload: dict,
    db: Session = Depends(session.get_db),
):
    """BUG-034: сканер уведомляет о прерывании задачи."""
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status in ("completed", "failed"):
        return {"status": task.status, "id": task_id, "already": True}
    task.status = "failed"
    task.completed_at = datetime.utcnow()
    db.commit()
    logger.info(f"[FailTask] Task {task_id} marked failed: {payload.get('reason', 'unknown')}")
    return {"status": "failed", "id": task_id}


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(session.get_db)):
    """BUG-034: ручная отмена задачи (Admin/Auditor)."""
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status in ("completed", "failed"):
        return {"status": task.status, "id": task_id, "already": True}
    task.status = "failed"
    task.completed_at = datetime.utcnow()
    db.commit()
    return {"status": "failed", "id": task_id}


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
    
    old_scanner_id = task.scanner_id
    
    task.status = "pending"
    task.scanner_id = None
    task.assigned_at = None
    db.commit()
    
    logger.info(f"[Task] Task {task_id} released from scanner {old_scanner_id}")
    
    return {
        "status": "released",
        "task_id": task_id,
        "old_scanner_id": old_scanner_id
    }


@router.delete("/{scanner_id}")
def delete_scanner(
    scanner_id: int,
    force: bool = False,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),
):
    """Удалить сканер (только Admin, BUG-048). Если force=True — освободить назначенные задания."""
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, f"Scanner {scanner_id} not found")

    active = db.query(models.ScanTask).filter(
        models.ScanTask.scanner_id == scanner_id,
        models.ScanTask.status.in_(["assigned", "pending"])
    ).first()

    if active and not force:
        raise HTTPException(
            409,
            f"Scanner {scanner_id} has active task {active.id}. Use force=true."
        )

    if force:
        db.query(models.ScanTask).filter(
            models.ScanTask.scanner_id == scanner_id,
            models.ScanTask.status.in_(["assigned"])
        ).update({"scanner_id": None, "status": "pending"})
        db.commit()

    db.delete(scanner)
    db.commit()

    return {"status": "deleted", "scanner_id": scanner_id}