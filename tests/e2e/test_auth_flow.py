# tests/e2e/test_auth_flow.py
import pytest


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_auth_flow(manager_url, anon_client):
    """login → JWT → защищённый endpoint → logout."""
    # 1. Логин
    r = anon_client.post(
        f"{manager_url}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10,
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]

    # 2. Защищённый endpoint с токеном
    r = anon_client.get(
        f"{manager_url}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json()["username"] == "admin"

    # 3. Без токена — 401
    r = anon_client.get(f"{manager_url}/api/auth/me", timeout=10)
    assert r.status_code == 401

    # 4. Неверный пароль — 401
    r = anon_client.post(
        f"{manager_url}/api/auth/login",
        json={"username": "admin", "password": "wrong"},
        timeout=10,
    )
    assert r.status_code == 401

    # 5. Logout
    r = anon_client.post(
        f"{manager_url}/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code in (200, 204), f"Logout: {r.status_code} {r.text}"


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_auth_mode(manager_url, anon_client):
    """Режим аутентификации доступен без токена."""
    r = anon_client.get(f"{manager_url}/api/auth/mode", timeout=10)
    assert r.status_code == 200
    assert "mode" in r.json()