# tests/unit/test_fp_file_path_v31326.py — Блок 5, BUG-098 (v3.13.26)
#
# КОНТЕКСТ (баг реальный, найден live 29.09.2026 на v3.13.25):
#   Одна и та же находка (id=1523) отдавалась по-разному:
#
#     GET /api/findings?task_id=41&status=false_positive
#       -> file_path = C:\test\scanner_clean\pii\phones_clean.txt   ✅ (файл)
#     GET /api/findings/false-positives
#       -> file_path = C:\test\scanner_clean                        🐛 (директория)
#
#   Причина (строка 256 list_false_positives):
#       "file_path": res_map.get(f.resource_id) or f.fragment_path
#   Приоритет был отдан res_map, а res_map[r.id] = r.path — это путь
#   РЕСУРСА (сканируемая директория), а не файл с находкой.
#   В list_findings/_finding_to_response путь фрагмента приоритетнее:
#       "file_path": finding.fragment_path
#
#   Фикс (v3.13.26): fragment_path первым, res_map — только fallback
#   (на случай находки без fragment_path).
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

# Директория ресурса (как в live-баге) и файл внутри неё.
RESOURCE_DIR = r"C:\test\scanner_clean"
FRAGMENT_FILE = r"C:\test\scanner_clean\pii\phones_clean.txt"


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


def _make_fp(db, *, fragment_path=FRAGMENT_FILE, status="false_positive", category="phone"):
    res = models.Resource(path=RESOURCE_DIR, type="filesystem")
    db.add(res)
    db.commit()
    db.refresh(res)

    f = models.Finding(
        resource_id=res.id,
        finding_type="pii",
        category=category,
        severity="medium",
        status=status,
        detector="presidio",
        fragment_type="text_line",
        match_text_masked="+7***-**-**",
        line_text_masked="phone: +7***-**-**",
        fragment_path=fragment_path,
        reviewed_at=datetime(2026, 9, 29, 18, 57, 17),
        fingerprint=f"fp-file-path-{category}",
        encryption_key_id="test-key-id",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


class TestFalsePositivesFilePath:
    def test_fp_file_path_is_fragment_path(self, db_session, client):
        """file_path = файл, а не директория ресурса (ядро BUG-098)."""
        f = _make_fp(db_session)

        r = client.get("/api/findings/false-positives")
        assert r.status_code == 200, r.text
        items = r.json()
        assert len(items) == 1, items
        assert items[0]["file_path"] == FRAGMENT_FILE, (
            f"file_path={items[0]['file_path']!r} — ожидался путь ФАЙЛА {FRAGMENT_FILE!r}"
        )

    def test_fp_file_path_not_resource_dir(self, db_session, client):
        """Путь ресурса (директория) НЕ должен попадать в file_path."""
        _make_fp(db_session)

        items = client.get("/api/findings/false-positives").json()
        assert items[0]["file_path"] != RESOURCE_DIR, (
            "file_path = директория ресурса — это исходный баг BUG-098"
        )
        assert "\\scanner_clean" in items[0]["file_path"]
        assert "phones_clean.txt" in items[0]["file_path"]

    def test_fp_file_path_matches_main_list(self, db_session, client):
        """Согласованность: /false-positives и /findings дают одинаковый путь."""
        f = _make_fp(db_session)

        fp_path = client.get("/api/findings/false-positives").json()[0]["file_path"]
        main = client.get(
            "/api/findings", params={"status": "false_positive"}
        ).json()

        assert len(main) == 1, main
        assert main[0]["id"] == f.id
        assert main[0]["file_path"] == fp_path, (
            f"расхождение путей: /findings={main[0]['file_path']!r} vs "
            f"/false-positives={fp_path!r}"
        )

    def test_fp_file_path_falls_back_to_resource(self, db_session, client):
        """Без fragment_path отдаём путь ресурса (fallback, не None)."""
        f = _make_fp(db_session, fragment_path=None)

        items = client.get("/api/findings/false-positives").json()
        assert len(items) == 1
        assert items[0]["file_path"] == RESOURCE_DIR, (
            "fallback на путь ресурса не сработал"
        )
        assert items[0]["id"] == f.id

    def test_fp_file_path_equals_fragment_path_helper(self, db_session, client):
        """file_path совпадает с findings_api._finding_to_response['file_path']."""
        f = _make_fp(db_session)

        expected = findings_api._finding_to_response(f)["file_path"]
        items = client.get("/api/findings/false-positives").json()
        assert items[0]["file_path"] == expected == FRAGMENT_FILE

    def test_fp_file_path_multiple_rows(self, db_session, client):
        """У каждой FP свой файл, а не общий путь ресурса."""
        res = models.Resource(path=RESOURCE_DIR, type="filesystem")
        db_session.add(res)
        db_session.commit()
        db_session.refresh(res)

        expected = {}
        for i, name in enumerate(("pii/phones_clean.txt", "pii/emails.txt", "code/secrets.py")):
            f = models.Finding(
                resource_id=res.id,
                finding_type="pii",
                category="phone" if i == 0 else ("email" if i == 1 else "api_key"),
                severity="medium",
                status="false_positive",
                detector="presidio",
                fragment_type="text_line",
                match_text_masked="***",
                line_text_masked="***",
                fragment_path=f"{RESOURCE_DIR}\\{name}",
                reviewed_at=datetime(2026, 9, 29, 18, 57, 17) + timedelta(minutes=i),
                fingerprint=f"fp-multi-{i}",
                encryption_key_id="test-key-id",
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
            db_session.add(f)
            db_session.commit()
            db_session.refresh(f)
            expected[f.id] = f.fragment_path

        items = client.get("/api/findings/false-positives").json()
        assert len(items) == 3, items
        for item in items:
            assert item["file_path"] == expected[item["id"]], (
                f"finding {item['id']}: {item['file_path']!r} != {expected[item['id']]!r}"
            )
        assert all(v not in RESOURCE_DIR for v in (i["file_path"] for i in items))
