"""Smoke-тесты BUG-077 (TASK-041, v3.13.17): bounding_box=None для OCR."""

import sys
from pathlib import Path
from unittest.mock import patch

# Пути: корень репо (пакет scanner) + scanner/ (пакеты core/classifiers/connectors)
ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.connectors.filesystem import FilesystemConnector  # noqa: E402
from scanner.src.finding import Finding  # noqa: E402


def _fake_finding():
    return Finding(
        line_number=1,
        line_text="email: test@example.com",
        match_text="test@example.com",
        start_pos=7, end_pos=23,
        finding_type="pii",
        category="email",
        detector="presidio",   # filesystem перезапишет на ocr для .png
    )


class TestOcrBoundingBox:
    """BUG-077: image_region без реальных координат → bounding_box=None."""

    def test_ocr_finding_bbox_is_none(self, tmp_path):
        """OCR-finding для .png: fragment_type=image_region, detector=ocr, bbox=None."""
        png = tmp_path / "dummy.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        connector = FilesystemConnector({})
        with patch.object(connector, "_extract_document", return_value="email: test@example.com"):
            with patch.object(connector, "_scan_text", return_value=[_fake_finding()]):
                findings = connector.scan_file(str(png), classifiers=[])
        assert len(findings) == 1
        f = findings[0]
        assert f.fragment_type == "image_region"
        assert f.detector == "ocr"
        assert f.bounding_box is None

    def test_text_finding_bbox_stays_none(self, tmp_path):
        """Обычный текстовый finding — bbox=None (не image_region)."""
        txt = tmp_path / "dummy.txt"
        txt.write_text("email: test@example.com", encoding="utf-8")
        connector = FilesystemConnector({})
        with patch.object(connector, "_read_text", return_value="email: test@example.com"):
            with patch.object(connector, "_scan_text", return_value=[_fake_finding()]):
                findings = connector.scan_file(str(txt), classifiers=[])
        assert len(findings) == 1
        assert findings[0].fragment_type == "text_line"
        assert findings[0].bounding_box is None