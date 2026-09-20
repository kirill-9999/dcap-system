# tests/unit/test_scanner_middleware_rbac.py — BUG-048b (Fix-спринт №2)
# Middleware преждевременно пропускал /api/scanner/* без извлечения JWT,
# из-за чего DELETE /api/scanner/{id} (require_admin) возвращал 401 для
# аутентифицированных пользователей вместо 403/404.
# Теперь запросы попадают в _is_machine_endpoint, где JWT извлекается.
import sys
from datetime import datetime
from pathlib import Path

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
from manager.src.auth.manager import AuthManager
from manager.src.auth.middleware import AuthMiddleware
from manager.src.auth.models import User, Role

from manager.src.api import scanner as scanner_api

pytestmark = [pytest.mark.unit]

SECRET = "test-secret-key-32-chars-long!!"


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

    # роли admin / viewer + пользователи
    admin_role = Role(name="admin", description="Full access")
    viewer_role = Role(name="viewer", description="Read only")
    session.add_all([admin_role, viewer_role])
    session.commit()

    admin = User(username="admin", is_active=True)
    admin.roles.append(admin_role)
    viewer = User(username="viewer", is_active=True)
    viewer.roles.append(viewer_role)
    session.add_all([admin, viewer])
    session.commit()
    session.refresh(admin)
    session.refresh(viewer)

    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": SECRET}})
    app.add_middleware(
        AuthMiddleware,
        auth_manager=am,
        db_session_factory=sessionmaker(
            bind=db_session.get_bind(), autoflush=False, autocommit=False
        ),
    )

    app.include_router(scanner_api.router)
    return TestClient(app)


def _token(auth_manager: AuthManager, user: User) -> str:
    return auth_manager.jwt.create_access_token(
        {"user_id": user.id, "username": user.username}
    )


@pytest.fixture()
def admin_token(client, db_session):
    admin = db_session.query(User).filter(User.username == "admin").first()
    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": SECRET}})
    return _token(am, admin)


@pytest.fixture()
def viewer_token(client, db_session):
    viewer = db_session.query(User).filter(User.username == "viewer").first()
    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": SECRET}})
    return _token(am, viewer)


# ============================================================
# BUG-048b: RBAC на DELETE /api/scanner/{id}
# ============================================================

def test_delete_scanner_viewer_403(client, viewer_token):
    resp = client.delete(
        "/api/scanner/999999",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403, f"viewer must get 403, got {resp.status_code}"


def test_delete_scanner_admin_404(client, admin_token):
    resp = client.delete(
        "/api/scanner/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404, f"admin must get 404 (not found), got {resp.status_code}"


def test_delete_scanner_unauth_401(client):
    resp = client.delete("/api/scanner/999999")
    assert resp.status_code == 401


def test_delete_scanner_garbage_token_401(client):
    resp = client.delete(
        "/api/scanner/999999",
        headers={"Authorization": "Bearer garbage.token.here"},
    )
    assert resp.status_code == 401


# ============================================================
# Machine-API остаётся публичным (by design)
# ============================================================

def test_scanner_heartbeat_public(client):
    """Machine-API heartbeat работает без JWT (by design)."""
    resp = client.post(
        "/api/scanner/heartbeat",
        json={"scanner_id": 1, "status": "idle"},
    )
    assert resp.status_code in (200, 400, 404)  # 400/404 если сканера нет


def test_scanner_register_public(client):
    """Machine-API register работает без JWT."""
    resp = client.post(
        "/api/scanner/register",
        json={"name": "test-mw-scanner"},
    )
    assert resp.status_code == 200


def test_scanner_list_public(client):
    """GET /api/scanner — machine-доступ, работает без JWT."""
    resp = client.get("/api/scanner")
    assert resp.status_code == 200


def test_scanner_list_with_jwt(client, viewer_token):
    """GET /api/scanner с JWT — тоже работает (JWT извлекается, но не обязателен)."""
    resp = client.get(
        "/api/scanner",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 200


def test_delete_scanner_mtls_relaxed_allows_jwt(client, admin_token):
    """В relaxed-режиме mTLS отсутствие сертификата не блокирует JWT."""
    resp = client.delete(
        "/api/scanner/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404  # не 401