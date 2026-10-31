# tests/unit/test_tasks_create.py — BUG-059 (Fix-спринт)
# POST /api/tasks/create падал с 500: WebUI шлёт resource_type='FILESYSTEM',
# БД хранит 'filesystem' — INSERT упирался в UNIQUE(path) (UniqueViolation).
# Фикс: нормализация type в lowercase + fallback поиска ресурса БЕЗ type.
import sys
from pathlib import Path

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
from manager.src.auth.dependencies import get_current_user
from manager.src.api import webui as webui_api

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
    from types import SimpleNamespace

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
    app.dependency_overrides[get_current_user] = _fake_admin
    app.include_router(webui_api.router)
    return TestClient(app)


def test_create_task_upper_type_ok(client, db_session):
    """BUG-059: resource_type='FILESYSTEM' (как шлёт WebUI) — 200, БД хранит lowercase."""
    r = client.post("/api/tasks/create", json={
        "resource_path": "E:/bug059-test-1",
        "resource_type": "FILESYSTEM",
    })
    assert r.status_code == 200, r.text
    res = db_session.query(models.Resource).filter(
        models.Resource.path == "E:/bug059-test-1"
    ).first()
    assert res is not None
    assert res.type == "filesystem"
    assert db_session.query(models.ScanTask).count() == 1


def test_create_task_twice_no_500(client, db_session):
    """Повторный вызов с тем же путём (case variants) — не 500."""
    for rt in ("FILESYSTEM", "filesystem", "FILESYSTEM"):
        r = client.post("/api/tasks/create", json={
            "resource_path": "E:/bug059-test-2",
            "resource_type": rt,
        })
        assert r.status_code == 200, r.text
    # одна цена ресурса, три задания
    assert db_session.query(models.Resource).filter(
        models.Resource.path == "E:/bug059-test-2"
    ).count() == 1
    assert db_session.query(models.ScanTask).count() == 3


def test_create_task_reuses_existing_lowercase_resource(client, db_session):
    """Ресурс уже создан с 'filesystem', создаём задание с 'FILESYSTEM' — без 500."""
    existing = models.Resource(path="E:/bug059-test-3", type="filesystem",
                               status="ACTIVE", enabled=True)
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    r = client.post("/api/tasks/create", json={
        "resource_path": "E:/bug059-test-3",
        "resource_type": "FILESYSTEM",
    })
    assert r.status_code == 200, r.text
    assert r.json()["resource_id"] == existing.id


def test_create_task_missing_path_400(client):
    r = client.post("/api/tasks/create", json={"resource_type": "FILESYSTEM"})
    assert r.status_code == 400