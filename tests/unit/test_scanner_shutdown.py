# tests/unit/test_scanner_shutdown.py — BUG-081 (TASK-052, v3.13.20)
# Graceful shutdown сканера: SIGINT → stop event; stop() → None в
# OCR request_queue; зависший OCRWorker завершается terminate/kill.
import sys
import threading
from queue import Empty
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.managed_scanner import ManagedScanner  # noqa: E402
from scanner.classifiers.ocr_worker import stop_ocr_worker  # noqa: E402

pytestmark = [pytest.mark.unit]


def _stubborn_worker(request_queue):
    """Зависший worker: читает очередь, игнорирует None, никогда не выходит."""
    while True:
        try:
            request_queue.get(timeout=1)
        except Empty:
            pass


def _make_scanner_obj() -> ManagedScanner:
    s = ManagedScanner.__new__(ManagedScanner)
    s._should_exit = False
    s._stop_event = threading.Event()
    s.heartbeat_thread = None
    s.classifiers = []
    return s


def test_sigint_sets_stop_event():
    """_handle_sigint → _stop_event.set() и _should_exit=True."""
    s = _make_scanner_obj()
    s._handle_sigint(2, None)
    assert s._stop_event.is_set()
    assert s._should_exit is True


def test_stop_sends_none_to_ocr_queue():
    """stop() → shutdown классификаторов → None в OCR request_queue."""
    q = mock.MagicMock()

    class _Shutdowner:
        def __init__(self, queue_):
            self._queue = queue_

        def shutdown(self):
            stop_ocr_worker(None, self._queue, None)

    s = _make_scanner_obj()
    s.heartbeat_thread = mock.MagicMock()
    s.classifiers = [_Shutdowner(q)]

    s.stop()

    q.put.assert_called_once_with(None, timeout=1)
    s.heartbeat_thread.stop.assert_called_once()


def test_stop_terminates_stubborn_process():
    """Если OCRWorker не завершился за 5 с → terminate → kill."""
    import multiprocessing as mp

    request_queue = mp.Queue()
    proc = mp.Process(target=_stubborn_worker, args=(request_queue,), name="OCRStubborn")
    proc.start()
    try:
        stop_ocr_worker(proc, request_queue, None)
        assert not proc.is_alive(), "OcrWorker должен быть завершён (terminate/kill)"
    finally:
        try:
            proc.join(timeout=1)
        except Exception:
            pass
        request_queue.close()
        request_queue.join_thread()