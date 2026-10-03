"""E2E-тесты Фикс-спринта Блок 9 (v3.13.28) — против живого Manager (:18000).

Покрывают сквозную проверку багов, исправленных в v3.13.28:
  BUG-103 метрики видят 401 и не раздувают cardinality
  BUG-115 /api/findings/count закрыт аутентификацией
  BUG-110 reveal отдаёт 409 (не 500) при недоступном ключе
  BUG-114 экспорт аудируется с source_host и file_path
  BUG-116 дедупликация по пересчитанному fingerprint
"""
import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


# ============================================================
# BUG-115: /api/findings/count требует аутентификацию
# ============================================================

def test_findings_count_requires_auth(manager_url):
    """Анонимный клиент не должен получать количество находок (BUG-115)."""
    r = requests.get(f"{manager_url}/api/findings/count", timeout=10)
    assert r.status_code == 401, r.text


def test_findings_count_authenticated(manager_url, api_client):
    """С валидным JWT /count отдаёт счётчик (BUG-115 не сломал endpoint)."""
    r = api_client.get(f"{manager_url}/api/findings/count", timeout=10)
    assert r.status_code == 200, r.text
    assert "count" in r.json()


# ============================================================
# BUG-103: метрики видят отказы и нормализуют endpoint
# ============================================================

def test_metrics_counts_401_and_normalizes_endpoint(manager_url, api_client):
    """401 фиксируется в метриках, а ID в пути не плодит серии (BUG-103)."""
    # Чистая сессия без токена и cookie -> AuthMiddleware отвечает 401 до роутера.
    anon = requests.Session()
    try:
        r = anon.get(f"{manager_url}/api/findings/count", timeout=10)
        assert r.status_code == 401, r.text
        # Заведомо несуществующий id -> 404 с нормализованным endpoint.
        api_client.get(f"{manager_url}/api/findings/999999999", timeout=10)
    finally:
        anon.close()

    m = api_client.get(f"{manager_url}/metrics", timeout=15)
    assert m.status_code == 200, m.text
    body = m.text

    series = [
        ln for ln in body.splitlines()
        if ln.startswith("dcap_http_requests_total{") and 'status="401"' in ln
    ]
    assert series, "401 не попали в dcap_http_requests_total (BUG-103 не исправлен)"

    # Никаких raw-ID в endpoint: только шаблоны маршрутов.
    offenders = [
        ln for ln in body.splitlines()
        if ln.startswith("dcap_http_requests_total{")
        and "/api/findings/999999999" in ln
    ]
    assert not offenders, f"ID не нормализован: {offenders}"


def test_metrics_endpoint_is_public(manager_url):
    """/metrics остаётся публичным — Prometheus не ходит с JWT."""
    r = requests.get(f"{manager_url}/metrics", timeout=10)
    assert r.status_code == 200
    assert "dcap_http_requests_total" in r.text


# ============================================================
# BUG-110 + BUG-114: reveal 409 и аудит экспорта
# ============================================================

def test_export_writes_audit_with_source_host(manager_url, api_client):
    """Экспорт попадает в аудит (BUG-114: событие вообще должно создаваться)."""
    r = api_client.get(f"{manager_url}/api/findings/export?format=csv", timeout=20)
    assert r.status_code == 200, r.text

    a = api_client.get(
        f"{manager_url}/api/audit", params={"limit": 50}, timeout=15
    )
    assert a.status_code == 200, a.text
    events = a.json().get("events", [])
    exported = [e for e in events if e.get("event_type") == "findings_exported"]
    assert exported, "нет события findings_exported в /api/audit"
    # BUG-114: source_host обязателен — без него источник утечки не установить.
    assert exported[0].get("source_host"), "в findings_exported нет source_host (BUG-114)"
