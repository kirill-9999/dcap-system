# tests/load/test_api_load.py
import concurrent.futures
import os
import time

import pytest

from fixtures.manager import create_task


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.requires_manager
def test_create_1000_tasks(api_client, manager_url, test_files_dir):
    """Создание 1000 заданий через API. Порог: <60 сек, без 5xx.

    NB: rate-limit Manager'а (300 req/min по IP) может вернуть 429 —
    это не 5xx, поэтому в errors не попадает.
    """
    N = int(os.getenv("DCAP_LOAD_TASKS", "1000"))
    errors = []
    latencies = []
    created = []

    def create_one(i):
        start = time.time()
        try:
            task_id = create_task(api_client, manager_url, str(test_files_dir))
            latencies.append(time.time() - start)
            if task_id is None:
                errors.append("no task_id in response")
            else:
                created.append(task_id)
        except Exception as e:
            errors.append(str(e))

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(create_one, range(N)))
    duration = time.time() - start

    assert len(errors) == 0, f"{len(errors)} errors: {errors[:5]}"
    assert duration < 60, f"Too slow: {duration:.1f}s for {N} tasks"

    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    print(f"\n[X] {N} tasks in {duration:.1f}s | created={len(created)} | "
          f"avg={avg * 1000:.1f}ms | p95={p95 * 1000:.1f}ms")


@pytest.mark.load
@pytest.mark.requires_manager
def test_get_findings_load(api_client, manager_url):
    """100 запросов к /api/findings параллельно (без 5xx)."""
    errors = []

    def get_one(_):
        try:
            r = api_client.get(f"{manager_url}/api/findings", params={"limit": 100}, timeout=(5, 60))
            if r.status_code >= 500:
                errors.append(r.status_code)
        except Exception as e:
            errors.append(str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(get_one, range(100)))

    assert len(errors) == 0, f"Errors: {errors[:5]}"