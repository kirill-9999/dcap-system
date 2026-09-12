"""E2E-тесты экспорта находок (День 40.4)."""
import csv
import io
import pytest
import requests

from fixtures.auth import login

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


@pytest.fixture
def viewer_client(manager_url):
    """Сессия под viewer-пользователем (создаётся через admin при необходимости)."""
    username, password = "e2e_viewer", "viewer12345"
    admin = login(manager_url)
    r = admin.get(f"{manager_url}/api/auth/users", params={"search": username}, timeout=10)
    exists = (r.status_code == 200 and any(
        u.get("username") == username for u in (r.json() or {}).get("items", [])
    ))
    if not exists:
        r = admin.post(f"{manager_url}/api/auth/users", timeout=10, json={
            "username": username,
            "password": password,
            "full_name": "E2E Viewer",
            "auth_source": "local",
            "is_active": True,
            "roles": ["viewer"],
        })
        if r.status_code not in (200, 201, 400):
            raise RuntimeError(f"create viewer user: {r.status_code} {r.text}")
    admin.close()

    session = login(manager_url, username=username, password=password)
    yield session
    session.close()


def test_export_csv_masked(manager_url, api_client):
    r = api_client.get(f"{manager_url}/api/findings/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["Content-Type"]
    assert "attachment" in r.headers["Content-Disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM
    reader = csv.reader(io.StringIO(r.content.decode("utf-8-sig")))
    headers = next(reader)
    assert "id" in headers and "match_text" in headers


def test_export_json_masked(manager_url, api_client):
    r = api_client.get(f"{manager_url}/api/findings/export?format=json")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_export_reveal_requires_auditor(manager_url, viewer_client):
    r = viewer_client.get(f"{manager_url}/api/findings/export?reveal=true")
    assert r.status_code == 403


def test_export_filters(manager_url, api_client):
    r = api_client.get(f"{manager_url}/api/findings/export?format=json&status=new")
    assert r.status_code == 200
    for item in r.json():
        assert item["status"] == "new"


def test_csv_injection_sanitized():
    from manager.src.core.csv_utils import sanitize_csv_cell
    assert sanitize_csv_cell("=cmd|' /C calc'!A0").startswith("'=")
    assert sanitize_csv_cell("+1234").startswith("'+")
    assert sanitize_csv_cell("@SUM(1)").startswith("'@")
    assert sanitize_csv_cell("normal") == "normal"