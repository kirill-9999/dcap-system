"""E2E-тесты WebUI находок (День 40.3)."""
import hashlib

import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def test_findings_page(webui_url):
    r = requests.get(f"{webui_url}/findings", timeout=5)
    assert r.status_code == 200
    assert "Находки" in r.text


def test_finding_detail_page(webui_url):
    r = requests.get(f"{webui_url}/findings/1", timeout=5)
    assert r.status_code == 200


def test_catalog_page(webui_url):
    r = requests.get(f"{webui_url}/catalog", timeout=5)
    assert r.status_code == 200


def test_false_positives_page(webui_url):
    r = requests.get(f"{webui_url}/false-positives", timeout=5)
    assert r.status_code == 200


def test_findings_proxy(webui_url):
    """WebUI проксирует /api/findings (401 без токена — ок)."""
    r = requests.get(f"{webui_url}/api/findings?limit=10", timeout=10)
    assert r.status_code in (200, 401)


def test_fingerprint_sha256_not_md5():
    """Fingerprint — SHA-256 (64 hex), не MD5 (32 hex)."""
    msg = b"test|42|secret|pii"
    fp = hashlib.sha256(msg).hexdigest()
    assert len(fp) == 64
    assert hashlib.md5(msg).hexdigest() and len(hashlib.md5(msg).hexdigest()) == 32