# manager/src/retention/cleaner.py
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from typing import Dict

from ..db import models
from .policies import RetentionPolicy

logger = logging.getLogger(__name__)


class Cleaner:
    """Очистка данных (удаление устаревших)."""

    def __init__(self, db: Session, policy: RetentionPolicy):
        self.db = db
        self.policy = policy

    def clean_archive_tables(self, dry_run: bool = False) -> Dict:
        """Удаление архивных записей старше archive_ttl_days."""
        archive_ttl = self.policy.get_archive_ttl()
        archive_cutoff = datetime.utcnow() - timedelta(days=archive_ttl)
        result = {}

        for model in (models.AuditLogArchive, models.FindingArchive):
            try:
                count = self.db.query(model).filter(model.created_at < archive_cutoff).count()
                if dry_run:
                    result[model.__tablename__] = {"deleted": count, "dry_run": True}
                    continue
                deleted = self.db.query(model).filter(model.created_at < archive_cutoff).delete()
                self.db.commit()
                result[model.__tablename__] = {"deleted": deleted}
                logger.info(f"Cleaned {deleted} rows from {model.__tablename__}")
            except Exception as e:
                self.db.rollback()
                result[model.__tablename__] = {"deleted": 0, "error": str(e)}

        return result

    def clean_completed_tasks(self, dry_run: bool = False) -> Dict:
        """Удаление завершённых задач старше ttl_days."""
        cutoff = self.policy.get_cutoff_date("tasks")
        if not cutoff:
            return {"deleted": 0}

        try:
            count = (
                self.db.query(models.ScanTask)
                .filter(
                    models.ScanTask.status == "completed",
                    models.ScanTask.completed_at < cutoff,
                )
                .count()
            )
            if dry_run:
                return {"deleted": count, "dry_run": True}

            deleted = (
                self.db.query(models.ScanTask)
                .filter(
                    models.ScanTask.status == "completed",
                    models.ScanTask.completed_at < cutoff,
                )
                .delete()
            )
            self.db.commit()
            logger.info(f"Cleaned {deleted} completed tasks")
            return {"deleted": deleted}

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning tasks: {e}")
            return {"deleted": 0, "error": str(e)}


def clean_log_rotation(rotate_days: int, max_size_mb: int) -> Dict:
    """Ротация лог-файлов по возрасту и размеру.

    Возвращает список удалённых/обрезанных файлов. Начинается поиском
    типовых лог-файлов в каталогах `logs/` репозитория.
    """
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]  # корень репо
    cutoff = datetime.utcnow() - timedelta(days=rotate_days)
    removed = []
    for pattern in ("logs/*.log", "**/logs/*.log", "audit-agent-*/logs/*.log"):
        for path in sorted(root.glob(pattern)):
            try:
                stat = path.stat()
                if datetime.fromtimestamp(stat.st_mtime) < cutoff:
                    path.unlink()
                    removed.append(str(path))
                    continue
                if max_size_mb and stat.st_size > max_size_mb * 1024 * 1024:
                    path.unlink()
                    removed.append(f"{path} (size>={max_size_mb}MB)")
            except OSError:
                continue
    return {"removed": removed}
