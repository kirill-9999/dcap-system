# tests/unit/test_webui_block5_v31322.py — День 48, Блок 5 (WebUI)
# Покрывает:
#   TASK-054 / BUG-087 — прокси WebUI ронял X-Total-Count и др. заголовки
#   TASK-056 / BUG-089 — /api/access/resources 500 на PostgreSQL (is_active == 1)
#   TASK-057 / BUG-090 — фильтры /api/findings: CSV-категории, пустые параметры
#   TASK-058 / BUG-091 — /api/audit без фильтра event_source
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
from manager.src.auth.dependencies import get_current_user
from manager.src.api import findings as findings_api
from manager.src.api import webui as webui_api
from manager.src.api import audit as audit_api
from webui.api.routes import forwarded_headers

pytestmark = [pytest.mark.unit]


class _FakeUser(SimpleNamespace):
    def has_role(self, name):
        return any(r.name == name for r in self.roles)


def _user(role: str = "admin"):
    return _FakeUser(
        id=7,
        username="test_" + role,
        roles=[SimpleNamespace(name=role)],
    )


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

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _user("admin")
    for _r in (findings_api.router, webui_api.router, audit_api.router):
        app.include_router(_r)
    return TestClient(app)


@pytest.fixture()
def resource(db_session):
    """Finding.resource_id — NOT NULL, нужна хотя бы одна Resource."""
    res = models.Resource(path="C:/data", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    return res


_FP = [0]


def _finding(db, res, **kw):
    _FP[0] += 1
    base = dict(
        resource_id=res.id,
        finding_type="pii",
        category="phone",
        severity="medium",
        status="new",
        detector="presidio",
        fragment_type="text_line",
        match_text_masked="+7***4567",
        line_text_masked="tel: +7***4567",
        fragment_path="C:/data/contacts.txt",
        fingerprint="fp-%d" % _FP[0],
        encryption_key_id="test-key-id",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    base.update(kw)
    f = models.Finding(**base)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ============================================================
# TASK-054 (BUG-087): прокси WebUI пробрасывает заголовки ответа
# ============================================================

class TestProxyHeaders:
    def test_custom_headers_forwarded(self):
        """X-Total-Count / X-Fragment-* доходят до браузера."""
        h = forwarded_headers(
            {
                "content-type": "application/json; charset=utf-8",
                "x-total-count": "667",
                "x-fragment-mode": "embedded",
                "x-fragment-hash": "9ecadc2f",
                "x-bounding-box": "{}",
            }
        )
        assert h["x-total-count"] == "667"
        assert h["x-fragment-mode"] == "embedded"
        assert h["x-fragment-hash"] == "9ecadc2f"
        assert h["x-bounding-box"] == "{}"

    def test_hop_by_hop_dropped(self):
        h = forwarded_headers(
            {
                "connection": "keep-alive",
                "transfer-encoding": "chunked",
                "content-length": "123",
                "content-encoding": "gzip",
                "x-total-count": "5",
            }
        )
        assert "connection" not in h
        assert "transfer-encoding" not in h
        assert "content-length" not in h
        assert "content-encoding" not in h
        assert h["x-total-count"] == "5"

    def test_set_cookie_dropped(self):
        """Cookie Manager'а через прокси не доходит (WebUI использует Bearer)."""
        h = forwarded_headers({"set-cookie": "access_token=abc; HttpOnly", "x-total-count": "1"})
        assert "set-cookie" not in h

    def test_case_insensitive(self):
        h = forwarded_headers({"X-Total-Count": "9", "SET-COOKIE": "a=b", "Connection": "close"})
        assert h["X-Total-Count"] == "9"
        assert "SET-COOKIE" not in h
        assert "Connection" not in h


# ============================================================
# TASK-057 (BUG-090): фильтры /api/findings
# ============================================================

class TestFindingsFilters:
    def test_total_count_header(self, client, db_session, resource):
        for _ in range(5):
            _finding(db_session, resource)
        r = client.get("/api/findings")
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "5"

    def test_category_single(self, client, db_session, resource):
        _finding(db_session, resource, category="phone")
        _finding(db_session, resource, category="email")
        r = client.get("/api/findings", params={"category": "phone"})
        assert r.headers["X-Total-Count"] == "1"
        assert r.json()[0]["category"] == "phone"

    def test_category_csv(self, client, db_session, resource):
        """BUG-090: "phone, email" — список категорий (раньше всегда 0)."""
        _finding(db_session, resource, category="phone")
        _finding(db_session, resource, category="email")
        _finding(db_session, resource, category="inn")
        r = client.get("/api/findings", params={"category": "phone, email"})
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "2"
        assert {f["category"] for f in r.json()} == {"phone", "email"}

    def test_category_csv_with_spaces(self, client, db_session, resource):
        _finding(db_session, resource, category="phone")
        _finding(db_session, resource, category="inn")
        r = client.get("/api/findings", params={"category": " phone ,  inn , "})
        assert r.headers["X-Total-Count"] == "2"

    def test_category_legacy_mixed(self, client, db_session, resource):
        """Legacy-категории фильтруются по finding_type, обычные — по category."""
        _finding(db_session, resource, finding_type="credentials", category="github_token")
        _finding(db_session, resource, finding_type="pii", category="phone")
        r = client.get("/api/findings", params={"category": "credentials,phone"})
        assert r.headers["X-Total-Count"] == "2"

    def test_detector_filter(self, client, db_session, resource):
        _finding(db_session, resource, detector="regex")
        _finding(db_session, resource, detector="presidio")
        r = client.get("/api/findings", params={"detector": "regex"})
        assert r.headers["X-Total-Count"] == "1"
        assert r.json()[0]["detector"] == "regex"

    def test_fragment_type_filter(self, client, db_session, resource):
        _finding(db_session, resource, fragment_type="image_region")
        _finding(db_session, resource, fragment_type="text_line")
        r = client.get("/api/findings", params={"fragment_type": "image_region"})
        assert r.headers["X-Total-Count"] == "1"
        assert r.json()[0]["fragment_type"] == "image_region"

    def test_search_filter(self, client, db_session, resource):
        _finding(db_session, resource, fragment_path="C:/data/secret/leak.txt")
        _finding(db_session, resource, fragment_path="C:/data/public/readme.md")
        r = client.get("/api/findings", params={"search": "secret"})
        assert r.headers["X-Total-Count"] == "1"
        assert "leak.txt" in r.json()[0]["file_path"]

    def test_combined_filters(self, client, db_session, resource):
        _finding(db_session, resource, category="phone", detector="presidio", status="new")
        _finding(db_session, resource, category="phone", detector="regex", status="new")
        _finding(db_session, resource, category="phone", detector="presidio", status="confirmed")
        r = client.get(
            "/api/findings",
            params={"category": "phone", "detector": "presidio", "status": "new"},
        )
        assert r.headers["X-Total-Count"] == "1"

    def test_order_by_id(self, client, db_session, resource):
        _finding(db_session, resource)
        _finding(db_session, resource)
        r = client.get("/api/findings", params={"order_by": "id", "order": "asc"})
        assert r.status_code == 200
        ids = [f["id"] for f in r.json()]
        assert ids == sorted(ids)

    @pytest.mark.parametrize("qs", ["task_id=", "resource_id=", "limit=", "offset="])
    def test_empty_numeric_params_not_422(self, client, db_session, resource, qs):
        """BUG-090: пустой параметр = "без фильтра", а не 422."""
        _finding(db_session, resource)
        r = client.get("/api/findings?" + qs)
        assert r.status_code == 200, r.text
        assert r.headers["X-Total-Count"] == "1"

    def test_empty_category_ignored(self, client, db_session, resource):
        _finding(db_session, resource)
        r = client.get("/api/findings?category=")
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "1"

    def test_count_endpoint_csv_category(self, client, db_session, resource):
        _finding(db_session, resource, category="phone")
        _finding(db_session, resource, category="email")
        _finding(db_session, resource, category="inn")
        r = client.get("/api/findings/count", params={"category": "phone,email"})
        assert r.status_code == 200
        assert r.json()["count"] == 2

    def test_count_endpoint_empty_task_id(self, client, db_session, resource):
        _finding(db_session, resource)
        r = client.get("/api/findings/count?task_id=")
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_export_csv_category(self, client, db_session, resource):
        _finding(db_session, resource, category="phone")
        _finding(db_session, resource, category="email")
        r = client.get(
            "/api/findings/export", params={"format": "csv", "category": "phone,email"}
        )
        assert r.status_code == 200
        assert r.headers["content-disposition"].startswith("attachment")
        assert r.text.count("\n") >= 3  # заголовок + 2 строки

    def test_export_empty_params(self, client, db_session, resource):
        _finding(db_session, resource)
        r = client.get("/api/findings/export?format=json&task_id=&resource_id=&limit=")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_has_fragment_from_embedded_data(self, client, db_session, resource):
        """BACKLOG-086: фрагмент в БД -> has_fragment даже без fragment_path."""
        _finding(
            db_session,
            resource,
            fragment_type="image_region",
            fragment_path=None,
            fragment_data=b"\x89PNG\r\n\x1a\n",
            fragment_hash="deadbeef",
        )
        r = client.get("/api/findings")
        assert r.json()[0]["has_fragment"] is True

    def test_has_fragment_false(self, client, db_session, resource):
        _finding(db_session, resource, fragment_type="text_line", fragment_path=None)
        assert client.get("/api/findings").json()[0]["has_fragment"] is False


# ============================================================
# TASK-056 (BUG-089): /api/access/resources — Boolean-колонка
# ============================================================

class TestAccessResources:
    @pytest.fixture()
    def shared(self, db_session):
        res = models.Resource(path="C:/share", type="filesystem")
        db_session.add(res)
        db_session.commit()
        db_session.refresh(res)
        db_session.add(
            models.AccessEntry(
                resource_id=res.id,
                principal_type="user",
                principal_name="alice",
                permission_type="read",
                is_active=True,
            )
        )
        db_session.add(
            models.AccessEntry(
                resource_id=res.id,
                principal_type="user",
                principal_name="bob",
                permission_type="write",
                is_active=False,
            )
        )
        db_session.commit()
        return res

    def test_access_resources_no_500(self, client, shared):
        """BUG-089: is_active == 1 -> 500 на PostgreSQL (boolean = integer)."""
        r = client.get("/api/access/resources")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["resources"][0]["entries_count"] == 1

    def test_access_entries_no_500(self, client, shared):
        r = client.get("/api/access/resources/%d/entries" % shared.id)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["entries"][0]["principal_name"] == "alice"

    def test_access_entries_filter(self, client, shared):
        r = client.get(
            "/api/access/resources/%d/entries" % shared.id, params={"principal": "ali"}
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1


# ============================================================
# TASK-058 (BUG-091): /api/audit — фильтр event_source
# ============================================================

class TestAuditFilters:
    def _log(self, db, **kw):
        base = dict(
            event_type="finding_reveal",
            event_source="api",
            user="auditor",
            file_path="C:/x",
            metadata_json={},
            created_at=datetime.utcnow(),
        )
        base.update(kw)
        row = models.AuditLog(**base)
        db.add(row)
        db.commit()
        return row

    def test_event_source_filter(self, client, db_session):
        """BUG-091: фильтр "Источник" в WebUI игнорировался."""
        self._log(db_session, event_source="api")
        self._log(db_session, event_source="scanner")
        self._log(db_session, event_source="windows_agent")
        r = client.get("/api/audit", params={"event_source": "scanner"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["events"][0]["event_source"] == "scanner"

    def test_event_type_filter(self, client, db_session):
        self._log(db_session, event_type="finding_reveal")
        self._log(db_session, event_type="fragment_accessed")
        r = client.get("/api/audit", params={"event_type": "fragment_accessed"})
        assert r.json()["total"] == 1

    def test_source_and_type_combined(self, client, db_session):
        self._log(db_session, event_source="api", event_type="finding_reveal")
        self._log(db_session, event_source="api", event_type="fragment_accessed")
        self._log(db_session, event_source="scanner", event_type="finding_reveal")
        r = client.get(
            "/api/audit",
            params={"event_source": "api", "event_type": "finding_reveal"},
        )
        assert r.json()["total"] == 1

    def test_no_filter_returns_all(self, client, db_session):
        for src in ("api", "scanner", "linux_agent"):
            self._log(db_session, event_source=src)
        r = client.get("/api/audit", params={"event_source": ""})
        assert r.json()["total"] == 3

    def test_user_filter_still_works(self, client, db_session):
        self._log(db_session, user="admin")
        self._log(db_session, user="auditor")
        r = client.get("/api/audit", params={"user": "admin"})
        assert r.json()["total"] == 1
