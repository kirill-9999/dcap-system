"""Тесты BUG-265/266/267 + BUG-270/271 (v3.14.4, UI hotfix).

Статические проверки исходников WebUI (Jinja2-шаблоны, JS, CSS) — без поднятого стека.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_js_checks_role():
    """BUG-265: dashboard.js содержит RBAC-проверку canAudit перед /api/audit/*."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    assert "canAudit" in src, "dashboard.js должен проверять роль"
    assert "Auth.hasRole" in src or "Auth.me" in src


def test_api_js_skips_403_in_console():
    """BUG-266: api.js не логирует 403 в console (ожидаемое RBAC-ограничение)."""
    src = (ROOT / "webui/static/js/api.js").read_text(encoding="utf-8")
    assert "status !== 403" in src or "status === 403" in src


def test_users_responsive_css():
    """BUG-270/271: users table обёрнута в .table-responsive-users."""
    tpl = (ROOT / "webui/templates/users.html").read_text(encoding="utf-8")
    assert "table-responsive-users" in tpl, "users.html: .table-responsive-users"
    css = (ROOT / "webui/static/css/components/tables.css").read_text(encoding="utf-8")
    assert "table-responsive-users" in css, "tables.css: правило для .table-responsive-users"


def test_dashboard_has_audit_charts_id():
    """BUG-267: dashboard.html содержит контейнер #auditCharts для плашки «Нет прав»."""
    tpl = (ROOT / "webui/templates/dashboard.html").read_text(encoding="utf-8")
    assert 'id="auditCharts"' in tpl or "chartAuditTypes" in tpl
