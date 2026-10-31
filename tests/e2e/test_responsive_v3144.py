"""E2E: responsive + RBAC-фронт (v3.14.4).

BUG-270/271 — /users: таблица в .table-responsive-users (горизонтальный скролл).
BACKLOG-324 — /findings: панель фильтров #filtersCollapse под кнопкой.
BUG-267 — / (dashboard): контейнер #auditCharts для плашки «Нет прав на аудит».
BUG-266 — api.js: нет console-спама на 403.
"""
import requests

import pytest


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_users_has_table_responsive(webui_url):
    """BUG-270/271: users.html содержит .table-responsive-users."""
    r = requests.get(f"{webui_url}/users", timeout=10)
    assert r.status_code == 200
    assert "table-responsive-users" in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_has_filters_collapse(webui_url):
    """BACKLOG-324: findings.html содержит #filtersCollapse + кнопку-тоггл."""
    r = requests.get(f"{webui_url}/findings", timeout=10)
    assert r.status_code == 200
    assert 'id="filtersCollapse"' in r.text
    assert "filters-toggle" in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_dashboard_has_audit_charts(webui_url):
    """BUG-267: dashboard.html содержит контейнер #auditCharts."""
    r = requests.get(f"{webui_url}/", timeout=10)
    assert r.status_code == 200
    assert 'id="auditCharts"' in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_api_js_skips_403_in_console(webui_url):
    """BUG-266: api.js не логирует 403 (проверка status !== 403)."""
    js = requests.get(f"{webui_url}/static/js/api.js", timeout=10).text
    assert "status !== 403" in js or "status === 403" in js
