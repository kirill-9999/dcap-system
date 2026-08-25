import requests
import pytest


class TestAuditAgentRegister:
    def test_register(self, manager_url):
        r = requests.post(
            f"{manager_url}/api/audit/agents/register",
            json={"name": "test-reg-agent", "hostname": "TEST-PC"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "agent_id" in data


class TestAuditAgentHeartbeat:
    def test_heartbeat(self, manager_url):
        r = requests.post(
            f"{manager_url}/api/audit/agents/register",
            json={"name": "test-hb-agent", "hostname": "TEST-PC"},
            timeout=10,
        )
        agent_id = r.json()["agent_id"]
        r2 = requests.post(
            f"{manager_url}/api/audit/agents/heartbeat",
            json={"agent_id": agent_id, "status": "online"},
            timeout=10,
        )
        assert r2.status_code == 200

    def test_heartbeat_updates_db(self, manager_url, db_conn):
        r = requests.post(
            f"{manager_url}/api/audit/agents/register",
            json={"name": "test-hb-db-agent", "hostname": "TEST-PC"},
            timeout=10,
        )
        agent_id = r.json()["agent_id"]
        requests.post(
            f"{manager_url}/api/audit/agents/heartbeat",
            json={"agent_id": agent_id, "status": "online"},
            timeout=10,
        )
        row = db_conn.execute(
            "SELECT last_heartbeat, status FROM audit_agents WHERE id = ?",
            (agent_id,),
        ).fetchone()
        assert row is not None
        assert row["last_heartbeat"] is not None
        assert row["status"] == "online"


class TestAuditEvents:
    def test_ingest_events(self, manager_url):
        r = requests.post(
            f"{manager_url}/api/audit/agents/register",
            json={"name": "test-ingest-agent", "hostname": "TEST-PC"},
            timeout=10,
        )
        agent_id = r.json()["agent_id"]
        events = [
            {"event_type": "read", "user": "test", "file_path": "D:\\integ_test.txt"},
            {"event_type": "write", "user": "test", "file_path": "D:\\integ_test2.txt"},
        ]
        r2 = requests.post(
            f"{manager_url}/api/audit/events",
            json={"agent_id": agent_id, "events": events},
            timeout=10,
        )
        assert r2.status_code == 200
        data = r2.json()
        assert data.get("saved", 0) >= 2

    def test_events_visible_in_api(self, manager_url, db_conn):
        r = requests.get(f"{manager_url}/api/audit", timeout=10)
        assert r.status_code == 200

    def test_audit_stats(self, manager_url):
        r = requests.get(f"{manager_url}/api/audit/stats", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data

    def test_events_stored_in_db(self, manager_url, db_conn):
        count = db_conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        assert count > 0, "No audit events in DB"
