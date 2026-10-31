# tests/unit/test_delete_resource_v31341.py — BUG-150 (v3.13.41)
#
# BUG-150: DELETE /api/resources/{id} падал с 500
# sqlalchemy.exc.IntegrityError: failed_files_task_id_fkey — 9+ FK с
# NO ACTION не позволяли удалить ресурс. Миграция 007_add_cascade_deletes
# перевела FK на ON DELETE CASCADE. На PG каскад делает основную работу;
# юнит-тест на SQLite проверяет контракт эндпоинта: ресурс → задание →
# findings/catalog_entries → DELETE → 204, все связанные записи удалены.
"""BUG-150 (v3.13.41): DELETE /api/resources/{id} → 204 + связанные записи удалены."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manager.src.api import resources as resources_api
from manager.src.auth.dependencies import get_current_user
from manager.src.db import models
from manager.src.db.session import get_db

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _admin()
    app.include_router(resources_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _admin():
    return SimpleNamespace(id=1, username="admin", roles=[SimpleNamespace(name="admin")])


def _make_resource(client, path="C:/data", type_="FILESYSTEM"):
    r = client.post("/api/resources", params={"path": path, "type": type_})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _make_scan_and_findings(db_session, rid):
    """Задание + findings + catalog_entries + failed_files, связанные с ресурсом."""
    task = models.ScanTask(
        resource_id=rid,
        source_path="C:/data",
        source_type="filesystem",
        status="completed",
    )
    db_session.add(task)
    db_session.flush()

    db_session.add_all(
        [
            models.Finding(
                resource_id=rid,
                task_id=task.id,
                finding_type="credentials",
                category="api_key",
                severity="high",
                fragment_type="text_line",
                line_number=1,
                fingerprint="fp-1",
                encryption_key_id="test-key",
                status="new",
            ),
            models.Finding(
                resource_id=rid,
                task_id=task.id,
                finding_type="pii",
                category="phone",
                severity="medium",
                fragment_type="text_line",
                line_number=2,
                fingerprint="fp-2",
                encryption_key_id="test-key",
                status="new",
            ),
            models.CatalogEntry(resource_id=rid, path="C:/data" + "\\sub\\report.xlsx"),
            models.FailedFile(
                resource_id=rid,
                task_id=task.id,
                file_path="C:/data/secret.txt",
                error_type="read_error",
                error_message="boom",
            ),
        ]
    )
    db_session.commit()
    return task


def test_delete_resource_returns_204_and_deletes_related(client, db_session):
    rid = _make_resource(client)
    _make_scan_and_findings(db_session, rid)

    assert db_session.query(models.ScanTask).count() == 1
    assert db_session.query(models.Finding).count() == 2
    assert db_session.query(models.CatalogEntry).count() == 1
    assert db_session.query(models.FailedFile).count() == 1

    r = client.delete(f"/api/resources/{rid}")
    assert r.status_code == 204, r.text

    assert db_session.query(models.Resource).count() == 0
    assert db_session.query(models.Finding).count() == 0
    assert db_session.query(models.ScanTask).count() == 0
    assert db_session.query(models.CatalogEntry).count() == 0
    assert db_session.query(models.FailedFile).count() == 0

    # удаление записалось в аудит (BUG-202: единая транзакция)
    log = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "resource_deleted")
        .first()
    )
    assert log is not None
    assert log.metadata_json.get("resource_id") == rid


def test_delete_missing_resource_returns_404(client):
    r = client.delete("/api/resources/424242")
    assert r.status_code == 404


def test_delete_resource_rolls_back_on_failure(client, db_session, monkeypatch):
    """BUG-202: 500 → ни изменения, ни записи аудита не остаётся."""
    rid = _make_resource(client, path="E:/rollback", type_="FILESYSTEM")

    class _Broken:
        def __enter__(self):
            raise RuntimeError("boom")

        def __exit__(self, *exc):
            return True

    monkeypatch.setattr(resources_api, "with_audit", lambda *a, **k: _Broken())

    r = client.delete(f"/api/resources/{rid}")
    assert r.status_code == 500
    assert db_session.query(models.Resource).filter(models.Resource.id == rid).count() == 1
    assert (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.event_type == "resource_deleted")
        .count()
        == 0
    )