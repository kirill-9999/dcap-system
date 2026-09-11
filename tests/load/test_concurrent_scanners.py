# tests/load/test_concurrent_scanners.py
import concurrent.futures
import os
import time

import pytest

from fixtures.manager import create_task


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.requires_manager
def test_concurrent_task_creation(api_client, manager_url, test_files_dir):
    """Создание 100 заданий параллельно (имитация N сканеров)."""
    N = int(os.getenv("DCAP_LOAD_SCANNERS", "100"))
    errors = []
    created = []

    def create_one(i):
        try:
            task_id = create_task(api_client, manager_url, str(test_files_dir))
            if task_id is None:
                errors.append("no task_id in response")
            else:
                created.append(task_id)
        except Exception as e:
            errors.append(str(e))

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(create_one, range(N)))
    duration = time.time() - start

    assert len(errors) == 0, f"Errors: {errors[:5]}"
    assert len(created) >= N * 0.95, f"Only {len(created)}/{N} created"
    print(f"\n📊 {N} tasks in {duration:.1f}s | created={len(created)}")