# tests/fixtures/auth.py — аутентификация (login, JWT-сессия).
import requests


def login(base_url: str, username: str = "admin", password: str = "admin123"):
    """Логин под дефолтным admin и возврат HTTP-сессии с Bearer-токеном.

    Дефолтный админ создаётся при старте Manager (db/init_roles.py: admin/admin123).
    """
    session = requests.Session()
    r = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    if r.status_code == 200:
        token = r.json().get("access_token")
        if token:
            session.headers["Authorization"] = f"Bearer {token}"
    return session


def get_token(base_url: str, username: str = "admin", password: str = "admin123") -> str:
    """Возвращает access_token (или пустую строку при неудаче)."""
    r = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    if r.status_code == 200:
        return r.json().get("access_token", "")
    return ""