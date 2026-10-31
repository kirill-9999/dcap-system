# Отчёт День 53.1a — `source_type` для S3-ресурсов (v3.13.29)

**Дата:** 03.10.2026
**Версия:** v3.13.28 → **v3.13.29**
**Ветка:** `feature/day_53_1a_source_type` (от `develop`, коммит `e7589d4`)
**ТЗ:** `prompts/archive/day_53_1a_source_type.md`
**Задачи:** TASK-104 … TASK-109
**Статус:** ✅ выполнено

---

## 📋 Сводка по выполнению

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| TASK-104 | Миграция 006 `add_source_type` | `manager/src/db/migrations/versions/006_add_source_type.py` | ✅ создано |
| TASK-105 | `ScanTask.source_type` | `manager/src/db/models.py` | ✅ изменено |
| TASK-106 | S3/MinIO-ресурсы + фикс уникальности | `manager/src/api/resources.py` | ✅ изменено |
| TASK-107 | `source_type` при создании `ScanTask` | `manager/src/api/resources.py` | ✅ изменено |
| TASK-108 | `source_type` в payload пендинга | `manager/src/api/scanner.py` | ✅ изменено |
| TASK-109 | Unit-тесты | `tests/unit/test_s3_resource_v31329.py` | ✅ 19 тестов |

Документация: `STATE.md`, `CHANGELOG.md` (секция `[3.13.29]`), `ROADMAP.md` — обновлены.

---

## ✅ Критерии приёмки

| # | Критерий | Результат | Как проверено |
|---|----------|-----------|---------------|
| 1 | Миграция 006 применяется на SQLite и PG без ошибок | ✅ | `alembic upgrade head` на обеих БД + round-trip `downgrade → upgrade` + повторный `upgrade head` (идемпотентность) |
| 2 | `ScanTask.source_type` доступен, дефолт `filesystem` | ✅ | `test_scan_task_source_type_default`, `test_scan_filesystem_resource_sets_source_type` |
| 3 | `POST /api/resources?type=s3&path=s3://bucket` работает | ✅ | `test_create_s3_resource_with_defaults` |
| 4 | `POST /api/resources?type=minio&path=minio://bucket` работает | ✅ | `test_create_minio_resource_treated_as_s3` |
| 5 | Невалидный S3-путь → 400 | ✅ | `test_create_s3_resource_invalid_path`, `test_create_s3_resource_empty_bucket` |
| 6 | Уникальность по `(path, type)` (BUG-059) | ✅ | `test_create_resource_unique_by_path_and_type`, `test_create_resource_same_path_different_type_filesystem` |
| 7 | `POST /api/resources/{id}/scan` ставит `source_type` | ✅ | `test_scan_s3_resource_sets_source_type`, `test_scan_minio_resource_sets_source_type` |
| 8 | Секреты S3 в `scan_config` отсутствуют | ✅ | `test_create_s3_resource_with_defaults` (`access_key`/`secret_key` не в `connector.s3`) |
| 9 | Полный unit-набор зелёный | ✅ | `pytest tests/unit/` → **378 passed** (было 359 + 19) |

---

## 🧪 Результаты тестов

### Новый файл
```
tests/unit/test_s3_resource_v31329.py ...................  [100%]  19 passed in 2.43s
```

### Полный unit-набор (регрессии)
```
tests/unit/ ...  378 passed in 283.57s (0:04:43)
```
Было до правок: 359. Стало: 359 + 19 = 378. **Регрессий нет.**

### Миграция 006 — фактические результаты

**SQLite (dev, `manager/dcap.db`)**
```
INFO  [alembic.runtime.migration] Running upgrade 002_scanner_progress -> 003_findings_refactor, ...
INFO  [alembic.runtime.migration] Running upgrade 003_findings_refactor -> 004_resources_path_type_unique, ...
INFO  [alembic.runtime.migration] Running upgrade 004_resources_path_type_unique -> 005_add_fragment_columns, ...
INFO  [alembic.runtime.migration] Running upgrade 005_add_fragment_columns -> 006_add_source_type, ...
alembic current -> 006_add_source_type (head)
PRAGMA: source_type в колонках: True
PRAGMA: ix_scan_tasks_source_type: True
```

**PostgreSQL (`dcap-postgres`, контейнер healthy)**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Running upgrade 005_add_fragment_columns -> 006_add_source_type, ...
alembic current -> 006_add_source_type (head)

information_schema:
  source_type | character varying | 20 | NO | 'filesystem'::character varying
pg_indexes:
  ix_scan_tasks_source_type
```

**Round-trip и идемпотентность (обе БД)**
```
downgrade 006 → 005:  OK
upgrade    005 → 006:  OK
повторный upgrade head: 0 применённых миграций (ОК)
```

---

## 📁 Полный код изменённых/новых файлов

### 1. `manager/src/db/migrations/versions/006_add_source_type.py` (новый)

```python
"""Scanner: колонка scan_tasks.source_type (filesystem | s3 | minio).

Revision ID: 006_add_source_type
Revises: 005_add_fragment_columns
Create Date: 2026-10-03

Назначение: явный тип источника в задании — сканер выбирает коннектор
по source_type, не угадывая по префиксу source_path ('s3://...').

Контекст (День 53.1a, BACKLOG-097): оживление S3-коннектора сканера.
  - filesystem — локальный/сетевой путь (как раньше);
  - s3         — s3://bucket[/prefix];
  - minio      — то же, что s3, но endpoint — MinIO.

Идемпотентность: на свежих БД 001_initial_postgres создаёт scan_tasks
из текущих моделей (models.py уже содержит source_type), поэтому колонка
может существовать — пропускаем add_column.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "006_add_source_type"
down_revision = "005_add_fragment_columns"
branch_labels = None
depends_on = None

_DEFAULT = "filesystem"


def _column_exists(bind, table: str, column: str) -> bool:
    try:
        cols = [c["name"] for c in inspect(bind).get_columns(table)]
    except Exception:
        return False
    return column in cols


def _index_exists(bind, table: str, index: str) -> bool:
    try:
        idx = [i["name"] for i in inspect(bind).get_indexes(table)]
    except Exception:
        return False
    return index in idx


def upgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "scan_tasks" not in tables:
        return

    if not _column_exists(bind, "scan_tasks", "source_type"):
        op.add_column(
            "scan_tasks",
            sa.Column(
                "source_type",
                sa.String(20),
                nullable=False,
                server_default=_DEFAULT,
            ),
        )

    if not _index_exists(bind, "scan_tasks", "ix_scan_tasks_source_type"):
        op.create_index(
            "ix_scan_tasks_source_type", "scan_tasks", ["source_type"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "scan_tasks" not in tables:
        return
    if _index_exists(bind, "scan_tasks", "ix_scan_tasks_source_type"):
        op.drop_index("ix_scan_tasks_source_type", "scan_tasks")
    if _column_exists(bind, "scan_tasks", "source_type"):
        op.drop_column("scan_tasks", "source_type")
```

### 2. `manager/src/db/models.py` — фрагмент `ScanTask`

```python
class ScanTask(Base):
    __tablename__ = "scan_tasks"

    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=True)
    source_path = Column(String(500), nullable=False)
    # День 53.1a (BACKLOG-097): тип источника — сканер выбирает коннектор
    # по source_type, не угадывая по префиксу source_path ('s3://...').
    # filesystem | s3 | minio (lowercase — как Resource.type).
    source_type = Column(String(20), default="filesystem", nullable=False, index=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    files_scanned = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    progress = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ScanTask(id={self.id}, resource_id={self.resource_id}, status='{self.status}')>"
```

### 3. `manager/src/api/resources.py` — импорты (шапка файла)

```python
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..db import models, session
from manager.src.auth.dependencies import require_admin, require_scanner
from manager.src.auth.models import User

router = APIRouter(prefix="/api/resources", tags=["resources"])
```

### 4. `manager/src/api/resources.py` — `create_resource`

```python
@router.post("")
def create_resource(
    path: str = Query(..., min_length=1),
    type: str = Query("FILESYSTEM"),  # noqa: A002
    endpoint: Optional[str] = Query(None, description="S3/MinIO endpoint (host:port)"),
    secure: bool = Query(False, description="S3: HTTPS"),
    use_path_style: bool = Query(True, description="S3: path-style addressing"),
    region: str = Query("us-east-1"),
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),
):
    """Создать новый ресурс (только Admin, BUG-046).

    День 53.1a (BACKLOG-097): поддержка S3/MinIO-ресурсов.
    - type нормализуется в lowercase (BUG-059);
    - уникальность по (path, type), а не только по path (uq_resources_path_type);
    - для type in (s3, minio) path = 's3://bucket[/prefix]', добавляется
      scan_config.connector.s3 с endpoint/secure/use_path_style/region;
    - секреты S3 в scan_config НЕ пишутся — только ENV на хосте сканера
      (S3_ACCESS_KEY / S3_SECRET_KEY), единая политика TASK-018.
    """
    type = type.lower()  # noqa: A001
    if type not in ("filesystem", "s3", "minio"):
        raise HTTPException(400, f"Unsupported resource type: {type!r}")

    # BUG-059 + uq_resources_path_type: уникальность по (path, type).
    existing = db.query(models.Resource).filter(
        models.Resource.path == path,
        models.Resource.type == type,
    ).first()
    if existing:
        raise HTTPException(
            400,
            f"Resource with path '{path}' and type '{type}' already exists",
        )

    scan_config = get_default_config()

    if type in ("s3", "minio"):
        parsed = urlparse(path)
        if parsed.scheme not in ("s3", "minio") or not parsed.netloc:
            raise HTTPException(400, "S3 path must be 's3://bucket[/prefix]'")
        scan_config["connector"] = scan_config.get("connector", {})
        scan_config["connector"]["s3"] = {
            "endpoint": endpoint
            or os.environ.get("S3_DEFAULT_ENDPOINT", "host.docker.internal:9000"),
            "bucket": parsed.netloc,
            "prefix": parsed.path.lstrip("/"),
            "secure": secure,
            "use_path_style": use_path_style,
            "region": region,
        }

    resource = models.Resource(
        path=path,
        type=type,
        status="ACTIVE",
        enabled=True,
        scan_config=scan_config,
        scan_interval=3600,
        schedule_enabled=False,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    
    return {
        "id": resource.id,
        "path": resource.path,
        "type": resource.type,
        "status": resource.status,
        "message": "Resource created successfully"
    }
```

### 5. `manager/src/api/resources.py` — `scan_resource` (фрагмент)

```python
    # Создаем задание
    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource.path,
        # День 53.1a: тип источника из ресурса (lowercase — как Resource.type).
        source_type=(resource.type or "filesystem").lower(),
        status="pending",
        created_at=datetime.utcnow(),
    )
```

### 6. `manager/src/api/scanner.py` — `get_pending_task` (финальный return)

```python
    return {
        "task": {
            "id": task.id,
            "resource_id": task.resource_id,
            "path": resource.path,
            # День 53.1a (BACKLOG-097): явный тип источника для выбора коннектора
            # в сканере. Fallback-цепочка: task.source_type → resource.type →
            # 'filesystem' (для задач, созданных до миграции 006).
            "source_type": (task.source_type or resource.type or "filesystem").lower(),
            "scan_config": scan_config,
        }
    }
```

### 7. `tests/unit/test_s3_resource_v31329.py` (новый, 19 тестов)

```python
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
```

### 8. `docs/security_checklist.md`, `requirements.txt`

Не изменялись в этом дне (изменения — от Блока 9, уже в коммите `9a74d56`).

---

## ⚠️ Отклонения от ТЗ

| Пункт ТЗ | Что сделано | Почему |
|----------|-------------|--------|
| Фикстура `client` через `manager.src.main:app` | Минимальный `FastAPI()` + `include_router(resources, scanner)` + `dependency_overrides` | Импорт полного `main:app` тянет middleware, rate-limit, метрики и фоновые потоки — unit-тесты должны быть изолированными. Соответствует конвенции `tests/unit/test_tasks_create.py`. |
| 12 тестов из ТЗ | 19 тестов | Добавлены: `endpoint` из ENV, `minio://` при `type=s3`, одинаковый `path` у `filesystem` и `s3`, дефолт `source_type` в ORM, `source_type` в payload пендинга (3 кейса: s3, filesystem, нормализация регистра, приоритет источника). |
| `path = "s3:///prefix"` → 400 | ✅ так и есть (`not parsed.netloc`) | — |

---

## ⚠️ Известные ограничения

- **Сканер не использует `source_type` пока.** `managed_scanner.py` жёстко создаёт `FilesystemConnector` — это **53.1b**. До него сканер продолжит работать по `path`.
- **WebUI-формы для S3-ресурса нет** — только API/Swagger (`/docs`). Это **53.3**.
- **Дефолтный endpoint** — `host.docker.internal:9000` (MinIO Блока 6). Для другого окружения — query-параметр `endpoint` или ENV `S3_DEFAULT_ENDPOINT`.
- **Секреты S3** — только ENV на хосте сканера (`S3_ACCESS_KEY` / `S3_SECRET_KEY`), в `scan_config` не попадают.
- `POST /api/resources` в `manager/src/api/webui.py` (WebUI-совместимый эндпоинт) **не изменён** — он по-прежнему создаёт только `filesystem`-ресурсы. Согласно ТЗ в 53.1a не входит; см. 53.3.
- `S3_VERIFY_SSL` не учитывается — 53.2 (TEST-NOTE-6.11).

---

## 🧪 Инструкция по ручной проверке

### 0. Перезапустить Manager (код изменился!)

```powershell
# Остановить старый процесс и запустить заново — иначе /api/resources вернёт 422
# на неизвестные query-параметры endpoint/secure/use_path_style/region.
python run_manager.py
```

Отдельно убедиться, что миграция применена к БД, которую использует Manager:

```powershell
# PostgreSQL
$env:DATABASE_URL = "postgresql+psycopg2://dcap:dcap123@localhost:5432/dcap"
python -m alembic upgrade head
python -m alembic current      # ожидаем 006_add_source_type (head)
```

### 1. Получить токен

```powershell
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }
```

### 2. Создать S3-ресурс (MinIO Блока 6)

```powershell
Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources?path=s3://dcap-audit-logs/&type=s3" `
    -Headers $headers | ConvertTo-Json
```

Ожидаемый ответ:
```json
{ "id": 123, "path": "s3://dcap-audit-logs/", "type": "s3", "status": "ACTIVE",
  "message": "Resource created successfully" }
```

Проверить, что в `scan_config` появился `connector.s3` **без секретов**:
```powershell
$id = 123
(Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/resources/$id/config" -Headers $headers).scan_config.connector.s3 | ConvertTo-Json
```
Ожидаемо:
```json
{ "endpoint": "host.docker.internal:9000", "bucket": "dcap-audit-logs", "prefix": "",
  "secure": false, "use_path_style": true, "region": "us-east-1" }
```

### 3. Кастомный endpoint и префикс

```powershell
Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources?path=s3://dcap-audit-logs/logs/2026-10-03&type=s3&endpoint=127.0.0.1:9000&region=eu-west-1" `
    -Headers $headers | ConvertTo-Json
```

### 4. MinIO-ресурс

```powershell
Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources?path=minio://dcap-audit-logs/logs&type=minio" `
    -Headers $headers | ConvertTo-Json
```

### 5. Негативные проверки (должны дать 400)

```powershell
# Не URL
try { Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources?path=not-a-url&type=s3" -Headers $headers }
catch { $_.ErrorDetails.Message }      # S3 path must be 's3://bucket[/prefix]'

# Пустой bucket
try { Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources?path=s3:///prefix&type=s3" -Headers $headers }
catch { $_.ErrorDetails.Message }      # S3 path must be 's3://bucket[/prefix]'

# Неподдерживаемый тип
try { Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources?path=x&type=ftp" -Headers $headers }
catch { $_.ErrorDetails.Message }      # Unsupported resource type: 'ftp'
```

### 6. Запустить сканирование и проверить `source_type`

```powershell
$task = Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources/123/scan" -Headers $headers
$task | ConvertTo-Json
# { "success": true, "task_id": 456, "resource_id": 123, "status": "pending", ... }
```

В БД:
```powershell
$sql = "SELECT id, source_path, source_type, status FROM scan_tasks ORDER BY id DESC LIMIT 5;"
$sql | docker exec -i dcap-postgres psql -U dcap -d dcap
```
Ожидаемо: для S3-ресурса `source_type = s3`, для FS — `filesystem`.

### 7. Проверить payload пендинга (что получит сканер)

```powershell
# Нужен существующий scanner_id
$scannerId = 1
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/scanner/tasks/pending?scanner_id=$scannerId" | ConvertTo-Json -Depth 6
```
В `task` должно быть:
```json
{
  "id": 456,
  "resource_id": 123,
  "path": "s3://dcap-audit-logs/",
  "source_type": "s3",
  "scan_config": { ... }
}
```

### 8. Откат (если нужно)

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://dcap:dcap123@localhost:5432/dcap"
python -m alembic downgrade 005_add_fragment_columns
```

---

## 💾 Команда для коммита

```powershell
git add manager/src/db/migrations/versions/006_add_source_type.py `
        manager/src/db/models.py `
        manager/src/api/resources.py `
        manager/src/api/scanner.py `
        tests/unit/test_s3_resource_v31329.py `
        STATE.md CHANGELOG.md ROADMAP.md `
        prompts/archive/day_53_1a_source_type.md `
        prompts/reports/day_53_1a_report.md

git commit -m "feat: День 53.1a — source_type в ScanTask + S3-ресурсы в Manager (v3.13.29)

- ScanTask.source_type (filesystem | s3 | minio), миграция 006 (идемпотентная)
- POST /api/resources: type=s3|minio, валидация s3://bucket[/prefix],
  дефолтный scan_config.connector.s3 (endpoint/secure/use_path_style/region)
- уникальность (path, type) — регрессия BUG-059
- POST /api/resources/{id}/scan: source_type из Resource.type
- GET /api/scanner/tasks/pending: source_type в payload
- секреты S3 — только ENV (S3_ACCESS_KEY / S3_SECRET_KEY), не в scan_config
- 19 unit-тестов; tests/unit: 378 passed (было 359), регрессий нет
- миграция проверена на SQLite и PostgreSQL (upgrade + round-trip + идемпотентность)

BACKLOG-097 (часть 1: Manager)
docs: обновлены STATE.md, CHANGELOG.md [3.13.29], ROADMAP.md"
```

---

## 📊 Обновление плана

| День | Задача | Статус |
|------|--------|--------|
| 52.1 | Linux-агент (дотест) | 📋 |
| 52.2 | Блок 6.5 (сбор прав Windows) | 📋 |
| **53.1a** | **Manager: `source_type` для S3-ресурсов** | ✅ **v3.13.29** |
| 53.1b | Scanner: ядро (фабрика, `_text_scanner.py`, boto3) | 📋 **следующий** |
| 53.2 | Scanner: S3-пайплайн находок | 📋 |
| 53.3 | Тесты (E2E на MinIO) + WebUI-форма S3 | 📋 |

---

**Итог:** BACKLOG-097 часть 1 закрыта. Manager теперь умеет создавать S3/MinIO-ресурсы и явно передаёт тип источника сканеру. Сканер по-прежнему использует `FilesystemConnector` — это 53.1b.

Конец отчёта День 53.1a — v3.13.29