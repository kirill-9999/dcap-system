# tests/unit/test_stale_tasks.py — BUG-034: зависшие задачи (stale/running/fail/cancel)
# Задача 5 ТЗ BUG-034:
#   - test_mark_stale_scanner_fails_running_tasks
#   - test_fail_task_endpoint
#   - test_cancel_task_endpoint
import sys
from datetime import datetime, timedelta
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

from manager.src.api import scanner as scanner_api
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
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    from starlette.middleware.base import BaseHTTPMiddleware  # actual auth not needed

    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(scanner_api.router)
    return TestClient(app)


def _make_scanner(db, session_=None, last_heartbeat_delta_minutes=5, status="active"):
    hb = datetime.utcnow() - timedelta(minutes=last_heartbeat_delta_minutes)
    _s = models.Scanner(name=f"test-scanner-{id(hb)}", status=status, last_heartbeat=hb)
    db.add(_s)
    db.commit()
    db.refresh(_s)
    return _s


def _make_task(db, scanner_id, status="running", source_path=r"E:\test_smoke"):
    t = models.ScanTask(
        scanner_id=scanner_id,
        source_path=source_path,
        status=status,
        assigned_at=datetime.utcnow(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_mark_stale_scanner_fails_running_tasks(db_session):
    """Задача 3: stale-сканер + running задача -> задача failed."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=5)
    task = _make_task(db_session, sc.id, status="running")

    scanner_api._mark_stale_scanners(db_session)

    db_session.refresh(task)
    assert task.status == "failed"
    assert task.completed_at is not None


def test_mark_stale_scanner_fails_assigned_tasks(db_session):
    """Задача 3: stale-сканер + assigned задача -> задача failed (регрессия BUG-034.1)."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=5)
    task = _make_task(db_session, sc.id, status="assigned")

    scanner_api._mark_stale_scanners(db_session)

    db_session.refresh(task)
    assert task.status == "failed"


def test_mark_stale_scanner_ignores_fresh_scanner(db_session):
    """Свежий сканер (heartbeat в норме) не трогаем."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=0)
    task = _make_task(db_session, sc.id, status="running")

    scanner_api._mark_stale_scanners(db_session)

    db_session.refresh(task)
    assert task.status == "running"


def test_fail_task_endpoint(client, db_session):
    """Задача 2: POST /api/scanner/tasks/15/fail -> status=failed."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=0)
    task = _make_task(db_session, sc.id, status="running")

    r = client.post(f"/api/scanner/tasks/{task.id}/fail", json={"reason": "scanner aborted"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "failed"
    assert data["id"] == task.id

    db_session.refresh(task)
    assert task.status == "failed"
    assert task.completed_at is not None


def test_fail_task_endpoint_already_failed(client, db_session):
    """Повторный fail на уже failed -> already=True, статус не меняется."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=0)
    task = _make_task(db_session, sc.id, status="failed")

    r = client.post(f"/api/scanner/tasks/{task.id}/fail", json={"reason": "again"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "failed"
    assert data["already"] is True


def test_fail_task_endpoint_not_found(client, db_session):
    r = client.post("/api/scanner/tasks/99999/fail", json={"reason": "x"})
    assert r.status_code == 404


def test_cancel_task_endpoint(client, db_session):
    """Задача 4: POST /api/scanner/tasks/15/cancel -> status=failed."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=0)
    task = _make_task(db_session, sc.id, status="assigned")

    r = client.post(f"/api/scanner/tasks/{task.id}/cancel")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "failed"
    assert data["id"] == task.id

    db_session.refresh(task)
    assert task.status == "failed"


def test_cancel_task_endpoint_already_completed(client, db_session):
    """Отмена уже выполненной -> already=True, статус сохранён."""
    sc = _make_scanner(db_session, last_heartbeat_delta_minutes=0)
    task = _make_task(db_session, sc.id, status="completed")

    r = client.post(f"/api/scanner/tasks/{task.id}/cancel")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    assert data["already"] is True


def test_cancel_task_endpoint_not_found(client, db_session):
    r = client.post("/api/scanner/tasks/99999/cancel")
    assert r.status_code == 404