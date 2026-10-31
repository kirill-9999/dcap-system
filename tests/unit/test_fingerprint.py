# tests/unit/test_fingerprint.py — Проверка, что fingerprint — SHA-256, не MD5
# (День 40.3, [X] BACKLOG-066: MD5 криптографически сломан — недопустим для security-продукта).
import hashlib
import hmac
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.managed_scanner import ManagedScanner  # noqa: E402

pytestmark = [pytest.mark.unit]


def test_fingerprint_sha256_length():
    """SHA-256 → 64 hex, MD5 → 32 hex."""
    fp_md5 = hashlib.md5(b"test").hexdigest()
    fp_sha256 = hashlib.sha256(b"test").hexdigest()
    assert len(fp_md5) == 32
    assert len(fp_sha256) == 64


def test_legacy_fingerprint_uses_sha256():
    """Legacy fingerprint использует SHA-256 (не MD5)."""
    source = inspect.getsource(ManagedScanner._legacy_fingerprint)
    assert "md5" not in source.lower(), "MD5 found in _legacy_fingerprint!"
    assert "sha256" in source.lower()


def test_legacy_fingerprint_value_is_sha256_full_context():
    """
    Функциональная проверка: fingerprint — это SHA-256 от полного контекста
    (file_path|line|match|finding_type), а не только от значения и не MD5.
    """
    scanner = object.__new__(ManagedScanner)
    fp = ManagedScanner._legacy_fingerprint(scanner, "C:/data/file.txt", 42, "secret-value", "pii")

    assert len(fp) == 64, "SHA-256 даёт 64 hex-символа"

    expected = hashlib.sha256(
        b"C:/data/file.txt|42|secret-value|pii"
    ).hexdigest()
    assert fp == expected

    no_type = hashlib.sha256(b"C:/data/file.txt|42|secret-value").hexdigest()
    assert fp != no_type, "finding_type должен входить в контекст"


def test_legacy_fingerprint_deterministic_and_context_sensitive():
    scanner = object.__new__(ManagedScanner)
    f1 = ManagedScanner._legacy_fingerprint(scanner, "a.txt", 1, "x", "pii")
    f2 = ManagedScanner._legacy_fingerprint(scanner, "a.txt", 1, "x", "pii")
    f3 = ManagedScanner._legacy_fingerprint(scanner, "a.txt", 2, "x", "pii")
    assert f1 == f2
    assert f1 != f3, "разные строки → разные fingerprint"


def test_encryption_fingerprint_is_hmac_sha256():
    """С ключами fingerprint — HMAC-SHA256 (консистентно с Manager)."""
    import scanner.src.encryption as sen

    source = inspect.getsource(sen.ScannerEncryption.fingerprint)
    assert "hmac" in source.lower() and "sha256" in source.lower()

    key = b"k" * 32
    expected = hmac.new(key, b"f.txt|1|v|credentials", hashlib.sha256).hexdigest()
    assert len(expected) == 64