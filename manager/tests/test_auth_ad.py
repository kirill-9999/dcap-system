# manager/tests/test_auth_ad.py
"""
Тесты AD-аутентификации (День 33): явный логин через AD (пароль),
автосоздание пользователя и маппинг AD групп → роли (т.ч. через Role.ad_group).

Запуск: python -m pytest manager/tests/test_auth_ad.py -v
"""

import sys
import asyncio
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from manager.src.auth.models import Base, User, Role
from manager.src.auth.manager import AuthManager


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return engine, session_factory()


def _seed_roles(db):
    roles = [
        Role(name="admin", description="Full access", ad_group="DCAP_Admins"),
        Role(name="auditor", description="Audit access", ad_group="DCAP_Auditors"),
        Role(name="scanner", description="Scan access", ad_group="DCAP_Scanners"),
        Role(name="viewer", description="Read-only", ad_group=None),
    ]
    db.add_all(roles)
    db.commit()
    return {r.name: r for r in roles}


def _auth_manager():
    config = {
        "auth": {
            "mode": "hybrid",
            "ad": {
                "server": "dc.example.com",
                "domain": "EXAMPLE",
                "base_dn": "DC=example,DC=com",
                "username": "svc",
                "password": "pw",
            },
            "auto_create_ad_users": True,
            "default_role": "viewer",
        }
    }
    return AuthManager(config)


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestAdPasswordAuth:
    def test_auto_create_ad_user_and_map_roles(self):
        engine, db = _make_session()
        seed = _seed_roles(db)

        am = _auth_manager()
        # Мок: AD доступен и возвращает пользователя с группой DCAP_Admins
        am.ad_auth.is_available = mock.Mock(return_value=True)
        am.ad_auth.domain = "EXAMPLE"
        am.ad_auth.authenticate = mock.Mock(
            return_value={
                "username": "ivanov",
                "email": "ivanov@example.com",
                "full_name": "Ivan Ivanov",
                "groups": ["DCAP_Admins", "Domain Users"],
            }
        )
        am.windows_auth.get_ad_user_from_db = mock.Mock(return_value=None)

        user = _run_async(am._authenticate_ad_password(db, "EXAMPLE\\ivanov", "secret"))

        assert user is not None
        assert user.username == "ivanov"
        assert user.domain_user == "EXAMPLE\\ivanov"
        assert user.auth_source == "ad"
        role_names = {r.name for r in user.roles}
        assert "admin" in role_names, role_names  # DCAP_Admins → admin (через Role.ad_group)
        assert "viewer" not in role_names
        db.close()
        engine.dispose()

    def test_existing_ad_user_updated_last_login(self):
        engine, db = _make_session()
        seed = _seed_roles(db)
        user = User(username="petrov", domain_user="EXAMPLE\\petrov", auth_source="ad")
        db.add(user)
        db.commit()

        am = _auth_manager()
        am.ad_auth.is_available = mock.Mock(return_value=True)
        am.ad_auth.domain = "EXAMPLE"
        am.ad_auth.authenticate = mock.Mock(
            return_value={
                "username": "petrov",
                "groups": ["DCAP_Auditors"],
            }
        )
        am.windows_auth.get_ad_user_from_db = mock.Mock(return_value=user)

        result = _run_async(am._authenticate_ad_password(db, "EXAMPLE\\petrov", "pw"))
        assert result is user
        assert user.last_login is not None
        db.close()
        engine.dispose()

    def test_invalid_ad_credentials_returns_none(self):
        engine, db = _make_session()
        _seed_roles(db)

        am = _auth_manager()
        am.ad_auth.is_available = mock.Mock(return_value=True)
        am.ad_auth.domain = "EXAMPLE"
        am.ad_auth.authenticate = mock.Mock(return_value=None)

        user = _run_async(am._authenticate_ad_password(db, "EXAMPLE\\sidorov", "wrong"))
        assert user is None
        db.close()
        engine.dispose()

    def test_group_mapping_via_config(self):
        engine, db = _make_session()
        seed = _seed_roles(db)

        config = {
            "auth": {
                "mode": "hybrid",
                "windows_auth": {"group_mapping": {"DevOps": "auditor"}},
                "auto_create_ad_users": True,
                "default_role": "viewer",
            }
        }
        am = AuthManager(config)
        am.ad_auth.is_available = mock.Mock(return_value=True)
        am.ad_auth.domain = "CORP"
        am.ad_auth.authenticate = mock.Mock(
            return_value={
                "username": "kuznetsov",
                "groups": ["DevOps"],
            }
        )
        am.windows_auth.get_ad_user_from_db = mock.Mock(return_value=None)

        user = _run_async(am._authenticate_ad_password(db, "CORP\\kuznetsov", "pw"))
        role_names = {r.name for r in user.roles}
        assert "auditor" in role_names
        db.close()
        engine.dispose()
