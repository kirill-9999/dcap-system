"""E2E-тест BUG-086 (v3.13.21): контексты findings не содержат сырых секретов.

Сценарий: через API Manager проверить, что context_before / context_after
(API отдаёт уже маскированные значения) находок не содержат сырых
credentials/US-phone (ghp_, Basic base64, xoxb-, sk-, AKIA, +1 …).
Требует пересканированных данных (см. task 40 в ТЗ).
"""
import re

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]

# Сырые паттерны, которые НЕ должны встречаться в контекстах
_RAW_PATTERNS = {
    "github_token": r"ghp_[a-zA-Z0-9]{20,}",
    "basic_auth": r"Basic [A-Za-z0-9+/=]{10,}",
    "slack_token": r"xox[baprs]-[a-zA-Z0-9-]{10,}",
    "aws_key": r"AKIA[A-Z0-9]{16}",
    "api_key": r"sk-[a-zA-Z0-9-]{20,}",
    "us_phone": r"\+1[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}",
}
_RAW_RE = {k: re.compile(v) for k, v in _RAW_PATTERNS.items()}

_SCOPE = ("github_token", "slack_token", "aws_key", "api_key", "basic_auth",
          "database_url", "jwt_token", "phone", "password", "token")


def test_contexts_have_no_raw_secrets(manager_url, api_client):
    """BUG-086: в контекстах findings последнего скана нет сырых credentials."""
    r = api_client.get(f"{manager_url}/api/findings", params={"limit": 1000}, timeout=15)
    assert r.status_code == 200
    findings = r.json() or []
    # Старые findings (v<=3.13.19) могут содержать raw — BUG-086 мог их покрыть;
    # проверяем только findings последнего (актуального) скана.
    task_ids = {f.get("task_id") for f in findings if f.get("task_id")}
    if not task_ids:
        pytest.skip("Нет findings в системе")
    latest = max(task_ids)
    latest_findings = [f for f in findings if f.get("task_id") == latest]
    scoped = [f for f in latest_findings if f.get("category") in _SCOPE]
    if len(scoped) < 2:
        pytest.skip("Недостаточно findings категорий BUG-086 (пересканируйте, см. task 40)")

    checked = 0
    for f in scoped:
        cat = f.get("category")
        for field in ("context_before", "context_after"):
            ctx = f.get(field)
            if not ctx:
                continue
            for raw_name, rx in _RAW_RE.items():
                assert not rx.search(ctx), (
                    f"finding {f['id']} ({cat}) field {field}: сырой паттерн {raw_name}: {ctx!r}"
                )
            checked += 1
    assert checked > 0, "нет контекстов для проверки"