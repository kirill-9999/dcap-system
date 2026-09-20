"""Unit-тесты scripts/reencrypt_findings.py (TASK-016)."""
import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manager.src.auth import models as auth_models  # noqa: E402  (таблица users)
from manager.src.db import models  # noqa: E402
from manager.src.core.encryption import FindingEncryption  # noqa: E402

_script_path = ROOT / "scripts" / "reencrypt_findings.py"
_spec = importlib.util.spec_from_file_location("reencrypt_findings", _script_path)
reenc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reenc)


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def keys():
    old = FindingEncryption(key=b"O" * 32, hmac_key=b"O" * 32, key_id="key-old")
    new = FindingEncryption(key=b"N" * 32, hmac_key=b"N" * 32, key_id="key-new")
    return old, new


def _add_findings(db, count, enc, corrupt=False, key_id_override=None):
    from manager.src.db.models import Finding

    out = []
    for i in range(count):
        enc_key = key_id_override or enc.key_id
        f = Finding(
            resource_id=1,
            finding_type="credentials",
            category="password",
            fragment_type="text_line",
            line_number=i,
            match_text_masked="***",
            match_text_encrypted=("broken" if corrupt else enc.encrypt("ct")),
            fingerprint=f"fp-{i}-{enc_key}",
            encryption_key_id=enc_key,
        )
        db.add(f)
        out.append(f)
    db.commit()
    return out


def test_reencrypt_basic(db_engine, keys):
    """10 находок ключом key-old → расшифровка новым ключом работает."""
    old, new = keys
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        _add_findings(db, 10, old)

    stats = reenc.run_reencrypt(db_engine, old, new, batch_size=3)
    assert stats["total"] == 10
    assert stats["already_new"] == 0
    assert stats["reencrypted"] == 10
    assert stats["skipped"] == 0

    with Session() as db:
        rows = db.query(models.Finding).all()
        assert all(r.encryption_key_id == "key-new" for r in rows)
        for r in rows:
            assert new.decrypt(r.match_text_encrypted) == "ct"


def test_reencrypt_skips_new_key_id(db_engine, keys):
    """Находки уже с новым key_id не трогаются (идемпотентность)."""
    old, new = keys
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        _add_findings(db, 5, new)
        _add_findings(db, 3, old)

    stats = reenc.run_reencrypt(db_engine, old, new, batch_size=2)
    assert stats["total"] == 8
    assert stats["already_new"] == 5
    assert stats["reencrypted"] == 3
    assert stats["skipped"] == 0

    with Session() as db:
        rows = db.query(models.Finding).all()
        assert all(r.encryption_key_id == "key-new" for r in rows)


def test_reencrypt_dry_run(db_engine, keys):
    """dry-run: считает, но не пишет в БД."""
    old, new = keys
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        _add_findings(db, 4, old)

    stats = reenc.run_reencrypt(db_engine, old, new, batch_size=2, dry_run=True)
    assert stats["dry_run"] is True
    assert stats["reencrypted"] == 4

    with Session() as db:
        rows = db.query(models.Finding).all()
        assert all(r.encryption_key_id == "key-old" for r in rows)


def test_reencrypt_error_handling(db_engine, keys):
    """Повреждённый ciphertext (decrypt fail) → skip; остальные перешифрованы."""
    old, new = keys
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        _add_findings(db, 8, old)
        _add_findings(db, 2, old, corrupt=True)

    stats = reenc.run_reencrypt(db_engine, old, new, batch_size=4)
    assert stats["total"] == 10
    assert stats["reencrypted"] == 8
    assert stats["skipped"] == 2
    assert len(stats["skipped_ids"]) == 2

    with Session() as db:
        rows = db.query(models.Finding).all()
        corrupted = [r for r in rows if r.match_text_encrypted == "broken"]
        assert all(r.encryption_key_id == "key-old" for r in corrupted)
        good = [r for r in rows if r.match_text_encrypted != "broken"]
        assert all(r.encryption_key_id == "key-new" for r in good)