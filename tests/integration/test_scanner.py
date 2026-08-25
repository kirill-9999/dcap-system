import requests
import pytest


class TestScannerRegister:
    def test_register(self, manager_url):
        r = requests.post(
            f"{manager_url}/api/scanner/register",
            json={"name": "test-integ-scanner", "hostname": "TEST-PC"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "scanner_id" in data

    def test_register_duplicate(self, manager_url):
        payload = {"name": "dup-scanner", "hostname": "TEST-PC"}
        r1 = requests.post(f"{manager_url}/api/scanner/register", json=payload, timeout=10)
        r2 = requests.post(f"{manager_url}/api/scanner/register", json=payload, timeout=10)
        assert r1.status_code == 200
        assert r2.status_code == 200


class TestScannerHeartbeat:
    def test_heartbeat(self, manager_url):
        r = requests.post(
            f"{manager_url}/api/scanner/register",
            json={"name": "hb-scanner", "hostname": "TEST-PC"},
            timeout=10,
        )
        scanner_id = r.json()["scanner_id"]
        r2 = requests.post(
            f"{manager_url}/api/scanner/heartbeat",
            json={"scanner_id": scanner_id, "status": "idle"},
            timeout=10,
        )
        assert r2.status_code == 200

    def test_heartbeat_updates_last_seen(self, manager_url, db_conn):
        r = requests.post(
            f"{manager_url}/api/scanner/register",
            json={"name": "hb-check-scanner", "hostname": "TEST-PC"},
            timeout=10,
        )
        scanner_id = r.json()["scanner_id"]
        requests.post(
            f"{manager_url}/api/scanner/heartbeat",
            json={"scanner_id": scanner_id, "status": "idle"},
            timeout=10,
        )
        row = db_conn.execute(
            "SELECT last_heartbeat FROM scanners WHERE id = ?", (scanner_id,)
        ).fetchone()
        assert row is not None
        assert row["last_heartbeat"] is not None


class TestScannerTaskFlow:
    def test_pending_tasks(self, manager_url):
        r = requests.get(
            f"{manager_url}/api/scanner/tasks/pending",
            params={"scanner_id": 1},
            timeout=10,
        )
        assert r.status_code in (200, 404)

    def test_submit_results(self, manager_url, test_resource):
        if test_resource is None:
            pytest.skip("No test resource")
        r = requests.post(
            f"{manager_url}/api/resources/{test_resource}/scan",
            timeout=10,
        )
        task_id = r.json().get("id")
        if not task_id:
            pytest.skip("Could not create task")
        r2 = requests.post(
            f"{manager_url}/api/scanner/tasks/{task_id}/results",
            json={
                "findings": [
                    {"file_path": "test.txt", "category": "pii",
                     "value": "test@mail.com", "confidence": 0.95}
                ],
                "failed_files": [],
                "stats": {"files_scanned": 1, "files_failed": 0},
            },
            timeout=10,
        )
        assert r2.status_code == 200
