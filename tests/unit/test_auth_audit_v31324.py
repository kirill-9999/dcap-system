# tests/unit/test_auth_audit_v31324.py — BUG-095 (TASK-061/062, v3.13.24)
#
# Аудит аутентификации и управления пользователями в audit_logs.
# До v3.13.24 события auth_login / auth_failed / auth_logout / user_* /
# role_* НЕ писались — требования 152-ФЗ / GDPR / PCI DSS 10.2.x не выполнялись.
"""BUG-095 (TASK-061..062, v3.13.24): аудит auth и управления пользователями."""
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
from manager.src.auth.audit import _sanitize, role_diff
from manager.src.auth.dependencies import get_current_user
from manager.src.auth.manager import AuthManager
from manager.src.auth.models import Role, User
from manager.src.auth.rate_limit import login_limiter
from manager.src.db import models
from manager.src.db.session import get_db

pytestmark = [pytest.mark.unit]

JWT_SECRET = "test-secret-bug095"
ADMIN_PW = "admin123"
USER_PW = "user123"


# ===== fixtures =====


@pytest.fixture(autouse=True)
def _no_login_rate_limit():
    """Лимит 5 попыток/мин на IP мешал бы серии тестов (TestClient IP один)."""
    old_max, old_window = login_limiter.max_attempts, login_limiter.window_seconds
    login_limiter.max_attempts = 1000
    login_limiter._attempts.clear()
    yield
    login_limiter.max_attempts = old_max
    login_limiter.window_seconds = old_window
    login_limiter._attempts.clear()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def seeded(db_session):
    """Роли + admin (audit_system) + два локальных пользователя."""
    for name in ("admin", "auditor", "viewer"):
        db_session.add(Role(name=name))
    db_session.commit()

    admin = User(username="admin", auth_source="local", is_active=True)
    admin.set_password(ADMIN_PW)
    admin.roles = [db_session.query(Role).filter(Role.name == "admin").first()]
    db_session.add(admin)

    auditor = User(username="auditor", auth_source="local", is_active=True)
    auditor.set_password(USER_PW)
    auditor.roles = [db_session.query(Role).filter(Role.name == "auditor").first()]
    db_session.add(auditor)

    blocked = User(username="blocked", auth_source="local", is_active=False)
    blocked.set_password(USER_PW)
    db_session.add(blocked)

    db_session.commit()
    for u in (admin, auditor, blocked):
        db_session.refresh(u)
    return {"admin": admin, "auditor": auditor, "blocked": blocked}


@pytest.fixture()
def client(db_session, seeded):
    """TestClient с auth-роутером, реальным AuthManager (mode=local) и SQLite."""
    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": JWT_SECRET}})
    auth_router.set_auth_manager(am)

    app = FastAPI()

    def _override_get_db():
        yield db_session

    def _override_current_user():
        return seeded["admin"]

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    app.include_router(auth_router.router)
    with TestClient(app) as c:
        yield c
    auth_router.set_auth_manager(None)


# ===== helpers =====


def _events(db, event_type=None):
    q = db.query(models.AuditLog)
    if event_type:
        q = q.filter(models.AuditLog.event_type == event_type)
    return q.order_by(models.AuditLog.id.asc()).all()


def _last(db, event_type):
    rows = _events(db, event_type)
    assert rows, f"нет событий {event_type}"
    return rows[-1]


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ===== TEST: аудит аутентификации (TASK-061) =====


class TestAuthAudit:
    def test_login_success_writes_auth_login(self, client, db_session):
        """POST /api/auth/login (успех) → audit_logs: event_type=auth_login."""
        r = _login(client, "admin", ADMIN_PW)
        assert r.status_code == 200, r.text

        log = _last(db_session, "auth_login")
        assert log.user == "admin"
        assert log.event_source == "api"
        assert log.file_path == "/api/auth/login"
        assert log.metadata_json["action"] == "login_success"
        assert log.metadata_json["auth_source"] == "local"
        assert log.metadata_json["auth_method"] == "local_jwt"
        assert "admin" in log.metadata_json["roles"]

    def test_login_failure_writes_auth_failed(self, client, db_session):
        """POST /api/auth/login (неверный пароль) → event_type=auth_failed."""
        r = _login(client, "admin", "wrong-password")
        assert r.status_code == 401, r.text

        log = _last(db_session, "auth_failed")
        assert log.user == "admin"
        assert log.metadata_json["action"] == "login_failed"
        assert log.metadata_json["reason"] == "invalid_credentials"
        assert log.metadata_json["attempted_username"] == "admin"
        assert not _events(db_session, "auth_login"), "неудачный вход не должен давать auth_login"

    def test_login_failure_no_password_in_metadata(self, client, db_session):
        """В metadata для auth_failed НЕТ пароля/хеша."""
        r = _login(client, "admin", "super-secret-password-123")
        assert r.status_code == 401

        log = _last(db_session, "auth_failed")
        blob = str(log.metadata_json).lower()
        assert "super-secret-password-123" not in blob
        assert "password" not in log.metadata_json
        assert "$2b$" not in blob, "хеш пароля не должен попадать в аудит"
        # Вся БД-строка тоже без секрета
        assert "super-secret-password-123" not in str(log.__dict__).lower()

    def test_logout_writes_auth_logout(self, client, db_session):
        """POST /api/auth/logout → event_type=auth_logout."""
        assert _login(client, "admin", ADMIN_PW).status_code == 200
        r = client.post("/api/auth/logout")
        assert r.status_code == 200, r.text

        log = _last(db_session, "auth_logout")
        assert log.user == "admin"
        assert log.file_path == "/api/auth/logout"
        assert log.metadata_json["action"] == "logout"
        assert log.metadata_json.get("jti"), "jti токена должен быть записан"
        # сам токен в аудит не пишется
        assert "eyJ" not in str(log.metadata_json)

    def test_auth_failed_invalid_user(self, client, db_session):
        """Несуществующий username → auth_failed, metadata.reason=user_not_found."""
        r = _login(client, "no_such_user", "whatever")
        assert r.status_code == 401, r.text

        log = _last(db_session, "auth_failed")
        assert log.user == "no_such_user"
        assert log.metadata_json["reason"] == "user_not_found"
        # HTTP-ответ остаётся общим — не перечисляем существующие учётки
        assert r.json()["detail"] == "Invalid credentials"

    def test_auth_failed_inactive_user(self, client, db_session):
        """is_active=False → auth_failed, metadata.reason=user_inactive."""
        r = _login(client, "blocked", USER_PW)
        assert r.status_code == 401, r.text

        log = _last(db_session, "auth_failed")
        assert log.user == "blocked"
        assert log.metadata_json["reason"] == "user_inactive"
        assert r.json()["detail"] == "Invalid credentials"


# ===== TEST: аудит управления пользователями (TASK-062) =====


class TestUserManagementAudit:
    def test_user_created_writes_event(self, client, db_session):
        """POST /api/auth/users → event_type=user_created, metadata.target_user_id."""
        r = client.post(
            "/api/auth/users",
            json={"username": "newbie", "password": "newbie123", "roles": ["viewer"]},
        )
        assert r.status_code == 200, r.text
        created = r.json()

        log = _last(db_session, "user_created")
        assert log.user == "admin", "actor — выполнивший admin"
        assert log.metadata_json["target_user_id"] == created["id"]
        assert log.metadata_json["target_username"] == "newbie"
        assert log.metadata_json["auth_source"] == "local"
        assert log.metadata_json["roles"] == ["viewer"]
        assert "newbie123" not in str(log.metadata_json)

    def test_user_updated_writes_event(self, client, db_session):
        """PUT /api/auth/users/{id} → event_type=user_updated."""
        r = client.put("/api/auth/users/2", json={"full_name": "New Name", "is_active": False})
        assert r.status_code == 200, r.text

        log = _last(db_session, "user_updated")
        assert log.user == "admin"
        assert log.metadata_json["target_user_id"] == 2
        assert log.metadata_json["target_username"] == "auditor"
        assert log.metadata_json["changes"]["is_active"] is False
        # PII-поля пишутся без значений
        assert log.metadata_json["changes"]["full_name"] == "changed"

    def test_user_deleted_writes_event(self, client, db_session):
        """DELETE /api/auth/users/{id} → event_type=user_deleted."""
        r = client.delete("/api/auth/users/2")
        assert r.status_code == 200, r.text

        log = _last(db_session, "user_deleted")
        assert log.user == "admin"
        assert log.metadata_json["target_user_id"] == 2
        assert log.metadata_json["target_username"] == "auditor"
        assert log.metadata_json["roles"] == ["auditor"]

    def test_password_change_writes_event(self, client, db_session):
        """POST /api/auth/change-password → user_password_changed (пароль НЕ в metadata)."""
        app_user = db_session.query(User).filter(User.username == "auditor").first()
        app_user.set_password(USER_PW)
        db_session.commit()
        client.app.dependency_overrides[get_current_user] = lambda: app_user

        r = client.post(
            "/api/auth/change-password",
            json={"old_password": USER_PW, "new_password": "brand-new-pass-999"},
        )
        assert r.status_code == 200, r.text

        log = _last(db_session, "user_password_changed")
        assert log.user == "auditor"
        assert log.metadata_json["target_user_id"] == app_user.id
        assert log.metadata_json["by_admin"] is False
        assert log.metadata_json["self_service"] is True
        assert "brand-new-pass-999" not in str(log.metadata_json)

    def test_password_reset_by_admin_writes_event(self, client, db_session):
        """Админ сбрасывает пароль через PUT /users/{id} → user_password_changed."""
        r = client.put("/api/auth/users/2", json={"password": "admin-reset-777"})
        assert r.status_code == 200, r.text

        log = _last(db_session, "user_password_changed")
        assert log.user == "admin", "actor — admin, выполнивший сброс"
        assert log.metadata_json["target_user_id"] == 2
        assert log.metadata_json["target_username"] == "auditor"
        assert log.metadata_json["by_admin"] is True
        assert "admin-reset-777" not in str(log.metadata_json)
        # пароль вырезан и из user_updated
        upd = _last(db_session, "user_updated")
        assert "password" not in upd.metadata_json.get("changes", {})

    def test_role_assigned_writes_event(self, client, db_session):
        """PUT /users/{id}/roles → event_type=role_assigned, metadata.role."""
        r = client.put("/api/auth/users/2/roles", json={"roles": ["auditor", "viewer"]})
        assert r.status_code == 200, r.text

        log = _last(db_session, "role_assigned")
        assert log.user == "admin"
        assert log.metadata_json["role"] == "viewer"
        assert log.metadata_json["target_user_id"] == 2
        assert log.metadata_json["target_username"] == "auditor"
        # уже назначенная роль повторно не логируется
        assert [e.metadata_json["role"] for e in _events(db_session, "role_assigned")] == ["viewer"]

    def test_role_revoked_writes_event(self, client, db_session):
        """PUT /users/{id}/roles без прежней роли → event_type=role_revoked."""
        r = client.put("/api/auth/users/2/roles", json={"roles": ["viewer"]})
        assert r.status_code == 200, r.text

        log = _last(db_session, "role_revoked")
        assert log.user == "admin"
        assert log.metadata_json["role"] == "auditor"
        assert log.metadata_json["target_user_id"] == 2


# ===== TEST: безопасность (метаданные) =====


class TestMetadataSafety:
    def test_sanitize_strips_password_and_token(self):
        """_sanitize() рекурсивно вырезает password/token/hash/secret (BUG-095)."""
        raw = {
            "action": "login",
            "password": "p@ss",
            "new_password": "n@ss",
            "password_hash": "$2b$12$abc",
            "access_token": "eyJhbGciOi",
            "jwt_secret_key": "s3cret",
            "nested": {"token": "eyJhbGciOi", "keep": 1},
            "list": [{"credential": "x"}, {"keep": 2}],
            "attempted_username": "admin",
        }
        clean = _sanitize(raw)

        assert clean["action"] == "login"
        assert clean["attempted_username"] == "admin"
        for banned in ("password", "new_password", "password_hash",
                       "access_token", "jwt_secret_key", "credential", "token"):
            assert banned not in clean, banned
        assert clean["nested"] == {"keep": 1}
        # элемент, у которого все ключи вырезаны, остаётся пустым объектом
        assert clean["list"] == [{}, {"keep": 2}]

    def test_role_diff(self):
        """Разница ролей: назначенные/снятые."""
        assert role_diff(["viewer"], ["viewer", "admin"]) == (["admin"], [])
        assert role_diff(["admin", "viewer"], ["viewer"]) == ([], ["admin"])
        assert role_diff([], ["viewer"]) == (["viewer"], [])
        assert role_diff(["viewer"], ["viewer"]) == ([], [])
