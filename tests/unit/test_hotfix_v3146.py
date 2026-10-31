"""BUG-NEW-4 (v3.14.6): checkAuditAccess — fail-safe, без fallback на RBAC."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "webui/static/js/dashboard.js"


def _check_audit_body() -> str:
    src = DASHBOARD.read_text(encoding="utf-8")
    m = re.search(r"async function checkAuditAccess\(\)\s*\{.*?\n\}", src, re.S)
    assert m, "checkAuditAccess() не найдена в dashboard.js"
    return m.group(0)


def test_dashboard_check_audit_no_rbac_fallback():
    """BUG-NEW-4: checkAuditAccess() не использует RBAC.isAuditor() как fallback."""
    body = _check_audit_body()
    assert "RBAC.isAuditor" not in body, (
        "RBAC.isAuditor() не должен использоваться в checkAuditAccess() — "
        "только Auth.me(), иначе viewer получает ложный доступ."
    )


def test_dashboard_check_audit_uses_auth_me():
    """BUG-NEW-4: checkAuditAccess() использует Auth.me() как единственный источник ролей."""
    body = _check_audit_body()
    assert "Auth.me()" in body or "Auth.me(" in body


def test_dashboard_check_audit_returns_false_on_error():
    """BUG-NEW-4: fail-safe — при ошибке Auth.me() возвращает false (не throw)."""
    body = _check_audit_body()
    assert "return false" in body, (
        "checkAuditAccess() должна содержать return false (fail-safe) "
        "при недоступности Auth.me() или ошибке."
    )