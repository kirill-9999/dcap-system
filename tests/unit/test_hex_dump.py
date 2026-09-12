"""Unit-тесты hex-дампа (День 40.4)."""
import pytest

pytestmark = pytest.mark.unit

from manager.src.core.hex_dump import format_hex_dump


def test_hex_dump_format():
    data = b"Hello World!"
    dump = format_hex_dump(data, base_offset=0)
    assert "00000000" in dump
    assert "48 65 6c 6c 6f" in dump
    assert "|Hello World!|" in dump


def test_hex_dump_non_printable():
    data = b"\x00\x01\x02abc"
    dump = format_hex_dump(data)
    assert "|...abc|" in dump


def test_hex_dump_offset():
    data = b"ABCD"
    dump = format_hex_dump(data, base_offset=0x100)
    assert "00000100" in dump


def test_hex_dump_empty():
    assert format_hex_dump(b"") == ""