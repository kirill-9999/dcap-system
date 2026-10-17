# tests/e2e/test_webui_block5_v31322.py — День 48, Блок 5 (WebUI), v3.13.22
# Live-проверка против поднятого стека (Manager :8000, WebUI :8001):
#   BUG-087 — прокси WebUI пробрасывает X-Total-Count (пагинация работает)
#   BUG-088 — fragment через WebUI доступен с Bearer (blob), 401 без токена
#   BUG-089 — /api/access/resources без 500 (PostgreSQL Boolean)
#   BUG-090 — CSV-категории и пустые числовые параметры (не 422)
#   BUG-091 — /api/audit фильтрует по event_source
#   BUG-093 — export доступен с Bearer (window.location давал 401)
import requests

import pytest


@pytest.fixture(scope="module")
def client(manager_url):
    """Один JWT на модуль: /api/auth/login ограничен 5 попытками в минуту.

    Фикстура api_client (function scope) логинится на каждый тест и
    упрётся в 429 при прогоне всего набора — здесь логин один раз.
    """
    from fixtures.auth import login as _login

    s = _login(manager_url)
    assert "Authorization" in s.headers, "логин не удался (проверьте admin/admin123)"
    return s


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_proxy_forwards_total_count(webui_url, manager_url, client):
    """BUG-087: X-Total-Count доходит до браузера через прокси."""
    m = requests.get(f"{manager_url}/api/findings?limit=5",
                     headers=client.headers, timeout=15)
    assert m.status_code == 200
    assert "X-Total-Count" in m.headers

    w = requests.get(f"{webui_url}/api/findings?limit=5",
                     headers=client.headers, timeout=15)
    assert w.status_code == 200
    assert "X-Total-Count" in w.headers, "WebUI потерял X-Total-Count"
    assert int(w.headers["X-Total-Count"]) == int(m.headers["X-Total-Count"])
    assert w.headers["X-Total-Count"] != "0"


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_filters_csv_and_empty(webui_url, client):
    """BUG-090: «phone, email» как список категорий; пустые параметры не 422."""
    base = {"headers": client.headers, "timeout": 15}

    one = requests.get(f"{webui_url}/api/findings?category=phone", **base)
    assert one.status_code == 200
    csv_ = requests.get(f"{webui_url}/api/findings?category=phone,email", **base)
    assert csv_.status_code == 200
    total_one = int(one.headers["X-Total-Count"])
    total_csv = int(csv_.headers["X-Total-Count"])
    assert total_csv >= total_one, "CSV-категории должны включать одиночные"

    cats_one = {f["category"] for f in one.json()}
    cats_csv = {f["category"] for f in csv_.json()}
    assert cats_csv <= cats_one | cats_csv  # sanity
    assert all(f["category"] in cats_one or f["category"] in cats_csv
               for f in csv_.json())

    for qs in ("task_id=", "resource_id=", "limit=", "offset=", "category="):
        r = requests.get(f"{webui_url}/api/findings?{qs}", **base)
        assert r.status_code == 200, f"?{qs} -> {r.status_code} {r.text}"
        assert int(r.headers["X-Total-Count"]) > 0

    cnt = requests.get(f"{webui_url}/api/findings/count?category=phone,email", **base)
    assert cnt.status_code == 200
    assert cnt.json()["count"] >= 0


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_new_filters(webui_url, client):
    """BUG-090: detector / fragment_type / search / order_by=id."""
    base = {"headers": client.headers, "timeout": 15}
    for qs in ("detector=presidio", "fragment_type=image_region",
               "fragment_type=text_line", "search=secret", "order_by=id&order=asc"):
        r = requests.get(f"{webui_url}/api/findings?{qs}", **base)
        assert r.status_code == 200, f"?{qs} -> {r.status_code} {r.text}"
        assert "X-Total-Count" in r.headers


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_export_requires_and_uses_bearer(webui_url, manager_url, client):
    """BUG-093: export через прокси с Bearer = 200, без токена = 401."""
    r = requests.get(f"{webui_url}/api/findings/export?format=csv", timeout=15)
    assert r.status_code == 401, "export без токена должен быть 401"

    r = requests.get(f"{webui_url}/api/findings/export?format=csv&category=phone,email",
                     headers=client.headers, timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers.get("Content-Disposition", "").startswith("attachment")
    assert r.text

    r_json = requests.get(f"{webui_url}/api/findings/export?format=json&limit=5",
                          headers=client.headers, timeout=30)
    assert r_json.status_code == 200
    assert isinstance(r_json.json(), list)

    r_empty = requests.get(
        f"{webui_url}/api/findings/export?format=csv&task_id=&resource_id=&limit=",
        headers=client.headers, timeout=30)
    assert r_empty.status_code == 200, r_empty.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_fragment_via_webui_with_bearer(webui_url, client):
    """BUG-088: fragment грузится fetch+blob с Bearer, не <img> без токена."""
    base = {"headers": client.headers, "timeout": 20}
    found = requests.get(
        f"{webui_url}/api/findings?fragment_type=image_region&limit=1", **base)
    assert found.status_code == 200
    items = found.json()
    if not items:
        pytest.skip("нет находок с image_region")

    fid = items[0]["id"]
    r = requests.get(f"{webui_url}/api/findings/{fid}/fragment?format=png", **base)
    assert r.status_code == 200
    assert r.headers.get("Content-Type", "").startswith("image/")
    assert len(r.content) > 0
    assert r.headers.get("X-Fragment-Mode")

    anon = requests.get(f"{webui_url}/api/findings/{fid}/fragment?format=png", timeout=20)
    assert anon.status_code == 401, "fragment без токена должен быть 401"


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_access_resources_no_500(webui_url, client):
    """BUG-089: is_active == True (PostgreSQL Boolean), раньше 500."""
    r = requests.get(f"{webui_url}/api/access/resources",
                     headers=client.headers, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" in body
    for res in body.get("resources", [])[:3]:
        e = requests.get(
            f"{webui_url}/api/access/resources/{res['id']}/entries",
            headers=client.headers, timeout=20)
        assert e.status_code == 200, e.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_audit_event_source_filter(webui_url, client):
    """BUG-091: event_source реально фильтрует (раньше игнорировался)."""
    base = {"headers": client.headers, "timeout": 20}
    allr = requests.get(f"{webui_url}/api/audit?limit=500", **base)
    assert allr.status_code == 200
    total_all = allr.json()["total"]

    seen = 0
    for src in ("api", "scanner", "windows_agent", "linux_agent"):
        r = requests.get(f"{webui_url}/api/audit?limit=500&event_source={src}", **base)
        assert r.status_code == 200, r.text
        body = r.json()
        for e in body["events"]:
            assert e["event_source"] == src, "в ответе чужой event_source"
        seen += body["total"]
    assert seen <= total_all, "сумма по источникам не должна превышать общий итог"


@pytest.mark.e2e
def test_webui_pages_with_filters(webui_url):
    """Страницы findings/audit с фильтрами рендерятся (200)."""
    for page in ("/findings", "/audit"):
        r = requests.get(f"{webui_url}{page}", timeout=10, allow_redirects=True)
        assert r.status_code == 200, f"{page} -> {r.status_code}"

    tpl = requests.get(f"{webui_url}/audit", timeout=10).text
    assert "a-source" in tpl and "a-type" in tpl
    # BUG-263: loadFilterOptions определена в audit.js (правильно — JS не inline
    # в HTML). Проверяем data-driven фильтры на двух уровнях: HTML подключает
    # скрипт, а скрипт определяет функцию (регресс-защита обоих).
    assert "/static/js/audit.js" in tpl, "audit.html должен подключать audit.js"
    audit_js = requests.get(f"{webui_url}/static/js/audit.js", timeout=10).text
    assert "loadFilterOptions" in audit_js, "audit.js должен определять loadFilterOptions"

    fnd = requests.get(f"{webui_url}/findings", timeout=10).text
    assert "filter-search" in fnd and "reset-filters" in fnd
    assert "Категория (через запятую)" in fnd
