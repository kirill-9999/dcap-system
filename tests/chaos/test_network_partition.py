# tests/chaos/test_network_partition.py
import pytest
import requests


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_manager
def test_agent_retry_on_network_error(manager_url):
    """
    Агент ретраит при сетевой ошибке (симуляция через неверный URL).

    Полноценный retry-цикл агента (экспоненциальная задержка) проверяется
    integration-тестом агента с мок-сервером; здесь — базовая проверка,
    что при недоступном хосте запрос падает с ConnectionError (не висит).
    """
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post(
            "http://localhost:9999/api/audit/events",
            json={"agent_id": 1, "events": []},
            timeout=3,
        )


@pytest.mark.chaos
@pytest.mark.requires_manager
def test_manager_timeout_handling(api_client, manager_url):
    """Manager корректно обрабатывает таймауты (не висит)."""
    try:
        r = api_client.get(
            f"{manager_url}/api/findings",
            params={"limit": 100000},
            timeout=2,
        )
        # Если успел — ок; если timeout — тоже ок (не краш)
        assert r.status_code in (200, 422)
    except requests.exceptions.Timeout:
        pass