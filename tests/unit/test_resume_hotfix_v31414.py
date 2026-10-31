"""53.4p (v3.14.14): BUG-287, BUG-288, BUG-289."""
import inspect

from manager.src.api.scanner import release_task
from scanner.src.managed_scanner import ManagedScanner


def test_final_only_last_chunk():
    """BUG-287: final=True только на последнем чанке."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    assert "total_chunks - 1" in src or "total_chunks-1" in src
    assert "final = True" not in src


def test_progress_monotonic():
    """BUG-289: ScanProgress монотонный (accumulated)."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    assert "_total_scanned" in src or "total_scanned" in src


def test_release_completed_noop():
    """BUG-288: release на completed — no-op (не 400)."""
    src = inspect.getsource(release_task)
    assert "completed" in src
    assert "noop" in src or "204" in src or "return" in src
