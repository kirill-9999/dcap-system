# tests/unit/test_auth_password_v31339.py — BUG-201 (v3.13.39)
#
# change-password возвращал 200 OK, но хеш пароля в БД НЕ обновлялся — вход
# продолжал работать только со старым паролем. Причина (реальная, прод):
# AuthMiddleware грузит request.state.user в СВОЕЙ сессии и закрывает её после
# dispatch; мутация этого объекта в хендлере не попадала в сессию get_db() —
# фактический commit был пустым.
#
# Тест воспроизводит прод-расклад: current_user — объект из ОТДЕЛЬНОЙ
# «middleware»-сессии, а хендлер пишет в свою (override get_db).
"""BUG-201 (v3.13.39): change-password реально меняет хеш + валидации + аудит."""
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
from manager.src.auth.manager import AuthManager
from manager.src.auth.models import Role, User
from manager.src.auth.rate_limit import login_limiter
from manager.src.db import models
from manager.src.db.session import get_db

pytestmark = [pytest.mark.unit]

JWT_SECRET = "test-secret-bug201"
USER_PW = "user123"
NEW_PW = "brand-new-pass-999"


@pytest.fixture(autouse=True)
def _no_login_rate_limit():
    """Лимит 5 попыток/мин на IP мешал бы серии логинов (TestClient IP один)."""
    old = login_limiter.max_attempts
    login_limiter.max_attempts = 1000
    login_limiter._attempts.clear()
    yield
    login_limiter.max_attempts = old
    login_limiter._attempts.clear()


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


def _seed_users(db):
    for name in ("admin", "auditor", "viewer"):
        db.add(Role(name=name))
    db.flush()
    auditor = User(username="auditor", auth_source="local", is_active=True)
    auditor.set_password(USER_PW)
    auditor.roles = [db.query(Role).filter(Role.name == "auditor").first()]
    db.add(auditor)
    db.commit()


@pytest.fixture()
def client(db_session):
    """TestClient, где current_user живёт в ОТДЕЛЬНОЙ «middleware»-БД.

    Пере-запрос пользователя в сессии хендлера — именно то, что чинит BUG-201;
    без него commit пустой и логин новым паролем не работает.
    """
    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": JWT_SECRET}})
    auth_router.set_auth_manager(am)

    # handler-БД (override get_db) — здесь живут данные, куда пишет хендлер.
    _seed_users(db_session)

    mw_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=mw_engine)
    mw_session = sessionmaker(bind=mw_engine, autoflush=False, autocommit=False)()
    _seed_users(mw_session)

    app = FastAPI()

    def _override_get_db():
        yield db_session

    def _override_current_user():
        return (
            mw_session.query(User).filter(User.username == "auditor").first()
        )

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    app.include_router(auth_router.router)
    with TestClient(app) as c:
        yield c
    mw_session.close()
    mw_engine.dispose()
    auth_router.set_auth_manager(None)


def _change(client, old, new, confirm=None):
    return client.post(
        "/api/auth/change-password",
        json={"old_password": old, "new_password": new, "confirm_password": confirm},
    )


def test_change_password_persists_in_db(client, db_session):
    """200 + хеш реально обновился: старый пароль не работает, новый — работает."""
    r = _change(client, USER_PW, NEW_PW, NEW_PW)
    assert r.status_code == 200, r.text

    old_login = client.post(
        "/api/auth/login", json={"username": "auditor", "password": USER_PW}
    )
    assert old_login.status_code == 401, old_login.text

    new_login = client.post(
        "/api/auth/login", json={"username": "auditor", "password": NEW_PW}
    )
    assert new_login.status_code == 200, new_login.text

    user = db_session.query(User).filter(User.username == "auditor").first()
    assert user.check_password(NEW_PW)
    assert not user.check_password(USER_PW)


def test_change_password_wrong_current_401(client):
    r = _change(client, "wrong-old", NEW_PW, NEW_PW)
    assert r.status_code == 401, r.text


def test_change_password_confirm_mismatch_400(client):
    r = _change(client, USER_PW, NEW_PW, "other-confirm")
    assert r.status_code == 400, r.text


def test_change_password_writes_audit_after_commit(client, db_session):
    r = _change(client, USER_PW, NEW_PW)
    assert r.status_code == 200, r.text

    rows = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "user_password_changed")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].metadata_json.get("target_username") == "auditor"
    assert rows[0].metadata_json.get("self_service") is True
    # Ни старый, ни новый пароль в аудит не попадают.
    assert USER_PW not in str(rows[0].metadata_json)
    assert NEW_PW not in str(rows[0].metadata_json)