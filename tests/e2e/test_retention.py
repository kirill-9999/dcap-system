# tests/e2e/test_retention.py
import pytest


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_retention_policies(api_client, manager_url):
    """Политики хранения доступны (требуют роль admin)."""
    r = api_client.get(f"{manager_url}/api/retention/policies")
    assert r.status_code == 200, f"Policies: {r.status_code} {r.text}"
    policies = r.json()
    assert isinstance(policies, dict)
    assert "policies" in policies


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_retention_manual_run(api_client, manager_url):
    """Ручной запуск архивации (POST /api/retention/run)."""
    r = api_client.post(f"{manager_url}/api/retention/run", json={})
    # 200 (синхронно выполнено) или 2xx — допустимо; Celery здесь не используется
    assert r.status_code in (200, 202), f"Retention run: {r.status_code} {r.text}"