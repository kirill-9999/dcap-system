"""Unit-тесты фабрики коннекторов (день 53.1b).

Покрытие:
- registered_types() содержит filesystem;
- create_line_connector('filesystem', {}) возвращает FilesystemConnector;
- create_line_connector('s3') → ValueError (не зарегистрирован в 53.1b);
- create_line_connector('minio') → ValueError;
- create_line_connector(None) → filesystem (дефолт);
- create_line_connector('FILESYSTEM') → filesystem (нормализация регистра).
"""
import os
import sys
from pathlib import Path

import pytest

# Пути: корень репо (пакет scanner) + scanner/ (пакеты core/classifiers/connectors).
# Второй путь нужен, потому что scanner/connectors/filesystem.py импортирует
# верхнеуровнево `from core.base import ...` (конвенция репо, как в
# test_ocr_bbox_v31317.py / test_scanner_findings.py).
ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.connectors.factory import (  # noqa: E402
    create_line_connector,
    registered_types,
)
from scanner.connectors.filesystem import FilesystemConnector  # noqa: E402


def test_registered_types_contains_filesystem():
    assert "filesystem" in registered_types()


def test_create_filesystem_returns_instance():
    c = create_line_connector("filesystem", {})
    assert isinstance(c, FilesystemConnector)


def test_create_filesystem_normalizes_case():
    c1 = create_line_connector("FILESYSTEM", {})
    c2 = create_line_connector("FiLeSyStEm", {})
    assert isinstance(c1, FilesystemConnector)
    assert isinstance(c2, FilesystemConnector)


def test_create_filesystem_default_when_none():
    c = create_line_connector(None, {})
    assert isinstance(c, FilesystemConnector)


def test_create_s3_raises_value_error():
    with pytest.raises(ValueError) as exc:
        create_line_connector("s3", {})
    assert "s3" in str(exc.value)
    assert "53.2" in str(exc.value)


def test_create_minio_raises_value_error():
    with pytest.raises(ValueError) as exc:
        create_line_connector("minio", {})
    assert "minio" in str(exc.value)


def test_create_unknown_raises_value_error():
    with pytest.raises(ValueError):
        create_line_connector("ftp", {})
