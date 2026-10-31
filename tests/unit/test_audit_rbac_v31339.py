# tests/unit/test_audit_rbac_v31339.py — BUG-214 / BUG-223 / BUG-142 (v3.13.39)
#
# BUG-214: журнал аудита (GET /api/audit, GET /api/audit/stats) был открыт
# viewer/scanner — события содержат PII и следы ревью. Теперь только Auditor+.
# BUG-223: GET /api/audit/{id} отсутствовал — metadata конкретного события
# нельзя было прочитать (проверка «кто и зачем обращался к находке»).
# BUG-142: /api/audit/stats не возвращал total_resources — KPI «Ресурсов»
# в dashboard.js всегда был 0.
"""BUG-214/223/142 (v3.13.39): RBAC на журнал, деталь события, total_resources."""
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manager.src.api import audit as audit_api
from manager.src.auth.dependencies import get_current_user
from manager.src.db import models
from manager.src.db.session import get_db

pytestmark = [pytest.mark.unit]


class _FakeUser(SimpleNamespace):
    def has_role(self, name):
        return any(r.name == name for r in self.roles)


def _user(role, username=None):
    return _FakeUser(
        id=35,
        username=username or ("test_" + role),
        roles=[SimpleNamespace(name=role)],
    )


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


@pytest.fixture()
def seeded(db_session):
    """Три ресурса + три аудит-события (один finder_reveal с metadata)."""
    for i in range(3):
        db_session.add(models.Resource(path=f"C:/res{i}", type="filesystem"))
    db_session.add(
        models.AuditLog(
            event_type="auth_login",
            event_source="api",
            user="admin",
            file_path="/api/auth/login",
            metadata_json={"action": "login", "auth_mode": "local"},
        )
    )
    db_session.add(
        models.AuditLog(
            event_type="finding_reveal",
            event_source="api",
            user="auditor",
            file_path="/api/findings/42/reveal",
            metadata_json={"finding_id": 42, "category": "email"},
        )
    )
    db_session.commit()
    return {"resources": 3}


def _make_client(db_session, user):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.include_router(audit_api.router)
    return TestClient(app)


def _all_roles_client(db_session, role, username=None):
    return _make_client(db_session, _user(role, username))


# — BUG-214: RBAC на журнал и статистику —


def test_audit_list_forbidden_for_viewer(db_session):
    c = _all_roles_client(db_session, "viewer")
    assert c.get("/api/audit").status_code == 403
    assert c.get("/api/audit/stats").status_code == 403


def test_audit_list_forbidden_for_scanner(db_session):
    c = _all_roles_client(db_session, "scanner")
    assert c.get("/api/audit").status_code == 403
    assert c.get("/api/audit/stats").status_code == 403


def test_audit_list_allowed_for_auditor(db_session, seeded):
    c = _all_roles_client(db_session, "auditor")
    r = c.get("/api/audit")
    assert r.status_code == 200, r.text
    assert len(r.json()["events"]) >= 2


def test_audit_list_allowed_for_admin(db_session, seeded):
    c = _all_roles_client(db_session, "admin")
    r = c.get("/api/audit")
    assert r.status_code == 200, r.text
    assert len(r.json()["events"]) >= 2


# — BUG-142: total_resources в статистике —


def test_audit_stats_includes_total_resources(db_session, seeded):
    c = _all_roles_client(db_session, "auditor")
    r = c.get("/api/audit/stats")
    assert r.status_code == 200, r.text
    assert r.json()["total_resources"] == 3


# — BUG-223: деталь события с metadata_json + 404 —


def test_audit_log_detail_returns_metadata(db_session, seeded):
    c = _all_roles_client(db_session, "auditor")
    reveal = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "finding_reveal")
        .first()
    )
    r = c.get(f"/api/audit/{reveal.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["event_type"] == "finding_reveal"
    assert body["metadata_json"]["finding_id"] == 42
    assert body["user"] == "auditor"


def test_audit_log_detail_not_found(db_session):
    c = _all_roles_client(db_session, "auditor")
    assert c.get("/api/audit/999999").status_code == 404