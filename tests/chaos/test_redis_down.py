# tests/chaos/test_redis_down.py
import time

import pytest
import requests

HEALTH_URL = "http://localhost:18000/api/health"


@pytest.mark.chaos
@pytest.mark.requires_docker
def test_redis_down_manager_works(compose_stack):
    """
    Падение Redis → Manager работает (fail-open).
    Rate-limit переключается на in-memory, кэш отключён (no-op).
    """
    redis = compose_stack("redis_test")
    if not redis.is_running():
        pytest.skip("Test stack (docker-compose.test.yml) not running")

    # 1. Останавливаем Redis
    redis.stop()
    time.sleep(3)

    # 2. Manager должен работать
    r = requests.get(HEALTH_URL, timeout=5)
    assert r.status_code == 200

    # 3. API-запросы работают (логин — без Redis, fail-open)
    r = requests.post(
        "http://localhost:18000/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=5,
    )
    assert r.status_code == 200, f"Login while Redis down: {r.status_code} {r.text}"

    # 4. Запускаем Redis обратно
    redis.start()
    time.sleep(5)

    # 5. Manager всё ещё работает
    r = requests.get(HEALTH_URL, timeout=5)
    assert r.status_code == 200