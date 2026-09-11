# tests/e2e/test_agents_flow.py
import uuid

import pytest

AGENT_NAME = f"e2e-agent-{uuid.uuid4().hex[:8]}"


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_agent_registration(api_client, manager_url):
    """Регистрация агента → heartbeat → события → просмотр."""
    # 1. Регистрация (схема RegisterAgentRequest: name/hostname/version)
    r = api_client.post(
        f"{manager_url}/api/audit/agents/register",
        json={
            "name": AGENT_NAME,
            "hostname": "test-host-e2e",
            "version": "3.7.0",
        },
    )
    assert r.status_code in (200, 201), f"Register failed: {r.text}"
    agent_id = r.json().get("agent_id")
    assert agent_id

    # 2. Heartbeat
    r = api_client.post(
        f"{manager_url}/api/audit/agents/heartbeat",
        json={"agent_id": agent_id, "status": "online"},
    )
    assert r.status_code in (200, 204), f"Heartbeat failed: {r.text}"

    # 3. Отправка события (схема AuditEventPayload: event_type/file_path/user/...)
    r = api_client.post(
        f"{manager_url}/api/audit/events",
        json={
            "agent_id": agent_id,
            "events": [
                {
                    "event_source": "linux_agent",
                    "event_type": "file_access",
                    "user": "testuser",
                    "file_path": "/tmp/test.txt",
                    "source_host": "test-host-e2e",
                }
            ],
        },
    )
    assert r.status_code in (200, 201, 202), f"Events failed: {r.text}"
    assert r.json().get("saved", 0) >= 1

    # 4. Проверка через GET
    r = api_client.get(f"{manager_url}/api/audit", params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json().get("events"), list)