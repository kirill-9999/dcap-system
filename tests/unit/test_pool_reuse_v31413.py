"""53.4o (v3.14.13): ProcessPoolExecutor — один на все чанки."""
import inspect

from scanner.src.managed_scanner import ManagedScanner


def test_executor_outside_chunk_loop():
    """BUG-286: ProcessPoolExecutor создаётся один раз вне цикла чанков."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    idx_pool = src.find("ProcessPoolExecutor")
    idx_for = src.find("for chunk_idx")
    assert idx_pool != -1, "ProcessPoolExecutor не найден"
    assert idx_for != -1, "for chunk_idx не найден"
    assert idx_pool < idx_for, "ProcessPoolExecutor должен быть до цикла чанков"


def test_executor_single_instance():
    """BUG-286: ProcessPoolExecutor — 1 экземпляр."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    assert src.count("with ProcessPoolExecutor") == 1
