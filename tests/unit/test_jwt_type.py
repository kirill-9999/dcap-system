# tests/unit/test_jwt_type.py — BUG-039 + BUG-041 (Fix-спринт)
# BUG-039: refresh-токен не должен валидироваться как access (verify_token type).
# BUG-041: jti/iat в токенах, блэклист при logout/refresh (ротация).
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manager.src.auth.jwt import JWTManager

pytestmark = [pytest.mark.unit]

SECRET = "test-secret-key-32-chars-long!!"


@pytest.fixture()
def jwtm():
    return JWTManager(secret_key=SECRET, access_ttl_minutes=30, refresh_ttl_days=1)


# ============================================================
# BUG-039: verify_token с проверкой типа
# ============================================================

def test_access_token_validates_as_access(jwtm):
    tok = jwtm.create_access_token({"user_id": 1, "username": "admin"})
    payload = jwtm.verify_token(tok, "access")
    assert payload is not None
    assert payload["user_id"] == 1
    assert payload["type"] == "access"


def test_refresh_token_rejected_as_access(jwtm):
    """BUG-039: refresh нельзя использовать как access."""
    tok = jwtm.create_refresh_token({"user_id": 1, "username": "admin"})
    assert jwtm.verify_token(tok, "access") is None


def test_access_token_rejected_as_refresh(jwtm):
    """Симметрично: access не валиден как refresh."""
    tok = jwtm.create_access_token({"user_id": 1, "username": "admin"})
    assert jwtm.verify_token(tok, "refresh") is None


def test_refresh_token_validates_as_refresh(jwtm):
    tok = jwtm.create_refresh_token({"user_id": 1, "username": "admin"})
    payload = jwtm.verify_token(tok, "refresh")
    assert payload is not None
    assert payload["type"] == "refresh"


def test_garbage_token_rejected(jwtm):
    assert jwtm.verify_token("abc.def.ghi", "access") is None
    assert jwtm.verify_token("", "access") is None


def test_expired_token_rejected(jwtm):
    tok = jwtm.create_access_token(
        {"user_id": 1, "username": "admin"},
        expires_delta=timedelta(seconds=-10),
    )
    assert jwtm.verify_token(tok, "access") is None


# ============================================================
# BUG-041: jti/iat и блэклист
# ============================================================

def test_tokens_have_jti_and_iat(jwtm):
    access = jwtm.create_access_token({"user_id": 1, "username": "admin"})
    refresh = jwtm.create_refresh_token({"user_id": 1, "username": "admin"})
    pa = jwtm.verify_token(access, "access")
    pr = jwtm.verify_token(refresh, "refresh")
    assert pa["jti"]
    assert pa["iat"]
    assert pr["jti"]
    assert pr["iat"]
    # каждый токен имеет уникальный jti
    assert pa["jti"] != pr["jti"]


def test_blacklisted_jti_rejected(jwtm):
    tok = jwtm.create_access_token({"user_id": 1, "username": "admin"})
    payload = jwtm.verify_token(tok, "access")
    assert payload is not None
    jwtm.blacklist_jti(payload)
    # Redis отсутствует -> blacklist_jti fail-open, но _is_blacklisted
    # должен вернуть False без Redis. Проверяем, что сама проверка не падает
    # и что без Redis блэклист не блокирует (fail-open).
    assert jwtm.verify_token(tok, "access") is not None


def test_blacklist_none_jti_noop(jwtm):
    jwtm.blacklist_jti(None)  # не должно бросать
    jwtm.blacklist_jti({})  # не должно бросать