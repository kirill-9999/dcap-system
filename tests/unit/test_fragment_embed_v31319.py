# tests/unit/test_fragment_embed_v31319.py
"""BACKLOG-086 (TASK-045..049, v3.13.19): встроенные OCR-фрагменты.

Сканер встраивает PNG в payload (fragment_base64) → Manager хранит байты
в findings.fragment_data → /fragment отдаёт из БД (неизменяемое доказательство).
"""
import base64
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

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

from manager.src.db import models  # noqa: E402
from manager.src.db.session import get_db  # noqa: E402
from manager.src.auth.manager import AuthManager  # noqa: E402
from manager.src.auth.middleware import AuthMiddleware  # noqa: E402
from manager.src.auth.models import User, Role  # noqa: E402
from manager.src.api import scanner as scanner_api  # noqa: E402
from manager.src.api import findings as findings_api  # noqa: E402

pytestmark = [pytest.mark.unit]

SECRET = "test-secret-key-32-chars-long!!"
IMG_BYTES = b"\x89PNG\r\n\x1a\nembedded-fragment-bytes"
FP_IMAGE = "f" + hashlib.sha256(b"image").hexdigest()
FP_TEXT = "f" + hashlib.sha256(b"text").hexdigest()


def _set_keys():
    os.environ["FINDINGS_ENCRYPTION_KEY"] = base64.b64encode(b"k" * 32).decode()
    os.environ["FINDINGS_HMAC_KEY"] = base64.b64encode(b"h" * 64).decode()
    os.environ["FINDINGS_KEY_ID"] = "test-key-1"


@pytest.fixture()
def session(tmp_path):
    _set_keys()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    for name in ("admin", "auditor", "viewer"):
        db.add(Role(name=name, description=name))
    db.commit()

    users = {}
    for name in ("admin", "auditor", "viewer"):
        u = User(username=name, is_active=True)
        u.roles.append(db.query(Role).filter(Role.name == name).first())
        db.add(u)
        users[name] = u
    db.commit()

    res = models.Resource(path=str(tmp_path / "res"), type="filesystem", status="ACTIVE")
    db.add(res)
    db.commit()
    db.refresh(res)

    task = models.ScanTask(
        resource_id=res.id, source_path=str(tmp_path), status="assigned"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    yield db, task.id
    db.close()
    engine.dispose()


@pytest.fixture()
def client(session):
    db, _task_id = session
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: (yield db)

    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": SECRET}})
    app.add_middleware(
        AuthMiddleware,
        auth_manager=am,
        db_session_factory=sessionmaker(
            bind=db.get_bind(), autoflush=False, autocommit=False
        ),
    )
    app.include_router(scanner_api.router)
    app.include_router(findings_api.router)
    return TestClient(app)


def _token(am: AuthManager, user: User) -> str:
    return am.jwt.create_access_token({"user_id": user.id, "username": user.username})


@pytest.fixture()
def tokens(session):
    db, _ = session
    am = AuthManager({"auth": {"mode": "local", "jwt_secret_key": SECRET}})
    return {
        name: {"Authorization": f"Bearer {_token(am, db.query(User).filter(User.username == name).first())}"}
        for name in ("admin", "auditor", "viewer")
    }


def _image_payload():
    return {
        "file_path": "C:/test/scanner_clean/images/screenshot_clean.png",
        "line_number": 1,
        "category": "email",
        "subcategory": "email",
        "finding_type": "pii",
        "value": "(encrypted)",
        "fragment_type": "image_region",
        "detector": "ocr",
        "bounding_box": None,
        "fingerprint": FP_IMAGE,
        "fragment_base64": base64.b64encode(IMG_BYTES).decode("ascii"),
        "fragment_mime": "image/png",
        "fragment_hash": hashlib.sha256(IMG_BYTES).hexdigest(),
        "fragment_size": len(IMG_BYTES),
    }


def _text_payload():
    return {
        "file_path": "C:/test/scanner_clean/notes/roles.txt",
        "line_number": 7,
        "category": "phone",
        "subcategory": "phone",
        "finding_type": "pii",
        "value": "(encrypted)",
        "fragment_type": "text_line",
        "detector": "presidio",
        "fingerprint": FP_TEXT,
    }


class TestFragmentEmbed:
    def test_fragment_saved_from_payload(self, session, client):
        """fragment_base64 → findings.fragment_data (decoded) + hash + size."""
        db, task_id = session
        r = client.post(
            f"/api/scanner/tasks/{task_id}/results",
            json={"findings": [_image_payload()], "stats": {"files_scanned": 1}},
            params={"batch": 1, "total": 1},
        )
        assert r.status_code == 200, r.text
        finding = db.query(models.Finding).filter(models.Finding.fingerprint == FP_IMAGE).first()
        assert finding is not None
        assert finding.fragment_data == IMG_BYTES
        assert finding.fragment_hash == hashlib.sha256(IMG_BYTES).hexdigest()
        assert finding.fragment_size == len(IMG_BYTES)
        assert finding.fragment_mime == "image/png"
        assert finding.fragment_embedded_at is not None

    def test_text_line_fragment_not_embedded(self, session, client):
        """text_line findings — fragment_data = None (не встраиваем)."""
        db, task_id = session
        r = client.post(
            f"/api/scanner/tasks/{task_id}/results",
            json={"findings": [_text_payload()], "stats": {}},
            params={"batch": 1, "total": 1},
        )
        assert r.status_code == 200, r.text
        finding = db.query(models.Finding).filter(models.Finding.fingerprint == FP_TEXT).first()
        assert finding is not None
        assert finding.fragment_type == "text_line"
        assert finding.fragment_data is None
        assert finding.fragment_size is None

    def test_fragment_endpoint_returns_embedded(self, session, client, tokens):
        """GET /fragment → из БД с X-Fragment-Mode: embedded."""
        db, _ = session
        f = models.Finding(
            resource_id=1,
            task_id=1,
            finding_type="pii",
            category="email",
            fragment_type="image_region",
            detector="ocr",
            fragment_path="C:/deleted/source.png",
            fingerprint=FP_IMAGE,
            encryption_key_id="test-key-1",
            fragment_data=IMG_BYTES,
            fragment_mime="image/png",
            fragment_hash=hashlib.sha256(IMG_BYTES).hexdigest(),
            fragment_size=len(IMG_BYTES),
            fragment_embedded_at=datetime.utcnow(),
        )
        db.add(f)
        db.commit()
        db.refresh(f)

        r = client.get(
            f"/api/findings/{f.id}/fragment", headers=tokens["auditor"]
        )
        assert r.status_code == 200
        assert r.headers["X-Fragment-Mode"] == "embedded"
        assert r.headers["X-Fragment-Hash"] == hashlib.sha256(IMG_BYTES).hexdigest()
        assert r.headers["Content-Type"].startswith("image/png")
        assert r.content == IMG_BYTES

    def test_fragment_endpoint_falls_back_to_path(self, session, client, tokens, tmp_path):
        """fragment_data IS NULL + fragment_path есть → full-image."""
        db, _ = session
        png = tmp_path / "screenshot_clean.png"
        png.write_bytes(IMG_BYTES)
        f = models.Finding(
            resource_id=1,
            task_id=1,
            finding_type="pii",
            category="email",
            fragment_type="image_region",
            detector="ocr",
            bounding_box=None,
            fragment_path=str(png),
            fingerprint="f" + hashlib.sha256(b"path").hexdigest(),
            encryption_key_id="test-key-1",
        )
        db.add(f)
        db.commit()
        db.refresh(f)

        r = client.get(
            f"/api/findings/{f.id}/fragment", headers=tokens["auditor"]
        )
        assert r.status_code == 200
        assert r.headers["X-Fragment-Mode"] == "full-image"
        assert r.content == IMG_BYTES

    def test_fragment_endpoint_404_when_nothing(self, session, client, tokens):
        """fragment_data NULL + fragment_path отсутствует → 404."""
        db, _ = session
        f = models.Finding(
            resource_id=1,
            task_id=1,
            finding_type="pii",
            category="email",
            fragment_type="image_region",
            detector="ocr",
            fragment_path="C:/does/not/exist.png",
            fingerprint="f" + hashlib.sha256(b"missing").hexdigest(),
            encryption_key_id="test-key-1",
        )
        db.add(f)
        db.commit()
        db.refresh(f)

        r = client.get(
            f"/api/findings/{f.id}/fragment", headers=tokens["auditor"]
        )
        assert r.status_code == 404

    def test_fragment_endpoint_requires_auditor(self, session, client, tokens):
        """GET /fragment: viewer → 403, auditor → 200."""
        db, _ = session
        f = models.Finding(
            resource_id=1,
            task_id=1,
            finding_type="pii",
            category="email",
            fragment_type="image_region",
            detector="ocr",
            fragment_path="C:/deleted/source.png",
            fingerprint="f" + hashlib.sha256(b"rbac").hexdigest(),
            encryption_key_id="test-key-1",
            fragment_data=IMG_BYTES,
            fragment_mime="image/png",
            fragment_hash=hashlib.sha256(IMG_BYTES).hexdigest(),
            fragment_size=len(IMG_BYTES),
            fragment_embedded_at=datetime.utcnow(),
        )
        db.add(f)
        db.commit()
        db.refresh(f)

        rv = client.get(f"/api/findings/{f.id}/fragment", headers=tokens["viewer"])
        assert rv.status_code == 403

        ra = client.get(f"/api/findings/{f.id}/fragment", headers=tokens["auditor"])
        assert ra.status_code == 200

    def test_fragment_hash_endpoint(self, session, client, tokens):
        """GET /fragment/hash → hash, size, mime, embedded_at."""
        db, _ = session
        f = models.Finding(
            resource_id=1,
            task_id=1,
            finding_type="pii",
            category="email",
            fragment_type="image_region",
            detector="ocr",
            fragment_path="C:/deleted/source.png",
            fingerprint="f" + hashlib.sha256(b"hash").hexdigest(),
            encryption_key_id="test-key-1",
            fragment_data=IMG_BYTES,
            fragment_mime="image/png",
            fragment_hash=hashlib.sha256(IMG_BYTES).hexdigest(),
            fragment_size=len(IMG_BYTES),
            fragment_embedded_at=datetime.utcnow(),
        )
        db.add(f)
        db.commit()
        db.refresh(f)

        r = client.get(
            f"/api/findings/{f.id}/fragment/hash", headers=tokens["auditor"]
        )
        assert r.status_code == 200
        data = r.json()
        assert data["finding_id"] == f.id
        assert data["hash"] == hashlib.sha256(IMG_BYTES).hexdigest()
        assert data["size"] == len(IMG_BYTES)
        assert data["mime"] == "image/png"
        assert data["embedded_at"] is not None

    def test_fragment_access_audited(self, session, client, tokens):
        """GET /fragment → запись в audit_logs (action=fragment_accessed)."""
        db, _ = session
        f = models.Finding(
            resource_id=1,
            task_id=1,
            finding_type="pii",
            category="email",
            fragment_type="image_region",
            detector="ocr",
            fragment_path="C:/deleted/source.png",
            fingerprint="f" + hashlib.sha256(b"audit").hexdigest(),
            encryption_key_id="test-key-1",
            fragment_data=IMG_BYTES,
            fragment_mime="image/png",
            fragment_hash=hashlib.sha256(IMG_BYTES).hexdigest(),
            fragment_size=len(IMG_BYTES),
            fragment_embedded_at=datetime.utcnow(),
        )
        db.add(f)
        db.commit()
        db.refresh(f)

        r = client.get(
            f"/api/findings/{f.id}/fragment", headers=tokens["auditor"]
        )
        assert r.status_code == 200

        logs = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.event_type == "fragment_accessed")
            .order_by(models.AuditLog.id.desc())
            .all()
        )
        assert len(logs) >= 1
        log = logs[0]
        assert log.user == "auditor"
        meta = log.metadata_json or {}
        assert meta.get("action") == "fragment_accessed"
        assert meta.get("finding_id") == f.id
        assert meta.get("mode") == "embedded"