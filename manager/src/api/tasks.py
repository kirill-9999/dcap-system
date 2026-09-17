from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..db import models, session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("")
def list_tasks(
    db: Session = Depends(session.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    resource_id: Optional[int] = None
):
    """Получить список заданий"""
    query = db.query(models.ScanTask)
    
    if status:
        query = query.filter(models.ScanTask.status == status)
    if resource_id:
        query = query.filter(models.ScanTask.resource_id == resource_id)
    
    tasks = query.order_by(models.ScanTask.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": t.id,
            "resource_id": t.resource_id,
            "status": t.status,
            "assigned_to": t.scanner_id,
            "assigned_at": t.assigned_at.isoformat() if t.assigned_at else None,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "findings_count": t.findings_count,
            "files_scanned": t.files_scanned,
            "files_failed": t.files_failed,
            "progress": t.progress
        }
        for t in tasks
    ]

@router.get("/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(session.get_db)
):
    """Получить детали задания"""
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    # BUG-027.2: top-level files_scanned синхронизируем с progress
    # из последнего heartbeat (иначе рассинхрон при живой задаче).
    pfiles = (task.progress or {}).get("files_scanned")
    top_files_scanned = int(pfiles) if pfiles is not None else (task.files_scanned or 0)

    return {
        "id": task.id,
        "resource_id": task.resource_id,
        "status": task.status,
        "assigned_to": task.scanner_id,
        "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "findings_count": task.findings_count,
        "files_scanned": top_files_scanned,
        "files_failed": task.files_failed,
        "progress": task.progress
    }

@router.post("/{task_id}/cancel")
def cancel_task_06045225(
    task_id: int,
    db: Session = Depends(session.get_db)
):
    """BUG-034.2 (06045225): cancel a task -> failed."""
    task = db.query(models.ScanTask).filter(
        models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "failed"
    task.completed_at = datetime.utcnow()
    db.commit()
    _bug34_cancel_06045225 = True
    return {"task_id": task_id, "status": task.status}


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(session.get_db)
):
    """Удалить задание"""
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Удаляем связанные записи
    db.query(models.Finding).filter(models.Finding.task_id == task_id).delete()
    db.query(models.CatalogEntry).filter(models.CatalogEntry.task_id == task_id).delete()
    db.query(models.FailedFile).filter(models.FailedFile.task_id == task_id).delete()
    
    db.delete(task)
    db.commit()
    
    return {"status": "deleted", "id": task_id}