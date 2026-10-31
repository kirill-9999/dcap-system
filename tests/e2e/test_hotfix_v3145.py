import pytest
import requests


@pytest.mark.e2e
def test_dashboard_kpi_mobile(webui_url):
    """BUG-273: На дашборде есть контейнер kpiRow."""
    html = requests.get(f"{webui_url}/", timeout=10).text
    assert "kpiRow" in html


@pytest.mark.e2e
def test_settings_last_run(webui_url):
    """BUG-NEW-6: На странице настроек есть элемент lastRun."""
    html = requests.get(f"{webui_url}/settings", timeout=10).text
    assert 'id="lastRun"' in html
