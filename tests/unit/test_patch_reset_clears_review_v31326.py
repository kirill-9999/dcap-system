# tests/unit/test_patch_reset_clears_review_v31326.py — Блок 5, BUG-100 (v3.13.26)
#
# КОНТЕКСТ (баг реальный, найден live 29.09.2026 на v3.13.25):
#   PATCH /api/findings/{id} со статусом 'new' (сброс ревью) НЕ очищал
#   поля ревью:
#
#     PATCH {status: false_positive} -> reviewed_by=35, reviewed_at=18:57:17
#     PATCH {status: new}            -> status=new, НО reviewed_by=35,
#                                         reviewed_at=18:58:05
#
#   То есть находка снова «new», но выглядит одобренной последним ревьюером:
#   /api/findings/false-positives сортирует по reviewed_at, а WebUI
#   показывает «кто и когда проверил» из этих полей — данные заведомо
#   неверные.
#
#   Причина: update_finding безусловно ставил reviewed_by=user.id и
#   reviewed_at=utcnow() для любого статуса, включая сброс в 'new'.
#
#   Фикс (v3.13.26): общая функция _apply_status() — при status='new'
#   reviewed_by/reviewed_at очищаются в None, comment берётся из body.
#   Тот же путь использует bulk_update.
#
# Тесты ниже — регрессионная защита: сброс из FP, из confirmed, из archived.
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

from manager.src.api import findings as findings_api
from manager.src.auth.dependencies import get_current_user
from manager.src.db import models
from manager.src.db.session import get_db

pytestmark = [pytest.mark.unit]


class _FakeUser(SimpleNamespace):
    def has_role(self, name):
        return any(r.name == name for r in self.roles)


def _user(role="auditor", username=None, uid=35):
    return _FakeUser(
        id=uid,
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
def resource(db_session):
    res = models.Resource(path="C:/data/reset-review", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    return res


@pytest.fixture()
def client(db_session):
    return _make_client(db_session, _user("auditor", username="test_auditor", uid=35))


def _make_finding(db, resource, *, status="new", reviewed=True, suffix="1"):
    f = models.Finding(
        resource_id=resource.id,
        finding_type="pii",
        category="email",
        severity="medium",
        status=status,
        detector="presidio",
        fragment_type="text_line",
        match_text_masked="a***@b.ru",
        line_text_masked="mail: a***@b.ru",
        fragment_path=f"C:/data/reset-review/mail-{suffix}.txt",
        comment="старое ревью" if reviewed else None,
        reviewed_by=35 if reviewed else None,
        reviewed_at=datetime(2026, 9, 29, 18, 57, 17) if reviewed else None,
        fingerprint=f"fp-reset-review-{suffix}",
        encryption_key_id="test-key-id",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def _reload(db, finding_id):
    """Читает находку заново из БД (проверка, а не только ответ PATCH)."""
    return db.query(models.Finding).filter(models.Finding.id == finding_id).first()


class TestPatchResetClearsReview:
    def test_patch_new_clears_reviewed_by(self, db_session, resource, client):
        """reviewed_by → None после сброса в new."""
        f = _make_finding(db_session, resource, status="false_positive")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "new"})
        assert r.status_code == 200, r.text

        db_finding = _reload(db_session, f.id)
        assert db_finding.status == "new"
        assert db_finding.reviewed_by is None, (
            f"reviewed_by={db_finding.reviewed_by} — должен быть очищен"
        )

    def test_patch_new_clears_reviewed_at(self, db_session, resource, client):
        """reviewed_at → None после сброса в new."""
        f = _make_finding(db_session, resource, status="false_positive")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "new"})
        assert r.status_code == 200, r.text

        db_finding = _reload(db_session, f.id)
        assert db_finding.reviewed_at is None, (
            f"reviewed_at={db_finding.reviewed_at} — должен быть очищен"
        )

    def test_patch_new_sets_comment_from_body(self, db_session, resource, client):
        """comment при сбросе = body.comment (решение ТЗ), а не старое значение."""
        f = _make_finding(db_session, resource, status="false_positive")

        r = client.patch(
            f"/api/findings/{f.id}",
            json={"status": "new", "comment": "вернули в работу"},
        )
        assert r.status_code == 200, r.text

        db_finding = _reload(db_session, f.id)
        assert db_finding.comment == "вернули в работу"

    def test_patch_new_from_fp_clears_all(self, db_session, resource, client):
        """Полный сценарий из ТЗ: false_positive -> new, все поля очищены."""
        f = _make_finding(db_session, resource, status="false_positive")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "new"})
        assert r.status_code == 200, r.text

        db_finding = _reload(db_session, f.id)
        assert db_finding.status == "new"
        assert db_finding.reviewed_by is None
        assert db_finding.reviewed_at is None
        # comment без body.comment — сбрасывается в None
        assert db_finding.comment is None

    def test_patch_new_from_confirmed_clears_all(self, db_session, resource, client):
        """confirmed -> new: тоже чистим ревью (BUG-100)."""
        f = _make_finding(db_session, resource, status="confirmed")

        r = client.patch(
            f"/api/findings/{f.id}", json={"status": "new", "comment": "спорно"}
        )
        assert r.status_code == 200, r.text

        db_finding = _reload(db_session, f.id)
        assert db_finding.status == "new"
        assert db_finding.reviewed_by is None
        assert db_finding.reviewed_at is None
        assert db_finding.comment == "спорно"

    def test_patch_review_status_still_sets_reviewer(self, db_session, resource, client):
        """Регрессия: для confirmed/false_positive/archived ревью НЕ чистится."""
        for status in ("confirmed", "false_positive", "archived"):
            f = _make_finding(db_session, resource, status="new", reviewed=False,
                              suffix=status)

            r = client.patch(f"/api/findings/{f.id}", json={"status": status})
            assert r.status_code == 200, r.text

            db_finding = _reload(db_session, f.id)
            assert db_finding.status == status
            assert db_finding.reviewed_by == 35, f"{status}: reviewed_by не проставлен"
            assert db_finding.reviewed_at is not None, f"{status}: reviewed_at не проставлен"

    def test_bulk_new_clears_review(self, db_session, resource, client):
        """Тот же фикс действует для POST /bulk со статусом new."""
        findings = [
            _make_finding(db_session, resource, status="false_positive", suffix=str(i))
            for i in range(3)
        ]

        r = client.post(
            "/api/findings/bulk",
            json={"finding_ids": [f.id for f in findings], "status": "new"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["updated"] == 3

        for f in findings:
            db_finding = _reload(db_session, f.id)
            assert db_finding.status == "new"
            assert db_finding.reviewed_by is None
            assert db_finding.reviewed_at is None

    def test_patch_response_reports_cleared_review(self, db_session, resource, client):
        """Ответ PATCH тоже отдаёт null (WebUI должен увидеть очистку)."""
        f = _make_finding(db_session, resource, status="false_positive")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "new"})
        assert r.status_code == 200, r.text

        body = r.json()
        assert body["status"] == "new"
        assert body["reviewed_by"] is None
        assert body["reviewed_at"] is None
