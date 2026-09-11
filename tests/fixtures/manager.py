# tests/fixtures/manager.py — HTTP-клиент Manager: задания, находки, статусы.
import time
from typing import Dict, Optional

READY_STATUSES = ("assigned", "running", "completed")


def create_task(client, base_url: str, resource_path: str, resource_type: str = "FILESYSTEM"):
    """Создать задание через POST /api/tasks/create (WebUI-формат).

    Ответ: {"success": true, "task_id": N, "resource_id": N, ...}.
    """
    r = client.post(
        f"{base_url}/api/tasks/create",
        json={"resource_path": resource_path, "resource_type": resource_type},
    )
    task_id = (r.json() or {}).get("task_id") or (r.json() or {}).get("id")
    return task_id


def get_task(client, base_url: str, task_id: int) -> Dict:
    r = client.get(f"{base_url}/api/tasks/{task_id}")
    r.raise_for_status()
    return r.json()


def delete_task(client, base_url: str, task_id: Optional[int]):
    if task_id is None:
        return
    try:
        client.delete(f"{base_url}/api/tasks/{task_id}")
    except Exception:
        pass


def wait_task_status(
    client,
    base_url: str,
    task_id: int,
    target: str,
    timeout: float = 300,
    interval: float = 2,
) -> str:
    """Ждёт, пока задание не примет статус target (или не упадёт)."""
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        r = client.get(f"{base_url}/api/tasks/{task_id}")
        assert r.status_code == 200, f"GET task {task_id}: {r.status_code} {r.text}"
        task = r.json()
        status = task.get("status")
        if status == target:
            return status
        if status == "failed":
            return status
        time.sleep(interval)
    return status or "unknown"


def wait_task_assigned(
    client,
    base_url: str,
    task_id: int,
    timeout: float = 60,
) -> str:
    """Ждёт назначения сканеру (status assigned/running/completed)."""
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        r = client.get(f"{base_url}/api/tasks/{task_id}")
        assert r.status_code == 200
        status = r.json().get("status")
        if status in READY_STATUSES:
            return status
        time.sleep(1)
    return status or "unknown"