# tests/e2e/test_findings_api.py — E2E-тест Findings API (День 40.1).
# Проверяет: submit результатов сканера → list (masked) → reveal → FP → bulk → delete.
import uuid
import time

import pytest
import requests

from fixtures.auth import login, get_token
from fixtures.manager import create_task, delete_task

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def _register_fake_scanner(manager_url):
    """Регистрирует тестового сканера (machine-эндпоинт, без JWT)."""
    name = f"e2e-findings-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{manager_url}/api/scanner/register",
        json={"name": name, "hostname": "localhost", "ip_address": "127.0.0.1"},
        timeout=10,
    )
    assert r.status_code == 200, f"Register scanner: {r.status_code} {r.text}"
    return r.json()["scanner_id"]


def _assign_task(api_client, manager_url, scanner_id, resource_path):
    """Создаёт задание и назначает на сканер (как бы берёт на исполнение).

    Сканер берёт первое pending-задание (включая старые из других тестов),
    поэтому используем фактически выданный task_id.
    """
    create_task(api_client, manager_url, resource_path)

    r = requests.get(
        f"{manager_url}/api/scanner/tasks/pending",
        params={"scanner_id": scanner_id},
        timeout=10,
    )
    assert r.status_code == 200, f"Get pending task: {r.status_code} {r.text}"
    task = (r.json() or {}).get("task")
    assert task and task.get("id"), f"No pending task assigned: {r.text}"
    return task["id"]


def _submit_results(manager_url, task_id, findings):
    """Отправляет результаты от имени сканера (старый формат v3.8)."""
    r = requests.post(
        f"{manager_url}/api/scanner/tasks/{task_id}/results",
        json={
            "findings": findings,
            "stats": {
                "files_scanned": 1,
                "files_failed": 0,
                "total_findings": len(findings),
                "completed_at": __import__("datetime").datetime.utcnow().isoformat(),
            },
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), f"Submit results: {r.status_code} {r.text}"
    return r.json()


def _wait_findings(api_client, manager_url, task_id, expect=1, timeout=30):
    deadline = time.time() + timeout
    findings = []
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id}, timeout=10)
        assert r.status_code == 200, f"GET findings: {r.text}"
        findings = r.json()
        if len(findings) >= expect:
            return findings
        time.sleep(1)
    return findings


# ============================================================
# ТЕСТЫ
# ============================================================

def test_findings_submit_list_masked(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Submit → объект хранится зашифрованным, а API отдаёт masked."""
    scanner_id = _register_fake_scanner(manager_url)
    task_id = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task_id)

    _submit_results(manager_url, task_id, [
        {
            "file_path": "C:/fake/data.txt",
            "line_number": 7,
            "category": "pii",
            "subcategory": "phone",
            "value": "+7-999-123-45-67",
            "confidence": 0.95,
            "context": "contact: +7-999-123-45-67",
        },
        {
            "file_path": "C:/fake/creds.env",
            "line_number": 3,
            "category": "credentials",
            "subcategory": "password",
            "value": "P@ssw0rdSecret",
            "confidence": 0.99,
        },
    ])

    findings = _wait_findings(api_client, manager_url, task_id, expect=2)
    assert len(findings) == 2, f"Expected 2 findings, got {len(findings)}"

    # Маскированные поля не содержат секрета
    body = " ".join(f.get("match_text", "") or "" for f in findings)
    assert "+7-999-123-45-67" not in body
    assert "P@ssw0rdSecret" not in body

    # Правильные типы/category
    types = {f.get("finding_type") for f in findings}
    assert types == {"pii", "credentials"}, f"finding_type mismatch: {types}"

    # legacy-поля для backward-совместимости
    for f in findings:
        assert f.get("file_path") is not None, "legacy file_path missing"
        assert f.get("has_encrypted") is True, "has_encrypted should be True"


def test_reveal_requires_auditor_and_logs(
    api_client, manager_url, test_files_dir, cleanup_tasks
):
    """Reveal: расшифровка доступна auditor/admin, анониму — 403 (auth required)."""
    scanner_id = _register_fake_scanner(manager_url)
    task_id = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task_id)

    _submit_results(manager_url, task_id, [
        {
            "file_path": "C:/fake/secret.txt",
            "line_number": 1,
            "category": "pii",
            "subcategory": "email",
            "value": "boss@corp.example",
            "confidence": 1.0,
        }
    ])
    findings = _wait_findings(api_client, manager_url, task_id, expect=1)
    finding = findings[0]

    # 1. Анонимный reveal — 401/403
    r = requests.post(
        f"{manager_url}/api/findings/{finding['id']}/reveal", timeout=10
    )
    assert r.status_code in (401, 403), f"Anonymous reveal: {r.status_code}"

    # 2. Admin reveal — успех, секрет расшифрован
    r = api_client.post(
        f"{manager_url}/api/findings/{finding['id']}/reveal", timeout=10
    )
    assert r.status_code == 200, f"Admin reveal: {r.status_code} {r.text}"
    revealed = r.json()
    assert revealed["match_text"] == "boss@corp.example", revealed

    # 3. Аудит reveal появился
    r = api_client.get(f"{manager_url}/api/audit", timeout=10)
    assert r.status_code == 200, f"GET audit: {r.status_code} {r.text}"
    events = r.json()
    if isinstance(events, dict):
        events = events.get("events", events.get("items", []))
    reveal_events = [e for e in events if e.get("event_type") == "finding_reveal"]
    assert reveal_events, "Expected at least one finding_reveal audit event"


def test_false_positive_and_stats(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Запись в few FP и статистика."""

    scanner_id = _register_fake_scanner(manager_url)
    task_id = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task_id)

    _submit_results(manager_url, task_id, [
        {"file_path": "C:/fake/fp.txt", "line_number": 1, "category": "pii",
         "subcategory": "phone", "value": "+79991234567", "confidence": 0.5},
        {"file_path": "C:/fake/tp.txt", "line_number": 2, "category": "credentials",
         "subcategory": "password", "value": "another-secret", "confidence": 0.98},
    ])
    findings = _wait_findings(api_client, manager_url, task_id, expect=2)
    assert len(findings) == 2

    # Отмечаем одну как false_positive
    fp = next(f for f in findings if f.get("finding_type") == "pii")
    r = api_client.patch(
        f"{manager_url}/api/findings/{fp['id']}",
        json={"status": "false_positive", "comment": "тестовое FP"},
        timeout=10,
    )
    assert r.status_code == 200, f"PATCH FP: {r.status_code} {r.text}"

    # Список FP
    r = api_client.get(f"{manager_url}/api/findings/false-positives", timeout=10)
    assert r.status_code == 200
    fp_list = r.json()
    assert any(f["id"] == fp["id"] for f in fp_list), "FP missing from list"

    # Статистика
    r = api_client.get(
        f"{manager_url}/api/findings/stats", params={"task_id": task_id}, timeout=10
    )
    assert r.status_code == 200, f"GET stats: {r.text}"
    stats = r.json()
    assert stats["total"] == 2
    assert stats["by_status"].get("false_positive") == 1, stats


def test_check_fingerprints_and_bulk(api_client, manager_url, test_files_dir, cleanup_tasks):
    """check-fingerprints (machine) + bulk update."""
    scanner_id = _register_fake_scanner(manager_url)
    task_id = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task_id)

    _submit_results(manager_url, task_id, [
        {"file_path": "C:/fake/z1.txt", "line_number": 1, "category": "pii",
         "subcategory": "phone", "value": "+7-000-000-00-00", "confidence": 0.9},
    ])
    findings = _wait_findings(api_client, manager_url, task_id, expect=1)
    assert len(findings) == 1

    # Отмечаем FP
    fid = findings[0]["id"]
    r = api_client.patch(
        f"{manager_url}/api/findings/{fid}",
        json={"status": "false_positive", "comment": "fp для check"},
        timeout=10,
    )
    assert r.status_code == 200

    # Проверяем fingerprint через machine-эндпоинт (без JWT)
    r = requests.post(
        f"{manager_url}/api/findings/check-fingerprints",
        json={"fingerprints": ["fake-unknown-1", "fake-fp-1", "fake-ok-1"]},
        timeout=10,
    )
    assert r.status_code == 200, f"check-fingerprints: {r.status_code} {r.text}"
    res = r.json()
    assert set(res.keys()) == {"false_positives", "confirmed", "new"}

    # Bulk-обновление подтверждаем
    r = api_client.post(
        f"{manager_url}/api/findings/bulk",
        json={"finding_ids": [fid], "status": "confirmed", "comment": "bulk"},
        timeout=10,
    )
    assert r.status_code == 200, f"bulk: {r.status_code} {r.text}"
    assert r.json()["updated"] == 1

    # Проверка, что подтверждено
    r = api_client.get(f"{manager_url}/api/findings/{fid}", timeout=10)
    assert r.json()["status"] == "confirmed"


def test_delete_requires_admin(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Delete — только admin (403 для обычного логина)."""
    scanner_id = _register_fake_scanner(manager_url)
    task_id = _assign_task(api_client, manager_url, scanner_id, str(test_files_dir))
    cleanup_tasks.append(task_id)

    _submit_results(manager_url, task_id, [
        {"file_path": "C:/fake/del.txt", "line_number": 1, "category": "code",
         "subcategory": "api_key", "value": "sk-DELETEME", "confidence": 1.0},
    ])
    findings = _wait_findings(api_client, manager_url, task_id, expect=1)
    fid = findings[0]["id"]

    r = api_client.delete(f"{manager_url}/api/findings/{fid}", timeout=10)
    assert r.status_code == 200, f"delete: {r.status_code} {r.text}"

    r = api_client.get(f"{manager_url}/api/findings/{fid}", timeout=10)
    assert r.status_code == 404, "Deleted finding should 404"