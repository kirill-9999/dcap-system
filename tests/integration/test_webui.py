import requests
import pytest


class TestWebUIDashboard:
    def test_homepage(self, webui_url):
        r = requests.get(webui_url, timeout=10)
        assert r.status_code == 200
        assert "DCAP" in r.text

    def test_homepage_no_cache(self, webui_url):
        r = requests.get(webui_url, timeout=10)
        assert r.headers.get("Cache-Control") == "no-store"

    def test_dashboard_elements(self, webui_url):
        r = requests.get(webui_url, timeout=10)
        html = r.text
        assert "page-dashboard" in html
        assert "total-findings" in html
        assert "active-scanners" in html
        assert "dashboard-audit-agents" in html


class TestWebUIPages:
    def test_findings_page(self, webui_url):
        r = requests.get(f"{webui_url}/findings", timeout=10)
        assert r.status_code == 200
        assert "page-findings" in r.text

    def test_tasks_page(self, webui_url):
        r = requests.get(f"{webui_url}/tasks", timeout=10)
        assert r.status_code == 200
        assert "page-tasks" in r.text

    def test_scanners_page(self, webui_url):
        r = requests.get(f"{webui_url}/scanners", timeout=10)
        assert r.status_code == 200
        assert "page-scanners" in r.text
        assert "agents-table" in r.text

    def test_resources_page(self, webui_url):
        r = requests.get(f"{webui_url}/resources", timeout=10)
        assert r.status_code == 200
        assert "page-resources" in r.text


class TestWebUIAPIs:
    def test_stats(self, webui_url):
        r = requests.get(f"{webui_url}/api/stats", timeout=10)
        assert r.status_code == 200
        assert "total_findings" in r.json()

    def test_findings(self, webui_url):
        r = requests.get(f"{webui_url}/api/findings", timeout=10)
        assert r.status_code == 200

    def test_tasks(self, webui_url):
        r = requests.get(f"{webui_url}/api/tasks", timeout=10)
        assert r.status_code == 200

    def test_scanners(self, webui_url):
        r = requests.get(f"{webui_url}/api/scanners", timeout=10)
        assert r.status_code == 200

    def test_resources(self, webui_url):
        r = requests.get(f"{webui_url}/api/resources", timeout=10)
        assert r.status_code == 200

    def test_audit(self, webui_url):
        r = requests.get(f"{webui_url}/api/audit", timeout=10)
        assert r.status_code == 200

    def test_audit_stats(self, webui_url):
        r = requests.get(f"{webui_url}/api/audit/stats", timeout=10)
        assert r.status_code == 200

    def test_audit_agents(self, webui_url):
        r = requests.get(f"{webui_url}/api/audit/agents", timeout=10)
        assert r.status_code == 200
        assert "total" in r.json()

    def test_audit_report_preview(self, webui_url):
        r = requests.post(
            f"{webui_url}/api/audit/report/preview",
            json={"days": 7},
            timeout=10,
        )
        assert r.status_code == 200
        assert "total" in r.json()

    def test_audit_report_excel(self, webui_url):
        r = requests.post(
            f"{webui_url}/api/audit/report/export/excel",
            json={"days": 7},
            timeout=10,
        )
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("Content-Type", "")

    def test_audit_report_pdf(self, webui_url):
        r = requests.post(
            f"{webui_url}/api/audit/report/export/pdf",
            json={"days": 7},
            timeout=10,
        )
        assert r.status_code == 200
        assert "pdf" in r.headers.get("Content-Type", "")


class TestWebUIVendor:
    def test_bootstrap_css(self, webui_url):
        r = requests.get(f"{webui_url}/static/vendor/css/bootstrap.min.css", timeout=10)
        assert r.status_code == 200

    def test_fontawesome(self, webui_url):
        r = requests.get(f"{webui_url}/static/vendor/css/fontawesome.min.css", timeout=10)
        assert r.status_code == 200

    def test_chartjs(self, webui_url):
        r = requests.get(f"{webui_url}/static/vendor/js/chart.umd.min.js", timeout=10)
        assert r.status_code == 200
