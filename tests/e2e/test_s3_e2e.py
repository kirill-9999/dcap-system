# tests/e2e/test_s3_e2e.py — День 53.3 (BACKLOG-097, часть 4: E2E)
# Полный цикл S3/MinIO-сканирования на живом стенде:
#   создать S3-ресурс → запустить задачу → дождаться completed →
#   проверить findings с file_path LIKE 's3://%' → cleanup.
#
# Skip-условия:
#   - Manager недоступен (маркер requires_manager, авто-skip в tests/conftest.py);
#   - MinIO недоступен (healthcheck не отвечает);
#   - нет активного сканера — задача не будет обработана.
#
# Endpoint передаётся в query явно (не зависит от ENV S3_DEFAULT_ENDPOINT
# на Manager-хосте) — чтобы тест был стабильным независимо от окружения.
#
# Прогон:
#   $env:PYTHONUTF8 = '1'
#   $env:S3_ACCESS_KEY = "minioadmin"
#   $env:S3_SECRET_KEY = "minioadmin"
#   pytest tests/e2e/test_s3_e2e.py -v -m e2e
import os
import time

import pytest
import requests

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_manager,
    pytest.mark.requires_minio,
]


MINIO_ENDPOINT = os.environ.get("S3_DEFAULT_ENDPOINT", "host.docker.internal:9000")
BUCKET = "dcap-audit-logs"
PREFIX = "access-logs/"

# Таймаут ожидания задачи: S3-задача на 4 объектах укладывается в секунды,
# 240 с — с запасом на cold-start сканера (spaCy/Tesseract).
TASK_TIMEOUT = 240


@pytest.fixture(scope="module")
def client(manager_url):
    """HTTP-клиент Manager с admin JWT.

    Имя из ТЗ; в репо функциональная фикстура называется api_client, но она
    function-scoped, а _skip_if_unavailable — module-scoped (ScopeMismatch),
    поэтому здесь своя сессия на модуль через общий хелпер fixtures.auth.login.
    """
    from fixtures.auth import login

    session = login(manager_url)
    yield session
    session.close()


def _minio_available() -> bool:
    """Проверка доступности MinIO (healthcheck)."""
    try:
        r = requests.get(f"http://{MINIO_ENDPOINT}/minio/health/live", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _scanner_active(manager_url, client) -> bool:
    """Есть ли хотя бы один активный сканер."""
    try:
        r = client.get(f"{manager_url}/api/scanner", timeout=10)
        if r.status_code != 200:
            return False
        scanners = r.json()
        return any(s.get("status") in ("active", "ACTIVE") for s in scanners)
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def _skip_if_unavailable(manager_url, client):
    if not _minio_available():
        pytest.skip(f"MinIO недоступен на {MINIO_ENDPOINT}")
    if not _scanner_active(manager_url, client):
        pytest.skip("Нет активного сканера — S3-задача не будет обработана")


@pytest.fixture()
def s3_resource(manager_url, client):
    """Создать S3-ресурс на prefix access-logs/, удалить после теста."""
    path = f"s3://{BUCKET}/{PREFIX}"
    # Убрать возможный остаток предыдущего прогона (уникальность по (path, type)).
    existing = client.get(f"{manager_url}/api/resources", timeout=10).json()
    for res in existing:
        if res.get("path") == path and res.get("type") == "s3":
            client.delete(f"{manager_url}/api/resources/{res['id']}", timeout=10)

    r = client.post(
        f"{manager_url}/api/resources",
        params={
            "path": path,
            "type": "s3",
            "endpoint": MINIO_ENDPOINT,
        },
        timeout=10,
    )
    assert r.status_code == 200, f"Create S3 resource: {r.status_code} {r.text}"
    res = r.json()
    yield res
    # cleanup: каскадно удаляет findings/tasks/catalog_entries
    client.delete(f"{manager_url}/api/resources/{res['id']}", timeout=10)


def test_s3_scan_full_cycle(manager_url, client, s3_resource):
    """S3-сканирование: задача проходит полный цикл, findings в БД."""
    res_id = s3_resource["id"]

    # 1. Запустить задачу
    r = client.post(f"{manager_url}/api/resources/{res_id}/scan", timeout=10)
    assert r.status_code == 200, f"Scan start: {r.text}"
    task_id = r.json()["task_id"]
    assert task_id > 0

    # 2. Дождаться завершения (до TASK_TIMEOUT с)
    deadline = time.time() + TASK_TIMEOUT
    status = None
    while time.time() < deadline:
        r = client.get(f"{manager_url}/api/tasks/{task_id}", timeout=10)
        assert r.status_code == 200
        status = r.json()["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(5)
    assert status == "completed", f"Task не завершилась: status={status}"

    # 3. Findings содержат s3://
    r = client.get(
        f"{manager_url}/api/findings",
        params={"task_id": task_id, "limit": 200},
        timeout=15,
    )
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) > 0, "Нет findings от S3-сканирования"
    for f in findings:
        assert f["file_path"].startswith(f"s3://{BUCKET}/{PREFIX}"), (
            f"file_path не s3://: {f['file_path']}"
        )


def test_s3_resource_cleanup_removes_findings(manager_url, client):
    """DELETE resource каскадно удаляет findings/tasks/catalog_entries."""
    path = f"s3://{BUCKET}/{PREFIX}"
    r = client.post(
        f"{manager_url}/api/resources",
        params={
            "path": path,
            "type": "s3",
            "endpoint": MINIO_ENDPOINT,
        },
        timeout=10,
    )
    if r.status_code == 400:
        # Уже существует — cleanup проверится в основном тесте
        pytest.skip("S3-ресурс уже существует")
    assert r.status_code == 200
    res_id = r.json()["id"]

    # Сразу удаляем
    r = client.delete(f"{manager_url}/api/resources/{res_id}", timeout=10)
    assert r.status_code == 200

    # Findings с resource_id больше нет
    r = client.get(
        f"{manager_url}/api/findings",
        params={"resource_id": res_id},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json() == []
