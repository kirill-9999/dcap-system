r"""Unit-тесты _collect_catalog_entries для s3:// (день 53.1b).

Покрытие:
- FS-путь: C:/x/y/file.txt → C:\x\y (как Path.parent);
- S3-путь: s3://bucket/a/b/file.txt → s3://bucket/a/b;
- S3-путь верхнего уровня: s3://bucket/file.txt → s3://bucket;
- пустой путь → "".
"""
import os
import sys
from pathlib import Path

# Пути: корень репо (пакет scanner) + scanner/ (верхнеуровневые core.*)
ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.managed_scanner import ManagedScanner  # noqa: E402


def _scanner_stub():
    """ManagedScanner без инициализации классификаторов."""
    s = ManagedScanner.__new__(ManagedScanner)
    return s


def test_parent_fs_path():
    s = _scanner_stub()
    parent = s._parent_of_path(r"C:\x\y\file.txt")
    assert parent.endswith("y")


def test_parent_s3_nested():
    s = _scanner_stub()
    assert s._parent_of_path("s3://bucket/a/b/file.txt") == "s3://bucket/a/b"


def test_parent_s3_top():
    s = _scanner_stub()
    assert s._parent_of_path("s3://bucket/file.txt") == "s3://bucket"


def test_parent_empty():
    s = _scanner_stub()
    assert s._parent_of_path("") == ""
