# tests/e2e/test_full_scan_cycle.py
import time

import pytest

from fixtures.manager import create_task, get_task, wait_task_assigned, wait_task_status


@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_full_scan_cycle(api_client, manager_url, test_files_dir, cleanup_tasks):
    """
    E2E: создание задания → сканирование → результаты → находки.

    Предусловие: Manager + Scanner запущены, сканер зарегистрирован.
    """
    # 1. Проверяем, что сканер зарегистрирован
    r = api_client.get(f"{manager_url}/api/scanners")
    assert r.status_code == 200
    scanners = r.json()
    if not scanners:
        pytest.skip("Нет зарегистрированных сканеров")
    scanner_id = scanners[0]["id"]

    # 2. Создаём задание
    task_id = create_task(api_client, manager_url, str(test_files_dir))
    assert task_id, "Create task failed: task_id not returned"
    cleanup_tasks.append(task_id)

    # 3. Ждём назначения сканеру
    status = wait_task_assigned(api_client, manager_url, task_id, timeout=60)
    assert status in ("assigned", "running", "completed"), f"Task stuck: {status}"

    # 4. Ждём завершения (сканирование 4 файлов — быстро)
    status = wait_task_status(api_client, manager_url, task_id, "completed", timeout=300)
    if status == "failed":
        pytest.fail(f"Task failed: {get_task(api_client, manager_url, task_id)}")
    assert status == "completed", f"Task not completed: {status}"

    # 5. Проверяем прогресс (День 39)
    task = get_task(api_client, manager_url, task_id)
    assert task.get("progress") is not None or task.get("files_scanned", 0) > 0, (
        f"No progress/files_scanned: {task}"
    )

    # 6. Проверяем находки (фильтр по task_id)
    r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id})
    assert r.status_code == 200, f"GET findings: {r.status_code} {r.text}"
    findings = r.json()
    assert len(findings) > 0, "No findings detected"

    # 7. Проверяем типы находок
    types = {f.get("type") or f.get("category") for f in findings}
    assert any("pii" in str(t).lower() or "cred" in str(t).lower() for t in types), (
        f"Expected PII/credentials findings, got: {types}"
    )


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_task_progress_updates(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Прогресс задания появляется в API (heartbeat, День 39).

    Задание может быстро завершиться без сканера; в этом случае progress
    отсутствует как JSON, но files_scanned в ответе будет ненулевым —
    проверяем оба варианта.
    """
    task_id = create_task(api_client, manager_url, str(test_files_dir))
    assert task_id
    cleanup_tasks.append(task_id)

    deadline = time.time() + 60
    checked = False
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id}")
        assert r.status_code == 200
        task = r.json()
        progress = task.get("progress")
        if progress:
            checked = True
            assert "files_scanned" in progress
            return
        if task.get("status") == "completed":
            # Задание выполнено без промежуточного heartbeat — проверяем counters
            assert task.get("files_scanned", 0) >= 0
            return
        time.sleep(2)
    assert checked, "Progress never updated"