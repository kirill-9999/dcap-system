# tests/unit/test_heartbeat_backoff.py — BUG-080 (TASK-051, v3.13.20)
# Heartbeat: exponential backoff 5→10→30→60→120 с, сброс на успехе,
# WARNING только на 1-м фейле и каждые 5, мгновенный выход по stop().
import threading
import logging
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.heartbeat import HeartbeatThread  # noqa: E402

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def thread() -> HeartbeatThread:
    return HeartbeatThread(manager_url="http://127.0.0.1:9", scanner_id=1, interval=30)


def test_backoff_steps(thread):
    """5, 10, 30, 60, 120 — и не больше 120."""
    assert thread.BACKOFF_STEPS == [5, 10, 30, 60, 120]
    slept = [thread._next_sleep(False) for _ in range(8)]
    assert slept == [5, 10, 30, 60, 120, 120, 120, 120]
    assert max(slept) == thread.BACKOFF_STEPS[-1]


def test_backoff_resets_on_success(thread):
    """После успеха fail_count = 0, sleep = interval."""
    assert thread._next_sleep(False) == 5
    assert thread._next_sleep(False) == 10
    assert thread._next_sleep(False) == 30
    assert thread._fail_count == 3

    sleep_after = thread._next_sleep(True)
    assert thread._fail_count == 0
    assert sleep_after == thread.interval


def test_warning_not_spam(thread, caplog):
    """WARNING только на 1-м фейле и каждые 5."""
    with caplog.at_level(logging.WARNING, logger="scanner.src.heartbeat"):
        for _ in range(11):
            thread._next_sleep(False)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 3, [w.getMessage() for w in warnings]

    attempts = []
    for w in warnings:
        m = w.getMessage()
        assert "Heartbeat failing" in m
        attempts.append(int(m.split("(")[1].split()[0]))
    assert attempts == [1, 5, 10]

    debug = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(debug) == 0  # DEBUG-фейлы логируются в _send_heartbeat (не в _next_sleep)


def test_stop_event_interrupts_sleep(thread, monkeypatch):
    """stop_event.wait() → мгновенный выход из sleep (не time.sleep)."""
    monkeypatch.setattr(HeartbeatThread, "BACKOFF_STEPS", [30])
    thread._send_heartbeat = lambda: False  # noqa: E731  — всегда фейл → сон 30 с

    t = threading.Thread(target=thread.run, daemon=True)
    t.start()
    time.sleep(0.4)  # поток точно заснул на wait(30)
    assert t.is_alive()

    thread.stop()
    t.join(timeout=2)
    assert not t.is_alive(), "stop() должен мгновенно прервать backoff-сон"