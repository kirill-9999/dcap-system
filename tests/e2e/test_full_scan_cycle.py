# tests/e2e/test_full_scan_cycle.py
import time

import pytest

from fixtures.manager import create_task, get_task, wait_task_assigned, wait_task_status

# BUG-096b (TASK-065, v3.13.25): после рефакторинга Findings (v3.13.22) API
# отдаёт ДВА независимых поля:
#   finding_type — крупная группа: pii | credentials | code
#   category     — гранулярная категория детектора: email, phone, aws_key, ...
# Тест читал f.get("type") (поля нет) → fallback на category, и искал в
# гранулярных категориях подстроки "pii"/"cred" — падал на любых реальных
# данных ({email, person, phone, aws_key}). Проверяем оба поля корректно.
KNOWN_FINDING_TYPES = {"pii", "credentials", "code"}
KNOWN_CATEGORIES = {
    # pii
    "email", "phone", "person", "inn", "snils", "passport", "credit_card",
    "date_time", "organization", "address", "ip_address", "account_number",
    "bank_account", "license_plate", "mac_address", "url",
    # credentials
    "password", "api_key", "aws_key", "jwt_token", "github_token", "slack_token",
    "token", "basic_auth", "database_url", "high_entropy", "private_key",
    "ssh_key", "certificate", "slack_webhook", "azure_key", "gcp_key",
    "nifi_credentials", "confluence_token", "jenkins_token", "openai_key",
    "anthropic_key", "telegram_bot_token", "sendgrid_key", "mailgun_key",
    "stripe_key", "twilio_key", "huggingface_key", "npm_token", "pypi_token",
    # code
    "hardcoded_secret", "connection_string",
}


@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_full_scan_cycle(api_client, manager_url, test_files_dir, cleanup_tasks):
    """
    E2E: создание задания → сканирование → результаты → находки.

    Предусловие: Manager + Scanner запущены, сканер зарегистрирован.
    """
    # 1. Проверяем, что сканер зарегистрирован
    r = api_client.get(f"{manager_url}/api/scanners")
    assert r.status_code == 200
    scanners = r.json()
    if not scanners:
        pytest.skip("Нет зарегистрированных сканеров")
    scanner_id = scanners[0]["id"]

    # 2. Создаём задание
    task_id = create_task(api_client, manager_url, str(test_files_dir))
    assert task_id, "Create task failed: task_id not returned"
    cleanup_tasks.append(task_id)

    # 3. Ждём назначения сканеру
    status = wait_task_assigned(api_client, manager_url, task_id, timeout=60)
    assert status in ("assigned", "running", "completed"), f"Task stuck: {status}"

    # 4. Ждём завершения (сканирование 4 файлов — быстро)
    status = wait_task_status(api_client, manager_url, task_id, "completed", timeout=300)
    if status == "failed":
        pytest.fail(f"Task failed: {get_task(api_client, manager_url, task_id)}")
    assert status == "completed", f"Task not completed: {status}"

    # 5. Проверяем прогресс (День 39)
    task = get_task(api_client, manager_url, task_id)
    assert task.get("progress") is not None or task.get("files_scanned", 0) > 0, (
        f"No progress/files_scanned: {task}"
    )

    # 6. Проверяем находки (фильтр по task_id)
    r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id})
    assert r.status_code == 200, f"GET findings: {r.status_code} {r.text}"
    findings = r.json()
    assert len(findings) > 0, "No findings detected"

    # 7. Проверяем классификацию находок (BUG-096b)
    #    finding_type — крупная группа, category — гранулярная категория.
    finding_types = {f.get("finding_type") for f in findings} - {None}
    categories = {f.get("category") for f in findings} - {None}

    assert finding_types, f"у находок нет finding_type: {findings[:2]}"
    assert finding_types <= KNOWN_FINDING_TYPES, f"неизвестный finding_type: {finding_types}"
    assert categories, f"у находок нет category: {findings[:2]}"
    unknown = categories - KNOWN_CATEGORIES
    assert not unknown, (
        f"неизвестные category {unknown}; находки: {[f.get('category') for f in findings]}"
    )
    assert any(t in ("pii", "credentials") for t in finding_types), (
        f"Expected PII/credentials findings, got finding_type={finding_types}, "
        f"category={categories}"
    )


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_task_progress_updates(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Прогресс задания появляется в API (heartbeat, День 39).

    Без сканера задача остаётся в статусе 'created' и не завершается —
    проверяем, что API корректно отдаёт пустой progress и статус.
    """
    task_id = create_task(api_client, manager_url, str(test_files_dir))
    assert task_id
    cleanup_tasks.append(task_id)

    r = api_client.get(f"{manager_url}/api/tasks/{task_id}", timeout=10)
    assert r.status_code == 200
    task = r.json()

    assert task.get("id") == task_id
    assert task.get("status") in ("pending", "assigned", "running", "completed", "failed")
    progress = task.get("progress")
    if progress:
        assert isinstance(progress, dict)