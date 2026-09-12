"""
API находок: список, детали, reveal, bulk, stats, FP.

Хранение: гибрид (masked + encrypted).
Расшифровка — только Auditor, с аудитом.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from manager.src.db.session import get_db
from manager.src.db.models import Finding
from manager.src.auth.models import User
from manager.src.auth.dependencies import (
    require_auth, require_auditor, require_admin
)
from manager.src.core.encryption import get_encryption
from manager.src.api.schemas_findings import (
    FindingResponse, FindingRevealResponse, FindingUpdateRequest,
    FindingBulkUpdateRequest, FindingBulkUpdateResponse,
    FindingStatsResponse, FalsePositiveResponse,
    CheckFingerprintsRequest, CheckFingerprintsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/findings", tags=["findings"])


# ========== ВСПОМОГАТЕЛЬНЫЕ ==========

def _finding_to_response(
    finding: Finding,
    user: Optional[User] = None,
    reveal: bool = False,
) -> dict:
    """Преобразует Finding в ответ (masked или revealed)."""
    enc = get_encryption()

    can_reveal = bool(user and user.has_role("auditor")) or bool(
        user and user.has_role("admin")
    )

    data = {
        "id": finding.id,
        "resource_id": finding.resource_id,
        "task_id": finding.task_id,
        "finding_type": finding.finding_type,
        "category": finding.category,
        "severity": finding.severity,
        "fragment_type": finding.fragment_type,
        "line_number": finding.line_number,
        "match_text": finding.match_text_masked,
        "line_text": finding.line_text_masked,
        "context_before": finding.context_before_masked,
        "context_after": finding.context_after_masked,
        "has_fragment": bool(finding.fragment_path),
        "bounding_box": finding.bounding_box,
        "byte_offset": finding.byte_offset,
        "byte_length": finding.byte_length,
        "status": finding.status,
        "reviewed_by": finding.reviewed_by,
        "reviewed_at": finding.reviewed_at,
        "comment": finding.comment,
        "confidence": finding.confidence,
        "detector": finding.detector,
        "first_seen_at": finding.first_seen_at,
        "last_seen_at": finding.last_seen_at,
        "has_encrypted": bool(finding.match_text_encrypted or finding.line_text_encrypted),
        "can_reveal": can_reveal,
        # legacy-поля (backward compat с v3.8.0)
        "file_path": finding.fragment_path,
        "value": finding.match_text_masked,
    }

    # Reveal (только если явно запрошен и есть права)
    if reveal and can_reveal:
        if finding.match_text_encrypted:
            data["match_text"] = enc.decrypt(finding.match_text_encrypted)
        if finding.line_text_encrypted:
            data["line_text"] = enc.decrypt(finding.line_text_encrypted)

    return data


# ========== LIST / GET ==========

@router.get("", response_model=list[FindingResponse])
def list_findings(
    resource_id: Optional[int] = None,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    order_by: str = Query("first_seen_at", pattern="^(first_seen_at|last_seen_at|severity|line_number)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Список находок (маскированное)."""
    q = db.query(Finding)

    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if status:
        q = q.filter(Finding.status == status)
    if finding_type:
        q = q.filter(Finding.finding_type == finding_type)
    if category:
        # legacy-backward compat: старые категории pii/credentials/code
        if category in ("pii", "credentials", "code"):
            q = q.filter(Finding.finding_type == category)
        else:
            q = q.filter(Finding.category == category)
    if severity:
        q = q.filter(Finding.severity == severity)

    col = getattr(Finding, order_by)
    q = q.order_by(desc(col) if order == "desc" else col)

    findings = q.offset(offset).limit(limit).all()
    return [_finding_to_response(f, user) for f in findings]


@router.get("/stats", response_model=FindingStatsResponse)
def get_stats(
    task_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Статистика по находкам."""
    q = db.query(Finding)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)

    total = q.count()

    filters = []
    if task_id:
        filters.append(Finding.task_id == task_id)
    if resource_id:
        filters.append(Finding.resource_id == resource_id)

    def _group_counts(col, f):
        sub = db.query(col, func.count(Finding.id))
        for flt in filters:
            sub = sub.filter(flt)
        return dict(sub.group_by(col).all())

    by_status = _group_counts(Finding.status, filters)
    by_type = _group_counts(Finding.finding_type, filters)
    by_category = _group_counts(Finding.category, filters)
    by_severity = _group_counts(Finding.severity, filters)

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_category": by_category,
        "by_severity": by_severity,
    }


@router.get("/count")
def get_findings_count_legacy(
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None,
    task_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Количество находок с фильтрацией (WebUI-формат, legacy)."""
    from manager.src.db.models import ScanTask
    q = db.query(Finding)
    if category:
        if category in ("pii", "credentials", "code"):
            q = q.filter(Finding.finding_type == category)
        else:
            q = q.filter(Finding.category == category)
    if file_path:
        q = q.filter(Finding.fragment_path.ilike(f"%{file_path}%"))
    if scanner_id:
        q = q.filter(
            Finding.task_id.in_(
                db.query(ScanTask.id).filter(ScanTask.scanner_id == scanner_id)
            )
        )
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    return {"count": q.count()}


@router.get("/false-positives", response_model=list[FalsePositiveResponse])
def list_false_positives(
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Список ложных срабатываний (для аудита)."""
    findings = (
        db.query(Finding)
        .filter(Finding.status == "false_positive")
        .order_by(desc(Finding.reviewed_at))
        .offset(offset).limit(limit).all()
    )
    return [
        {
            "id": f.id,
            "resource_id": f.resource_id,
            "line_number": f.line_number,
            "match_text_masked": f.match_text_masked,
            "category": f.category,
            "finding_type": f.finding_type,
            "comment": f.comment,
            "reviewed_by": f.reviewed_by,
            "reviewed_at": f.reviewed_at,
        }
        for f in findings
    ]


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Детали находки (маскированное)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    return _finding_to_response(finding, user)


# ========== REVEAL ==========

@router.post("/{finding_id}/reveal", response_model=FindingRevealResponse)
def reveal_finding(
    finding_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """
    Расшифровка находки. Только Auditor+. Логируется в audit_logs.
    """
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    enc = get_encryption()

    try:
        match_text = enc.decrypt(finding.match_text_encrypted) if finding.match_text_encrypted else None
        line_text = enc.decrypt(finding.line_text_encrypted) if finding.line_text_encrypted else None
    except ValueError:
        raise HTTPException(500, "Decryption failed")

    revealed_at = datetime.utcnow()

    # Аудит
    _log_reveal(db, user, finding, revealed_at, request)

    return {
        "id": finding.id,
        "match_text": match_text or "",
        "line_text": line_text,
        "context_before": finding.context_before_masked,  # контекст только masked
        "context_after": finding.context_after_masked,
        "revealed_at": revealed_at,
        "revealed_by": user.username,
    }


def _log_reveal(db, user, finding, revealed_at, request):
    """Пишет запись в audit_logs."""
    try:
        from manager.src.db.models import AuditLog
        log = AuditLog(
            event_type="finding_reveal",
            event_source="api",
            user=user.username,
            file_path=finding.fragment_path or f"finding:{finding.id}",
            source_host=request.client.host if request.client else None,
            metadata_json={
                "finding_id": finding.id,
                "category": finding.category,
                "finding_type": finding.finding_type,
                "action": "finding_revealed",
            },
            created_at=revealed_at,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log reveal: %s", e)
        db.rollback()


# ========== UPDATE ==========

@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: int,
    body: FindingUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Обновить статус находки (confirmed / false_positive)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    finding.status = body.status
    finding.comment = body.comment
    finding.reviewed_by = user.id
    finding.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(finding)

    return _finding_to_response(finding, user)


@router.post("/bulk", response_model=FindingBulkUpdateResponse)
def bulk_update(
    body: FindingBulkUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Массовое обновление статуса."""
    updated = 0
    skipped = 0
    errors = []

    findings = db.query(Finding).filter(Finding.id.in_(body.finding_ids)).all()
    found_ids = {f.id for f in findings}
    missing = set(body.finding_ids) - found_ids

    for f in findings:
        try:
            f.status = body.status
            f.comment = body.comment
            f.reviewed_by = user.id
            f.reviewed_at = datetime.utcnow()
            updated += 1
        except Exception as e:
            errors.append(f"Finding {f.id}: {e}")

    skipped = len(missing)
    for mid in missing:
        errors.append(f"Finding {mid}: not found")

    db.commit()
    return {"updated": updated, "skipped": skipped, "errors": errors}


# ========== DELETE ==========

@router.delete("/{finding_id}")
def delete_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Удалить находку (только Admin)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    # Удалить фрагмент (если есть)
    if finding.fragment_path:
        try:
            import os
            if os.path.exists(finding.fragment_path):
                os.remove(finding.fragment_path)
        except Exception as e:
            logger.warning("Failed to remove fragment: %s", e)

    db.delete(finding)
    db.commit()
    return {"deleted": finding_id}


# ========== CHECK FINGERPRINTS (для сканера) ==========

@router.post("/check-fingerprints", response_model=CheckFingerprintsResponse)
def check_fingerprints(
    body: CheckFingerprintsRequest,
    db: Session = Depends(get_db),
):
    """
    Проверка fingerprints перед отправкой находок (для сканера).
    Публичный (machine-эндпоинт, без JWT).
    """
    if not body.fingerprints:
        return {"false_positives": [], "confirmed": [], "new": []}

    existing = (
        db.query(Finding.fingerprint, Finding.status)
        .filter(Finding.fingerprint.in_(body.fingerprints))
        .all()
    )

    status_map = {fp: st for fp, st in existing}

    false_positives = [fp for fp in body.fingerprints if status_map.get(fp) == "false_positive"]
    confirmed = [fp for fp in body.fingerprints if status_map.get(fp) == "confirmed"]
    new = [fp for fp in body.fingerprints if fp not in status_map]

    return {
        "false_positives": false_positives,
        "confirmed": confirmed,
        "new": new,
    }