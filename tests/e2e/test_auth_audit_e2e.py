# tests/e2e/test_auth_audit_e2e.py — BUG-095 (TASK-061/062, v3.13.24)
#
# Live-проверка аудита аутентификации против поднятого Manager (:8000/:18000).
# До v3.13.24 события auth_login/auth_failed/auth_logout НЕ писались в audit_logs.
#
# ВНИМАНИЕ: /api/auth/login — лимит 5 попыток в минуту на IP (AUTH_LOGIN_MAX_ATTEMPTS),
# поэтому на модуль — один логин admin, остальные проверки переиспользуют токен.
import uuid

import pytest
import requests

AUTH_EVENTS = (
    "auth_login",
    "auth_failed",
    "auth_logout",
    "user_created",
    "user_updated",
    "user_deleted",
    "user_password_changed",
    "role_assigned",
    "role_revoked",
)


@pytest.fixture(scope="module")
def admin(manager_url):
    """Две admin-сессии на модуль (rate-limit логина: 5 попыток/мин на IP).

    `a` — основная (в конце теста логаутится, её токен попадает в blacklist),
    `b` — запасная, не логаутится (для проверок /api/audit ПОСЛЕ logout).
    """
    from fixtures.auth import login as _login

    a = _login(manager_url, "admin", "admin123")
    b = _login(manager_url, "admin", "admin123")
    if "Authorization" not in a.headers or "Authorization" not in b.headers:
        pytest.skip("логин admin не удался (проверьте admin/admin123)")
    return {"a": a, "b": b}


def _audit(manager_url, session, event_type, limit=5):
    r = requests.get(
        f"{manager_url}/api/audit?event_type={event_type}&limit={limit}",
        headers=session.headers,
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("events") or []


def _latest(manager_url, session, event_type):
    events = _audit(manager_url, session, event_type)
    return events[0] if events else None


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_full_auth_flow_audited(manager_url, admin):
    """Логин → CRUD пользователя → роли → удаление → logout: всё в audit_logs."""
    a, b = admin["a"], admin["b"]
    marker = f"e2e_audit_{uuid.uuid4().hex[:8]}"
    pw = "E2ePass123!"

    # 1. создание пользователя
    r = requests.post(
        f"{manager_url}/api/auth/users",
        headers=a.headers,
        json={"username": marker, "password": pw, "roles": ["viewer"]},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]

    ev = _latest(manager_url, b, "user_created")
    assert ev is not None, "нет user_created в /api/audit"
    assert ev["user"] == "admin"
    assert ev["metadata"]["target_user_id"] == uid
    assert ev["metadata"]["target_username"] == marker
    assert pw not in str(ev), "пароль не должен попадать в аудит"

    # 2. смена ролей
    r = requests.put(
        f"{manager_url}/api/auth/users/{uid}/roles",
        headers=a.headers,
        json={"roles": ["viewer", "auditor"]},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    ev = _latest(manager_url, b, "role_assigned")
    assert ev is not None, "нет role_assigned"
    assert ev["metadata"]["role"] == "auditor"
    assert ev["metadata"]["target_user_id"] == uid

    # 3. блокировка учётки
    r = requests.put(
        f"{manager_url}/api/auth/users/{uid}/status",
        headers=a.headers,
        json={"is_active": False},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    ev = _latest(manager_url, b, "user_updated")
    assert ev["metadata"]["changes"]["is_active"] is False

    # 4. неудачный вход отключённого пользователя
    r = requests.post(
        f"{manager_url}/api/auth/login",
        json={"username": marker, "password": pw},
        timeout=20,
    )
    assert r.status_code == 401, r.text
    ev = _latest(manager_url, b, "auth_failed")
    assert ev is not None, "нет auth_failed"
    assert ev["user"] == marker
    assert ev["metadata"]["reason"] == "user_inactive"
    assert pw not in str(ev), "пароль не должен попадать в аудит"

    # 5. удаление пользователя
    r = requests.delete(f"{manager_url}/api/auth/users/{uid}", headers=a.headers, timeout=20)
    assert r.status_code == 200, r.text
    ev = _latest(manager_url, b, "user_deleted")
    assert ev["metadata"]["target_user_id"] == uid
    assert ev["metadata"]["target_username"] == marker

    # 6. выход из системы (токен a после этого в blacklist — запросы только через b)
    r = requests.post(f"{manager_url}/api/auth/logout", headers=a.headers, timeout=20)
    assert r.status_code == 200, r.text

    ev = _latest(manager_url, b, "auth_logout")
    assert ev is not None, "нет auth_logout"
    assert ev["user"] == "admin"
    assert ev["file_path"] == "/api/auth/logout"

    # 7. auth_login — от логинов в фикстуре модуля
    ev = _latest(manager_url, b, "auth_login")
    assert ev is not None, "нет auth_login"
    assert ev["user"] == "admin"
    assert ev["file_path"] == "/api/auth/login"
    assert "eyJ" not in str(ev["metadata"]), "токен не должен попадать в аудит"


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_failed_login_audited(manager_url, admin):
    """Неудачный логин → auth_failed в audit_logs (проверка на сыром API)."""
    b = admin["b"]
    name = f"ghost_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{manager_url}/api/auth/login",
        json={"username": name, "password": "no-such-password"},
        timeout=20,
    )
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "Invalid credentials"

    events = _audit(manager_url, b, "auth_failed", limit=10)
    mine = [e for e in events if e.get("user") == name]
    assert mine, f"auth_failed для {name} не найден в /api/audit"
    assert mine[0]["metadata"]["reason"] == "user_not_found"
    assert "no-such-password" not in str(mine[0])
