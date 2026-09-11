# tests/chaos/test_postgres_down.py
import time

import pytest
import requests

from fixtures.auth import get_token

HEALTH_URL = "http://localhost:18000/api/health"
STATS_URL = "http://localhost:18000/api/stats"


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_docker
def test_postgres_down_graceful(compose_stack):
    """
    Падение PostgreSQL → Manager отдаёт 5xx → восстановление.

    Пулы Manager используют pool_pre_ping=True, поэтому после рестарта PG
    соединения переустанавливаются автоматически.
    """
    pg = compose_stack("postgres_test")
    if not pg.is_running():
        pytest.skip("Test stack (docker-compose.test.yml) not running")

    token = get_token("http://localhost:18000")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # 1. Останавливаем PG
    pg.stop()
    time.sleep(5)

    # 2. Manager не должен крашиться (контейнер жив)
    mgr = compose_stack("manager_test")
    assert mgr.is_running(), "Manager container died"

    # 3. API-запросы к БД дают 5xx (или таймаут — тоже допустимо)
    try:
        r = requests.get(STATS_URL, headers=headers, timeout=5)
        assert r.status_code in (500, 502, 503), f"Expected 5xx, got {r.status_code}"
    except requests.exceptions.ReadTimeout:
        pass  # тоже ок — запрос завис, ответа нет, но процесс жив

    # 4. Запускаем PG обратно
    pg.start()

    # 5. Ждём восстановления (pool_pre_ping)
    deadline = time.time() + 90
    last = None
    while time.time() < deadline:
        try:
            r = requests.get(HEALTH_URL, timeout=5)
            if r.status_code == 200:
                last = r
                break
        except Exception:
            pass
        time.sleep(3)
    else:
        pytest.fail("Manager did not recover after PG restart")

    assert last.status_code == 200