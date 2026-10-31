# tests/fixtures/manager.py — HTTP-клиент Manager: задания, находки, статусы.
import time
from typing import Dict, Optional

try:  # Python 3.7+ всегда доступен, но оставляем мягкий импорт
    from http.client import RemoteDisconnected
except ImportError:  # pragma: no cover
    RemoteDisconnected = OSError

try:
    from requests.exceptions import ChunkedEncodingError, ConnectionError as ReqConnError
    from requests.exceptions import Timeout as ReqTimeout

    _TRANSIENT = (ReqConnError, ReqTimeout, RemoteDisconnected, ChunkedEncodingError)
except ImportError:  # pragma: no cover - requests не установлен
    _TRANSIENT = (OSError,)

READY_STATUSES = ("assigned", "running", "completed")

# Таймауты HTTP (поддерживаемый timeout в средах с медленным Docker-стеком).
_TIMEOUT = (5, 300)

# BUG-096b (TASK-065, v3.13.25): uvicorn закрывает keep-alive соединение через
# timeout_keep_alive (5 с по умолчанию). Long-poll E2E с requests.Session ходит
# в Manager раз в 2-5 с, поэтому клиент регулярно переиспользует уже закрытый
# сокет и получает RemoteDisconnected («Connection aborted»). Наблюдалось
# стабильно на тестах с interval=5. Лечится повтором запроса, а не ожиданием
# самого Manager: сервер ответил бы мгновенно, если бы соединение жило.
_RETRY_ATTEMPTS = 3
_RETRY_DELAY = 0.5


def _get_with_retry(client, url: str, **kwargs):
    """GET с повтором при разрыве keep-alive соединения (BUG-096b)."""
    last_exc = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return client.get(url, **kwargs)
        except _TRANSIENT as exc:
            last_exc = exc
            if attempt == _RETRY_ATTEMPTS - 1:
                break
            time.sleep(_RETRY_DELAY)
            # Сбросить keep-alive пул, чтобы следующая попытка открыла новый сокет
            try:
                client.close()
            except Exception:
                pass
    raise last_exc


def create_task(client, base_url: str, resource_path: str, resource_type: str = "FILESYSTEM"):
    """Создать задание через POST /api/tasks/create (WebUI-формат).

    Ответ: {"success": true, "task_id": N, "resource_id": N, ...}.
    """
    r = client.post(
        f"{base_url}/api/tasks/create",
        json={"resource_path": resource_path, "resource_type": resource_type},
        timeout=_TIMEOUT,
    )
    task_id = (r.json() or {}).get("task_id") or (r.json() or {}).get("id")
    return task_id


def get_task(client, base_url: str, task_id: int) -> Dict:
    r = _get_with_retry(client, f"{base_url}/api/tasks/{task_id}", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def delete_task(client, base_url: str, task_id: Optional[int]):
    if task_id is None:
        return
    try:
        client.delete(f"{base_url}/api/tasks/{task_id}", timeout=_TIMEOUT)
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
        r = _get_with_retry(client, f"{base_url}/api/tasks/{task_id}", timeout=_TIMEOUT)
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
        r = _get_with_retry(client, f"{base_url}/api/tasks/{task_id}", timeout=_TIMEOUT)
        assert r.status_code == 200
        status = r.json().get("status")
        if status in READY_STATUSES:
            return status
        time.sleep(1)
    return status or "unknown"
