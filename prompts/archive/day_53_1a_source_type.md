ТЗ: День 53.1a — Manager: source_type для S3-ресурсов
Файл: prompts/tz/day_53_1a_source_type.md
Дата: 03.10.2026
Версия: v3.13.28 → v3.13.29
Статус: ✏️ Готово к разработке
Оценка: ~1.5–2 ч
Приоритет: 🔴 критично (BACKLOG-097 — часть 1: без этого сканер не сможет выбрать S3-коннектор)
Родительская задача: BACKLOG-097 «S3-коннектор сканера: интеграция в ядро + пайплайн находок»

🎯 ЦЕЛЬ
Добавить в ScanTask колонку source_type (filesystem | s3 | minio).

Научить POST /api/resources создавать S3/MinIO-ресурсы (type=s3|minio, path=s3://bucket[/prefix]).

При создании задачи POST /api/resources/{id}/scan прописывать source_type из Resource.type.

В GET /api/scanner/tasks/pending отдавать сканеру source_type в payload.

Покрыть unit-тестами.

Что НЕ входит в 53.1a:

правки сканера (53.1b, 53.2);

WebUI-форма добавления S3-ресурса (53.3);

E2E на MinIO (53.3);

S3LineConnector, _text_scanner.py, factory.py, boto3 — всё это 53.1b/53.2.

📌 ПРОБЛЕМА
Сейчас весь конвейер задач неявно файловый:

ScanTask (models.py) содержит только source_path (String(500)) — нет source_type.

POST /api/resources создаёт ресурс с произвольным type (query-параметр, дефолт FILESYSTEM), но валидация s3://-пути отсутствует.

POST /api/resources/{id}/scan создаёт задачу без указания типа источника.

GET /api/scanner/tasks/pending отдаёт сканеру только path и scan_config — сканер вынужден угадывать коннектор по префиксу s3://, а сейчас вообще создаёт FilesystemConnector жёстко.

Следствие: S3-коннектор в сканере (247 строк, scanner/connectors/s3_connector.py) не подключён — это мёртвый код с Дня 8.

Дополнительная проблема (несоответствие кода и БД): create_resource в resources.py проверяет уникальность только по path, хотя uq_resources_path_type (миграция 004_resources_path_type_unique, BUG-059) разрешает одинаковые path с разными type. Это регрессия.

📌 ПРЕДУСЛОВИЯ
✅ Основной стек Manager/Celery/PG/Redis — работает (v3.13.28).

✅ Миграции 001…005 применены.

✅ manager/src/db/migrations/env.py — стандартный (target_metadata = Base.metadata).

✅ MinIO поднят нативно (E:\Dev\MinIO\bin\minio.exe), бакет dcap-audit-logs наполнен seed-логами (scripts/minio-seed/access-logs/*).

✅ Пакет shared/ импортируется.

📁 ФАЙЛЫ (создаются / изменяются)
Создаются
Файл	Назначение
manager/src/db/migrations/versions/006_add_source_type.py	Миграция: scan_tasks.source_type + индекс
tests/unit/test_s3_resource_v31329.py	Unit-тесты
prompts/reports/day_53_1a_report.md	Отчёт о выполнении
Изменяются
Файл	Что меняется
manager/src/db/models.py	ScanTask.source_type
manager/src/api/resources.py	create_resource, scan_resource + импорты
manager/src/api/scanner.py	get_pending_task — source_type в payload
STATE.md	Обновление версии + следующий шаг
CHANGELOG.md	Секция [3.13.29]
ROADMAP.md	Отметка 53.1a выполненной
🔧 ДЕТАЛЬНОЕ ТЗ
TASK-104 — Миграция 006_add_source_type
Файл: manager/src/db/migrations/versions/006_add_source_type.py (создать)

Идемпотентность обязательна: на свежих БД 001_initial_postgres создаёт scan_tasks из текущих моделей (Base.metadata.sorted_tables), и колонка source_type может уже существовать. Стиль — как у 002_scanner_progress.py и 005_add_fragment_columns.py (inspect-guard).

Полный код:

python
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
TASK-105 — ScanTask.source_type в моделях
Файл: manager/src/db/models.py

Найти класс ScanTask. Добавить поле source_type сразу после source_path. Полный код класса:

python
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
Больше в этом файле ничего не менять.

TASK-106 — create_resource: S3-ресурсы + фикс уникальности
Файл: manager/src/api/resources.py

106.1. Импорты
В начале файла после существующих импортов добавить:

python
import os
from urllib.parse import urlparse
(остальные импорты — Optional из typing — уже есть.)

106.2. Функция create_resource — заменить полностью
Найти существующую @router.post("") → def create_resource(...) и заменить её целиком на:

python
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
        "message": "Resource created successfully",
    }
TASK-107 — scan_resource: source_type при создании ScanTask
Файл: manager/src/api/resources.py

В функции scan_resource найти блок создания задачи:

python
    # Создаем задание
    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource.path,
        status="pending",
        created_at=datetime.utcnow()
    )
Заменить на:

python
    # Создаем задание
    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource.path,
        # День 53.1a: тип источника из ресурса (lowercase — как Resource.type).
        source_type=(resource.type or "filesystem").lower(),
        status="pending",
        created_at=datetime.utcnow(),
    )
Больше в этом файле ничего не менять.

TASK-108 — /api/scanner/tasks/pending: source_type в payload
Файл: manager/src/api/scanner.py

В функции get_pending_task найти финальный return:

python
    return {
        "task": {
            "id": task.id,
            "resource_id": task.resource_id,
            "path": resource.path,
            "scan_config": scan_config
        }
    }
Заменить на:

python
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
Больше в этом файле ничего не менять.

TASK-109 — Unit-тесты
Файл: tests/unit/test_s3_resource_v31329.py (создать)

Полный код:

python
"""Unit-тесты Дня 53.1a: S3-ресурсы и source_type в задачах.

Покрытие:
- создание filesystem-ресурса (регрессия);
- создание s3-ресурса с дефолтами и кастомным endpoint;
- minio трактуется как s3;
- валидация s3-пути (не-url, пустой bucket);
- уникальность по (path, type);
- POST /api/resources/{id}/scan выставляет source_type;
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from manager.src.db import models, session as db_session  # noqa: E402
from manager.src.db.models import Base  # noqa: E402
from manager.src.auth.models import User  # noqa: F401,E402


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(engine, monkeypatch):
    """TestClient с подменённым get_db и авторизованным admin."""
    from manager.src.main import app
    from manager.src.auth import dependencies as auth_deps

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def _override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_session.get_db] = _override_get_db

    admin = User(username="test_admin", is_active=True)
    admin.set_password("x")
    app.dependency_overrides[auth_deps.require_admin] = lambda: admin
    app.dependency_overrides[auth_deps.require_scanner] = lambda: admin

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------- Создание ресурсов ----------

def test_create_filesystem_resource_default(client, db):
    r = client.post("/api/resources", params={"path": "C:/data", "type": "FILESYSTEM"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "filesystem"
    res = db.query(models.Resource).filter(models.Resource.id == body["id"]).first()
    assert res is not None
    assert res.type == "filesystem"


def test_create_s3_resource_with_defaults(client, db):
    r = client.post(
        "/api/resources",
        params={"path": "s3://dcap-audit-logs/", "type": "s3"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "s3"

    res = db.query(models.Resource).filter(models.Resource.id == body["id"]).first()
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


def test_create_s3_resource_with_custom_endpoint(client, db):
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
    res = db.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    s3 = res.scan_config["connector"]["s3"]
    assert s3["endpoint"] == "minio.local:9000"
    assert s3["bucket"] == "bucket"
    assert s3["prefix"] == "prefix"
    assert s3["secure"] is True
    assert s3["use_path_style"] is False
    assert s3["region"] == "eu-west-1"


def test_create_minio_resource_treated_as_s3(client, db):
    r = client.post(
        "/api/resources",
        params={"path": "minio://bucket/logs", "type": "minio"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "minio"
    res = db.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    assert "s3" in res.scan_config["connector"]


def test_create_s3_resource_invalid_path(client):
    r = client.post("/api/resources", params={"path": "not-a-url", "type": "s3"})
    assert r.status_code == 400
    assert "s3://" in r.json()["detail"]


def test_create_s3_resource_empty_bucket(client):
    r = client.post("/api/resources", params={"path": "s3:///prefix", "type": "s3"})
    assert r.status_code == 400


def test_create_resource_unique_by_path_and_type(client, db):
    """BUG-059 регрессия: (path, type) — составной ключ, не только path."""
    r1 = client.post("/api/resources", params={"path": "s3://b/x", "type": "s3"})
    assert r1.status_code == 200, r1.text
    # Тот же path, другой type — тоже можно.
    r2 = client.post("/api/resources", params={"path": "s3://b/x", "type": "minio"})
    assert r2.status_code == 200, r2.text
    # Тот же (path, type) — 400.
    r3 = client.post("/api/resources", params={"path": "s3://b/x", "type": "s3"})
    assert r3.status_code == 400


def test_create_resource_unsupported_type(client):
    r = client.post("/api/resources", params={"path": "x", "type": "ftp"})
    assert r.status_code == 400


# ---------- Задача: source_type ----------

def test_scan_s3_resource_sets_source_type(client, db):
    res_id = client.post(
        "/api/resources",
        params={"path": "s3://bucket/prefix", "type": "s3"},
    ).json()["id"]

    r = client.post(f"/api/resources/{res_id}/scan")
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]

    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    assert task is not None
    assert task.source_type == "s3"
    assert task.source_path == "s3://bucket/prefix"


def test_scan_filesystem_resource_sets_source_type(client, db):
    res_id = client.post(
        "/api/resources",
        params={"path": "C:/data", "type": "filesystem"},
    ).json()["id"]

    task_id = client.post(f"/api/resources/{res_id}/scan").json()["task_id"]
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    assert task.source_type == "filesystem"
🧪 КРИТЕРИИ ПРИЁМКИ
#	Критерий	Проверка
1	Миграция 006 применяется на SQLite и PG без ошибок	alembic upgrade head
2	ScanTask.source_type доступен, дефолт filesystem	test_scan_filesystem_resource_sets_source_type
3	POST /api/resources?type=s3&path=s3://bucket работает	test_create_s3_resource_with_defaults
4	POST /api/resources?type=minio&path=minio://bucket работает	test_create_minio_resource_treated_as_s3
5	Невалидный S3-путь → 400	test_create_s3_resource_invalid_path
6	Уникальность по (path, type) (BUG-059)	test_create_resource_unique_by_path_and_type
7	POST /api/resources/{id}/scan ставит source_type из ресурса	test_scan_s3_resource_sets_source_type
8	Секреты S3 в scan_config отсутствуют	test_create_s3_resource_with_defaults
9	Полный unit-набор зелёный (регрессий нет)	pytest tests/unit/ -q
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
1. Миграция
powershell
# Dev-БД (SQLite)
alembic upgrade head
alembic current

# Ожидание: "006_add_source_type (head)"
2. Unit-тесты
powershell
pytest tests/unit/test_s3_resource_v31329.py -v
pytest tests/unit/ -q
Ожидание:

новый файл — все тесты passed,

полный unit-набор — регрессий нет (было 359 passed, стало 359 + N).

3. Ручная проверка (при запущенном Manager)
powershell
# Получить токен
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

# Создать S3-ресурс
Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources?path=s3://dcap-audit-logs/&type=s3" `
    -Headers $headers | ConvertTo-Json

# Запустить сканирование
Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources/<RES_ID>/scan" `
    -Headers $headers | ConvertTo-Json

# Проверить, что задача получила source_type=s3
$task_id = <TASK_ID>
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/tasks/$task_id" `
    -Headers $headers | ConvertTo-Json -Depth 5 | Select-String "source_type"
4. Проверка в БД
powershell
$sql = "SELECT id, source_path, source_type, status FROM scan_tasks ORDER BY id DESC LIMIT 5;"
$sql | docker exec -i dcap-postgres psql -U dcap -d dcap
Ожидание: для S3-задачи source_type = s3, для FS — filesystem.

📝 СВОДКА ПРАВОК
#	Файл	Действие	Задача
1	manager/src/db/migrations/versions/006_add_source_type.py	Создан	TASK-104
2	manager/src/db/models.py	ScanTask.source_type	TASK-105
3	manager/src/api/resources.py	Импорты + create_resource + scan_resource	TASK-106, TASK-107
4	manager/src/api/scanner.py	get_pending_task — source_type в payload	TASK-108
5	tests/unit/test_s3_resource_v31329.py	Создан	TASK-109
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ
WebUI-форма добавления S3-ресурса — не входит в 53.1a. Пока создание S3-ресурса возможно только через API (curl/Swagger). Форма — в 53.3.

Сканер ещё не умеет S3. source_type в payload начнёт использоваться в 53.1b. До этого сканер продолжит игнорировать поле и работать по path.

Дефолтный endpoint — host.docker.internal:9000 (MinIO Блока 6). Для другого окружения — переопределить через query-параметр или ENV S3_DEFAULT_ENDPOINT.

S3_VERIFY_SSL — не в этом ТЗ, будет учтён в 53.2 (TEST-NOTE-6.11 в s3_connector.py:110).

📋 ОТКРЫТЫЕ ВОПРОСЫ
MinIO type — трактуем s3 и minio одинаково (один коннектор, различие только в endpoint). ✅ Согласовано архитектором.

Query-параметры для POST /api/resources — endpoint, secure, use_path_style, region. ✅ Согласовано архитектором.

Секреты S3 — только ENV на хосте сканера (S3_ACCESS_KEY/S3_SECRET_KEY), не в scan_config. ✅ Согласовано.

⚠️ ЧТО НЕ ДЕЛАЕМ
Не трогаем сканер (managed_scanner.py, s3_connector.py, filesystem.py).

Не добавляем boto3 в requirements.txt сканера — это 53.1b.

Не создаём _text_scanner.py, factory.py, S3LineConnector — это 53.1b/53.2.

Не делаем WebUI-форму для S3 — это 53.3.

Не трогаем get_default_config() — секция connector.s3 добавляется поверх неё.

💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_53_1a_source_type

git add manager/src/db/migrations/versions/006_add_source_type.py \
        manager/src/db/models.py \
        manager/src/api/resources.py \
        manager/src/api/scanner.py \
        tests/unit/test_s3_resource_v31329.py \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/reports/day_53_1a_report.md

git commit -m "feat: День 53.1a — source_type в ScanTask + S3-ресурсы в Manager (v3.13.29)

- ScanTask.source_type (filesystem | s3 | minio), миграция 006
- POST /api/resources: type=s3|minio, валидация s3://bucket[/prefix],
  дефолтный scan_config.connector.s3 (endpoint/secure/use_path_style/region)
- уникальность (path, type) — регрессия BUG-059
- POST /api/resources/{id}/scan: source_type из Resource.type
- GET /api/scanner/tasks/pending: source_type в payload
- секреты S3 — только ENV (S3_ACCESS_KEY / S3_SECRET_KEY), не в scan_config

BACKLOG-097 (часть 1: Manager)
docs: обновлён STATE.md (v3.13.29)"
📊 ОБНОВЛЕНИЕ ПЛАНА
День	Задача	Статус
52.1	Linux-агент (дотест)	📋
52.2	Блок 6.5 (сбор прав Windows)	📋
53.1a	Manager: source_type для S3-ресурсов	🔄 В РАБОТЕ
53.1b	Scanner: ядро (фабрика, _text_scanner.py, boto3)	📋
53.2	Scanner: S3-пайплайн находок	📋
53.3	Тесты + WebUI-форма S3	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ
Обновить STATE.md (по инструкции из AGENTS.md):

Обновлено: — текущая дата,

Текущая версия: — v3.13.29,

Следующий шаг — «53.1b: Scanner, ядро (фабрика коннекторов, _text_scanner.py, boto3, source_type в managed_scanner.py)».

Обновить CHANGELOG.md — секция [3.13.29].

Обновить ROADMAP.md — отметить 53.1a выполненной.

Переместить ТЗ в prompts/archive/day_53_1a_source_type.md.

Отчёт — в prompts/reports/day_53_1a_report.md (формат — как у day_50_bug102_celery_mapper_report.md):

сводка по выполнению,

полный код изменённых/новых файлов,

команда для коммита,

результаты pytest,

инструкция по ручной проверке (curl-команды).

Автор ТЗ: архитектор
Дата: 03.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.29 — ScanTask.source_type, POST /api/resources?type=s3|minio, source_type в payload задачи; сканер (53.1b) сможет выбрать коннектор по явному типу.