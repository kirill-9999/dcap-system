"""BUG-136: decode_text_bytes должен пробовать cp1251 после utf-8 (день 53.2)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scanner.connectors._text_scanner import decode_text_bytes  # noqa: E402


def test_decode_utf8_still_works():
    assert decode_text_bytes("привет мир".encode("utf-8")) == "привет мир"


def test_decode_cp1251_now_works():
    """Регрессия BUG-136: раньше возвращалась пустая строка."""
    result = decode_text_bytes("привет".encode("cp1251"))
    assert result == "привет"


def test_decode_ascii():
    assert decode_text_bytes(b"hello") == "hello"


def test_decode_binary_returns_none():
    assert decode_text_bytes(b"\x00\x01\x02\x03" * 2048) is None


def test_decode_invalid_bytes_falls_back_to_ignore():
    """Если ни utf-8 strict, ни cp1251 strict не подошли — игнорируем."""
    bad = b"\xff\xfe\xfd\xfc"
    result = decode_text_bytes(bad)
    assert isinstance(result, str)  # не падает
