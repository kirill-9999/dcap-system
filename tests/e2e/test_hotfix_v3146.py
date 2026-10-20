"""BUG-NEW-4 (v3.14.6): dashboard.js без RBAC.isAuditor в checkAuditAccess."""
import re
import pytest
import requests


@pytest.mark.e2e
def test_dashboard_js_has_no_rbac_fallback(webui_url):
    js = requests.get(f"{webui_url}/static/js/dashboard.js", timeout=10).text
    m = re.search(r"async function checkAuditAccess\(\)\s*\{.*?\n\}", js, re.S)
    assert m, "checkAuditAccess() не найдена в собранном dashboard.js"
    assert "RBAC.isAuditor" not in m.group(0), (
        "В собранном dashboard.js есть RBAC.isAuditor в checkAuditAccess() — "
        "фикс не доехал до контейнера."
    )