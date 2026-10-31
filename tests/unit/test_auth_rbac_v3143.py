# tests/unit/test_auth_rbac_v3143.py — RBAC Hotfix & Security (ТЗ 53.4e, v3.14.3)
#
# BUG-253: нельзя снять роль admin с себя (лок-аут).
# BUG-254: пользователь без ролей бесполезен — хотя бы одна роль.
# BUG-257: системные роли (admin/auditor/scanner/viewer) — name/ad_group
#          иммутабельны, правится только description.
# BUG-258: кастомные роли без permissions отключены до v3.1.0 (POST → 403).
"""53.4e (v3.14.3): RBAC-защита пользователей и ролей.

6 тестов: POST /roles → 403; PUT /roles/{system} (name) → 400;
PUT /roles/{system} (description) → 200; POST /users (без ролей) → 400;
PUT /users/{self} (без admin) → 400; PUT /users/{self} (с admin) → 200.
"""
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


def _system_role_id(db, name="admin"):
    return db.query(Role).filter(Role.name == name).first().id


# — BUG-258: кастомные роли отключены —


def test_create_role_disabled_403(client, db):
    r = client.post("/api/auth/roles", json={"name": "ops_reader"})
    assert r.status_code == 403, r.text
    assert "Кастомные роли отключены" in r.json()["detail"]
    assert db.query(Role).filter(Role.name == "ops_reader").count() == 0


# — BUG-257: системные роли иммутабельны по name / ad_group —


def test_system_role_rename_forbidden_400(client, db):
    rid = _system_role_id(db, "admin")
    r = client.put(f"/api/auth/roles/{rid}", json={"name": "superadmin"})
    assert r.status_code == 400, r.text
    assert db.query(Role).filter(Role.name == "superadmin").count() == 0
    assert db.query(Role).filter(Role.id == rid).first().name == "admin"


def test_system_role_description_editable_200(client, db):
    rid = _system_role_id(db, "viewer")
    r = client.put(f"/api/auth/roles/{rid}", json={"description": "Read-only"})
    assert r.status_code == 200, r.text
    role = db.query(Role).filter(Role.id == rid).first()
    assert role.description == "Read-only"
    assert role.name == "viewer"


# — BUG-254: хотя бы одна роль при создании пользователя —


def test_create_user_without_roles_400(client, db):
    r = client.post(
        "/api/auth/users",
        json={"username": "no_roles", "password": "secret123", "roles": []},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Выберите хотя бы одну роль"
    assert db.query(User).filter(User.username == "no_roles").count() == 0


# — BUG-253: нельзя снять admin с себя —


def test_update_self_remove_admin_forbidden_400(client, db, admin):
    r = client.put(f"/api/auth/users/{admin.id}", json={"roles": ["viewer"]})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Нельзя снять роль admin с себя"
    assert [x.name for x in db.query(User).filter(User.id == admin.id).first().roles] == ["admin"]


def test_update_self_keep_admin_ok_200(client, db, admin):
    r = client.put(f"/api/auth/users/{admin.id}", json={"roles": ["admin"]})
    assert r.status_code == 200, r.text
    assert "admin" in r.json()["roles"]
