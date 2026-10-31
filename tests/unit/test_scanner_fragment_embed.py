# tests/unit/test_scanner_fragment_embed.py
"""BACKLOG-086 (TASK-046/050, v3.13.19): сканер встраивает OCR-фрагмент."""
import base64
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scanner.src.managed_scanner as ms  # noqa: E402
from scanner.src.finding import Finding  # noqa: E402

pytestmark = [pytest.mark.unit]

DATA = b"\x89PNG\r\n\x1a\nfake-png-for-embed"


def _image_finding(path: Path):
    return Finding(
        line_number=1,
        line_text="",
        match_text="test@example.com",
        start_pos=0,
        end_pos=17,
        finding_type="pii",
        category="email",
        fragment_type="image_region",
        fragment_path=str(path),
    )


class TestScannerEmbedsFragment:
    def test_small_image_embedded(self, tmp_path):
        """PNG < 2 МБ → fragment_base64 в payload."""
        png = tmp_path / "small.png"
        png.write_bytes(DATA)
        emb = ms._embed_fragment(_image_finding(png))
        assert emb["fragment_base64"] == base64.b64encode(DATA).decode("ascii")
        assert emb["fragment_mime"] == "image/png"
        assert emb["fragment_size"] == len(DATA)

    def test_large_image_not_embedded(self, tmp_path):
        """PNG > 2 МБ → fragment_base64 = None, fragment_path сохраняется."""
        png = tmp_path / "large.png"
        png.write_bytes(b"\0" * (ms.MAX_FRAGMENT_EMBED_SIZE + 1))
        assert ms._embed_fragment(_image_finding(png)) == {}
        # finding сохраняется по fragment_path (Manager знает путь)
        f = _image_finding(png)
        assert f.fragment_path == str(png)

    def test_text_line_not_embedded(self, tmp_path):
        """text_line → fragment_base64 = None."""
        txt = tmp_path / "notes.txt"
        txt.write_text("email: test@example.com", encoding="utf-8")
        f = Finding(
            line_number=1,
            line_text="email: test@example.com",
            match_text="test@example.com",
            start_pos=7,
            end_pos=23,
            finding_type="pii",
            category="email",
            fragment_type="text_line",
            fragment_path=str(txt),
        )
        assert ms._embed_fragment(f) == {}

    def test_hash_matches_data(self, tmp_path):
        """fragment_hash == sha256(b64decode(fragment_base64))."""
        png = tmp_path / "hash.png"
        png.write_bytes(DATA)
        emb = ms._embed_fragment(_image_finding(png))
        decoded = base64.b64decode(emb["fragment_base64"])
        assert emb["fragment_hash"] == hashlib.sha256(decoded).hexdigest()

    def test_custom_max_size_env(self, tmp_path, monkeypatch):
        """MAX_FRAGMENT_EMBED_SIZE=1024 → файл 2 КБ не встраивается.

        Константа читается из env при старте сканера — здесь имитируем
        перезапуск с меньшим лимитом через monkeypatch атрибута модуля.
        """
        monkeypatch.setattr(ms, "MAX_FRAGMENT_EMBED_SIZE", 1024)
        png = tmp_path / "bigger.png"
        png.write_bytes(b"\0" * 2048)
        assert ms._embed_fragment(_image_finding(png)) == {}

    def test_split_by_size_batches(self, tmp_path, monkeypatch):
        """TASK-050: findings разбиваются по MAX_BATCH_SIZE_BYTES."""
        monkeypatch.setattr(ms, "_MAX_BATCH_COUNT", 1000)
        big = {
            "file_path": "C:/x/a.png",
            "fragment_size": 2 * 1024 * 1024,  # 2 МБ каждый
        }
        small = {"file_path": "C:/x/b.txt", "fragment_size": 10}
        items = [dict(big) for _ in range(4)] + [dict(small)] * 5
        batches = ms._split_by_size(items, 5 * 1024 * 1024)
        assert all(sum(b.get("fragment_size", 0) for b in batch) <= 5 * 1024 * 1024 for batch in batches)
        assert sorted(x["file_path"] for b in batches for x in b) == sorted(
            x["file_path"] for x in items
        )