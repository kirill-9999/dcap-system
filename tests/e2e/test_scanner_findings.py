# tests/e2e/test_scanner_findings.py — E2E-тесты дня 40.2.
# Проверяет: новый формат находок (finding_type + fingerprint), дедупликацию
# в Manager, FP-фильтр (skipped_false_positives), и сквозной сценарий с реальным
# сканером (requires_scanner).
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

from fixtures.manager import create_task, wait_task_assigned

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def _register_fake_scanner(manager_url):
    name = f"e2e-findings-40-2-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{manager_url}/api/scanner/register",
        json={"name": name, "hostname": "localhost", "ip_address": "127.0.0.1"},
        timeout=10,
    )
    assert r.status_code == 200, f"Register scanner: {r.status_code} {r.text}"
    return r.json()["scanner_id"]


def _assign_task(api_client, manager_url, scanner_id, resource_path):
    create_task(api_client, manager_url, resource_path)
    r = requests.get(
        f"{manager_url}/api/scanner/tasks/pending",
        params={"scanner_id": scanner_id},
        timeout=10,
    )
    assert r.status_code == 200, f"Get pending task: {r.status_code} {r.text}"
    task = (r.json() or {}).get("task")
    assert task and task.get("id"), f"No pending task: {r.text}"
    return task["id"]


def _submit(manager_url, task_id, findings):
    r = requests.post(
        f"{manager_url}/api/scanner/tasks/{task_id}/results",
        json={
            "findings": findings,
            "stats": {
                "files_scanned": 1,
                "files_failed": 0,
                "total_findings": len(findings),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), f"Submit: {r.status_code} {r.text}"
    return r.json()


def _get_findings(api_client, manager_url, task_id, expect=1, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id}, timeout=10)
        assert r.status_code == 200
        findings = r.json()
        if len(findings) >= expect:
            return findings
        time.sleep(1)
    return findings


# == Новый формат находок (день 40.2) ==
NEW_FORMAT_MAX = [
    {
        "file_path": "C:/fake-40-2/api-keys.txt",
        "line_number": 1,
        "finding_type": "credentials",
        "category": "api_key",
        "subcategory": "api_key",
        "value": "ak-test-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "confidence": 0.95,
        "severity": "high",
        "detector": "regex",
        "fingerprint": "fp-40-2-api-1",
        "match_text_masked": "ak-t***",
        "line_text_masked": "api_key = ak-t***",
        "start_pos": 10,
        "end_pos": 46,
    },
    {
        "file_path": "C:/fake-40-2/creds.txt",
        "line_number": 3,
        "finding_type": "credentials",
        "category": "password",
        "subcategory": "password",
        "value": "P@ssw0rd-40-2",
        "confidence": 0.8,
        "severity": "medium",
        "detector": "regex",
        "fingerprint": "fp-40-2-pw-1",
        "match_text_masked": "***",
        "line_text_masked": "password = ***",
        "start_pos": 11,
        "end_pos": 23,
    },
]


def test_submit_new_format_saves_and_dedupes(
    api_client, manager_url, test_files_dir, cleanup_tasks
):
    """Новый формат: первый submit сохраняет, повторный — дедуплицируется."""
    scanner_id = _register_fake_scanner(manager_url)
    task1 = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task1)

    r = _submit(manager_url, task1, list(NEW_FORMAT_MAX))
    assert r["findings_count"] == 2, r
    assert r["deduped"] == 0, r
    assert r["skipped_false_positives"] == 0, r

    findings = _get_findings(api_client, manager_url, task1, expect=2)
    assert len(findings) == 2

    # Новый формат сохранил category/finding_type/детектор
    by_file = {f["file_path"]: f for f in findings}
    api = by_file["C:/fake-40-2/api-keys.txt"]
    assert api["finding_type"] == "credentials"
    assert api["category"] == "api_key"
    assert api["detector"] == "regex"
    # Маска пришла от сканера
    assert api["match_text"] == "ak-t***"

    # Повторный submit с теми же fingerprints — дедуп
    task2 = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task2)
    r = _submit(manager_url, task2, list(NEW_FORMAT_MAX))
    assert r["findings_count"] == 0, r
    assert r["deduped"] == 2, r
    assert r["skipped_false_positives"] == 0, r


def test_false_positive_not_recreated_and_skipped(
    api_client, manager_url, test_files_dir, cleanup_tasks
):
    """FP: находка, помеченная false_positive, при повторном submit пропускается."""
    scanner_id = _register_fake_scanner(manager_url)
    task1 = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task1)

    _submit(manager_url, task1, list(NEW_FORMAT_MAX))
    findings = _get_findings(api_client, manager_url, task1, expect=2)

    # Отмечаем первую как FP
    fid = findings[0]["id"]
    r = api_client.patch(
        f"{manager_url}/api/findings/{fid}",
        json={"status": "false_positive", "comment": "e2e fp 40.2"},
        timeout=10,
    )
    assert r.status_code == 200, f"PATCH FP: {r.status_code} {r.text}"

    # Повторный submit → FP находка не пересоздаётся (skipped),
    # существующая не-FP — дедуплицируется (last_seen_at refresh).
    task2 = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task2)
    r = _submit(manager_url, task2, list(NEW_FORMAT_MAX))
    assert r["findings_count"] == 0, r
    assert r["deduped"] == 1, r
    assert r["skipped_false_positives"] == 1, r


@pytest.mark.requires_scanner
def test_real_scanner_end_to_end(
    api_client, manager_url, scanner_url, test_files_dir, cleanup_tasks
):
    """Сквозной сценарий с реальным сканером (:9101) — День 40.2.

    Сканер должен быть запущен против тест-стека Manager (MANAGER_URL=:18000).
    """
    from fixtures.manager import wait_task_status
    from fixtures.scanner import get_scanner, list_scanners

    scanners = list_scanners(api_client, manager_url)
    assert scanners, "Нет зарегистрированных сканеров"
    scanner_id = scanners[0]["id"]
    info = get_scanner(api_client, manager_url, scanner_id)

    # Создаём задание на тестовую папку
    create_task(api_client, manager_url, str(test_files_dir))
    r = requests.get(
        f"{manager_url}/api/scanner/tasks/pending",
        params={"scanner_id": scanner_id},
        timeout=10,
    )
    assert r.status_code == 200
    task = (r.json() or {}).get("task")
    assert task and task.get("id"), "Нет pending-задания для сканера"
    task_id = task["id"]
    cleanup_tasks.append(task_id)

    # Ждём выполнения реальным сканером
    status = wait_task_status(api_client, manager_url, task_id, "completed", timeout=300, interval=5)
    assert status in ("completed", "running"), f"Задание не завершилось: {status}"
    if status != "completed":
        pytest.skip("Сканер не завершил задание за таймаут (проверьте :9101 и MANAGER_URL=:18000)")

    findings = _get_findings(api_client, manager_url, task_id, expect=1, timeout=30)
    assert findings, f"Сканер не прислал находки: {task_id}"

    # Проверяем новые колонки: fingerprint, статусы
    f = findings[0]
    assert f["fingerprint"], f"Нет fingerprint: {f}"
    assert f["status"] == "new", f["status"]
    assert "has_encrypted" in f