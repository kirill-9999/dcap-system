"""E2E-тесты фрагментов находок (День 40.4)."""
import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def _find_fragment_id(api_client, manager_url, fragment_type, with_hex=False):
    """Ищет находку нужного fragment_type в /api/findings (admin)."""
    r = api_client.get(f"{manager_url}/api/findings", params={"limit": 1000}, timeout=10)
    if r.status_code != 200:
        return None
    for f in r.json() or []:
        if f.get("fragment_type") != fragment_type:
            continue
        if with_hex and not f.get("hex_preview") and not (f.get("has_fragment") and f.get("byte_offset") is not None):
            continue
        return f["id"]
    return None


def test_image_region_fragment(manager_url, api_client):
    """image_region → PNG."""
    fid = _find_fragment_id(api_client, manager_url, "image_region")
    if fid is None:
        pytest.skip("No image_region finding in test data")
    r = api_client.get(f"{manager_url}/api/findings/{fid}/fragment")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_byte_range_hex(manager_url, api_client):
    """byte_range → hex-дамп."""
    fid = _find_fragment_id(api_client, manager_url, "byte_range", with_hex=True)
    if fid is None:
        pytest.skip("No byte_range finding in test data")
    r = api_client.get(f"{manager_url}/api/findings/{fid}/fragment?format=hex")
    assert r.status_code == 200
    assert "00000000" in r.text or "|" in r.text


def test_text_fragment_rejected(manager_url, api_client):
    """text_line → 400."""
    fid = _find_fragment_id(api_client, manager_url, "text_line")
    if fid is None:
        pytest.skip("No text_line finding")
    r = api_client.get(f"{manager_url}/api/findings/{fid}/fragment")
    assert r.status_code == 400


def test_fragment_requires_auth(manager_url):
    """Без токена → 401."""
    r = requests.get(f"{manager_url}/api/findings/1/fragment", timeout=5)
    assert r.status_code == 401