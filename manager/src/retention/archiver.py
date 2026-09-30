# manager/src/retention/archiver.py
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from typing import Dict

from ..db import models
from .policies import RetentionPolicy

# BUG-102 (TASK-072): Finding.reviewer = relationship("User") — строка, User живёт
# в manager.src.auth.models. Без этого импорта модуль падает при standalone-запуске
# (Celery worker, retention по расписанию): "expression 'User' failed to locate a name".
# Цикла нет: db.models не тянет retention, auth.models тянет только db.models.
from manager.src.auth.models import User  # noqa: F401

logger = logging.getLogger(__name__)


class Archiver:
    """Архивация данных (перемещение в архивные таблицы)."""

    def __init__(self, db: Session, policy: RetentionPolicy):
        self.db = db
        self.policy = policy

    def _move_to_archive(self, rows, archive_model, to_dict):
        """Move the given ORM rows into archive_model.

        Returns number archived.
        """
        self.db.flush()
        archived = 0
        for row in rows:
            data = to_dict(row)
            archive = archive_model(**data)
            self.db.add(archive)
            self.db.delete(row)
            archived += 1
        self.db.commit()
        return archived

    def archive_audit_events(self, dry_run: bool = False) -> Dict:
        """Архивация устаревших аудит-событий в архивную таблицу."""
        if not self.policy.archive_enabled():
            return {"archived": 0, "skipped": "archive disabled"}

        cutoff = self.policy.get_cutoff_date("audit_events")
        if not cutoff:
            return {"archived": 0, "error": "No TTL configured"}

        try:
            events = (
                self.db.query(models.AuditLog)
                .filter(models.AuditLog.created_at < cutoff)
                .order_by(models.AuditLog.created_at)
                .all()
            )
            if not events:
                return {"archived": 0}

            logger.info(f"Archiving {len(events)} audit events")
            if dry_run:
                return {"archived": len(events), "dry_run": True}

            def _to_archive(e):
                return {
                    "agent_id": e.agent_id,
                    "event_type": e.event_type,
                    "event_source": e.event_source,
                    "user": e.user,
                    "user_sid": e.user_sid,
                    "file_path": e.file_path,
                    "old_path": e.old_path,
                    "source_host": e.source_host,
                    "metadata_json": e.metadata_json,
                    "created_at": e.created_at,
                    "archived_at": datetime.utcnow(),
                }

            archived = self._move_to_archive(events, models.AuditLogArchive, _to_archive)
            logger.info(f"Archived {archived} audit events")
            return {"archived": archived}

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error archiving audit events: {e}")
            return {"archived": 0, "error": str(e)}

    def archive_findings(self, dry_run: bool = False) -> Dict:
        """Архивация устаревших находок в архивную таблицу."""
        cutoff = self.policy.get_cutoff_date("findings")
        if not cutoff:
            return {"archived": 0, "error": "No TTL configured"}

        try:
            findings = (
                self.db.query(models.Finding)
                .filter(models.Finding.first_seen_at < cutoff)
                .order_by(models.Finding.first_seen_at)
                .all()
            )
            if not findings:
                return {"archived": 0}

            logger.info(f"Archiving {len(findings)} findings")
            if dry_run:
                return {"archived": len(findings), "dry_run": True}

            def _to_archive(f):
                return {
                    "task_id": f.task_id,
                    "resource_id": f.resource_id,
                    "file_path": f.fragment_path or "",
                    "line_number": f.line_number,
                    "category": f.category,
                    "subcategory": None,
                    "value": f.match_text_masked or f.line_text_masked,
                    "confidence": f.confidence,
                    "context": f.context_before_masked,
                    "created_at": f.first_seen_at,
                    "archived_at": datetime.utcnow(),
                }

            archived = self._move_to_archive(findings, models.FindingArchive, _to_archive)
            logger.info(f"Archived {archived} findings")
            return {"archived": archived}

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error archiving findings: {e}")
            return {"archived": 0, "error": str(e)}
