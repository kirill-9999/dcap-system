import requests
import pytest


class TestE2E:
    def test_full_cycle(self, manager_url, webui_url):
        results = []

        r = requests.get(f"{manager_url}/api/health", timeout=10)
        results.append(("Manager health", r.status_code == 200))

        r = requests.get(webui_url, timeout=10)
        results.append(("WebUI homepage", r.status_code == 200))

        r = requests.get(f"{manager_url}/", allow_redirects=False, timeout=10)
        results.append(("Manager redirect", r.status_code in (307, 301, 302)))

        r = requests.post(
            f"{manager_url}/api/audit/agents/register",
            json={"name": "e2e-agent", "hostname": "E2E-TEST"},
            timeout=10,
        )
        agent_id = r.json().get("agent_id") if r.status_code == 200 else None
        results.append(("Audit agent registered", agent_id is not None))

        if agent_id:
            r = requests.post(
                f"{manager_url}/api/audit/events",
                json={"agent_id": agent_id, "events": [
                    {"event_type": "read", "user": "e2e", "file_path": "D:\\e2e.txt"}
                ]},
                timeout=10,
            )
            results.append(("Audit event ingested", r.status_code == 200))

        r = requests.get(f"{webui_url}/api/audit", timeout=10)
        results.append(("WebUI audit API", r.status_code == 200))

        r = requests.get(f"{webui_url}/api/audit/stats", timeout=10)
        results.append(("WebUI audit stats", r.status_code == 200))

        r = requests.post(
            f"{webui_url}/api/audit/report/preview",
            json={"days": 7},
            timeout=10,
        )
        results.append(("Report preview", r.status_code == 200))

        r = requests.post(
            f"{webui_url}/api/audit/report/export/excel",
            json={"days": 7},
            timeout=10,
        )
        results.append(("Report Excel", r.status_code == 200))

        r = requests.post(
            f"{webui_url}/api/audit/report/export/pdf",
            json={"days": 7},
            timeout=10,
        )
        results.append(("Report PDF", r.status_code == 200))

        passed = sum(1 for _, ok in results if ok)
        total = len(results)
        for name, ok in results:
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] {name}")

        assert passed == total, f"E2E: {passed}/{total} passed, {total - passed} failed"

    def test_db_consistency(self, db_conn):
        tables = [
            "resources", "scanners", "scan_tasks", "findings",
            "audit_agents", "audit_logs",
        ]
        for t in tables:
            row = db_conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            assert row is not None, f"Table {t} does not exist"

        agents = db_conn.execute("SELECT COUNT(*) FROM audit_agents").fetchone()[0]
        assert agents > 0, "No audit agents in DB"

        events = db_conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        assert events > 0, "No audit events in DB"
