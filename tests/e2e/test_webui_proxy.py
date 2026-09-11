# tests/e2e/test_webui_proxy.py
import pytest
import requests


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_webui_proxy(webui_url, api_client, manager_url):
    """WebUI проксирует запросы в Manager.

    /api/stats в Manager защищён JWT (AuthMiddleware), поэтому без токена
    WebUI возвращает 401, а с Bearer-токеном — 200.
    """
    # 1. Health WebUI
    r = requests.get(f"{webui_url}/health", timeout=5)
    assert r.status_code == 200

    # 2. Без токена — 401 (защищённый endpoint, прокси не подменяет ответ)
    r = requests.get(f"{webui_url}/api/stats", timeout=10)
    assert r.status_code == 401

    # 3. Прокси с авторизацией: Bearer-заголовок пробрасывается в Manager
    r = requests.get(f"{webui_url}/api/stats", headers=api_client.headers, timeout=10)
    assert r.status_code == 200, f"WebUI proxy /api/stats: {r.status_code} {r.text}"
    assert isinstance(r.json(), dict)


@pytest.mark.e2e
def test_webui_pages_render(webui_url):
    """Страницы WebUI рендерятся (200).

    Дашборд — это корень '/'; '/' + '/login' + '/catalog' покрывают
    страницы с рендером шаблонов.
    """
    for page in ["/", "/login", "/catalog"]:
        r = requests.get(f"{webui_url}{page}", timeout=5, allow_redirects=True)
        assert r.status_code == 200, f"Page {page} failed: {r.status_code}"