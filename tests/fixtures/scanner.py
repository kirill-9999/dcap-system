# tests/fixtures/scanner.py — HTTP-клиент Scanner (регистрация, heartbeat, метрики).


def list_scanners(client, base_url: str):
    """Список зарегистрированных сканеров (GET /api/scanners)."""
    r = client.get(f"{base_url}/api/scanners")
    r.raise_for_status()
    return r.json()


def get_scanner(client, base_url: str, scanner_id: int):
    r = client.get(f"{base_url}/api/scanner/{scanner_id}")
    r.raise_for_status()
    return r.json()


def register_scanner(client, base_url: str, name: str, hostname: str = None):
    """Регистрация сканера (POST /api/scanner/register)."""
    payload = {"name": name}
    if hostname:
        payload["hostname"] = hostname
    r = client.post(f"{base_url}/api/scanner/register", json=payload)
    return r


def heartbeat(client, base_url: str, scanner_id: int, status: str = "idle", task_id=None, progress=None):
    """Отправка heartbeat (POST /api/scanner/heartbeat)."""
    payload = {"scanner_id": scanner_id, "status": status}
    if task_id is not None:
        payload["task_id"] = task_id
    if progress is not None:
        payload["progress"] = progress
    r = client.post(f"{base_url}/api/scanner/heartbeat", json=payload)
    return r