# manager/src/api/retention.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from ..config import get_config
from ..db.session import get_db
from ..retention.policies import RetentionPolicy
from ..retention.exporter import Exporter
from ..retention.runtime import run_retention
from ..retention import state
from ..auth.dependencies import require_admin
from ..auth.models import User

router = APIRouter(prefix="/api/retention", tags=["retention"])


class ExportRequest(BaseModel):
    data_type: str = "audit"
    limit: int = 10000


@router.get("/policies")
def get_retention_policies(_: User = Depends(require_admin)):
    """Получение текущих политик хранения."""
    config = get_config()
    policy = RetentionPolicy(config)
    return {
        "policies": policy._policies,
        "enabled": config.get("retention", {}).get("enabled", True),
        "interval_hours": config.get("retention", {}).get("interval_hours", 24),
    }


@router.post("/run")
def run_retention_manual(dry_run: bool = False, _: User = Depends(require_admin)):
    """Ручной запуск архивации и очистки (синхронно)."""
    result = run_retention(dry_run=dry_run)
    return {"status": "completed", "dry_run": dry_run, "result": result}


@router.get("/status")
def get_retention_status(_: User = Depends(require_admin)):
    """Статус последней архивации и планировщика."""
    config = get_config()
    return {
        **state.get_retention_status(),
        "enabled": config.get("retention", {}).get("enabled", True),
        "interval_hours": config.get("retention", {}).get("interval_hours", 24),
    }


@router.post("/start")
def start_retention_scheduler(_: User = Depends(require_admin)):
    """Постановка прогона архивации в очередь Celery (retention).

    День 36-37: фоновый планировщик заменён Celery Beat; этот эндпоинт
    отправляет задачу run_retention в очередь для немедленного выполнения.
    Если Celery недоступен — возвращает 503 (Manager работает, но задача
    не выполнится без worker'а).
    """
    try:
        from ..workers.tasks import run_retention as run_retention_task

        result = run_retention_task.delay(dry_run=False)
        return {"status": "queued", "task_id": result.id}
    except Exception:
        raise HTTPException(503, "Celery broker unavailable")


@router.post("/export")
def export_archive(
    payload: Optional[ExportRequest] = None,
    data_type: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Ручной экспорт архивных данных в файл."""
    if payload is not None:
        data_type = payload.data_type
        limit = payload.limit
    if limit is None:
        limit = 10000
    if data_type is None:
        data_type = "audit"
    if limit < 1:
        raise HTTPException(400, "limit must be >= 1")
    exporter = Exporter(get_config())
    if data_type == "audit":
        result = exporter.export_archived_audit_events(db, limit)
    elif data_type == "findings":
        result = exporter.export_archived_findings(db, limit)
    else:
        raise HTTPException(400, f"Unsupported data type: {data_type}")
    return result
