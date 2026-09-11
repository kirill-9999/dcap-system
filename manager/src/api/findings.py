from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..db import models, session

router = APIRouter(prefix="/api/findings", tags=["findings"])

@router.get("")
def list_findings(
    db: Session = Depends(session.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    resource_id: Optional[int] = None,
    category: Optional[str] = None,
    min_confidence: Optional[int] = None,
    task_id: Optional[int] = None
):
    """Получить список находок"""
    query = db.query(models.Finding)
    
    if resource_id:
        query = query.filter(models.Finding.resource_id == resource_id)
    if task_id:
        query = query.filter(models.Finding.task_id == task_id)
    if category:
        query = query.filter(models.Finding.category == category)
    if min_confidence:
        query = query.filter(models.Finding.confidence >= min_confidence)
    
    findings = query.order_by(models.Finding.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": f.id,
            "task_id": f.task_id,
            "resource_id": f.resource_id,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "category": f.category,
            "subcategory": f.subcategory,
            "value": f.value,
            "confidence": f.confidence / 100.0,  # Преобразуем обратно в 0-1
            "context": f.context,
            "created_at": f.created_at.isoformat()
        }
        for f in findings
    ]

@router.get("/count")
def get_findings_count(
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None,
    task_id: Optional[int] = None,
    db: Session = Depends(session.get_db)
):
    """Количество находок с фильтрацией (WebUI-формат)"""
    query = db.query(models.Finding)
    if category:
        query = query.filter(models.Finding.category == category)
    if file_path:
        query = query.filter(models.Finding.file_path.ilike(f"%{file_path}%"))
    if scanner_id:
        query = query.filter(
            models.Finding.task_id.in_(
                db.query(models.ScanTask.id).filter(models.ScanTask.scanner_id == scanner_id)
            )
        )
    if task_id:
        query = query.filter(models.Finding.task_id == task_id)
    return {"count": query.count()}


@router.get("/{finding_id}")
def get_finding(
    finding_id: int,
    db: Session = Depends(session.get_db)
):
    """Получить детали находки"""
    finding = db.query(models.Finding).filter(models.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    
    return {
        "id": finding.id,
        "task_id": finding.task_id,
        "resource_id": finding.resource_id,
        "file_path": finding.file_path,
        "line_number": finding.line_number,
        "category": finding.category,
        "subcategory": finding.subcategory,
        "value": finding.value,
        "confidence": finding.confidence / 100.0,
        "context": finding.context,
        "created_at": finding.created_at.isoformat()
    }

@router.delete("/{finding_id}")
def delete_finding(
    finding_id: int,
    db: Session = Depends(session.get_db)
):
    """Удалить находку"""
    finding = db.query(models.Finding).filter(models.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    
    db.delete(finding)
    db.commit()
    
    return {"status": "deleted", "id": finding_id}

@router.get("/stats")
def get_findings_stats(
    resource_id: Optional[int] = None,
    db: Session = Depends(session.get_db)
):
    """Получить статистику по находкам"""
    query = db.query(models.Finding)
    
    if resource_id:
        query = query.filter(models.Finding.resource_id == resource_id)
    
    total = query.count()
    
    # Статистика по категориям
    categories = {}
    for category in ["pii", "credentials", "code"]:
        count = query.filter(models.Finding.category == category).count()
        if count > 0:
            categories[category] = count
    
    return {
        "total": total,
        "categories": categories,
        "resource_id": resource_id
    }