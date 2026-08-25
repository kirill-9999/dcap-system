import pytest
import requests
import sqlite3
from pathlib import Path


@pytest.fixture(scope="session")
def manager_url():
    return "http://localhost:8000"


@pytest.fixture(scope="session")
def webui_url():
    return "http://localhost:8001"


@pytest.fixture(scope="session")
def db_path():
    return Path("manager/dcap.db")


@pytest.fixture
def db_conn(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def test_resource(manager_url):
    resp = requests.post(
        f"{manager_url}/api/resources",
        json={"path": "D:/Projects/dcap-system/test_files", "type": "FILESYSTEM"},
        timeout=10,
    )
    if resp.status_code == 200:
        rid = resp.json().get("id")
        yield rid
        requests.delete(f"{manager_url}/api/resources/{rid}", timeout=10)
    else:
        existing = requests.get(f"{manager_url}/api/resources", timeout=10)
        if existing.status_code == 200 and existing.json():
            yield existing.json()[0]["id"]
        else:
            yield None


@pytest.fixture(scope="session")
def test_agent(manager_url):
    resp = requests.post(
        f"{manager_url}/api/audit/agents/register",
        json={"name": "test-integration-agent", "hostname": "TEST-PC"},
        timeout=10,
    )
    if resp.status_code == 200:
        aid = resp.json().get("agent_id")
        yield aid
    else:
        yield None
