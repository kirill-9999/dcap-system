"""E2E-тест BACKLOG-086 (v3.13.19): фрагмент переживает удаление исходника.

Сценарий ТЗ:
  1. Найти OCR-finding (image_region) с встроенным фрагментом
  2. GET /fragment → 200, X-Fragment-Mode: embedded
  3. Удалить исходный PNG с хоста
  4. GET /fragment → всё ещё 200 (доказательство в БД)
  5. GET /fragment/hash → hash совпадает с X-Fragment-Hash
"""
import os

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def _find_embedded_ocr_id(api_client, manager_url):
    """Ищет image_region finding с встроенным фрагментом (has_fragment + bbox пусто)."""
    r = api_client.get(f"{manager_url}/api/findings", params={"limit": 1000}, timeout=10)
    if r.status_code != 200:
        return None
    for f in r.json() or []:
        if f.get("fragment_type") != "image_region":
            continue
        if not f.get("has_fragment"):
            continue
        if f.get("bounding_box"):
            continue  # встроенные (bbox=None) — это сценарий внедрения
        return f["id"]
    return None


def test_fragment_survives_source_deletion(manager_url, api_client):
    """BACKLOG-086: «Файл удалили — доказательство осталось»."""
    fid = _find_embedded_ocr_id(api_client, manager_url)
    if fid is None:
        pytest.skip("No embedded image_region finding in test data")

    # 1) Находим исходный путь
    r = api_client.get(f"{manager_url}/api/findings/{fid}", timeout=10)
    assert r.status_code == 200
    src = r.json().get("file_path") or r.json().get("fragment_path")
    assert src, "finding.file_path required"

    # 2) Фрагмент из БД (embedded)
    frag = api_client.get(f"{manager_url}/api/findings/{fid}/fragment", timeout=10)
    assert frag.status_code == 200
    assert frag.headers.get("X-Fragment-Mode") == "embedded"
    api_hash = frag.headers.get("X-Fragment-Hash")
    assert api_hash

    # 3+4) Удаляем исходник и повторяем запрос (восстановление в finally)
    backup = None
    try:
        if os.path.isfile(src):
            with open(src, "rb") as f:
                backup = f.read()
            os.remove(src)

        after = api_client.get(f"{manager_url}/api/findings/{fid}/fragment", timeout=10)
        assert after.status_code == 200, "фрагмент должен быть доступен после удаления исходника"
        assert after.headers.get("X-Fragment-Mode") == "embedded"
        assert after.content.startswith(b"\x89PNG\r\n\x1a\n")
    finally:
        if backup is not None:
            with open(src, "wb") as f:
                f.write(backup)

    # 5) Hash-endpoint совпадает
    meta = api_client.get(f"{manager_url}/api/findings/{fid}/fragment/hash", timeout=10)
    assert meta.status_code == 200
    body = meta.json()
    assert body["hash"] == api_hash
    assert body["size"] == len(after.content)
    assert body["mime"] == "image/png"