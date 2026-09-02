# manager/src/retention/exporter.py
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from sqlalchemy.orm import Session

from ..db import models

logger = logging.getLogger(__name__)


class Exporter:
    """Экспорт архивных данных в файлы (JSON/CSV)."""

    def __init__(self, config: dict):
        self.config = config
        self.export_config = config.get("retention", {}).get("export", {})
        self.enabled = self.export_config.get("enabled", True)
        self.format = str(self.export_config.get("format", "json")).lower()
        self.export_dir = Path(self.export_config.get("path", "data/archive/"))
        try:
            self.export_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.export_dir = Path("data/archive/")
            self.export_dir.mkdir(parents=True, exist_ok=True)

    def _make_filename(self, prefix: str) -> Path:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return self.export_dir / f"{prefix}_{ts}.{self.format}"

    def _write(self, filename: Path, data: List[dict]) -> None:
        if self.format == "csv":
            self._write_csv(filename, data)
        else:
            self._write_json(filename, data)

    def _write_json(self, filename: Path, data: List[dict]) -> None:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _write_csv(self, filename: Path, data: List[dict]) -> None:
        if not data:
            return
        with open(filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)

    def export_archived_audit_events(self, db: Session, limit: int = 10000) -> Dict:
        if not self.enabled:
            return {"exported": 0, "error": "Export disabled"}
        try:
            events = (
                db.query(models.AuditLogArchive)
                .order_by(models.AuditLogArchive.created_at.desc())
                .limit(limit)
                .all()
            )
            if not events:
                return {"exported": 0}
            filename = self._make_filename("audit_archive")
            self._write(filename, [e.to_dict() for e in events])
            logger.info(f"Exported {len(events)} audit events to {filename}")
            return {"exported": len(events), "file": str(filename)}
        except Exception as e:
            logger.error(f"Error exporting audit events: {e}")
            return {"exported": 0, "error": str(e)}

    def export_archived_findings(self, db: Session, limit: int = 10000) -> Dict:
        if not self.enabled:
            return {"exported": 0, "error": "Export disabled"}
        try:
            findings = (
                db.query(models.FindingArchive)
                .order_by(models.FindingArchive.created_at.desc())
                .limit(limit)
                .all()
            )
            if not findings:
                return {"exported": 0}
            filename = self._make_filename("findings_archive")
            self._write(filename, [f.to_dict() for f in findings])
            logger.info(f"Exported {len(findings)} findings to {filename}")
            return {"exported": len(findings), "file": str(filename)}
        except Exception as e:
            logger.error(f"Error exporting findings: {e}")
            return {"exported": 0, "error": str(e)}
