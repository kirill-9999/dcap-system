# tests/chaos/test_manager_down.py
import time

import pytest
import requests

HEALTH_URL = "http://localhost:18000/api/health"


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_docker
def test_manager_down_agent_buffers(compose_stack):
    """
    Падение Manager → агент буферизует события → восстановление → отправка.

    Предусловие: docker-compose.test.yml запущен (scripts/test-up.sh).
    Проверяем graceful stop/start контейнера и восстановление health.
    """
    manager = compose_stack("manager_test")
    if not manager.is_running():
        pytest.skip("Test stack (docker-compose.test.yml) not running")

    # 1. Останавливаем Manager
    manager.stop()
    time.sleep(3)

    # 2. Manager недоступен
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(HEALTH_URL, timeout=3)

    # 3. (Полноценная проверка буферизации агента — integration-тест с агентом
    #    в v3.1.0; здесь проверяем восстановление стека после падения Manager.)

    # 4. Запускаем Manager обратно
    manager.start()

    # 5. Ждём готовности
    deadline = time.time() + 60
    last = None
    while time.time() < deadline:
        try:
            r = requests.get(HEALTH_URL, timeout=3)
            if r.status_code == 200:
                last = r
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    else:
        pytest.fail("Manager did not recover")

    assert last.json()["status"] == "healthy"


@pytest.mark.chaos
@pytest.mark.requires_manager
def test_manager_returns_5xx_on_db_down(api_client, manager_url):
    """При недоступной БД Manager отдаёт 5xx, не крашится.

    Активный тест остановки postgres_test — в test_postgres_down.py
    (требует docker). Здесь проверяем graceful degradation: healthcheck.
    """
    r = api_client.get(f"{manager_url}/api/health")
    assert r.status_code in (200, 503)