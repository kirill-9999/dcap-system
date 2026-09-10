# manager/src/workers/tasks.py
"""Celery-задачи Manager (День 36-37).

Очереди: audit_events, scanner_tasks, retention, reports.
Задачи выполняют реальную работу с БД через SessionLocal (каждый процесс
Celery worker создаёт собственные сессии). Фоновые потоки scheduler'а
(День 35) заменены Celery Beat (см. celery_app.beat_schedule).
"""
import logging
from datetime import datetime, timedelta

from celery import group

from .celery_app import app
from ..db.session import SessionLocal
from ..config import get_config

logger = logging.getLogger(__name__)


# ============================================================
# AUDIT EVENTS
# ============================================================


@app.task(bind=True, name="manager.src.workers.tasks.process_audit_event")
def process_audit_event(self, event: dict):
    """Запись одного события аудита в БД (асинхронно с входящего API)."""
    from ..db import models

    db = SessionLocal()
    try:
        agent_id = event.get("agent_id")
        created_at = event.get("created_at")
        audit = models.AuditLog(
            agent_id=agent_id,
            event_type=event.get("event_type") or "unknown",
            event_source=event.get("event_source") or "agent",
            user=event.get("user"),
            user_sid=event.get("user_sid"),
            file_path=event.get("file_path") or "",
            old_path=event.get("old_path"),
            source_host=event.get("source_host"),
            metadata_json=event.get("metadata") or {},
            created_at=(
                datetime.fromisoformat(created_at) if created_at else datetime.utcnow()
            ),
        )
        db.add(audit)
        db.commit()
        return {"status": "saved", "event_id": audit.id}
    except Exception as e:  # noqa: BLE001
        logger.error(f"process_audit_event failed: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)
    finally:
        db.close()


@app.task(bind=True, name="manager.src.workers.tasks.enqueue_audit_batch")
def enqueue_audit_batch(self, events: list, agent_id: int):
    """Разбить батч событий на отдельные задачи (paralell ingest)."""
    if isinstance(events, (list, tuple)):
        group(
            process_audit_event.s({**ev, "agent_id": agent_id}) for ev in events
        ).apply_async(queue="audit_events")
    return {"dispatched": len(events)}


# ============================================================
# SCANNER TASKS
# ============================================================


@app.task(bind=True, name="manager.src.workers.tasks.assign_scanner_task")
def assign_scanner_task(self, task_id: int):
    """Постановка задачи сканирования в очередь для агента-сканера.

    Сканер забирает задачи по pull (GET /api/scanner/tasks/next), поэтому
    задача лишь помечает ScanTask как 'queued'. Реальная отправка выполняется
    агентом при опросе Manager.
    """
    from ..db import models

    db = SessionLocal()
    try:
        task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
        if not task:
            return {"error": f"ScanTask {task_id} not found"}
        if task.status in ("pending", "queued"):
            task.status = "queued"
            task.assigned_at = datetime.utcnow()
            db.commit()
        return {"task_id": task.id, "status": task.status}
    except Exception as e:  # noqa: BLE001
        logger.error(f"assign_scanner_task failed: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)
    finally:
        db.close()


@app.task(bind=True, name="manager.src.workers.tasks.process_scanner_task")
def process_scanner_task(self, task_id: int):
    """Запуск задачи сканирования (вызывается агентом или по расписанию).

    В День 36-37 работа сканера остаётся на агенте (scanner), который
    тянет задачи и шлёт результаты в POST /api/scanner/tasks/{id}/report.
    Данная задача используется для пометки/журналирования и совместима
    с будущими расширениями (асинхронное сканирование на стороне Manager).
    """
    from ..db import models

    db = SessionLocal()
    try:
        task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
        if not task:
            return {"error": f"ScanTask {task_id} not found"}
        if task.status == "queued":
            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()
        return {"task_id": task.id, "status": task.status}
    except Exception as e:  # noqa: BLE001
        logger.error(f"process_scanner_task failed: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)
    finally:
        db.close()


@app.task(bind=True, name="manager.src.workers.tasks.scan_resource")
def scan_resource(self, resource_id: int):
    """Создание задачи сканирования для ресурса (по расписанию/API)."""
    from ..db import models

    db = SessionLocal()
    try:
        resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            return {"error": f"Resource {resource_id} not found"}
        source_path = resource.path
        existing = (
            db.query(models.ScanTask)
            .filter(
                models.ScanTask.resource_id == resource_id,
                models.ScanTask.status.in_(["pending", "queued", "running"]),
            )
            .first()
        )
        if existing:
            return {"task_id": existing.id, "status": "already_active"}
        task = models.ScanTask(
            resource_id=resource_id,
            source_path=source_path,
            status="queued",
            created_at=datetime.utcnow(),
            assigned_at=datetime.utcnow(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return {"task_id": task.id, "status": task.status}
    except Exception as e:  # noqa: BLE001
        logger.error(f"scan_resource failed: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)
    finally:
        db.close()


@app.task(name="manager.src.workers.tasks.sweep_scheduled_scans")
def sweep_scheduled_scans():
    """Ежечасный обход расписания (Schedule) и постановка задач (sweep).

    Для каждого enabled Schedule с наступившим next_run_at создаётся
    задача сканирования resource (scan_resource).
    """
    from croniter import croniter
    from ..db import models

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        schedules = (
            db.query(models.Schedule)
            .filter(
                models.Schedule.enabled == True,  # noqa: E712
                models.Schedule.next_run_at.is_(None)
                | (models.Schedule.next_run_at <= now),
            )
            .all()
        )
        dispatched = []
        for sched in schedules:
            if sched.resource_id is None:
                sched.enabled = False
                continue
            if not croniter.is_valid(sched.cron_expression):
                sched.enabled = False
                continue
            # Постановка задачи (как асинхронная цепочка — не блокируя)
            scan_resource.apply_async(
                args=[sched.resource_id], queue="scanner_tasks"
            )
            itr = croniter(sched.cron_expression, now)
            sched.last_run_at = now
            sched.next_run_at = itr.get_next(datetime)
            sched.updated_at = now
            dispatched.append({"schedule_id": sched.id, "resource_id": sched.resource_id})
        db.commit()
        return {"dispatched": dispatched}
    except Exception as e:  # noqa: BLE001
        logger.error(f"sweep_scheduled_scans failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


# ============================================================
# RETENTION
# ============================================================


@app.task(bind=True, name="manager.src.workers.tasks.run_retention")
def run_retention(self, dry_run: bool = False):
    """Полный цикл архивации и очистки (Celery Beat, очередь retention)."""
    from ..retention.runtime import run_retention as _run_retention

    try:
        result = _run_retention(dry_run=dry_run)
        logger.info(f"Retention (Celery) completed: {result}")
        return result
    except Exception as e:  # noqa: BLE001
        logger.error(f"Retention (Celery) failed: {e}")
        self.retry(exc=e, countdown=60 * 5, max_retries=3)


@app.task(name="manager.src.workers.tasks.clean_log_rotation_task")
def clean_log_rotation_task():
    """Ротация файловых логов (после основного retention-цикла)."""
    from ..retention.cleaner import clean_log_rotation
    from ..config import get_config as _get_config

    cfg = _get_config().get("retention", {}).get("logs", {})
    return clean_log_rotation(
        cfg.get("rotate_days", 30), cfg.get("max_size_mb", 100)
    )


# ============================================================
# REPORTS
# ============================================================


@app.task(bind=True, name="manager.src.workers.tasks.generate_report")
def generate_report(self, report_type: str = "audit", **filters):
    """Фоновая генерация отчёта (PDF/XLSX) в очередь reports.

    Результат возвращается в metadata задачи; реальный экспорт выполняется
    синхронно в существующем коде API `/api/audit/report/*`. Для Celery
    оставлен интерфейс-заглушка, совместимая с будущим расширением.
    """
    try:
        # Реальная генерация отчётов (День 23) использует синхронные
        # эндпоинты webui-прокси. Здесь — обёртка под асинхронный вызов.
        return {
            "report_type": report_type,
            "filters": filters,
            "status": "queued",
            "note": "Synchronous export available at /api/audit/report/export/*",
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"generate_report failed: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)


@app.task(name="manager.src.workers.tasks.export_audit_report")
def export_audit_report(fmt: str = "json", **filters):
    """Экспорт аудита в JSON/CSV (архивация) — асинхронная обёртка."""
    from ..retention.exporter import Exporter
    from ..config import get_config as _get_config

    db = SessionLocal()
    try:
        exporter = Exporter(_get_config())
        if fmt == "json":
            path = exporter.export_archived_audit_events(db)
        elif fmt == "csv":
            # Exporter пишет JSON по умолчанию; CSV доступен через _write_csv.
            # Здесь переиспользуем экспорт архивных событий (JSON-совместимые файлы).
            path = exporter.export_archived_audit_events(db)
        else:
            return {"error": f"unsupported format: {fmt}"}
        return {"exported": path}
    finally:
        db.close()