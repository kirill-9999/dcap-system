# tests/chaos/test_scanner_crash.py
import time

import pytest

from fixtures.manager import create_task
from fixtures.scanner import get_scanner, list_scanners


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_manager
def test_scanner_inactive_alert(api_client, manager_url):
    """
    Если сканер не шлёт heartbeat >120 сек → Manager помечает inactive
    (BACKLOG-038: _mark_stale_scanners).

    ВАЖНО: тест требует остановки сканера вручную (или subprocess).
    Автоматизация — в v3.1.0 (с полным chaos-стеком).
    """
    pytest.skip("Требует ручной остановки сканера (автоматизация в v3.1.0)")


@pytest.mark.chaos
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_scanner_active_during_long_task(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Сканер НЕ помечается inactive во время задания (BACKLOG-037)."""
    task_id = create_task(api_client, manager_url, str(test_files_dir))
    cleanup_tasks.append(task_id)

    scanners = list_scanners(api_client, manager_url)
    if not scanners:
        pytest.skip("Нет сканеров")
    scanner_id = scanners[0]["id"]

    for _ in range(5):
        info = get_scanner(api_client, manager_url, scanner_id)
        if info["status"] != "active":
            pytest.fail(f"Scanner became inactive during task: {info}")
        time.sleep(5)