import requests
import pytest


class TestManagerHealth:
    def test_health(self, manager_url):
        r = requests.get(f"{manager_url}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"

    def test_root_redirect(self, manager_url):
        r = requests.get(f"{manager_url}/", allow_redirects=False, timeout=10)
        assert r.status_code in (307, 301, 302)
        assert "8001" in r.headers.get("Location", "")


class TestResources:
    def test_list_resources(self, manager_url):
        r = requests.get(f"{manager_url}/api/resources", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_delete_resource(self, manager_url):
        r = requests.post(
            f"{manager_url}/api/resources",
            params={"path": "D:/test_integ", "type": "FILESYSTEM"},
            timeout=10,
        )
        assert r.status_code == 200
        rid = r.json()["id"]

        r2 = requests.delete(f"{manager_url}/api/resources/{rid}", timeout=10)
        assert r2.status_code == 200

    def test_scan_resource(self, manager_url, test_resource):
        if test_resource is None:
            pytest.skip("No test resource")
        r = requests.post(
            f"{manager_url}/api/resources/{test_resource}/scan",
            timeout=10,
        )
        assert r.status_code == 200


class TestTasks:
    def test_list_tasks(self, manager_url):
        r = requests.get(f"{manager_url}/api/tasks", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestFindings:
    def test_list_findings(self, manager_url):
        r = requests.get(f"{manager_url}/api/findings", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestCatalog:
    def test_catalog(self, manager_url):
        r = requests.get(f"{manager_url}/api/catalog", timeout=10)
        assert r.status_code == 200

    def test_catalog_tree(self, manager_url):
        r = requests.get(f"{manager_url}/api/catalog/tree", timeout=10)
        assert r.status_code == 200


class TestPermissions:
    def test_get_mode(self, manager_url):
        r = requests.get(f"{manager_url}/api/permissions/mode", timeout=10)
        assert r.status_code == 200
        assert "current_mode" in r.json()


class TestAuditManager:
    def test_audit_stats(self, manager_url):
        r = requests.get(f"{manager_url}/api/audit/stats", timeout=10)
        assert r.status_code == 200
        assert "total" in r.json()

    def test_audit_events(self, manager_url):
        r = requests.get(f"{manager_url}/api/audit", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "events" in data or "total" in data
