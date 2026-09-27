# tests/unit/test_audit_reveal_user_v31323.py — День 48.1, BUG-087 (аудит reveal), v3.13.23
#
# КОНТЕКСТ (результат диагностики):
#   ТЗ утверждало, что POST /api/findings/{id}/reveal пишет в audit_logs
#   user = "dcap" вместо реального пользователя. Баг НЕ подтвердился:
#   INSERT в PostgreSQL содержит корректное значение ('auditor'), см. отчёт
#   day_48.1_bug087_audit_user_report.md.
#
#   Причина ложного срабатывания: в диагностическом SQL колонка `user`
#   была указана БЕЗ кавычек. В PostgreSQL `user` — зарезервированный
#   keyword (синоним CURRENT_USER), поэтому `SELECT user FROM audit_logs`
#   возвращает имя роли БД ("dcap"), а не значение колонки.
#   Правильно: SELECT "user" FROM audit_logs.
#
# Тесты ниже — регрессионная защита: audit_logs.user обязан содержать
# реального пользователя (reveal / export / fragment), и колонка должна
# называться `user` (иначе сломается и SQL, и модели).
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manager.src.auth.dependencies import get_current_user
from manager.src.db import models
from manager.src.db.session import get_db
from manager.src.api import findings as findings_api

pytestmark = [pytest.mark.unit]


class _FakeUser(SimpleNamespace):
    def has_role(self, name):
        return any(r.name == name for r in self.roles)


def _user(role="auditor", username=None):
    return _FakeUser(
        id=35,
        username=username or ("test_" + role),
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


def _make_client(db_session, user):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.include_router(findings_api.router)
    return TestClient(app)


@pytest.fixture()
def finding(db_session):
    res = models.Resource(path="C:/data", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)

    f = models.Finding(
        resource_id=res.id,
        finding_type="pii",
        category="email",
        severity="medium",
        status="new",
        detector="presidio",
        fragment_type="text_line",
        match_text_masked="a***@b.ru",
        line_text_masked="mail: a***@b.ru",
        fragment_path="C:/data/emails.txt",
        fingerprint="fp-audit-user-1",
        encryption_key_id="test-key-id",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


def _last(db, event_type):
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.event_type == event_type)
        .order_by(models.AuditLog.id.desc())
        .first()
    )


class TestRevealAuditUser:
    def test_reveal_audit_user_is_actual_user(self, db_session, finding):
        """Reveal под auditor → audit_logs.user == 'test_auditor'."""
        client = _make_client(db_session, _user("auditor", username="test_auditor"))

        r = client.post(f"/api/findings/{finding.id}/reveal")
        assert r.status_code == 200, r.text
        assert r.json()["revealed_by"] == "test_auditor"

        log = _last(db_session, "finding_reveal")
        assert log is not None, "аудит reveal не записан"
        assert log.user == "test_auditor", (
            f"audit_logs.user={log.user!r} — должен совпадать с revealed_by"
        )
        assert log.event_source == "api"
        assert log.metadata_json["finding_id"] == finding.id

    def test_reveal_audit_user_not_dcap(self, db_session, finding):
        """Regression: user НЕ должен быть 'dcap' (имя роли БД)."""
        client = _make_client(db_session, _user("admin", username="test_admin"))

        r = client.post(f"/api/findings/{finding.id}/reveal")
        assert r.status_code == 200, r.text

        log = _last(db_session, "finding_reveal")
        assert log is not None
        assert log.user != "dcap", "audit_logs.user = 'dcap' — это CURRENT_USER, не пользователь"
        assert log.user == r.json()["revealed_by"]

    def test_reveal_admin_and_auditor_differ(self, db_session, finding):
        """Разные пользователи → разные значения в аудите (нет общей подмены)."""
        for role in ("admin", "auditor"):
            client = _make_client(db_session, _user(role, username="test_" + role))
            assert client.post(f"/api/findings/{finding.id}/reveal").status_code == 200

        users = [
            row[0]
            for row in db_session.query(models.AuditLog.user)
            .filter(models.AuditLog.event_type == "finding_reveal")
            .all()
        ]
        assert users == ["test_admin", "test_auditor"]


class TestOtherAuditEvents:
    def test_export_audit_user_is_actual_user(self, db_session, finding):
        """findings_exported — тот же путь, user реальный."""
        client = _make_client(db_session, _user("auditor", username="test_auditor"))

        r = client.get("/api/findings/export?format=csv")
        assert r.status_code == 200, r.text

        log = _last(db_session, "findings_exported")
        assert log is not None
        assert log.user == "test_auditor"

    def test_fragment_audit_user_is_actual_user(self, db_session, finding):
        """fragment_accessed — user реальный (BACKLOG-086: встроенный фрагмент)."""
        client = _make_client(db_session, _user("auditor", username="test_auditor"))

        finding.fragment_type = "image_region"
        finding.fragment_data = b"\x89PNG\r\n\x1a\n" + b"0" * 32
        db_session.commit()

        r = client.get(f"/api/findings/{finding.id}/fragment/hash")
        assert r.status_code == 200, r.text

        log = _last(db_session, "fragment_accessed")
        assert log is not None
        assert log.user == "test_auditor"
        assert log.metadata_json["mode"] == "hash"


class TestColumnNaming:
    def test_audit_log_user_column_name(self):
        """Колонка называется `user` — в SQL её нужно брать в кавычки.

        Регрессия на переименование: иначе диагностика снова начнёт
        показывать CURRENT_USER вместо значения.
        """
        col = models.AuditLog.__table__.c["user"]
        assert col.name == "user"
        assert "user" in models.AuditLog.__table__.c

    def test_audit_log_user_has_no_python_default(self):
        """Нет Python-side default: значение приходит из user.username."""
        col = models.AuditLog.__table__.c["user"]
        assert col.default is None
        assert col.nullable is True
