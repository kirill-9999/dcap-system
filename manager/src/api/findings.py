"""
API находок: список, детали, reveal, bulk, stats, FP.

Хранение: гибрид (masked + encrypted).
Расшифровка — только Auditor, с аудитом.
"""
import csv
import io
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from manager.src.db.session import get_db
from manager.src.db.models import Finding
from manager.src.auth.models import User
from manager.src.auth.dependencies import (
    require_auth, require_auditor, require_admin, require_viewer
)
from manager.src.core.encryption import get_encryption
from manager.src.core.image_fragment import crop_image
from manager.src.core.hex_dump import format_hex_dump
from manager.src.core.csv_utils import sanitize_csv_cell
from manager.src.api.schemas_findings import (
    FindingResponse, FindingRevealResponse, FindingUpdateRequest,
    FindingBulkUpdateRequest, FindingBulkUpdateResponse,
    FindingStatsResponse, FalsePositiveResponse,
    CheckFingerprintsRequest, CheckFingerprintsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/findings", tags=["findings"])


def _json_default(o):
    """Сериализация datetime и пр. для HTTP-ответов (День 40.4)."""
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


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
        "encryption_key_id": finding.encryption_key_id,
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

    total = q.count()
    findings = q.offset(offset).limit(limit).all()
    payload = [_finding_to_response(f, user) for f in findings]
    return Response(
        content=json.dumps(payload, ensure_ascii=False, default=_json_default),
        media_type="application/json; charset=utf-8",
        headers={"X-Total-Count": str(total)},
    )


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
    # W-66/W-67: file_path из resource + reviewed_by_username из users.
    from manager.src.db import models as _m
    resource_ids = [f.resource_id for f in findings if f.resource_id]
    reviewer_ids = [f.reviewed_by for f in findings if f.reviewed_by]
    res_map = {}
    if resource_ids:
        for r in db.query(_m.Resource).filter(_m.Resource.id.in_(set(resource_ids))).all():
            res_map[r.id] = r.path
    reviewer_map = {}
    if reviewer_ids:
        for u in db.query(_m.User).filter(_m.User.id.in_(set(reviewer_ids))).all():
            reviewer_map[u.id] = u.username
    return [
        {
            "id": f.id,
            "resource_id": f.resource_id,
            "file_path": res_map.get(f.resource_id) or f.fragment_path,
            "line_number": f.line_number,
            "match_text_masked": f.match_text_masked,
            "category": f.category,
            "finding_type": f.finding_type,
            "comment": f.comment,
            "reviewed_by": f.reviewed_by,
            "reviewed_by_username": reviewer_map.get(f.reviewed_by),
            "reviewed_at": f.reviewed_at,
        }
        for f in findings
    ]


# ========== EXPORT ==========

@router.get("/export")
async def export_findings(
    format: str = Query("csv", pattern="^(csv|json)$"),
    reveal: bool = Query(False),
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    task_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    limit: int = Query(10000, le=100000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor),
):
    """
    Экспорт находок.

    - format=csv|json (по умолчанию csv)
    - reveal=true → расшифровка (только Auditor+, с аудитом)
    - По умолчанию — маскированное
    """
    if reveal and not _is_auditor(current_user):
        raise HTTPException(403, "Reveal requires Auditor role")

    # Импорт модели для legacy-filters (как в list_findings)
    q = db.query(Finding)
    if status:
        q = q.filter(Finding.status == status)
    if finding_type:
        q = q.filter(Finding.finding_type == finding_type)
    if category:
        if category in ("pii", "credentials", "code"):
            q = q.filter(Finding.finding_type == category)
        else:
            q = q.filter(Finding.category == category)
    if severity:
        q = q.filter(Finding.severity == severity)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)

    findings = q.order_by(desc(Finding.first_seen_at)).limit(limit).all()

    # Аудит
    _log_export(db, current_user, format, reveal, findings, {
        "status": status, "finding_type": finding_type,
        "category": category, "severity": severity,
        "task_id": task_id, "resource_id": resource_id,
    })

    if format == "csv":
        return _export_csv(findings, reveal)
    return _export_json(findings, reveal)


def _log_export(db, user, export_format, reveal, findings, filters):
    """Пишет запись в audit_logs (findings_exported)."""
    try:
        from manager.src.db.models import AuditLog
        log = AuditLog(
            event_type="findings_exported",
            event_source="api",
            user=user.username,
            file_path="/",
            metadata_json={
                "format": export_format,
                "reveal": reveal,
                "action": "findings_exported_revealed" if reveal else "findings_exported_masked",
                "count": len(findings),
                "filters": filters,
            },
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log findings export: %s", e)
        db.rollback()


def _resolve_text(finding: Finding, field: str, reveal: bool) -> str:
    """masked → reveal при необходимости."""
    if reveal:
        encrypted = getattr(finding, f"{field}_encrypted", None)
        if encrypted:
            return get_encryption().decrypt(encrypted)
    return getattr(finding, f"{field}_masked", "") or ""


def _export_csv(findings, reveal: bool) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "file_path", "line_number", "finding_type", "category",
        "severity", "status", "match_text", "line_text",
        "first_seen_at", "last_seen_at",
    ])
    for f in findings:
        match = _resolve_text(f, "match_text", reveal)
        line = _resolve_text(f, "line_text", reveal)
        writer.writerow([
            f.id,
            sanitize_csv_cell(f.fragment_path or ""),
            f.line_number or "",
            f.finding_type, f.category, f.severity, f.status,
            sanitize_csv_cell(match), sanitize_csv_cell(line),
            f.first_seen_at.isoformat() if f.first_seen_at else "",
            f.last_seen_at.isoformat() if f.last_seen_at else "",
        ])
    content = "\ufeff" + output.getvalue()  # BOM для Excel
    filename = f"findings_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _finding_to_export_dict(finding: Finding, reveal: bool) -> dict:
    return {
        "id": finding.id,
        "resource_id": finding.resource_id,
        "task_id": finding.task_id,
        "file_path": finding.fragment_path,
        "line_number": finding.line_number,
        "finding_type": finding.finding_type,
        "category": finding.category,
        "severity": finding.severity,
        "status": finding.status,
        "fragment_type": finding.fragment_type,
        "bounding_box": finding.bounding_box,
        "byte_offset": finding.byte_offset,
        "byte_length": finding.byte_length,
        "match_text": _resolve_text(finding, "match_text", reveal),
        "line_text": _resolve_text(finding, "line_text", reveal),
        "first_seen_at": finding.first_seen_at.isoformat() if finding.first_seen_at else None,
        "last_seen_at": finding.last_seen_at.isoformat() if finding.last_seen_at else None,
    }


def _export_json(findings, reveal: bool) -> Response:
    data = [_finding_to_export_dict(f, reveal) for f in findings]
    filename = f"findings_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


# ========== FRAGMENT ==========

def _is_auditor(user: User) -> bool:
    """Права Auditor+ (расшифровка PII без маски)."""
    return bool(user and (user.has_role("auditor") or user.has_role("admin")))


@router.get("/{finding_id}/fragment")
async def get_finding_fragment(
    finding_id: int,
    request: Request,
    format: str = Query("png", pattern="^(png|hex)$"),
    db: Session = Depends(get_db),
    # BACKLOG-086 (TASK-048, v3.13.19): RBAC ужесточён — фрагменты содержат PII,
    # доступ к /fragment теперь только Auditor+ (было Viewer+, BUG-079).
    current_user: User = Depends(require_auditor),
):
    """
    Вернуть фрагмент находки.

    TASK-048 (BACKLOG-086): приоритеты —
      1) fragment_data в БД → embedded (устойчив к удалению исходника);
      2) bounding_box → crop;
      3) bbox=None + fragment_path на хосте → full-image;
      4) иначе 404.

    - image_region → PNG
    - byte_range   → hex-дамп (format=hex)
    - text_line/text_context → 400 (текст отдаётся в /api/findings/{id})
    """
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    if finding.fragment_type == "image_region":
        resp = _get_image_fragment(finding)
        _log_fragment_access(db, current_user, finding, _mode_of(resp), request)
        return resp

    if finding.fragment_type == "byte_range":
        resp = _get_hex_fragment(finding)
        _log_fragment_access(db, current_user, finding, "hex", request)
        return resp

    raise HTTPException(400, f"Fragment not available for type: {finding.fragment_type}")


def _mode_of(resp: Response) -> str:
    """BACKLOG-086 (TASK-048): mode для аудита из ответа."""
    return resp.headers.get("X-Fragment-Mode") or "bbox-crop"


def _log_fragment_access(db, user, finding, mode: str, request) -> None:
    """BACKLOG-086 (TASK-048): аудит доступа к фрагменту (action=fragment_accessed).

    Каждый GET /fragment и /fragment/hash логируется. Metadata содержит
    finding_id и mode (embedded|full-image|bbox-crop|hex).
    """
    try:
        from manager.src.db.models import AuditLog
        log = AuditLog(
            event_type="fragment_accessed",
            event_source="api",
            user=user.username if user else None,
            file_path=finding.fragment_path or f"finding:{finding.id}",
            source_host=request.client.host if request.client else None,
            metadata_json={
                "action": "fragment_accessed",
                "finding_id": finding.id,
                "mode": mode,
            },
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log fragment access: %s", e)
        db.rollback()


@router.get("/{finding_id}/fragment/hash")
async def get_fragment_hash(
    finding_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor),
):
    """BACKLOG-086 (TASK-048): метаданные встроенного фрагмента (для аудита)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    if not finding.fragment_data:
        raise HTTPException(404, "No embedded fragment")
    _log_fragment_access(db, current_user, finding, "hash", request)
    return {
        "finding_id": finding.id,
        "hash": finding.fragment_hash,
        "size": finding.fragment_size,
        "mime": finding.fragment_mime,
        "embedded_at": finding.fragment_embedded_at,
    }


def _get_image_fragment(finding: Finding) -> Response:
    """Отдать PNG-фрагмент.

    TASK-048 (BACKLOG-086): приоритеты —
      1) fragment_data в БД (embedded) → отдаём байты из БД с X-Fragment-Mode:
         embedded + X-Fragment-Hash. Работает даже если исходный файл удалён;
      2) фрагмент/исходник на хосте Manager (full-image / crop);
      3) иначе 404.
    """
    # 1) Встроенный фрагмент (BACKLOG-086): неизменяемое доказательство в БД.
    if finding.fragment_data:
        headers = {
            "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
            "X-Fragment-Mode": "embedded",
        }
        if finding.fragment_hash:
            headers["X-Fragment-Hash"] = finding.fragment_hash
        return Response(
            content=finding.fragment_data,
            media_type=finding.fragment_mime or "image/png",
            headers=headers,
        )

    path = finding.fragment_path if finding.fragment_path else None

    if path and os.path.isfile(path):
        # BUG-077 (TASK-042, v3.13.17): OCR-координаты не вычисляются
        # (Tesseract без tsv) → bbox=None. Отдаём весь файл (Вариант 1).
        if finding.fragment_type == "image_region" and not finding.bounding_box:
            with open(path, "rb") as f:
                data = f.read()
            return Response(
                content=data,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
                    "X-Fragment-Mode": "full-image",
                },
            )
        # A: файл уже вырезанного фрагмента (нет box / это PNG) — отдать напрямую
        if not finding.bounding_box or path.lower().endswith(".png"):
            with open(path, "rb") as f:
                data = f.read()
            return Response(
                content=data,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
                    "X-Bounding-Box": json.dumps(finding.bounding_box or {}),
                },
            )
        # B: исходник + bounding_box — вырезаем через Pillow
        try:
            data = crop_image(path, finding.bounding_box)
        except Exception:
            logger.exception("Crop failed for finding %s", finding.id)
            raise HTTPException(404, "Fragment not available")
        # Кэшировать рядом с исходником
        cache_path = f"{os.path.splitext(path)[0]}_fragment_{finding.id}.png"
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(data)
        except Exception:
            logger.warning("Failed to cache fragment for finding %s", finding.id)
        return Response(
            content=data,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
                "X-Bounding-Box": json.dumps(finding.bounding_box or {}),
            },
        )

    raise HTTPException(404, "Fragment not available")


def _get_hex_fragment(finding: Finding, window: int = 64) -> Response:
    """Hex-дамп вокруг byte_offset."""
    if finding.hex_preview:
        return Response(
            content=finding.hex_preview,
            media_type="text/plain; charset=utf-8",
        )

    if not finding.fragment_path or not os.path.isfile(finding.fragment_path):
        raise HTTPException(404, "Fragment not available")

    offset = finding.byte_offset or 0
    length = finding.byte_length or 0
    start = max(0, offset - window)
    end = offset + length + window

    with open(finding.fragment_path, "rb") as f:
        f.seek(start)
        data = f.read(end - start)

    dump = format_hex_dump(data, base_offset=start)
    return Response(content=dump, media_type="text/plain; charset=utf-8")


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