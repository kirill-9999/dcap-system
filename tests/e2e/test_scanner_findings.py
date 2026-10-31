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


def _release_stale_tasks(api_client, manager_url, scanner_id, limit=10):
    """Освободить задания, застрявшие в assigned (BUG-097, TASK-066).

    Manager освобождает зависшее задание только по таймауту в
    TASK_TIMEOUT_MINUTES (30 минут). Перед сквозным тестом очередь
    очищается, чтобы не ждать по 30 минут на каждое накопленное задание.
    """
    from fixtures.manager import _get_with_retry

    r = _get_with_retry(api_client, f"{manager_url}/api/tasks", timeout=10)
    if r.status_code != 200:
        return []
    released = []
    for t in r.json():
        if t.get("status") != "assigned" or t.get("scanner_id") != scanner_id:
            continue
        rr = api_client.post(
            f"{manager_url}/api/scanner/tasks/{t['id']}/release", timeout=10
        )
        if rr.status_code == 200:
            released.append(t["id"])
        if len(released) >= limit:
            break
    return released


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
    from fixtures.manager import _get_with_retry

    deadline = time.time() + timeout
    findings = []
    while time.time() < deadline:
        r = _get_with_retry(
            api_client, f"{manager_url}/api/findings", params={"task_id": task_id}, timeout=10
        )
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
@pytest.mark.timeout(600)
def test_real_scanner_end_to_end(
    api_client, manager_url, scanner_url, test_files_dir, cleanup_tasks
):
    """Сквозной сценарий с реальным сканером (:9101) — День 40.2.

    BUG-096b (TASK-065, v3.13.25), три исправления:
      1) precheck — если нет активного зарегистрированного сканера, тест
         скипается (иначе он падал бы на таймауте в не-сканерном окружении);
      2) retry на разрыв keep-alive соединения при опросе статуса задания
         (RemoteDisconnected) — см. fixtures.manager._get_with_retry;
      3) бюджет ожидания задания (240 с) меньше лимита теста
         (@pytest.mark.timeout(600)): глобальный timeout = 300 в pyproject.toml
         иначе убивал тест ровно в момент ожидания задания.
    """
    from fixtures.manager import wait_task_status
    from fixtures.scanner import get_scanner, list_scanners

    scanners = list_scanners(api_client, manager_url)
    assert scanners, "Нет зарегистрированных сканеров"

    active = [s for s in scanners if s.get("status") in ("active", "idle", "assigned", "running")]
    if not active:
        pytest.skip(
            "Нет активного сканера в Manager "
            f"(найдено {len(scanners)}: {[s.get('status') for s in scanners]})"
        )
    scanner_id = active[0]["id"]
    info = get_scanner(api_client, manager_url, scanner_id)

    # BUG-097 (TASK-066): очередь очищается от зависших заданий, иначе новое
    # задание встаёт в конец и ждёт 30-минутный stale-таймаут Manager
    # (TASK_TIMEOUT_MINUTES = 30) на каждом зависшем задании.
    released = _release_stale_tasks(api_client, manager_url, scanner_id)
    if released:
        print(f"\n[INFO] Освобождено зависших заданий: {released}")

    # Создаём задание на тестовую папку.
    # BUG-097 (TASK-066): задание НЕ забирается вручную через /tasks/pending —
    # этот вызов сам переводит его в assigned, и реальный сканер (который
    # забирает только pending) уже никогда его не подхватит. Здесь ждём, пока
    # сканер сам возьмёт задание в своём цикле опроса.
    task_id = create_task(api_client, manager_url, str(test_files_dir))
    assert task_id, "Задание не создано"
    cleanup_tasks.append(task_id)

    # Ждём выполнения реальным сканером (бюджет < лимита теста, см. docstring)
    status = wait_task_status(
        api_client, manager_url, task_id, "completed", timeout=240, interval=4
    )
    assert status in ("completed", "running"), f"Задание не завершилось: {status}"
    if status != "completed":
        pytest.skip("Сканер не завершил задание за таймаут (проверьте :9101 и MANAGER_URL)")

    findings = _get_findings(api_client, manager_url, task_id, expect=1, timeout=60)
    assert findings, f"Сканер не прислал находки: {task_id}"

    # Проверяем контракт ответа /api/findings.
    # BUG-096b (TASK-065, v3.13.25): ассерт на finding["fingerprint"] был
    # устаревшим — Manager отдаёт явный whitelist полей (_finding_to_dict), и
    # fingerprint (внутренний ключ дедупликации) в ответ не входит; наружу он
    # доступен только через POST /api/findings/check-fingerprints.
    f = findings[0]
    assert f["status"] == "new", f["status"]
    assert "has_encrypted" in f
    assert f["severity"], "Пустой severity"
    assert f["finding_type"] in ("pii", "credentials", "code"), f["finding_type"]
    assert f["category"], "Пустая категория"
