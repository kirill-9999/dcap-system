# audit-agent-s3/tests/unit/test_state.py
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.state import StateManager


def test_set_get():
    with tempfile.TemporaryDirectory() as td:
        sm = StateManager(str(Path(td) / "state"))
        sm.set("agent_id", 42)
        assert sm.get_agent_id() == 42


def test_default():
    with tempfile.TemporaryDirectory() as td:
        sm = StateManager(str(Path(td) / "state"))
        assert sm.get("missing", "dflt") == "dflt"
        assert sm.get_agent_id() is None
        assert sm.get_last_processed() is None


def test_last_processed():
    with tempfile.TemporaryDirectory() as td:
        sm = StateManager(str(Path(td) / "state"))
        sm.set_last_processed("access-logs/001.csv")
        sm2 = StateManager(str(Path(td) / "state"))
        assert sm2.get_last_processed() == "access-logs/001.csv"


def test_delete():
    with tempfile.TemporaryDirectory() as td:
        sm = StateManager(str(Path(td) / "state"))
        sm.set("agent_id", 1)
        sm.delete("agent_id")
        assert sm.get_agent_id() is None


def test_file_persistence():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "state"
        sm = StateManager(str(d))
        sm.set("agent_id", 7)
        persisted = json.loads((d / "agent_id.json").read_text(encoding="utf-8"))
        assert persisted == 7
