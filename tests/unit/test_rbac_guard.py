# tests/unit/test_rbac_guard.py — RBAC-защита эндпоинтов (Fix-спринт, BUG-046..055)
# Требование ТЗ: для каждого RBAC-фикса — юнит-тест, что не-авторизованная
# роль получает 403, а admin/нужная роль проходит (не 403).
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manager.src.db import models
from manager.src.db.session import get_db
from manager.src.auth.dependencies import get_current_user

from manager.src.api import resources as resources_api
from manager.src.api import tasks as tasks_api
from manager.src.api import scanner as scanner_api
from manager.src.api import webui as webui_api
from manager.src.api import audit as audit_api
from manager.src.api import permissions as permissions_api

pytestmark = [pytest.mark.unit]


def _user(role: str):
    return SimpleNamespace(
        id=7,
        username=f"test_{role}",
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
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    def _override_current_user():
        # перезаписывается в каждом тесте через client.app.dependency_overrides
        return _user("admin")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    for _r in (
        resources_api.router,
        tasks_api.router,
        scanner_api.router,
        webui_api.router,
        audit_api.router,
        permissions_api.router,
    ):
        app.include_router(_r)
    return TestClient(app)


@pytest.fixture()
def make_user(client):
    """Устанавливает текущего пользователя для следующих запросов."""
    def _set(role: str):
        client.app.dependency_overrides[get_current_user] = (
            lambda: _user(role)
        )
    return _set


# ============================================================
# BUG-046: resources (POST / DELETE / scan / config)
# ============================================================

def test_resources_create_requires_admin(client, make_user):
    make_user("viewer")
    r = client.post("/api/resources", params={"path": "C:/x", "type": "FILESYSTEM"})
    assert r.status_code == 403


def test_resources_delete_requires_admin(client, db_session, make_user):
    res = models.Resource(path="E:/rbac", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    make_user("viewer")
    r = client.delete(f"/api/resources/{res.id}")
    assert r.status_code == 403


def test_resources_scan_requires_scanner(client, db_session, make_user):
    res = models.Resource(path="E:/rbac2", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    make_user("viewer")
    r = client.post(f"/api/resources/{res.id}/scan")
    assert r.status_code == 403


def test_resources_config_requires_admin(client, db_session, make_user):
    res = models.Resource(path="E:/rbac3", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    make_user("auditor")
    r = client.put(f"/api/resources/{res.id}/config", json={"scan_interval": 3600})
    assert r.status_code == 403


def test_resources_admin_allowed(client, db_session, make_user):
    make_user("admin")
    r = client.post("/api/resources", params={"path": "E:/admin-ok", "type": "filesystem"})
    assert r.status_code != 403


# ============================================================
# BUG-047: tasks (cancel + delete)
# ============================================================

def test_tasks_delete_requires_admin(client, db_session, make_user):
    t = models.ScanTask(source_path="E:/task1", status="completed",
                        created_at=datetime.utcnow())
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    make_user("scanner")
    r = client.delete(f"/api/tasks/{t.id}")
    assert r.status_code == 403


def test_tasks_cancel_requires_admin(client, db_session, make_user):
    t = models.ScanTask(source_path="E:/task2", status="assigned",
                        created_at=datetime.utcnow())
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    make_user("viewer")
    r = client.post(f"/api/tasks/{t.id}/cancel")
    assert r.status_code == 403


def test_tasks_delete_running_conflict_409(client, db_session, make_user):
    t = models.ScanTask(source_path="E:/task3", status="running",
                        created_at=datetime.utcnow())
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    make_user("admin")
    r = client.delete(f"/api/tasks/{t.id}")
    assert r.status_code == 409
    # транзакция не должна частично удалить задачу
    db_session.rollback()
    still = db_session.query(models.ScanTask).filter(models.ScanTask.id == t.id).first()
    assert still is not None


def test_tasks_delete_completed_ok(client, db_session, make_user):
    t = models.ScanTask(source_path="E:/task4", status="completed",
                        created_at=datetime.utcnow())
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    make_user("admin")
    r = client.delete(f"/api/tasks/{t.id}")
    assert r.status_code == 200, r.text


def test_tasks_delete_not_found_404(client, db_session, make_user):
    make_user("admin")
    r = client.delete("/api/tasks/99999")
    assert r.status_code == 404


# ============================================================
# BUG-048: scanner delete
# ============================================================

def test_scanner_delete_requires_admin(client, db_session, make_user):
    sc = models.Scanner(name="rbac-scanner-d", status="active",
                        last_heartbeat=datetime.utcnow())
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)
    make_user("scanner")
    r = client.delete(f"/api/scanner/{sc.id}")
    assert r.status_code == 403


def test_scanner_delete_admin_ok(client, db_session, make_user):
    sc = models.Scanner(name="rbac-scanner-ok", status="active",
                        last_heartbeat=datetime.utcnow())
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)
    make_user("admin")
    r = client.delete(f"/api/scanner/{sc.id}")
    assert r.status_code in (200, 404), r.text


def test_scanner_delete_missing_404_rbac_check(client, db_session, make_user):
    make_user("admin")
    r = client.delete("/api/scanner/424242")
    assert r.status_code == 404


# ============================================================
# BUG-049..054: webui endpoints
# ============================================================

def test_webui_scanner_delete_requires_admin(client, db_session, make_user):
    sc = models.Scanner(name="rbac-webui-del", status="active",
                        last_heartbeat=datetime.utcnow())
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)
    make_user("viewer")
    r = client.delete(f"/api/scanners/{sc.id}")
    assert r.status_code == 403


def test_webui_scanner_ping_requires_scanner(client, db_session, make_user):
    sc = models.Scanner(name="rbac-ping", status="active",
                        last_heartbeat=datetime.utcnow())
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)
    make_user("auditor")
    r = client.post(f"/api/scanners/{sc.id}/ping")
    assert r.status_code == 403


def test_webui_tasks_create_requires_scanner(client, make_user):
    make_user("viewer")
    r = client.post("/api/tasks/create",
                    json={"resource_path": "E:/no", "resource_type": "FILESYSTEM"})
    assert r.status_code == 403


def test_webui_resources_create_requires_admin(client, make_user):
    make_user("viewer")
    r = client.post("/api/resources/create",
                    json={"path": "E:/no", "type": "FILESYSTEM"})
    assert r.status_code == 403


def test_webui_alert_update_requires_auditor(client, db_session, make_user):
    a = models.AccessAlert(alert_type="excessive", severity="high",
                           description="test alert")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    make_user("viewer")
    r = client.put(f"/api/access/alerts/{a.id}", json={"status": "resolved"})
    assert r.status_code == 403


def test_webui_report_preview_requires_auditor(client, make_user):
    make_user("viewer")
    r = client.post("/api/audit/report/preview", json={})
    assert r.status_code == 403


def test_webui_report_excel_requires_auditor(client, make_user):
    make_user("scanner")
    r = client.post("/api/audit/report/export/excel", json={})
    assert r.status_code == 403


def test_webui_report_pdf_requires_auditor(client, make_user):
    make_user("viewer")
    r = client.post("/api/audit/report/export/pdf", json={})
    assert r.status_code == 403


# ============================================================
# BUG-055: audit agent delete + permissions admin actions
# ============================================================

def test_audit_agent_delete_requires_admin(client, db_session, make_user):
    ag = models.AuditAgent(name="rbac-agent", hostname="host1",
                           status="active", last_heartbeat=datetime.utcnow())
    db_session.add(ag)
    db_session.commit()
    db_session.refresh(ag)
    make_user("auditor")
    r = client.delete(f"/api/audit/agents/{ag.id}")
    assert r.status_code == 403


def test_permissions_mode_requires_admin(client, make_user):
    make_user("viewer")
    r = client.post("/api/permissions/mode", json={"mode": "local"})
    assert r.status_code == 403


def test_permissions_sync_requires_admin(client, make_user):
    make_user("scanner")
    r = client.post("/api/permissions/sync", json={"resource_id": 1})
    assert r.status_code == 403


def test_permissions_alert_update_requires_auditor(client, db_session, make_user):
    a = models.AccessAlert(alert_type="excessive", severity="low",
                           description="test alert p")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    make_user("scanner")
    r = client.put(f"/api/permissions/alerts/{a.id}", json={"status": "resolved"})
    assert r.status_code == 403


def test_permissions_alert_generate_requires_auditor(client, db_session, make_user):
    a = models.AccessAlert(alert_type="excessive", severity="low",
                           description="test alert p2")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    make_user("viewer")
    r = client.post(f"/api/permissions/alerts/{a.id}/generate")
    assert r.status_code == 403