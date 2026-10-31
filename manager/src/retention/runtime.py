# manager/src/retention/runtime.py
import logging
from datetime import datetime

from ..db.session import SessionLocal
from ..config import get_config
from .policies import RetentionPolicy
from .archiver import Archiver
from .cleaner import Cleaner, clean_log_rotation
from .exporter import Exporter
from . import state

logger = logging.getLogger(__name__)


def run_retention(dry_run: bool = False) -> dict:
    """Выполнить полный цикл архивации и очистки.

    Синхронная реализация вместо Celery-задачи: менеджер не использует
    брокер очередей, поэтому прогон происходит в вызывающем потоке
    (по расписанию — в фоновом потоке scheduler-а, по API — напрямую).
    """
    if state.get_retention_status().get("running") and not dry_run:
        return {"skipped": "retention already running"}

    state.set_running(True)
    try:
        config = get_config()
        if not config.get("retention", {}).get("enabled", True):
            return {"enabled": False, "skipped": "retention disabled in config"}

        policy = RetentionPolicy(config)
        db = SessionLocal()

        try:
            archiver = Archiver(db, policy)
            result_audit = archiver.archive_audit_events(dry_run)
            result_findings = archiver.archive_findings(dry_run)

            cleaner = Cleaner(db, policy)
            result_clean = cleaner.clean_archive_tables(dry_run)
            result_tasks = cleaner.clean_completed_tasks(dry_run)

            exporter = Exporter(config)
            result_export = exporter.export_archived_audit_events(db)
        finally:
            db.close()

        logs_config = config.get("retention", {}).get("logs", {})
        result_logs = clean_log_rotation(
            logs_config.get("rotate_days", 30),
            logs_config.get("max_size_mb", 100),
        )

        result = {
            "archived_audit": result_audit,
            "archived_findings": result_findings,
            "cleaned_archive": result_clean,
            "cleaned_tasks": result_tasks,
            "exported": result_export,
            "rotated_logs": result_logs,
            "dry_run": dry_run,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if not dry_run:
            state.set_last_run(result)

        logger.info(f"Retention run completed (dry_run={dry_run})")
        return result
    finally:
        state.set_running(False)


def run_retention_sync(dry_run: bool = False) -> dict:
    """Обёртка для вызова из FastAPI-зависимости (синхронная)."""
    return run_retention(dry_run=dry_run)
