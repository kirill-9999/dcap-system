# tests/e2e/test_s3_scan_v31341.py — День 53.4a-доп5 (BUG-149)
# S3-скан MinIO на специальном датасете с известными секретами:
#   создать временный префикс e2e-v31341-*/ с объектами (PII + credentials),
#   создать S3-ресурс → запустить задачу → дождаться completed →
#   files_scanned > 0 и ≥ 9 находок с file_path s3://... → cleanup.
#
# Отличие от test_s3_e2e: датасет детерминированный (не зависит от реального
# содержимого access-logs), поэтому требование "≥ 9 находок" выполняется
# при любой схеме бакета.
#
# Skip-условия: Manager недоступен; MinIO healthcheck не отвечает;
# нет активного сканера (авто-skip в tests/conftest.py + _skip_if_unavailable).
#
# Прогон:
#   $env:PYTHONUTF8 = '1'
#   $env:S3_ACCESS_KEY = "minioadmin"; $env:S3_SECRET_KEY = "minioadmin"
#   pytest tests/e2e/test_s3_scan_v31341.py -v -m e2e
import os
import time
import uuid

import pytest
import requests

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_manager,
    pytest.mark.requires_minio,
]


MINIO_ENDPOINT = os.environ.get("S3_DEFAULT_ENDPOINT", "host.docker.internal:9000")
BUCKET = "dcap-audit-logs"
# Уникальный префикс, чтобы не конфликтовать между прогонами.
PREFIX = f"e2e-v31341-{uuid.uuid4().hex[:8]}/"

# 240 с — с запасом на cold-start сканера (spaCy/Tesseract).
TASK_TIMEOUT = 400

# Датасет: 3 объекта с заведомо известными секретами.
DATASET = {
    "billing-2026.csv": (
        "customer,email,phone,card,ip\n"
        "alice.smith@example.com,+1-415-555-0132,4111-1111-1111-1111,203.0.113.42\n"
        "bob.jones@example.org,+44-20-7946-0958,5500-0000-0000-0004,198.51.100.7\n"
    ),
    "app-backup.env": (
        "DB_PASSWORD=Hunter2P4ss#9qwz\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        "SECRET_TOKEN=K9xQv2mN4rT8zL0pW6s\n"
        "DATABASE_URL=postgresql://dbadmin:Qz7#Lope9!k3@db.internal:5432/app\n"
    ),
    "credentials.properties": (
        "db.password=S3curePa$$w0rd!2026\n"
        "jwt.secret=0a2b3c4d5e6f708192a3b4c5d6e7f809\n"
        "smtp.login=svc-reports@dcap.local\n"
    ),
}

EXPECTED_MIN_FINDINGS = 9


def _minio_available() -> bool:
    try:
        r = requests.get(f"http://{MINIO_ENDPOINT}/minio/health/live", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _scanner_active(manager_url, client) -> bool:
    try:
        r = client.get(f"{manager_url}/api/scanner", timeout=10)
        if r.status_code != 200:
            return False
        return any(s.get("status") in ("active", "ACTIVE") for s in r.json())
    except Exception:
        return False


def _s3_client():
    try:
        import boto3
    except ImportError:
        pytest.skip("boto3 не установлен")
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
        verify=False,
    )


@pytest.fixture(scope="module")
def client(manager_url):
    from fixtures.auth import login

    session = login(manager_url)
    yield session
    session.close()


@pytest.fixture(scope="module", autouse=True)
def _skip_if_unavailable(manager_url, client):
    if not _minio_available():
        pytest.skip(f"MinIO недоступен на {MINIO_ENDPOINT}")
    if not _scanner_active(manager_url, client):
        pytest.skip("Нет активного сканера — S3-задача не будет обработана")


@pytest.fixture(scope="module")
def s3_dataset():
    """Загрузить датасет в MinIO под временным префиксом, удалить после."""
    s3 = _s3_client()
    for name, body in DATASET.items():
        s3.put_object(
            Bucket=BUCKET,
            Key=f"{PREFIX}{name}",
            Body=body.encode("utf-8"),
            ContentType="text/plain",
        )
    try:
        yield PREFIX
    finally:
        # cleanup: убрать объекты временного префикса.
        for name in DATASET:
            try:
                s3.delete_object(Bucket=BUCKET, Key=f"{PREFIX}{name}")
            except Exception:
                pass


@pytest.fixture(scope="module")
def s3_resource(manager_url, client, s3_dataset):
    """S3-ресурс на временный префикс; удаляется в конце модуля."""
    path = f"s3://{BUCKET}/{PREFIX}"
    r = client.post(
        f"{manager_url}/api/resources",
        params={"path": path, "type": "s3", "endpoint": MINIO_ENDPOINT},
        timeout=10,
    )
    if r.status_code == 400:
        # Уже существует после падения (path+type уникален) — переиспользуем.
        existing = client.get(f"{manager_url}/api/resources", timeout=10).json()
        rid = next((x["id"] for x in existing if x.get("path") == path), None)
        if rid is None:
            pytest.fail(f"Не удалось переиспользовать S3-ресурс: {r.text}")
        yield {"id": rid}
        return
    assert r.status_code == 200, f"Create S3 resource: {r.status_code} {r.text}"
    res = r.json()
    yield res
    client.delete(f"{manager_url}/api/resources/{res['id']}", timeout=10)


def test_s3_scan_returns_files_and_findings(manager_url, client, s3_resource, s3_dataset):
    """BUG-149: S3-скан возвращает > 0 files и ≥ 9 находок."""
    res_id = s3_resource["id"]

    # 1. Запустить задачу
    r = client.post(f"{manager_url}/api/resources/{res_id}/scan", timeout=10)
    assert r.status_code == 200, f"Scan start: {r.text}"
    task_id = r.json()["task_id"]

    # 2. Дождаться завершения
    deadline = time.time() + TASK_TIMEOUT
    status = None
    files_scanned = 0
    while time.time() < deadline:
        r = client.get(f"{manager_url}/api/tasks/{task_id}", timeout=10)
        assert r.status_code == 200
        payload = r.json()
        status = payload["status"]
        files_scanned = payload.get("files_scanned") or 0
        if status in ("completed", "failed"):
            break
        time.sleep(5)
    assert status == "completed", (
        f"Task не завершилась успешно: status={status} files_scanned={files_scanned}"
    )

    # 3. > 0 files
    assert files_scanned > 0, "files_scanned == 0 — регрессия BUG-149"

    # 4. ≥ 9 находок, все с file_path s3://...
    r = client.get(
        f"{manager_url}/api/findings",
        params={"task_id": task_id, "limit": 500},
        timeout=15,
    )
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) >= EXPECTED_MIN_FINDINGS, (
        f"Находок {len(findings)} < {EXPECTED_MIN_FINDINGS} — датасет не распознан"
    )
    for f in findings:
        assert f["file_path"].startswith(f"s3://{BUCKET}/{PREFIX}"), (
            f"file_path не из S3-датасета: {f['file_path']}"
        )