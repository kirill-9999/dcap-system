# tests/unit/test_audit_rollback_v31339.py — BUG-202 (v3.13.39)
#
# with_audit(): бизнес-изменение и аудит-запись коммитятся ОДНОЙ транзакцией.
# До v3.13.39 разные части кода писали изменение и аудит отдельно — при
# rollback аудит мог остаться в БД, а изменение — нет (нарушение целостности
# журнала 152-ФЗ / PCI DSS 10.2.x).
"""BUG-202 (v3.13.39): единая транзакция «изменение + аудит» через with_audit."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manager.src.api.audit_helper import _log_audit, with_audit
from manager.src.db import models

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()
    engine.dispose()


def _audit_count(db, event_type):
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.event_type == event_type)
        .count()
    )


def test_with_audit_writes_audit_and_commits(db_session):
    """Успешный блок: аудит-запись появляется в БД (commit выполнен)."""
    with with_audit(
        db_session,
        "resource_created",
        user="test_admin",
        file_path="C:/ok",
        metadata={"action": "created"},
    ):
        db_session.add(models.Resource(path="C:/ok", type="filesystem"))

    assert _audit_count(db_session, "resource_created") == 1
    row = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "resource_created")
        .first()
    )
    assert row.user == "test_admin"
    assert row.file_path == "C:/ok"
    assert row.metadata_json == {"action": "created"}
    # Изменение тоже закоммичено.
    assert db_session.query(models.Resource).filter(models.Resource.path == "C:/ok").count() == 1


def test_with_audit_rolls_back_audit_on_exception(db_session):
    """Исключение в теле блока: НИ аудита, НИ изменения — транзакция откатилась."""
    with pytest.raises(RuntimeError):
        with with_audit(
            db_session,
            "resource_created",
            user="test_admin",
            file_path="C:/rollback",
            metadata={"action": "created"},
        ):
            db_session.add(models.Resource(path="C:/rollback", type="filesystem"))
            db_session.flush()
            raise RuntimeError("boom")

    assert _audit_count(db_session, "resource_created") == 0
    assert db_session.query(models.Resource).filter(models.Resource.path == "C:/rollback").count() == 0


def test_with_audit_rolls_back_business_change(db_session):
    """Уже закоммиченное изменение НЕ теряется; несохранённое — откатывается."""
    db_session.add(models.Resource(path="C:/keep", type="filesystem"))
    db_session.commit()
    before = db_session.query(models.Resource).count()

    with pytest.raises(ValueError):
        with with_audit(
            db_session,
            "resource_deleted",
            user="test_admin",
            file_path="C:/keep",
            metadata={"action": "deleted"},
        ):
            db_session.delete(
                db_session.query(models.Resource).filter(models.Resource.path == "C:/keep").first()
            )
            db_session.flush()
            raise ValueError("nope")

    assert _audit_count(db_session, "resource_deleted") == 0
    assert db_session.query(models.Resource).count() == before


def test_log_audit_sanitizes_secrets_and_accepts_orm_user(db_session):
    """_log_audit: секреты вырезаются _sanitize(), user может быть ORM (сервис)."""
    from types import SimpleNamespace

    orm_user = SimpleNamespace(username="service_admin")

    _log_audit(
        db_session,
        "resource_updated",
        user=orm_user,
        file_path="C:/cfg",
        metadata={
            "action": "updated",
            "changed_fields": ["scan_config"],
            "scan_config": {"s3_secret_access_key": "AKIA-SECRET", "region": "eu"},
        },
    )
    db_session.commit()

    row = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "resource_updated")
        .first()
    )
    assert row is not None
    assert row.user == "service_admin"
    assert "s3_secret_access_key" not in row.metadata_json
    assert row.metadata_json["scan_config"]["region"] == "eu"