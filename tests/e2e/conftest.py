# tests/e2e/conftest.py — фикстуры E2E (День 40-41).
import pytest

from fixtures.scanner import get_scanner, list_scanners


@pytest.fixture
def scanners(api_client, manager_url):
    """Список зарегистрированных сканеров (пустой список — нет сканеров)."""
    return list_scanners(api_client, manager_url)


@pytest.fixture
def first_active_scanner(api_client, manager_url):
    """Первый активный сканер; skip, если сканеров нет (требуется сканер)."""
    from fixtures.scanner import get_scanner as _get

    scanners = list_scanners(api_client, manager_url)
    if not scanners:
        pytest.skip("Нет зарегистрированных сканеров")
    scanner_id = scanners[0]["id"]
    info = _get(api_client, manager_url, scanner_id)
    if info.get("status") != "active":
        pytest.skip(f"Сканер {scanner_id} не active: {info.get('status')}")
    return info