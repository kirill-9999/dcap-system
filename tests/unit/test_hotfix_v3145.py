"""Tests for BUG-NEW-4/5/6/7, BUG-273, BUG-272 (v3.14.5)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_rbac_uses_auth_me():
    """BUG-NEW-4: dashboard.js использует Auth.me() для надежной проверки ролей."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    assert "Auth.me()" in src, "dashboard.js должен использовать Auth.me()"


def test_api_skips_401_redirect_change_password():
    """BUG-NEW-5: api.js не делает редирект на /login при 401 для change-password."""
    src = (ROOT / "webui/static/js/api.js").read_text(encoding="utf-8")
    assert "change-password" in src


def test_settings_has_last_run():
    """BUG-NEW-6: settings.html содержит элемент для lastRun."""
    tpl = (ROOT / "webui/templates/settings.html").read_text(encoding="utf-8")
    assert 'id="lastRun"' in tpl


def test_settings_counters_have_spacing():
    """BUG-NEW-7: добавлен отступ у stat-label."""
    tpl = (ROOT / "webui/templates/settings.html").read_text(encoding="utf-8")
    assert "stat-label me-2" in tpl


def test_kpi_cards_mobile_css():
    """BUG-273: CSS для KPI-карточек на мобильных."""
    css = (ROOT / "webui/static/css/main.css").read_text(encoding="utf-8")
    assert "max-width: 480px" in css
    assert ".kpi-grid" in css
