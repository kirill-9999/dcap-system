"""Тесты ScanState (53.4n, v3.14.12, BUG-280)."""
import json
import tempfile
from pathlib import Path

import pytest

sys_path = None
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scanner" / "src"))

from state_manager import ScanState


def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        state = ScanState(42, state_dir=d)
        state.save(last_completed_chunk=3, findings_count=10, total_chunks=10)
        state2 = ScanState(42, state_dir=d)
        data = state2.load()
        assert data["last_completed_chunk"] == 3
        assert data["findings_count"] == 10
        assert state2.get_resume_chunk() == 4


def test_load_wrong_task_ignored():
    with tempfile.TemporaryDirectory() as d:
        state = ScanState(42, state_dir=d)
        state.save(last_completed_chunk=3)
        other = ScanState(99, state_dir=d)
        assert other.load() == {}


def test_clear_removes_file():
    with tempfile.TemporaryDirectory() as d:
        state = ScanState(7, state_dir=d)
        state.save(last_completed_chunk=0)
        assert (Path(d) / "scan_7.json").exists()
        state.clear()
        assert not (Path(d) / "scan_7.json").exists()


def test_corrupted_file_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "scan_5.json"
        path.write_text("{not json", encoding="utf-8")
        state = ScanState(5, state_dir=d)
        assert state.load() == {}


def test_resume_chunk_default_zero():
    with tempfile.TemporaryDirectory() as d:
        state = ScanState(1, state_dir=d)
        assert state.get_resume_chunk() == 0


def test_atomic_write_no_tmp_left():
    with tempfile.TemporaryDirectory() as d:
        state = ScanState(3, state_dir=d)
        state.save(last_completed_chunk=1)
        tmp_files = [p for p in Path(d).iterdir() if p.name.startswith(".scan_")]
        assert tmp_files == []
