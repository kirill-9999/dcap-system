# tests/unit/test_roles_crud_audit_v31339.py — BUG-181 / BUG-168 (v3.13.39)
#
# BUG-181: CRUD ролей (POST/PUT/DELETE /api/auth/roles) не писался в аудит —
# создать или удалить роль можно было без следов. Теперь role_created /
# role_updated / role_deleted.
# BUG-168: системные роли (admin/auditor/scanner/viewer) нельзя переименовывать
# и менять AD-group — иначе RBAC ломается; правится только description.
"""BUG-181/168 (v3.13.39): аудит CRUD ролей + защита системных ролей."""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manager.src.auth import router as auth_router
from manager.src.auth.dependencies import get_current_user
from manager.src.auth.models import Role, User
from manager.src.db import models
from manager.src.db.session import get_db

pytestmark = [pytest.mark.unit]

ADMIN_PW = "admin123"


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
def db(db_session):
    return db_session


@pytest.fixture()
def admin(db_session):
    for name in ("admin", "auditor", "viewer", "scanner"):
        db_session.add(Role(name=name))
    db_session.commit()
    a = User(username="admin", auth_source="local", is_active=True)
    a.set_password(ADMIN_PW)
    a.roles = [db_session.query(Role).filter(Role.name == "admin").first()]
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


@pytest.fixture()
def client(db_session, admin):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.include_router(auth_router.router)
    return TestClient(app)


def _role_count(db, event_type):
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.event_type == event_type)
        .count()
    )


def _system_role_id(db, name="admin"):
    return db.query(Role).filter(Role.name == name).first().id


# — BUG-181: аудит CRUD ролей —


def test_role_created_writes_audit(client, db):
    # BUG-258 (v3.14.3): создание кастомных ролей отключено (403) — событие
    # role_created через API больше не достижимо и не пишется.
    r = client.post("/api/auth/roles", json={"name": "report_reader", "description": "RO"})
    assert r.status_code == 403, r.text
    assert _role_count(db, "role_created") == 0


def test_role_updated_writes_audit(client, db):
    rid = _system_role_id(db, "viewer")
    r = client.put(
        f"/api/auth/roles/{rid}",
        json={"description": "View-only access"},
    )
    assert r.status_code == 200, r.text
    assert _role_count(db, "role_updated") == 1
    row = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "role_updated")
        .first()
    )
    assert row.metadata_json.get("changes") == {"description": "changed"}


def test_role_deleted_writes_audit(client, db):
    # BUG-258 (v3.14.3): создание ролей отключено — наполняем БД напрямую.
    role = Role(name="temp_role")
    db.add(role)
    db.commit()
    db.refresh(role)
    rid = role.id

    r = client.delete(f"/api/auth/roles/{rid}")
    assert r.status_code == 200, r.text
    assert _role_count(db, "role_deleted") == 1
    row = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "role_deleted")
        .first()
    )
    assert row.metadata_json.get("role_name") == "temp_role"


# — BUG-168: системные роли immutable —


def test_system_role_cannot_be_renamed(client, db):
    rid = _system_role_id(db, "admin")
    r = client.put(f"/api/auth/roles/{rid}", json={"name": "superadmin"})
    assert r.status_code == 400, r.text
    assert db.query(Role).filter(Role.name == "superadmin").count() == 0


def test_system_role_ad_group_immutable(client, db):
    rid = _system_role_id(db, "auditor")
    r = client.put(f"/api/auth/roles/{rid}", json={"ad_group": "DOMAIN\\Auditors"})
    assert r.status_code == 400, r.text


def test_system_role_description_editable(client, db):
    rid = _system_role_id(db, "scanner")
    r = client.put(f"/api/auth/roles/{rid}", json={"description": "Scanner role"})
    assert r.status_code == 200, r.text
    role = db.query(Role).filter(Role.id == rid).first()
    assert role.description == "Scanner role"
    assert role.name == "scanner"


def test_custom_role_can_be_renamed(client, db):
    # BUG-258 (v3.14.3): создание ролей отключено — наполняем БД напрямую.
    role = Role(name="archive_admin")
    db.add(role)
    db.commit()
    db.refresh(role)
    rid = role.id

    r = client.put(f"/api/auth/roles/{rid}", json={"name": "archive_manager"})
    assert r.status_code == 200, r.text
    assert db.query(Role).filter(Role.id == rid).first().name == "archive_manager"