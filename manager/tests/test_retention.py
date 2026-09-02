# manager/tests/test_retention.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # корень репо

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from manager.src.db.models import (
    Base,
    AuditLog,
    AuditLogArchive,
    Finding,
    FindingArchive,
    ScanTask,
)
from manager.src.retention.policies import RetentionPolicy
from manager.src.retention.archiver import Archiver
from manager.src.retention.cleaner import Cleaner, clean_log_rotation


CONFIG = {
    "retention": {
        "enabled": True,
        "interval_hours": 24,
        "audit_events": {
            "ttl_days": 90,
            "archive_ttl_days": 365,
            "archive_enabled": True,
        },
        "findings": {"ttl_days": 180},
        "tasks": {"ttl_days": 30},
        "logs": {"rotate_days": 30, "max_size_mb": 100},
        "export": {"enabled": True, "format": "json", "path": "temp/test_archive/"},
    }
}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _old_log(db, days=95):
    e = AuditLog(
        agent_id=1,
        event_type="write",
        event_source="agent",
        user="test",
        file_path="C:/x/y.txt",
        created_at=datetime.utcnow() - timedelta(days=days),
    )
    db.add(e)
    db.commit()
    return e


def test_policies_defaults():
    policy = RetentionPolicy(CONFIG)
    assert policy.get_ttl("audit_events") == 90
    assert policy.get_ttl("findings") == 180
    assert policy.get_ttl("tasks") == 30
    assert policy.get_archive_ttl() == 365
    assert policy.archive_enabled() is True
    cutoff = policy.get_cutoff_date("tasks")
    assert cutoff is not None


def test_archiver_audit_events(db):
    _old_log(db)
    # свежее событие не трогаем
    db.add(AuditLog(agent_id=1, event_type="read", file_path="C:/new.txt"))
    db.commit()

    archiver = Archiver(db, RetentionPolicy(CONFIG))
    result = archiver.archive_audit_events(dry_run=False)

    assert result["archived"] == 1
    assert db.query(AuditLog).count() == 1
    assert db.query(AuditLogArchive).count() == 1
    arch = db.query(AuditLogArchive).one()
    assert arch.event_type == "write"
    assert arch.archived_at is not None


def test_archiver_audit_dry_run(db):
    _old_log(db)
    archiver = Archiver(db, RetentionPolicy(CONFIG))
    result = archiver.archive_audit_events(dry_run=True)
    assert result["dry_run"] is True
    assert result["archived"] == 1
    assert db.query(AuditLog).count() == 1
    assert db.query(AuditLogArchive).count() == 0


def test_archiver_findings(db):
    db.add(
        Finding(
            task_id=1,
            resource_id=1,
            file_path="C:/f.txt",
            category="secret",
            value="tok",
            created_at=datetime.utcnow() - timedelta(days=200),
        )
    )
    db.commit()
    archiver = Archiver(db, RetentionPolicy(CONFIG))
    result = archiver.archive_findings(dry_run=False)
    assert result["archived"] == 1
    assert db.query(Finding).count() == 0
    assert db.query(FindingArchive).count() == 1


def test_cleaner_archive_tables(db):
    db.add(
        AuditLogArchive(
            event_type="write",
            file_path="C:/old.txt",
            created_at=datetime.utcnow() - timedelta(days=400),
        )
    )
    db.add(
        AuditLogArchive(
            event_type="read",
            file_path="C:/fresh.txt",
            created_at=datetime.utcnow() - timedelta(days=10),
        )
    )
    db.add(
        FindingArchive(
            category="secret",
            value="v",
            file_path="C:/of.txt",
            created_at=datetime.utcnow() - timedelta(days=400),
        )
    )
    db.commit()

    cleaner = Cleaner(db, RetentionPolicy(CONFIG))
    result = cleaner.clean_archive_tables(dry_run=False)

    audit = result["audit_logs_archive"]["deleted"]
    findings = result["findings_archive"]["deleted"]
    assert audit == 1
    assert findings == 1
    assert db.query(AuditLogArchive).count() == 1  # свежий остался
    assert db.query(FindingArchive).count() == 0


def test_cleaner_completed_tasks(db):
    db.add(
        ScanTask(
            source_path="C:/p",
            status="completed",
            completed_at=datetime.utcnow() - timedelta(days=40),
        )
    )
    db.add(ScanTask(source_path="C:/fresh", status="running"))
    db.commit()

    cleaner = Cleaner(db, RetentionPolicy(CONFIG))
    result = cleaner.clean_completed_tasks(dry_run=False)
    assert result["deleted"] == 1
    assert db.query(ScanTask).count() == 1


def test_exporter_json(db, tmp_path):
    from manager.src.retention.exporter import Exporter

    db.add(AuditLogArchive(event_type="write", file_path="C:/a.txt", event_source="agent"))
    db.commit()

    cfg = dict(CONFIG)
    cfg["retention"]["export"]["path"] = str(tmp_path)
    exporter = Exporter(cfg)
    result = exporter.export_archived_audit_events(db, limit=100)
    assert result["exported"] == 1
    assert Path(result["file"]).exists()
    data = json.loads(Path(result["file"]).read_text(encoding="utf-8"))
    assert data[0]["event_type"] == "write"


def test_exporter_csv(db, tmp_path):
    from manager.src.retention.exporter import Exporter

    db.add(AuditLogArchive(event_type="read", file_path="C:/b.txt", event_source="agent"))
    db.commit()

    cfg = dict(CONFIG)
    cfg["retention"]["export"]["format"] = "csv"
    cfg["retention"]["export"]["path"] = str(tmp_path)
    exporter = Exporter(cfg)
    result = exporter.export_archived_audit_events(db, limit=100)
    assert result["exported"] == 1
    lines = Path(result["file"]).read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("id")
    assert "read" in lines[1]


def test_stale_running_flag_does_not_block():
    """Устаревший флаг running=true не должен блокировать новый прогон."""
    from manager.src.retention import state
    from manager.src.retention.runtime import run_retention

    state._state["running"] = True
    state.set_last_run({"archived_audit": {"archived": 0}})
    assert state.get_retention_status()["running"] is False

    result = run_retention(dry_run=True)
    assert "skipped" not in result
