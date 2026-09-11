# tests/e2e/test_scanner_heartbeat.py
import time

import pytest
import requests

from fixtures.scanner import get_scanner, list_scanners


@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_scanner_heartbeat_keeps_active(api_client, manager_url):
    """Сканер остаётся active во время длительного задания (BACKLOG-037).

    Heartbeat-тред сканера шлёт POST /api/scanner/heartbeat каждые ~30 сек,
    поэтому статус не протухает (STALE_THRESHOLD = 2 мин).
    """
    scanners = list_scanners(api_client, manager_url)
    if not scanners:
        pytest.skip("Нет сканеров")
    scanner_id = scanners[0]["id"]

    # Проверяем initial status
    info = get_scanner(api_client, manager_url, scanner_id)
    assert info["status"] == "active", f"Scanner not active: {info['status']}"

    # Ждём >60 сек (2 heartbeat-интервала) и проверяем, что всё ещё active
    time.sleep(65)
    info = get_scanner(api_client, manager_url, scanner_id)
    assert info["status"] == "active", f"Scanner went inactive without task: {info['status']}"


@pytest.mark.e2e
@pytest.mark.requires_scanner
def test_scanner_metrics_available(scanner_url):
    """Метрики сканера :9101 доступны (День 39)."""
    r = requests.get(f"{scanner_url}/metrics", timeout=5)
    assert r.status_code == 200
    assert "dcap_scanner_files_scanned_total" in r.text
    assert "dcap_scanner_findings_total" in r.text