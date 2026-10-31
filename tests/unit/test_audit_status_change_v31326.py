# tests/unit/test_audit_status_change_v31326.py — Блок 5, BUG-101 (v3.13.26)
#
# КОНТЕКСТ (баг реальный, найден live 29.09.2026 на v3.13.25):
#   Смена статуса находки (PATCH /api/findings/{id} и POST /api/findings/bulk)
#   НЕ писалась в audit_logs. Диагностический запрос за 30 минут показал
#   0 записей finding_confirmed / finding_false_positive / finding_updated —
#   только auth_login (3 шт.), при том что PATCH/bulk были вызваны 10+ раз.
#
#   Сравнение подтвердило, что аудит в этом модуле работает:
#     POST /{id}/reveal            -> finding_reveal       ✅
#     GET  /{id}/fragment          -> fragment_accessed    ✅
#     GET  /findings/export        -> findings_exported    ✅
#     PATCH /{id}                  -> (пусто)              🐛
#     POST /bulk                   -> (пусто)              🐛
#
#   Причина: в update_finding и bulk_update не было вызова AuditLog —
#   статус менялся и коммитился молча.
#
#   Фикс (v3.13.26): хелпер _log_finding_status_change() с маппингом
#   статуса на event_type (confirmed -> finding_confirmed, new -> finding_reset),
#   вызов в PATCH (via='patch') и в bulk (via='bulk', по записи на находку).
#   Записи копятся без коммита и пишутся одним коммитом вызывающего кода.
#
# Тесты ниже — регрессионная защита: 4 статуса через PATCH, bulk (N записей),
#   метаданные old/new status, различение via и реальный пользователь.
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
    res = models.Resource(path="C:/data/audit-status", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    return res


@pytest.fixture()
def client(db_session):
    return _make_client(db_session, _user("auditor", username="test_auditor"))


def _make_finding(db, resource, *, category="email", status="new", suffix="1"):
    f = models.Finding(
        resource_id=resource.id,
        finding_type="pii",
        category=category,
        severity="medium",
        status=status,
        detector="presidio",
        fragment_type="text_line",
        match_text_masked="a***@b.ru",
        line_text_masked="mail: a***@b.ru",
        fragment_path=f"C:/data/audit-status/{category}-{suffix}.txt",
        fingerprint=f"fp-audit-status-{category}-{suffix}",
        encryption_key_id="test-key-id",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def _status_logs(db):
    """Все записи аудита смены статуса, по возрастанию id."""
    types = (
        "finding_confirmed",
        "finding_false_positive",
        "finding_archived",
        "finding_reset",
        "finding_updated",
        "finding_deleted",
    )
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.event_type.in_(types))
        .order_by(models.AuditLog.id)
        .all()
    )


class TestPatchStatusAudit:
    def test_patch_confirmed_writes_audit(self, db_session, resource, client):
        """new -> confirmed пишет finding_confirmed."""
        f = _make_finding(db_session, resource, status="new")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "confirmed"})
        assert r.status_code == 200, r.text

        logs = _status_logs(db_session)
        assert len(logs) == 1, f"ожидалась 1 запись аудита, получено {len(logs)}"
        assert logs[0].event_type == "finding_confirmed"
        assert logs[0].event_source == "api"

    def test_patch_false_positive_writes_audit(self, db_session, resource, client):
        """new -> false_positive пишет finding_false_positive."""
        f = _make_finding(db_session, resource, status="new")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "false_positive"})
        assert r.status_code == 200, r.text

        logs = _status_logs(db_session)
        assert len(logs) == 1
        assert logs[0].event_type == "finding_false_positive"

    def test_patch_archived_writes_audit(self, db_session, resource, client):
        """confirmed -> archived пишет finding_archived."""
        f = _make_finding(db_session, resource, status="confirmed")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "archived"})
        assert r.status_code == 200, r.text

        logs = _status_logs(db_session)
        assert len(logs) == 1
        assert logs[0].event_type == "finding_archived"

    def test_patch_new_reset_writes_audit(self, db_session, resource, client):
        """Сброс в new пишет finding_reset (не finding_new)."""
        f = _make_finding(db_session, resource, status="false_positive")

        r = client.patch(f"/api/findings/{f.id}", json={"status": "new"})
        assert r.status_code == 200, r.text

        logs = _status_logs(db_session)
        assert len(logs) == 1
        assert logs[0].event_type == "finding_reset"

    def test_patch_audit_metadata_has_old_new_status(self, db_session, resource, client):
        """metadata: old_status, new_status, comment, finding_id."""
        f = _make_finding(db_session, resource, status="new")

        r = client.patch(
            f"/api/findings/{f.id}",
            json={"status": "false_positive", "comment": "шаблон не PII"},
        )
        assert r.status_code == 200, r.text

        log = _status_logs(db_session)[0]
        meta = log.metadata_json
        assert meta["old_status"] == "new", meta
        assert meta["new_status"] == "false_positive", meta
        assert meta["comment"] == "шаблон не PII", meta
        assert meta["finding_id"] == f.id
        assert meta["action"] == "status_changed"
        assert meta["category"] == f.category
        assert meta["finding_type"] == f.finding_type
        assert log.file_path == f.fragment_path

    def test_patch_audit_sequence_of_changes(self, db_session, resource, client):
        """Несколько PATCH подряд — запись на каждое, old_status сквозной."""
        f = _make_finding(db_session, resource, status="new")

        for status in ("confirmed", "false_positive", "new"):
            r = client.patch(f"/api/findings/{f.id}", json={"status": status})
            assert r.status_code == 200, r.text

        logs = _status_logs(db_session)
        assert [x.event_type for x in logs] == [
            "finding_confirmed",
            "finding_false_positive",
            "finding_reset",
        ]
        assert [x.metadata_json["old_status"] for x in logs] == [
            "new",
            "confirmed",
            "false_positive",
        ]

    def test_patch_failed_404_writes_no_audit(self, db_session, client):
        """404 не должен оставлять записей аудита."""
        r = client.patch("/api/findings/999999", json={"status": "confirmed"})
        assert r.status_code == 404, r.text
        assert _status_logs(db_session) == []


class TestBulkStatusAudit:
    def test_bulk_confirmed_writes_audit_per_finding(self, db_session, resource, client):
        """Вариант A из ТЗ: по одной записи на каждую находку."""
        findings = [
            _make_finding(db_session, resource, category="email", suffix=str(i))
            for i in range(4)
        ]

        r = client.post(
            "/api/findings/bulk",
            json={"finding_ids": [f.id for f in findings], "status": "confirmed"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["updated"] == 4

        logs = _status_logs(db_session)
        assert len(logs) == 4, f"ожидалось 4 записи, получено {len(logs)}"
        assert all(x.event_type == "finding_confirmed" for x in logs)
        assert sorted(x.metadata_json["finding_id"] for x in logs) == sorted(
            f.id for f in findings
        )

    def test_bulk_false_positive_writes_audit(self, db_session, resource, client):
        """Тот же путь для false_positive."""
        findings = [
            _make_finding(db_session, resource, category="phone", suffix=str(i))
            for i in range(3)
        ]

        r = client.post(
            "/api/findings/bulk",
            json={
                "finding_ids": [f.id for f in findings],
                "status": "false_positive",
                "comment": "служебный",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["updated"] == 3

        logs = _status_logs(db_session)
        assert len(logs) == 3
        assert all(x.event_type == "finding_false_positive" for x in logs)
        assert all(x.metadata_json["new_status"] == "false_positive" for x in logs)
        assert all(x.metadata_json["comment"] == "служебный" for x in logs)

    def test_bulk_new_writes_audit_per_finding(self, db_session, resource, client):
        """Сброс в new через bulk пишет finding_reset."""
        findings = [
            _make_finding(db_session, resource, status="false_positive", suffix=str(i))
            for i in range(2)
        ]

        r = client.post(
            "/api/findings/bulk",
            json={"finding_ids": [f.id for f in findings], "status": "new"},
        )
        assert r.status_code == 200, r.text

        logs = _status_logs(db_session)
        assert len(logs) == 2
        assert all(x.event_type == "finding_reset" for x in logs)
        assert all(x.metadata_json["old_status"] == "false_positive" for x in logs)

    def test_bulk_missing_ids_skipped_and_logged(self, db_session, resource, client):
        """Отсутствующие id — skipped, аудит только по реальным находкам."""
        f = _make_finding(db_session, resource, suffix="only")

        r = client.post(
            "/api/findings/bulk",
            json={"finding_ids": [f.id, 999999], "status": "confirmed"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["updated"] == 1
        assert body["skipped"] == 1
        assert any("999999" in e for e in body["errors"])

        logs = _status_logs(db_session)
        assert len(logs) == 1
        assert logs[0].metadata_json["finding_id"] == f.id

    def test_bulk_audit_metadata_via_patch_vs_bulk(self, db_session, resource):
        """via различает источник: 'patch' для PATCH, 'bulk' для POST /bulk."""
        f_patch = _make_finding(db_session, resource, category="email", suffix="p")
        f_bulk = _make_finding(db_session, resource, category="email", suffix="b")

        c1 = _make_client(db_session, _user("auditor", username="patcher"))
        assert c1.patch(
            f"/api/findings/{f_patch.id}", json={"status": "confirmed"}
        ).status_code == 200

        c2 = _make_client(db_session, _user("auditor", username="bulker"))
        assert c2.post(
            "/api/findings/bulk",
            json={"finding_ids": [f_bulk.id], "status": "confirmed"},
        ).status_code == 200

        logs = {x.metadata_json["finding_id"]: x for x in _status_logs(db_session)}
        assert logs[f_patch.id].metadata_json["via"] == "patch"
        assert logs[f_bulk.id].metadata_json["via"] == "bulk"

    def test_audit_user_is_current_user(self, db_session, resource):
        """audit_logs.user = текущий пользователь, а не 'dcap'/система."""
        f = _make_finding(db_session, resource, suffix="user")

        client = _make_client(db_session, _user("auditor", username="reviewer_a"))
        assert client.patch(
            f"/api/findings/{f.id}", json={"status": "confirmed"}
        ).status_code == 200

        log = _status_logs(db_session)[0]
        assert log.user == "reviewer_a", f"audit_logs.user={log.user!r}"

    def test_audit_user_differs_per_request(self, db_session, resource):
        """Два разных пользователя → две записи с разными user."""
        f = _make_finding(db_session, resource, suffix="multi")

        for name in ("alice", "bob"):
            c = _make_client(db_session, _user("auditor", username=name))
            assert c.patch(
                f"/api/findings/{f.id}", json={"status": "confirmed"}
            ).status_code == 200

        assert [x.user for x in _status_logs(db_session)] == ["alice", "bob"]

    def test_bulk_audit_persisted_single_transaction(self, db_session, resource, client):
        """Все записи bulk попадают в БД (единый commit в конце)."""
        findings = [
            _make_finding(db_session, resource, category="inn", suffix=str(i))
            for i in range(5)
        ]

        r = client.post(
            "/api/findings/bulk",
            json={"finding_ids": [f.id for f in findings], "status": "archived"},
        )
        assert r.status_code == 200, r.text

        # Новая сессия читает из БД — записи не зависят от кэша сессии.
        engine = db_session.get_bind()
        verify = sessionmaker(bind=engine)()
        try:
            count = (
                verify.query(models.AuditLog)
                .filter(models.AuditLog.event_type == "finding_archived")
                .count()
            )
            assert count == 5, f"в БД {count} записей, ожидалось 5"
        finally:
            verify.close()


class TestDeleteAudit:
    """Открытый вопрос ТЗ: «что с DELETE findings? Тоже не пишется?»

    Ответ: не писался. Удаление — изменение данных, поэтому в v3.13.26
    добавлена запись finding_deleted (в том же коммите, что и сам DELETE).
    """

    def test_delete_writes_audit(self, db_session, resource):
        """DELETE /{id} -> finding_deleted с old_status и путём фрагмента."""
        f = _make_finding(db_session, resource, status="false_positive", suffix="del")
        admin = _make_client(db_session, _user("admin", username="deleter"))

        r = admin.delete(f"/api/findings/{f.id}")
        assert r.status_code == 200, r.text
        assert r.json() == {"deleted": f.id}

        logs = _status_logs(db_session)
        assert len(logs) == 1, f"ожидалась 1 запись аудита, получено {len(logs)}"
        log = logs[0]
        assert log.event_type == "finding_deleted"
        assert log.user == "deleter"
        assert log.event_source == "api"
        assert log.file_path == f.fragment_path
        assert log.metadata_json["finding_id"] == f.id
        assert log.metadata_json["old_status"] == "false_positive"
        assert log.metadata_json["via"] == "delete"

    def test_delete_audit_survives_row_removal(self, db_session, resource):
        """После удаления находки запись аудита остаётся в БД."""
        f = _make_finding(db_session, resource, suffix="gone")
        admin = _make_client(db_session, _user("admin", username="deleter"))

        assert admin.delete(f"/api/findings/{f.id}").status_code == 200

        # Находки больше нет
        assert db_session.query(models.Finding).filter(
            models.Finding.id == f.id
        ).first() is None

        engine = db_session.get_bind()
        verify = sessionmaker(bind=engine)()
        try:
            log = (
                verify.query(models.AuditLog)
                .filter(models.AuditLog.event_type == "finding_deleted")
                .first()
            )
            assert log is not None, "аудит удаления не сохранился"
            assert log.metadata_json["finding_id"] == f.id
        finally:
            verify.close()

    def test_delete_404_writes_no_audit(self, db_session):
        """DELETE несуществующей находки -> 404 и без записи аудита."""
        admin = _make_client(db_session, _user("admin", username="deleter"))

        r = admin.delete("/api/findings/999999")
        assert r.status_code == 404, r.text
        assert _status_logs(db_session) == []
