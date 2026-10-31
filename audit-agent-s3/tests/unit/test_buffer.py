# audit-agent-s3/tests/unit/test_buffer.py
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.buffer import BufferManager
from shared.event_schema import UnifiedEvent


def make_event(i=1):
    return UnifiedEvent(
        event_type="read",
        event_source="s3_agent",
        user="u",
        file_path=f"s3://bucket/key{i}",
        metadata={"i": i},
        created_at="2026-08-31T10:00:00",
    )


def test_store_and_get_unsent():
    with tempfile.TemporaryDirectory() as td:
        buf = BufferManager({"path": str(Path(td) / "buffer.db"), "max_events": 100, "cleanup_days": 7})
        buf.store_event(make_event(1))
        buf.store_event(make_event(2))
        unsent = buf.get_unsent()
        assert len(unsent) == 2
        assert unsent[0][1].file_path == "s3://bucket/key1"
        buf.close()


def test_mark_sent():
    with tempfile.TemporaryDirectory() as td:
        buf = BufferManager({"path": str(Path(td) / "buffer.db"), "max_events": 100, "cleanup_days": 7})
        buf.store_event(make_event(1))
        buf.store_event(make_event(2))
        ids = [e[0] for e in buf.get_unsent()]
        buf.mark_sent(ids)
        assert buf.get_unsent() == []
        stats = buf.get_stats()
        assert stats["pending"] == 0
        assert stats["sent"] == 2
        buf.close()


def test_max_events_drops_oldest():
    with tempfile.TemporaryDirectory() as td:
        buf = BufferManager({"path": str(Path(td) / "buffer.db"), "max_events": 5, "cleanup_days": 7})
        for i in range(8):
            buf.store_event(make_event(i))
        unsent = buf.get_unsent(limit=100)
        # oldest dropped; remaining <= max_events
        assert len(unsent) <= 5
        buf.close()


def test_cleanup_old_events():
    import sqlite3
    with tempfile.TemporaryDirectory() as td:
        dbp = Path(td) / "buffer.db"
        buf = BufferManager({"path": str(dbp), "max_events": 100, "cleanup_days": 7})
        buf.store_event(make_event(1))
        ids = [e[0] for e in buf.get_unsent()]
        buf.mark_sent(ids)
        conn = sqlite3.connect(str(dbp))
        conn.execute("UPDATE events SET created_at = datetime('now', '-10 days')")
        conn.commit()
        conn.close()
        buf.cleanup_old_events()
        assert buf.get_stats()["total"] == 0
        buf.close()


def test_stats():
    with tempfile.TemporaryDirectory() as td:
        buf = BufferManager({"path": str(Path(td) / "buffer.db"), "max_events": 100, "cleanup_days": 7})
        assert buf.get_stats() == {"total": 0, "pending": 0, "sent": 0, "retries": 0}
        buf.store_event(make_event(1))
        s = buf.get_stats()
        assert s["total"] == 1 and s["pending"] == 1
        buf.close()
