"""Unit-тесты фабрики коннекторов (день 53.1b, дополнено в 53.2).

Покрытие:
- registered_types() содержит filesystem, s3, minio;
- create_line_connector('filesystem', {}) возвращает FilesystemConnector;
- create_line_connector('s3'/'minio') возвращает S3LineConnector (день 53.2);
- create_line_connector(None) → filesystem (дефолт);
- create_line_connector('FILESYSTEM') → filesystem (нормализация регистра);
- неизвестный source_type → ValueError со списком доступных.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

# Секреты S3 — только ENV (день 53.2, политика TASK-018). Нужны для создания
# S3LineConnector в тестах фабрики.
os.environ.setdefault("S3_ACCESS_KEY", "test-access")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")

from scanner.connectors.factory import (  # noqa: E402
    create_line_connector,
    registered_types,
)
from scanner.connectors.filesystem import FilesystemConnector  # noqa: E402


def test_registered_types_contains_all():
    types = registered_types()
    assert "filesystem" in types
    assert "s3" in types
    assert "minio" in types


def test_registered_types_exact():
    assert registered_types() == ["filesystem", "minio", "s3"]


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


def test_create_s3_returns_s3_line_connector(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "x")
    monkeypatch.setenv("S3_SECRET_KEY", "y")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        from scanner.connectors.s3_line_connector import S3LineConnector
        c = create_line_connector("s3", {"bucket": "b"})
        assert isinstance(c, S3LineConnector)


def test_create_minio_returns_s3_line_connector(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "x")
    monkeypatch.setenv("S3_SECRET_KEY", "y")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        from scanner.connectors.s3_line_connector import S3LineConnector
        c = create_line_connector("minio", {"bucket": "b"})
        assert isinstance(c, S3LineConnector)


def test_create_unknown_raises_value_error():
    with pytest.raises(ValueError) as exc:
        create_line_connector("ftp", {})
    # Сообщение содержит список доступных типов
    assert "filesystem" in str(exc.value)
