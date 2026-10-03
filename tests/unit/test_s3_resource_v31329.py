# tests/unit/test_s3_resource_v31329.py — День 53.1a (BACKLOG-097, часть 1: Manager)
# ScanTask.source_type + создание S3/MinIO-ресурсов через POST /api/resources.
# Покрытие:
#   - создание filesystem-ресурса (регрессия);
#   - создание s3-ресурса с дефолтами и кастомным endpoint;
#   - minio трактуется как s3;
#   - валидация s3-пути (не-url, пустой bucket);
#   - уникальность по (path, type) — регрессия BUG-059;
#   - POST /api/resources/{id}/scan выставляет source_type;
#   - GET /api/scanner/tasks/pending отдаёт source_type.
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manager.src.db import models
from manager.src.db.session import get_db
from manager.src.auth import dependencies as auth_deps
from manager.src.api import resources as resources_api
from manager.src.api import scanner as scanner_api

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    def _fake_admin():
        return SimpleNamespace(
            id=1,
            username="admin",
            roles=[SimpleNamespace(name="admin")],
        )

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[auth_deps.require_admin] = _fake_admin
    app.dependency_overrides[auth_deps.require_scanner] = _fake_admin
    app.include_router(resources_api.router)
    app.include_router(scanner_api.router)
    return TestClient(app)


# ---------- Создание ресурсов ----------

def test_create_filesystem_resource_default(client, db_session):
    r = client.post("/api/resources", params={"path": "C:/data", "type": "FILESYSTEM"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "filesystem"
    res = db_session.query(models.Resource).filter(models.Resource.id == body["id"]).first()
    assert res is not None
    assert res.type == "filesystem"


def test_create_s3_resource_with_defaults(client, db_session):
    r = client.post(
        "/api/resources",
        params={"path": "s3://dcap-audit-logs/", "type": "s3"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "s3"

    res = db_session.query(models.Resource).filter(models.Resource.id == body["id"]).first()
    s3 = (res.scan_config or {}).get("connector", {}).get("s3", {})
    assert s3["bucket"] == "dcap-audit-logs"
    assert s3["prefix"] == ""
    assert s3["secure"] is False
    assert s3["use_path_style"] is True
    assert s3["region"] == "us-east-1"
    assert "endpoint" in s3
    # Секретов в scan_config быть не должно.
    assert "access_key" not in s3
    assert "secret_key" not in s3


def test_create_s3_resource_with_custom_endpoint(client, db_session):
    r = client.post(
        "/api/resources",
        params={
            "path": "s3://bucket/prefix",
            "type": "s3",
            "endpoint": "minio.local:9000",
            "secure": True,
            "use_path_style": False,
            "region": "eu-west-1",
        },
    )
    assert r.status_code == 200, r.text
    res = db_session.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    s3 = res.scan_config["connector"]["s3"]
    assert s3["endpoint"] == "minio.local:9000"
    assert s3["bucket"] == "bucket"
    assert s3["prefix"] == "prefix"
    assert s3["secure"] is True
    assert s3["use_path_style"] is False
    assert s3["region"] == "eu-west-1"


def test_create_s3_resource_endpoint_from_env(client, db_session, monkeypatch):
    """Без query-параметра endpoint берётся из S3_DEFAULT_ENDPOINT."""
    monkeypatch.setenv("S3_DEFAULT_ENDPOINT", "minio.default:9999")
    r = client.post("/api/resources", params={"path": "s3://bucket", "type": "s3"})
    assert r.status_code == 200, r.text
    res = db_session.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    assert res.scan_config["connector"]["s3"]["endpoint"] == "minio.default:9999"


def test_create_minio_resource_treated_as_s3(client, db_session):
    r = client.post(
        "/api/resources",
        params={"path": "minio://bucket/logs", "type": "minio"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "minio"
    res = db_session.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    assert "s3" in res.scan_config["connector"]


def test_create_s3_resource_invalid_path(client):
    r = client.post("/api/resources", params={"path": "not-a-url", "type": "s3"})
    assert r.status_code == 400
    assert "s3://" in r.json()["detail"]


def test_create_s3_resource_empty_bucket(client):
    r = client.post("/api/resources", params={"path": "s3:///prefix", "type": "s3"})
    assert r.status_code == 400


def test_create_s3_resource_mismatched_scheme(client):
    """type=s3, но схема minio:// — принимаем (один коннектор), s3:// при type=filesystem — нет."""
    r = client.post("/api/resources", params={"path": "minio://bucket", "type": "s3"})
    assert r.status_code == 200, r.text


def test_create_resource_unique_by_path_and_type(client):
    """BUG-059 регрессия: (path, type) — составной ключ, не только path."""
    r1 = client.post("/api/resources", params={"path": "s3://b/x", "type": "s3"})
    assert r1.status_code == 200, r1.text
    # Тот же path, другой type — тоже можно.
    r2 = client.post("/api/resources", params={"path": "s3://b/x", "type": "minio"})
    assert r2.status_code == 200, r2.text
    # Тот же (path, type) — 400.
    r3 = client.post("/api/resources", params={"path": "s3://b/x", "type": "s3"})
    assert r3.status_code == 400


def test_create_resource_same_path_different_type_filesystem(client):
    """Тот же path у filesystem и s3 — не конфликт (уникальность по (path, type))."""
    r1 = client.post("/api/resources", params={"path": "s3://bucket", "type": "filesystem"})
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/resources", params={"path": "s3://bucket", "type": "s3"})
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] != r2.json()["id"]


def test_create_resource_unsupported_type(client):
    r = client.post("/api/resources", params={"path": "x", "type": "ftp"})
    assert r.status_code == 400


# ---------- Задача: source_type ----------

def test_scan_s3_resource_sets_source_type(client, db_session):
    res_id = client.post(
        "/api/resources",
        params={"path": "s3://bucket/prefix", "type": "s3"},
    ).json()["id"]

    r = client.post(f"/api/resources/{res_id}/scan")
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]

    task = db_session.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    assert task is not None
    assert task.source_type == "s3"
    assert task.source_path == "s3://bucket/prefix"


def test_scan_minio_resource_sets_source_type(client, db_session):
    res_id = client.post(
        "/api/resources",
        params={"path": "minio://bucket/logs", "type": "minio"},
    ).json()["id"]
    task_id = client.post(f"/api/resources/{res_id}/scan").json()["task_id"]
    task = db_session.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    assert task.source_type == "minio"


def test_scan_filesystem_resource_sets_source_type(client, db_session):
    res_id = client.post(
        "/api/resources",
        params={"path": "C:/data", "type": "filesystem"},
    ).json()["id"]

    task_id = client.post(f"/api/resources/{res_id}/scan").json()["task_id"]
    task = db_session.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    assert task.source_type == "filesystem"


def test_scan_task_source_type_default(client, db_session):
    """ScanTask без явного source_type → дефолт filesystem (миграция 006)."""
    res = models.Resource(path="C:/direct", type="filesystem", status="ACTIVE", enabled=True)
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)

    task = models.ScanTask(resource_id=res.id, source_path="C:/direct", status="pending",
                           created_at=datetime.utcnow())
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    assert task.source_type == "filesystem"


# ---------- Payload для сканера ----------

def test_pending_task_payload_has_source_type_s3(client, db_session):
    scanner = models.Scanner(name="sc-s3", status="online")
    db_session.add(scanner)
    db_session.commit()
    db_session.refresh(scanner)

    res_id = client.post(
        "/api/resources",
        params={"path": "s3://bucket/prefix", "type": "s3"},
    ).json()["id"]
    client.post(f"/api/resources/{res_id}/scan")

    r = client.get("/api/scanner/tasks/pending", params={"scanner_id": scanner.id})
    assert r.status_code == 200, r.text
    task = r.json()["task"]
    assert task is not None
    assert task["source_type"] == "s3"
    assert task["path"] == "s3://bucket/prefix"


def test_pending_task_payload_has_source_type_filesystem(client, db_session):
    scanner = models.Scanner(name="sc-fs", status="online")
    db_session.add(scanner)
    db_session.commit()
    db_session.refresh(scanner)

    res_id = client.post(
        "/api/resources",
        params={"path": "C:/data", "type": "filesystem"},
    ).json()["id"]
    client.post(f"/api/resources/{res_id}/scan")

    task = client.get("/api/scanner/tasks/pending", params={"scanner_id": scanner.id}).json()["task"]
    assert task["source_type"] == "filesystem"


def test_pending_task_payload_normalizes_uppercase_source_type(client, db_session):
    """source_type в верхнем регистре → lower в payload (День 53.1a)."""
    scanner = models.Scanner(name="sc-up", status="online")
    db_session.add(scanner)
    db_session.commit()
    db_session.refresh(scanner)

    res = models.Resource(path="s3://bucket", type="S3", status="ACTIVE", enabled=True)
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)

    task_row = models.ScanTask(resource_id=res.id, source_path="s3://bucket", status="pending",
                               created_at=datetime.utcnow())
    db_session.add(task_row)
    db_session.commit()
    task_row.source_type = "S3"
    db_session.commit()

    task = client.get("/api/scanner/tasks/pending", params={"scanner_id": scanner.id}).json()["task"]
    assert task["source_type"] == "s3"


def test_pending_task_payload_prefers_task_source_type(client, db_session):
    """Fallback-цепочка: task.source_type приоритетнее resource.type."""
    scanner = models.Scanner(name="sc-prio", status="online")
    db_session.add(scanner)
    db_session.commit()
    db_session.refresh(scanner)

    res = models.Resource(path="s3://bucket", type="minio", status="ACTIVE", enabled=True)
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)

    task_row = models.ScanTask(resource_id=res.id, source_path="s3://bucket", status="pending",
                               created_at=datetime.utcnow())
    db_session.add(task_row)
    db_session.commit()
    task_row.source_type = "filesystem"
    db_session.commit()

    task = client.get("/api/scanner/tasks/pending", params={"scanner_id": scanner.id}).json()["task"]
    assert task["source_type"] == "filesystem"