# tests/unit/test_fp_pagination_v31326.py — Блок 5, BUG-099 (v3.13.26)
#
# КОНТЕКСТ (баг реальный, найден live 29.09.2026 на v3.13.25):
#   GET /api/findings/false-positives?offset=-1  -> 500
#   GET /api/findings/false-positives?limit=-5   -> 500
#
#   Сравнение: GET /api/findings?offset=-1 -> 200 (там с v3.13.x применён
#   _clamp_int из фикса BUG-084, а в /false-positives остались старые
#   limit: int = Query(100, le=1000) / offset: int = 0).
#
#   Причина: у offset не было ge=0, а у limit не было ge=1 — отрицательные
#   значения доходили до .offset(-1) / .limit(-5), и PostgreSQL возвращал
#   ошибку «OFFSET must not be negative» -> 500.
#
#   Фикс (v3.13.26): OptInt + _clamp_int(limit, 100, 1, 1000) и
#   _clamp_int(offset, 0, 0, 10_000_000) — как в list_findings.
#
# Тесты ниже — регрессионная защита: отрицательные/нулевые/слишком большие
#   значения схлопываются в дефолт, валидная пагинация продолжает работать.
import sys
from datetime import datetime, timedelta
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
def client(db_session):
    return _make_client(db_session, _user("auditor"))


@pytest.fixture()
def fp_rows(db_session):
    """7 ложных срабатываний — хватает для проверки limit/offset."""
    res = models.Resource(path="C:/data/fp-page", type="filesystem")
    db_session.add(res)
    db_session.commit()
    db_session.refresh(res)

    rows = []
    for i in range(7):
        f = models.Finding(
            resource_id=res.id,
            finding_type="pii",
            category="email",
            severity="medium",
            status="false_positive",
            detector="presidio",
            fragment_type="text_line",
            match_text_masked="a***@b.ru",
            line_text_masked="mail: a***@b.ru",
            fragment_path=f"C:/data/fp-page/mail-{i}.txt",
            reviewed_by=None,
            # разный reviewed_at, чтобы порядок был детерминированным
            reviewed_at=datetime(2026, 9, 1, 10, 0, 0) + timedelta(minutes=i),
            fingerprint=f"fp-fp-page-{i}",
            encryption_key_id="test-key-id",
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        db_session.add(f)
        rows.append(f)
    db_session.commit()
    for f in rows:
        db_session.refresh(f)
    return rows


class TestFalsePositivesPagination:
    def test_fp_offset_negative_200(self, client, fp_rows):
        """?offset=-1 -> 200 (раньше 500), схлопывается в 0."""
        r = client.get("/api/findings/false-positives", params={"offset": -1})
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert len(r.json()) == 7, "offset=-1 должен трактоваться как offset=0"

    def test_fp_limit_negative_200(self, client, fp_rows):
        """?limit=-5 -> 200 (раньше 500).

        Семантика clamp — как в list_findings: _clamp_int(limit, 100, 1, 1000)
        поднимает отрицательное значение к нижней границе lo=1, поэтому
        отдаётся 1 запись (а не 500 и не пустой список).
        """
        r = client.get("/api/findings/false-positives", params={"limit": -5})
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert len(r.json()) == 1, "limit=-5 должен схлопнуться в lo=1"

    def test_fp_limit_zero_200(self, client, fp_rows):
        """?limit=0 -> 200 и выборка из 1 записи (lo=1, а не пустой список)."""
        r = client.get("/api/findings/false-positives", params={"limit": 0})
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert len(r.json()) == 1, "limit=0 должен схлопнуться в lo=1, а не в пустую выборку"

    def test_fp_limit_too_large_200(self, client, fp_rows):
        """?limit=99999 -> 200, ограничение 1000."""
        r = client.get("/api/findings/false-positives", params={"limit": 99999})
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert len(r.json()) == 7

    def test_fp_valid_pagination(self, client, fp_rows):
        """Валидные limit/offset работают как раньше: limit=3, offset=2."""
        r = client.get(
            "/api/findings/false-positives", params={"limit": 3, "offset": 2}
        )
        assert r.status_code == 200, r.text
        items = r.json()
        assert len(items) == 3, f"ожидалось 3 записи, получено {len(items)}"

        all_ids = [x.id for x in fp_rows]
        assert not set(x["id"] for x in items) & set(all_ids[:2]), (
            "offset=2 не должен возвращать первые 2 записи"
        )

    def test_fp_offset_beyond_end_returns_empty(self, client, fp_rows):
        """offset за концом выборки -> пустой список, но 200."""
        r = client.get("/api/findings/false-positives", params={"offset": 100})
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_fp_empty_and_negative_params_200(self, client):
        """Нет FP + отрицательные параметры -> 200 и пустой список."""
        r = client.get(
            "/api/findings/false-positives", params={"limit": -1, "offset": -1}
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert r.json() == []

    def test_fp_blank_params_200(self, client, fp_rows):
        """Пустые ?limit=&offset= -> дефолт (BUG-090, _blank_to_none)."""
        r = client.get(
            "/api/findings/false-positives?limit=&offset=",
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert len(r.json()) == 7
