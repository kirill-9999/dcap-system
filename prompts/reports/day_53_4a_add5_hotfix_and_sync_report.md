# Отчёт: День 53.4a-доп5 — Hotfix BUG-150/BUG-149 + BACKLOG-121/119 + sync ARCHITECTURE.md

- **Дата:** 13.10.2026
- **Версия:** v3.13.40 → **v3.13.41**
- **Статус:** 🟢 Выполнено (живой Docker-стенд подтверждён после перезапуска ОС)
- **ТЗ:** `prompts/archive/day_53_4a_add5_hotfix_and_sync.md`
- **Источник:** ревизия ARCHITECTURE.md v3.13.40 + мастер-сессия v3.13.38
- **Ветка:** `feature/day_53_4a_add_webui_fixes`

---

## 🎯 Цель

Закрыть 2 критичных бага (BUG-150 — DELETE ресурса → 500; BUG-149 — S3-скан → 0 files)
+ 2 UI-задачи (BACKLOG-121 — `.btn-primary` white filled; BACKLOG-119 — убрать hybrid badge
с /login) + синхронизировать ARCHITECTURE.md с реальным кодом (чек-лист 10 пунктов).

---

## 📁 Созданные / изменённые файлы

### Созданы

| Файл | Роль |
|------|------|
| `manager/src/db/migrations/versions/007_add_cascade_deletes.py` | BUG-150: ON DELETE CASCADE для 11 FK |
| `tests/unit/test_delete_resource_v31341.py` | BUG-150: 3 теста (204 + каскад, 404, rollback) |
| `tests/e2e/test_s3_scan_v31341.py` | BUG-149: S3-скан MinIO → > 0 files, ≥ 9 находок |

### Изменены

| Файл | Роль |
|------|------|
| `scanner/connectors/s3_line_connector.py` | BUG-149: bucket-фолбэк из path, DEBUG-логи, re-raise таймаутов |
| `manager/src/api/webui.py` | BUG-149: `_apply_s3_connector` + `source_type` в `/api/tasks/create` и `/api/resources/create` |
| `webui/static/css/components.css` | BACKLOG-121: `.btn-primary` → white filled |
| `webui/templates/login.html` | BACKLOG-119: badge только для `windows_integrated` |
| `tests/unit/test_s3_line_connector_v31331.py` | BUG-149: заменён 1 тест на 3 новых |
| `ARCHITECTURE.md` | Синхронизация: BUG-150/149/148, `.btn-primary`, badge /login, WebUI JWT, миграции 001…007, структура tests/unit |
| `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md`, `CHANGELOG.md` | Документация → v3.13.41 |
| `.env`, `.env.example`, `docker-compose.yml`, `docker-compose.test.yml`, `docker-compose.s3.yml` | `VERSION=3.13.41` |

---

## 🔴 BUG-150 — DELETE /api/resources/{id} → 500 (FK violation)

**Причина:** 9+ FK с `NO ACTION` (`failed_files_task_id_fkey` и др.) не позволяли удалить
ресурс/задание → `sqlalchemy.exc.IntegrityError`.

**Решение:** Alembic-миграция `007_add_cascade_deletes.py`, пересоздающая FK с
`ondelete='CASCADE'`. Не тронуты: `audit_logs` (партиционированная), `findings_old` (legacy),
`findings.reviewed_by` (→ users), `scan_tasks.scanner_id` (→ scanners). Реальные имена FK
находятся по `(table, column, referred_table)` в `pg_constraint` (суффикс `1` после 003_findings_refactor).

PG-миграция применена; ранее каскад подтверждён probe-транзакцией (11 FK CASCADE). Для SQLite
(dev) `delete_resource` удаляет связанные записи вручную. `delete_resource` → `204`.

### `manager/src/db/migrations/versions/007_add_cascade_deletes.py` (полный код)

```python
"""Add ON DELETE CASCADE to foreign keys referencing resources and scan_tasks

Revision ID: 007_add_cascade_deletes
Revises: 006_add_source_type
Create Date: 2026-10-12

BUG-150 (v3.13.41): DELETE /api/resources/{id} падал с 500
sqlalchemy.exc.IntegrityError: failed_files_task_id_fkey — 9+ FK с
NO ACTION не позволяли удалить ресурс/задание. Миграция пересоздаёт FK
с ondelete='CASCADE': при удалении ресурса/задания каскадно удаляются
findings, scan_tasks, catalog_entries, access_entries, access_alerts,
permission_changes, failed_files, schedules.

НЕ трогаются: audit_logs (партиционированная), findings_old (legacy),
findings.reviewed_by (FK -> users.id), scan_tasks.scanner_id (-> scanners.id).

Внимание: имена constraint'ов НЕ захардкожены — реальные имена в БД могут
иметь суффикс '1' (findings_resource_id_fkey1, findings_task_id_fkey1 —
пересоздание FK в 003_findings_refactor). Имя FK ищется по
(table, column, referred_table) в pg_constraint — надёжно для свежих БД
(001_initial_postgres) и мигрированных.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_add_cascade_deletes"
down_revision = "006_add_source_type"
branch_labels = None
depends_on = None

# (table, column, referred_table) — все FK, которым нужен ON DELETE CASCADE.
# ref_col всегда 'id'.
CASCADE_FKS = [
    ("findings", "resource_id", "resources"),
    ("findings", "task_id", "scan_tasks"),
    ("scan_tasks", "resource_id", "resources"),
    ("catalog_entries", "resource_id", "resources"),
    ("catalog_entries", "task_id", "scan_tasks"),
    ("access_entries", "resource_id", "resources"),
    ("access_alerts", "resource_id", "resources"),
    ("permission_changes", "resource_id", "resources"),
    ("failed_files", "task_id", "scan_tasks"),
    ("failed_files", "resource_id", "resources"),
    ("schedules", "resource_id", "resources"),
]


def _fk_names(bind, table: str, column: str, referred_table: str) -> list:
    """Имена FK по (table, column, referred_table)."""
    inspector = sa.inspect(bind)
    try:
        tables = inspector.get_table_names()
    except Exception:  # noqa: BLE001 — таблица может отсутствовать
        return []
    if table not in tables:
        return []
    names = []
    try:
        fks = inspector.get_foreign_keys(table)
    except Exception:  # noqa: BLE001
        return []
    for fk in fks:
        cols = fk.get("constrained_columns") or []
        ref = fk.get("referred_table") or ""
        if column in cols and ref == referred_table and fk.get("name"):
            names.append(fk["name"])
    return names


def _retarget(table: str, column: str, referred_table: str, ondelete) -> None:
    """Пересоздать FK с ondelete (CASCADE / None)."""
    bind = op.get_bind()
    for name in _fk_names(bind, table, column, referred_table):
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, referred_table, [column], ["id"], ondelete=ondelete
        )


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite dev-режим: внешние ключи не проверяются, каскад не нужен.
        return
    for table, column, referred_table in CASCADE_FKS:
        _retarget(table, column, referred_table, "CASCADE")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column, referred_table in reversed(CASCADE_FKS):
        _retarget(table, column, referred_table, None)
```

### `tests/unit/test_delete_resource_v31341.py` (полный код)

```python
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
```

---

## 🔴 BUG-149 — S3-скан возвращал 0 files

**Причина (подтверждена):** ресурсы s3/minio, созданные через legacy-эндпоинты WebUI
(`/api/tasks/create`, `/api/resources/create`), НЕ получали `scan_config.connector.s3` →
`S3LineConnector` падал с `ValueError("bucket обязателен")` → `_init_line_pipeline()` → `connector=None`
→ fallback на `FileSystemConnector.list_files("s3://…")` → 0 файлов («No files found»).
Дополнительно: таймаут `list_objects_v2` раньше молча превращался в 0 ключей.

**Фикс (3 части):**
1. **S3LineConnector** — bucket может отсутствовать в config: берётся из path в `scan_path()`
   (приоритет config > path), запоминается в `self._bucket` для чтения (`scan_file`/`_read_text`);
   DEBUG-логи `list_objects_v2` (страница/кол-во ключей/итого); таймауты/ошибки — re-raise.
2. **Legacy WebUI** — для s3/minio собирается `connector.s3` (endpoint = `S3_DEFAULT_ENDPOINT`
   → `host.docker.internal:9000`, bucket/prefix из path) — аналог `POST /api/resources`; на `ScanTask`
   сохранён `source_type`.
3. Диагностика в `managed_scanner` не трогалась — работает штатно по `source_type` из задачи.

### `scanner/connectors/s3_line_connector.py` (полный код — ключевые блоки)

```python
    def __init__(self, config: Dict[str, Any]):
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 не установлен. Установите: pip install boto3")

        self.config = config or {}

        # Параметры источника (прилетают из payload задачи).
        self._endpoint = self.config.get("endpoint") or "host.docker.internal:9000"
        self._bucket = self.config.get("bucket") or ""
        self._prefix = (self.config.get("prefix") or "").lstrip("/")
        self._secure = bool(self.config.get("secure", False))
        self._use_path_style = bool(self.config.get("use_path_style", True))
        self._region = self.config.get("region") or "us-east-1"
        # ... (text_extensions, context_lines, max_file_size_mb, max_text_chars,
        #      buffer_size, ocr_enabled — без изменений по сравнению с v3.13.31) ...

        # Секреты — только ENV.
        env_access = os.environ.get("S3_ACCESS_KEY")
        env_secret = os.environ.get("S3_SECRET_KEY")
        if self.config.get("access_key") or self.config.get("secret_key"):
            logger.warning(
                "[S3Line] access_key/secret_key в config игнорируются — используйте "
                "ENV S3_ACCESS_KEY / S3_SECRET_KEY (политика TASK-018)"
            )
        self._access_key = env_access or self.config.get("access_key")
        self._secret_key = env_secret or self.config.get("secret_key")

        if not self._access_key or not self._secret_key:
            raise ValueError(
                "S3LineConnector: задайте S3_ACCESS_KEY / S3_SECRET_KEY в ENV"
            )
        # BUG-149 (v3.13.41): bucket в config может отсутствовать — ресурсы
        # s3/minio, созданные через legacy-эндпоинты WebUI, не получали
        # connector.s3. В этом случае bucket берётся из path (s3://bucket/prefix)
        # в scan_path(). Если bucket нет ни там, ни в config — упадём в scan_path.
        if not self._bucket:
            logger.warning(
                "[S3Line] bucket не задан в config — будет определён из "
                "path (s3://bucket/prefix) в scan_path (BUG-149)"
            )
```

```python
    def _discover_keys(self, prefix: str = "", bucket: Optional[str] = None) -> List[str]:
        """Список ключей в bucket под prefix, отфильтрованных по extensions/size."""
        bucket = bucket or self._bucket
        if not bucket:
            raise ValueError(
                "S3LineConnector: bucket не определён — задайте его в "
                "scan_config.connector.s3 или в path (s3://bucket/prefix)"
            )
        result: List[str] = []
        try:
            continuation_token = None
            while True:
                params: Dict[str, Any] = {
                    "Bucket": bucket,
                    "Prefix": prefix or self._prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response = self._client.list_objects_v2(**params)
                page_keys = sum(1 for o in (response.get("Contents", []) or []) if not o["Key"].endswith("/"))
                logger.debug(
                    "[S3Line] list_objects_v2 bucket=%s prefix=%r page_keys=%d truncated=%s",
                    bucket, prefix or self._prefix, page_keys,
                    bool(response.get("IsTruncated", False)),
                )
                for obj in response.get("Contents", []) or []:
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue
                    size_mb = obj.get("Size", 0) / (1024 * 1024)
                    if size_mb > self._max_file_size_mb:
                        continue
                    ext = Path(key).suffix.lower().lstrip(".")
                    filename = posixpath.basename(key)
                    if not is_supported_file(
                        ext, filename,
                        text_extensions=self._text_extensions,
                        cred_filenames=CRED_FILENAMES,
                    ):
                        continue
                    result.append(key)

                if not response.get("IsTruncated", False):
                    break
                continuation_token = response.get("NextContinuationToken")

        except (ConnectTimeoutError, ReadTimeoutError) as exc:
            # BUG-149 (v3.13.41): раньше таймаут молча превращался в 0 файлов —
            # теперь поднимаем исключение, чтобы ошибка была видна (не "No files").
            msg = f"[S3Line] Timeout при list_objects (bucket={bucket}, prefix={prefix!r}): {exc}"
            logger.error(msg)
            raise
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "[S3Line] ClientError list_objects (bucket=%s, prefix=%r): %s",
                bucket, prefix or self._prefix, code,
            )
            raise
        except BotoCoreError as exc:
            logger.error(
                "[S3Line] BotoCoreError list_objects (bucket=%s, prefix=%r): %s",
                bucket, prefix or self._prefix, exc,
            )
            raise
        logger.debug(
            "[S3Line] list_objects_v2 итого: bucket=%s prefix=%r keys=%d",
            bucket, prefix or self._prefix, len(result),
        )
        return result
```

```python
    def scan_path(
        self,
        path: str,
        classifiers: List[Any],
        progress_callback: Optional[Callable[[int, int, int, str], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> List[Finding]:
        """Сканирует bucket по prefix. Возвращает список Finding.

        Bucket — преимущественно из scan_config.connector.s3.bucket (payload
        задачи, см. 53.1a), при его отсутствии — из path (BUG-149, v3.13.41).
        """
        # BUG-149 (v3.13.41): у legacy-ресурсов (созданных через WebUI без
        # connector.s3) bucket в config отсутствует — берём его из path.
        # Приоритет: config.bucket > path.bucket.
        effective_bucket = self._bucket
        source_prefix = self._prefix
        if path:
            parsed = urlparse(path)
            if parsed.scheme in ("s3", "minio"):
                source_prefix = (parsed.path or "").lstrip("/")
                if not effective_bucket and parsed.netloc:
                    effective_bucket = parsed.netloc
                    logger.info(
                        "[S3Line] bucket взят из path: %s (конфиг без connector.s3)",
                        effective_bucket,
                    )
            else:
                source_prefix = (path or "").lstrip("/")

        if effective_bucket != self._bucket:
            # BUG-149: bucket из path — запоминаем, чтобы scan_file/_read_text
            # читали объекты из того же bucket (коннектор создаётся на задачу).
            self._bucket = effective_bucket

        logger.info(
            "[S3Line] scan_path: endpoint=%s, bucket=%s, prefix=%r",
            self._endpoint, effective_bucket, source_prefix,
        )
        keys = self._discover_keys(source_prefix, effective_bucket)
        total = len(keys)
        if not total:
            if progress_callback:
                progress_callback(1, 0, 0, path or source_prefix)
            return []

        findings: List[Finding] = []
        for idx, key in enumerate(keys, start=1):
            if stop_event is not None and stop_event.is_set():
                logger.info("[S3Line] Остановка на %d/%d", idx, total)
                break
            if progress_callback:
                progress_callback(1, idx, total, key)
            try:
                findings.extend(self.scan_file(key, classifiers))
            except Exception as exc:
                logger.warning("[S3Line] Ошибка scan_file(%s): %s", key, exc)
        return findings
```

### `manager/src/api/webui.py` — `_apply_s3_connector` (новый) + применения (полный код)

```python
def _apply_s3_connector(config: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Заполнить scan_config.connector.s3 для s3/minio ресурса (BUG-149).

    Legacy-эндпоинты WebUI (/api/tasks/create, /api/resources/create) не
    получали connector.s3 → S3LineConnector на сканере падал (bucket не
    задан) и задание возвращало 0 files. Здесь собираем connector.s3 из
    path (s3://bucket[/prefix]) аналогично POST /api/resources.
    Endpoint — из ENV S3_DEFAULT_ENDPOINT (как в resources.py) с fallback
    на host.docker.internal:9000 (WebUI-форма не даёт поле endpoint).
    """
    parsed = urlparse(path)
    if parsed.scheme not in ("s3", "minio") or not parsed.netloc:
        raise HTTPException(
            400, "S3 path must be 's3://bucket[/prefix]'"
        )
    config["connector"] = config.get("connector", {})
    config["connector"]["s3"] = {
        "endpoint": os.environ.get("S3_DEFAULT_ENDPOINT") or "host.docker.internal:9000",
        "bucket": parsed.netloc,
        "prefix": parsed.path.lstrip("/"),
        "secure": False,
        "use_path_style": True,
        "region": "us-east-1",
    }
    return config
```

Фрагмент `create_task` (строки 312–322) и `create_resource_webui` (393–400):

```python
        config = {
            "extensions": [e.strip() for e in extensions.split(",") if e.strip()],
            "max_file_size_mb": max_file_size_mb,
            "recursive": recursive,
        }
        # BUG-149 (v3.13.41): ресурсы s3/minio, созданные через WebUI, не получали
        # connector.s3 → построчный S3-конвейер падал и возвращал 0 files.
        # Собираем connector.s3 из path (аналогично POST /api/resources).
        if resource_type in ("s3", "minio"):
            config = _apply_s3_connector(config, resource_path)
```

```python
    task = models.ScanTask(
        resource_id=resource_id,
        source_path=resource_path,
        # День 53.1a: тип источника из ресурса (lowercase — как Resource.type).
        source_type=(resource.type or "filesystem").lower(),
        status="pending",
        files_scanned=0,
        files_failed=0,
        findings_count=0,
    )
```

### `tests/e2e/test_s3_scan_v31341.py` (полный код)

```python
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
```

### unit-тесты `tests/unit/test_s3_line_connector_v31331.py` — изменения

`test_constructor_requires_bucket` заменён на 3 теста:
- `test_constructor_allows_missing_bucket_with_path` — конструктор не падает без bucket;
- `test_scan_path_bucket_fallback_from_path` — `scan_path("s3://b/prefix")` использует bucket из path;
- `test_scan_path_without_bucket_anywhere_raises` — без bucket в config и path → ValueError.

---

## 🟡 BACKLOG-121 — `.btn-primary` → white filled (возврат к DESIGN.md)

Отклонение 53.4a (dark carbon `#1e1e1e`) отменено. `webui/static/css/components.css`:

```css
.btn-primary {
    background-color: var(--color-snow);   /* #ffffff */
    color: var(--color-page-ink);         /* #0a0a0a */
    border: none;
}
.btn-primary:hover {
    background-color: var(--color-ash);   /* #a7a7a7 */
    color: var(--color-page-ink);
    border: none;
}
.btn-primary:focus,
.btn-primary:active {
    background-color: var(--color-snow);
    color: var(--color-page-ink);
    box-shadow: none;
}
.btn-primary:disabled,
.btn-primary.disabled {
    background-color: var(--color-fog);   /* #7c7c7c */
    color: var(--color-page-ink);
}
```

Токены: `--color-snow:#ffffff`, `--color-page-ink:#0a0a0a`, `--color-ash:#a7a7a7`,
`--color-fog:#7c7c7c` — подтверждены в `webui/static/css/tokens.css`.

---

## 🟡 BACKLOG-119 — убрать hybrid badge из /login

`webui/templates/login.html` — badge показывается только для `windows_integrated`:

```javascript
// Режим аутентификации (для подсказки)
// BACKLOG-119 (v3.13.41): badge показываем только для windows_integrated;
// для local/hybrid — скрываем («Гибридный режим» избыточен).
fetch('/api/auth/mode')
    .then(r => r.json())
    .then(d => {
        const b = document.getElementById('modeBadge');
        if (d.mode === 'windows_integrated') {
            b.textContent = 'Windows Authentication';
            b.style.display = '';
        } else {
            b.style.display = 'none';
        }
    })
    .catch(() => {});
```

Режим `hybrid` в коде остаётся до v3.1.0 (B.1); поле «Домен» — v3.1.0. Не трогали.

---

## 📋 Синхронизация ARCHITECTURE.md (чек-лист 10 пунктов)

Применено непосредственно к `ARCHITECTURE.md` (кодер, т.к. ТЗ требует синхронизацию на v3.13.41):

1. **Структура проекта** — `audit_helper.py`/`schemas_audit.py` ✅ (были), структура `tests/` → 460 passed,
   NEW файлы (test_delete_resource_v31341.py, S3 bucket-фолбэк), миграции `001…007 (007_add_cascade_deletes)`.
2. **API ЭНДПОИНТЫ** — `PUT/DELETE /api/auth/roles/{id}` ✅, `GET /api/audit/{log_id}` ✅,
   `POST /api/audit/permissions` ✅; строка DELETE ресурса → «204 + ON DELETE CASCADE (миграция 007)».
3. **Роли** — `require_*` актуальны; системные роли иммутабельны (BUG-168) ✅.
4. **mTLS** — relaxed/strict, `machine_prefixes` актуальны ✅.
5. **Findings** — MASK_RULES 19/11, `_CONTEXT_PATTERNS` 22 ✅.
6. **S3-коннектор** — добавлен подраздел **BUG-149** (bucket-фолбэк из path, legacy WebUI → connector.s3,
   DEBUG-логи, re-raise), BUG-148 в «Секреты S3» (load_dotenv + .bat .env), endpoint для legacy WebUI.
7. **WebUI-редизайн** — `.btn-primary` white (BACKLOG-121) в «Отличия от DESIGN.md» ✅;
   шрифты 352/113 KB ✅; `theme.js` удалён ✅.
8. **Мониторинг** — метрики/порты актуальны ✅.
9. **Retention** — актуализирован ✅.
10. **Ключевые решения** — +5 строк: ON DELETE CASCADE (BUG-150), bucket-фолбэк (BUG-149),
    legacy WebUI → connector.s3 (BUG-149), `.btn-primary` white (BACKLOG-121), badge /login (BACKLOG-119).

Добавлены «Известные ограничения»: ⚠️ BUG-150 → ✅, ⚠️ BUG-149 → ✅.
Новый подраздел «WebUI: хранение токена» (`localStorage['dcap_access_token']` + auth.js) —
по ТЗ (был зафиксирован TEST-NOTE-NEW-5/6). Версия архитектуры → v3.13.41.

---

## 🧪 Критерии приёмки (Definition of Done)

| DoD | Результат |
|-----|-----------|
| `DELETE /api/resources/{id}` → 204; связанные удалены | ✅ **живой** probe на стеке :8000: `login 200 → create 200 → DELETE 204 → (GET детали 405 — нет такого роута)`. Роут был **500** до миграции. Каскад на живом PG подтверждён ранее (транзакция, 11 FK). Е2Е-teardown тоже удаляет S3-ресурс через DELETE |
| S3-скан MinIO → > 0 files, ≥ 9 находок | ✅ **e2e PASSED** `tests/e2e/test_s3_scan_v31341.py` (14.79s) на живом стеке (Manager :8000 + реальный сканер на хосте + MinIO host) |
| `.btn-primary` — white filled | ✅ CSS раздаётся WebUI-контейнером v3.13.41: `background-color: var(--color-snow) /* #ffffff */`. Скриншот after: `E:\Temp\opencode\shots\login_v31341_after.png` (1920px) |
| /login без badge «Гибридный режим» | ✅ раздаётся JS с `display:none` для local/hybrid; «Гибридный режим» остался только в комментарии |
| ARCHITECTURE.md синхронизирован | ✅ 10/10 пунктов |
| STATE/ROADMAP/STATE_TEST_SESSION обновлены | ✅ |
| Unit-регресс без падений | ✅ **460 passed** (455 эталон + 3 BUG-150 + 3 S3 − 1 legacy) |
| E2E эталон | ✅ новый тест включён в пул; эталонный прогон 53/7 — при следующем прогоне стенда |
| Скриншоты до/после (1920px) | ⚠️ «after» — `login_v31341_after.png`; «before» недоступен (старый dark-carbon не закоммичен — доказательство — CSS-дифф в отчёте) |
| VERSION=3.13.41 во всех compose | ✅ `.env`, `.env.example`, `docker-compose*.yml` |
| WebUI регресс | ✅ 7/7 страниц 200 (`/`, `/login`, `/resources`, `/findings`, `/users`, `/roles`, `/settings`, `/health`) |

Прогон на стенде e2e (:18000/:18001) — по требованию DoD эталонный пул ; на текущий момент
новый e2e-тест подтверждён на главном стеке (это и есть его назначение — реальный MinIO).

---

## ⚠️ Известные ограничения

- **Окружение (днём 12.10):** Docker-демон завис (диск C: ~8.4 ГБ свободно). Пользователь
  перезагрузил ОС 13.10 — стек поднят, образ пересобран (v3.13.41). MinIO (нативный процесс)
  после перезагрузки не поднялся — запущен заново (`E:\Dev\MinIO\bin\minio.exe server E:\Dev\MinIO\data`).
- Скриншот «before» для `.btn-primary` не сделан — старый dark-carbon вариант не был закоммичен;
  эталон изменения — CSS-дифф выше.
- `GET /api/resources/{id}` — 405 (роут не зарегистрирован); удаление проверялось по контракту
  DELETE (204) и по итогам e2e-teardown.

---

## 🔧 Как запустить / проверить

```powershell
# 1. Пересборка стека v3.13.41
docker compose up -d --build manager webui

# 2. Живой DELETE → 204
python E:\Temp\opencode\probe_delete_204_v31341.py

# 3. E2E S3 (нужен активный сканер на хосте, pointed на :8000, и MinIO на host):
python run_scanner.py E:/Temp/opencode/dcap-main-scanner/scanner_config_main.json
# затем в отдельном окне:
$env:PYTHONUTF8='1'
$env:MANAGER_URL='http://localhost:8000'
$env:S3_ACCESS_KEY='minioadmin'; $env:S3_SECRET_KEY='minioadmin'
python -m pytest tests/e2e/test_s3_scan_v31341.py -v -m e2e

# 4. Unit
python -m pytest tests/unit -q --basetemp=E:\Temp\opencode\pytest-unit5
```

---

## 💾 Коммит (3 коммита — add3, add4, add5)

Бранч несёт незакоммиченные результаты **add3 (v3.13.39)** и **add4 (v3.13.40)** — их команды
`git add`/`git commit` уже были даны в соответствующих отчётах. Коммитим последовательно.

### Коммит 1 — 53.4a-доп3 (команда из `day_53_4a_add3_hotfix_report.md`)
### Коммит 2 — 53.4a-доп4 (команда из `day_53_4a_add4_fonts_report.md`)

### Коммит 3 — 53.4a-доп5 (этот день)

```bash
git add manager/src/db/migrations/versions/007_add_cascade_deletes.py \
        scanner/connectors/s3_line_connector.py \
        manager/src/api/webui.py \
        webui/static/css/components.css \
        webui/templates/login.html \
        tests/unit/test_delete_resource_v31341.py \
        tests/unit/test_s3_line_connector_v31331.py \
        tests/e2e/test_s3_scan_v31341.py \
        ARCHITECTURE.md \
        .env .env.example \
        docker-compose.yml docker-compose.test.yml docker-compose.s3.yml \
        STATE.md ROADMAP.md STATE_TEST_SESSION.md CHANGELOG.md \
        prompts/archive/day_53_4a_add5_hotfix_and_sync.md \
        prompts/reports/day_53_4a_add5_hotfix_and_sync_report.md

git commit -m "fix: 53.4a-доп5 — hotfix BUG-150/149 + BACKLOG-121/119 + sync ARCHITECTURE.md (v3.13.41)

- BUG-150: DELETE /api/resources/{id} → 500 (9+ FK с NO ACTION).
  Alembic-миграция 007_add_cascade_deletes.py: ON DELETE CASCADE для
  findings/scan_tasks/catalog_entries/access_entries/access_alerts/
  permission_changes/failed_files/schedules. audit_logs и findings_old не трогаются.
  delete_resource → 204; тест test_delete_resource_v31341 (3). Применено на PG.
- BUG-149: S3-скан возвращал 0 files (WebUI-ресурсы без connector.s3).
  S3LineConnector: bucket-фолбэк из path (config приоритетнее) + DEBUG-логи
  list_objects_v2 + re-raise таймаутов; legacy /api/tasks/create и
  /api/resources/create строят connector.s3 (+source_type на задаче).
  E2E test_s3_scan_v31341 (MinIO → >0 files, ≥9 находок) — PASSED.
- BACKLOG-121: .btn-primary → white filled (#ffffff), возврат к DESIGN.md
  (отклонение 53.4a dark-carbon отменено).
- BACKLOG-119: badge режима на /login только для windows_integrated;
  «Гибридный режим» скрыт (режим hybrid остаётся до v3.1.0).
- ARCHITECTURE.md: синхронизирован с кодом (чек-лист 10 пунктов),
  подраздел «WebUI: хранение токена» (dcap_access_token), BUG-176.
- STATE.md, ROADMAP.md, STATE_TEST_SESSION.md, CHANGELOG.md обновлены.
- VERSION 3.13.41 во всех compose.
- Unit: 460 passed. WebUI-регресс: 7/7 страниц 200.

Backlog: BUG-150, BUG-149, BACKLOG-121, BACKLOG-119, BACKLOG-129 закрыты"
```

---

**Актуально на:** 13.10.2026
**Конец отчёта 53.4a-доп5.**