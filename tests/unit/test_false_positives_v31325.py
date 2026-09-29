# tests/unit/test_false_positives_v31325.py — BUG-096 (TASK-064, v3.13.25)
#
# КОНТЕКСТ (баг реальный, воспроизведён live 27.09.2026):
#   GET /api/findings/false-positives падал с 500, КАК ТОЛЬКО в БД появлялась
#   хотя бы одна запись со status=false_positive:
#
#     File "manager/src/api/findings.py", line 324, in list_false_positives
#       for u in db.query(_m.User).filter(_m.User.id.in_(...)).all():
#     AttributeError: module 'manager.src.db.models' has no attribute 'User'
#
#   Причина: ORM-модель User определена в manager.src.auth.models, а не в
#   manager.src.db.models. Цикл обогащения reviewed_by_username выполняется
#   только при FP > 0 — поэтому на пустом списке эндпоинт отвечал 200, и баг
#   не проявлялся в тестах.
#
#   Фикс (v3.13.25): в findings.py импортированы Finding, Resource из
#   manager.src.db.models и User из manager.src.auth.models (уже был импорт),
#   локальный алиас `from manager.src.db import models as _m` удалён.
#
# Тесты ниже — регрессионная защита:
#   1. FP > 0 → 200 (раньше 500) и reviewed_by_username заполнен;
#   2. FP = 0 → 200, пустой список (цикл не выполняется);
#   3. reviewed_by_username корректен для нескольких ревьюеров + file_path.
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
    res = models.Resource(path="C:/data/fp-demo", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)
    return res


@pytest.fixture()
def reviewer(db_session):
    """Реальная строка users: нужна, чтобы reviewed_by_username заполнился."""
    return _add_reviewer(db_session, 35, "test_auditor")


def _add_reviewer(db, uid, username):
    from manager.src.auth.models import User as AuthUser

    u = AuthUser(id=uid, username=username, auth_source="local", is_active=True)
    u.set_password("user123")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_finding(db, resource, *, category="email", status="new", fingerprint=None):
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
        fragment_path="C:/data/fp-demo/emails.txt",
        fingerprint=fingerprint or f"fp-fp-demo-{category}-{status}",
        encryption_key_id="test-key-id",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def _mark_false_positive(db, finding, reviewer_id, comment=None):
    """Эмулирует PATCH /api/findings/{id} {"status": "false_positive"}."""
    finding.status = "false_positive"
    finding.comment = comment
    finding.reviewed_by = reviewer_id
    finding.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(finding)
    return finding


class TestFalsePositives:
    def test_false_positives_empty(self, db_session):
        """FP = 0 → 200, пустой список (цикл обогащения не выполняется)."""
        client = _make_client(db_session, _user("auditor"))
        r = client.get("/api/findings/false-positives")
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_false_positives_with_data(self, db_session, resource, reviewer):
        """FP > 0 → 200 (ранее 500: AttributeError _m.User)."""
        finding = _make_finding(db_session, resource, category="email")
        _mark_false_positive(db_session, finding, reviewer_id=reviewer.id)

        client = _make_client(db_session, _user("auditor", uid=reviewer.id))
        r = client.get("/api/findings/false-positives")

        assert r.status_code == 200, f"ожидался 200, получено {r.status_code}: {r.text}"
        items = r.json()
        assert len(items) == 1, f"ожидалась 1 запись FP, получено {len(items)}"
        assert items[0]["id"] == finding.id
        assert items[0]["category"] == "email"
        assert items[0]["finding_type"] == "pii"
        assert items[0]["reviewed_by"] == reviewer.id
        assert items[0]["reviewed_by_username"] == "test_auditor"
        assert items[0]["reviewed_at"] is not None

    def test_false_positives_reviewed_by_username(self, db_session, resource, reviewer):
        """reviewed_by_username = username ревьюера из auth.models.User."""
        f1 = _make_finding(db_session, resource, category="email")
        _mark_false_positive(db_session, f1, reviewer_id=reviewer.id, comment="не PII")
        f2 = _make_finding(db_session, resource, category="phone")
        _mark_false_positive(db_session, f2, reviewer_id=reviewer.id, comment="служебный")

        client = _make_client(db_session, _user("auditor", uid=reviewer.id))
        r = client.get("/api/findings/false-positives")
        assert r.status_code == 200, r.text

        by_id = {item["id"]: item for item in r.json()}
        assert by_id[f1.id]["reviewed_by_username"] == "test_auditor"
        assert by_id[f1.id]["comment"] == "не PII"
        assert by_id[f2.id]["reviewed_by_username"] == "test_auditor"
        assert by_id[f2.id]["comment"] == "служебный"
        # BUG-098 (v3.13.26): file_path = fragment_path (файл), а не путь
        # ресурса (директория) — раньше здесь ожидалось "C:/data/fp-demo".
        assert by_id[f1.id]["file_path"] == "C:/data/fp-demo/emails.txt"
        assert by_id[f1.id]["category"] == "email"

    def test_false_positives_admin_reviewer(self, db_session, resource, reviewer):
        """Тот же путь для admin-ревьюера (роль admin тоже допущена)."""
        f = _make_finding(db_session, resource, category="aws_key")
        _mark_false_positive(db_session, f, reviewer_id=reviewer.id)

        client = _make_client(db_session, _user("admin", username="test_admin", uid=reviewer.id))
        r = client.get("/api/findings/false-positives")
        assert r.status_code == 200, r.text
        assert r.json()[0]["reviewed_by_username"] == "test_auditor"

    def test_false_positives_deleted_reviewer(self, db_session, resource):
        """Ревьюер удалён из users → 200 и reviewed_by_username = None (не 500)."""
        f = _make_finding(db_session, resource, category="inn")
        _mark_false_positive(db_session, f, reviewer_id=999)

        client = _make_client(db_session, _user("auditor"))
        r = client.get("/api/findings/false-positives")
        assert r.status_code == 200, r.text
        assert r.json()[0]["reviewed_by_username"] is None


class TestNoDbModelsUserRegression:
    def test_db_models_has_no_user_attribute(self):
        """Регрессия на сам баг: User обязан отсутствовать в db.models.

        Если кто-то снова добавит обращение к models.User в findings.py,
        этот тест напомнит, что модель живёт в manager.src.auth.models.
        """
        assert not hasattr(models, "User"), (
            "manager.src.db.models.User не существует — "
            "используйте manager.src.auth.models.User"
        )

    def test_findings_module_resolves_correct_models(self):
        """findings.py обязан использовать auth.models.User и db.models.Resource."""
        assert findings_api.User.__module__ == "manager.src.auth.models"
        assert findings_api.Resource is models.Resource
        assert findings_api.Finding is models.Finding

    def test_list_false_positives_source_has_no_db_models_user(self):
        """Статическая проверка кода эндпоинта: нет обращения к models.User.

        Комментарии и строковые литералы отбрасываются через tokenize, чтобы
        проверка не ловила служебные упоминания модели в описаниях.
        """
        import io
        import re
        import tokenize

        src = Path(findings_api.__file__).read_text(encoding="utf-8")
        code = []
        with io.StringIO(src) as fh:
            for tok in tokenize.generate_tokens(fh.readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                code.append(tok.string)
        code_src = " ".join(code)

        pattern = r"(?:^|[^\w.])(?:_m|models)\s*\.\s*User\b"
        assert re.search(pattern, code_src) is None, (
            "в findings.py осталось обращение к <models>.User (BUG-096)"
        )
