# tests/e2e/test_audit_reveal_user_e2e.py — День 48.1, BUG-087 (аудит reveal), v3.13.23
#
# Live-проверка против поднятого стека (Manager :8000 / :18000).
#
# ТЗ утверждало: reveal под auditor пишет в audit_logs user="dcap".
# Диагностика (день 48.1) показала, что баг ложный: INSERT в PostgreSQL
# содержит реального пользователя, а "dcap" — это CURRENT_USER (роль БД),
# которая возвращалась некавыченным `SELECT user FROM audit_logs`.
#
# Тесты фиксируют правильное поведение и защищают от регрессии:
#   1. live-reveal под auditor → /api/audit отдаёт user == "auditor"
#   2. прямая SQL-проверка (если доступна БД) с кавычками `"user"`
#   3. API-значение совпадает со значением в БД
import os

import pytest
import requests

AUDITOR = ("auditor", "auditor123")
DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""


@pytest.fixture(scope="module")
def auditor(manager_url):
    """Один JWT на модуль: /api/auth/login — 5 попыток в минуту."""
    from fixtures.auth import login as _login

    s = _login(manager_url, AUDITOR[0], AUDITOR[1])
    if "Authorization" not in s.headers:
        pytest.skip("логин auditor не удался (проверьте auditor/auditor123)")
    me = requests.get(f"{manager_url}/api/auth/me", headers=s.headers, timeout=15)
    if me.status_code == 200 and me.json().get("username") != AUDITOR[0]:
        pytest.skip(f"роль {AUDITOR[0]} без прав auditor: {me.text}")
    return s


def _any_finding_id(manager_url, session):
    r = requests.get(f"{manager_url}/api/findings?limit=1", headers=session.headers, timeout=20)
    r.raise_for_status()
    items = r.json()
    if not items:
        pytest.skip("нет находок для reveal")
    return items[0]["id"]


def _last_audit_event(manager_url, session, event_type):
    r = requests.get(
        f"{manager_url}/api/audit?event_type={event_type}&limit=1",
        headers=session.headers,
        timeout=20,
    )
    r.raise_for_status()
    events = r.json().get("events") or []
    return events[0] if events else None


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_reveal_writes_correct_user(manager_url, auditor):
    """Live: reveal под auditor → audit_logs.user == 'auditor' (не 'dcap')."""
    fid = _any_finding_id(manager_url, auditor)

    r = requests.post(
        f"{manager_url}/api/findings/{fid}/reveal", headers=auditor.headers, timeout=30
    )
    assert r.status_code == 200, r.text
    assert r.json()["revealed_by"] == AUDITOR[0], r.text

    ev = _last_audit_event(manager_url, auditor, "finding_reveal")
    assert ev is not None, "нет записи finding_reveal в /api/audit"
    assert ev["user"] == AUDITOR[0], (
        f"audit_logs.user={ev['user']!r}, ожидался {AUDITOR[0]!r}"
    )
    assert ev["user"] != "dcap", "user == 'dcap' — это CURRENT_USER, а не пользователь"
    assert str(ev.get("metadata", {}).get("finding_id")) == str(fid)


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_reveal_user_stable_across_calls(manager_url, auditor):
    """Повторные reveal дают того же пользователя (нет подмены при длинных сессиях)."""
    fid = _any_finding_id(manager_url, auditor)
    seen = []
    for _ in range(3):
        r = requests.post(
            f"{manager_url}/api/findings/{fid}/reveal", headers=auditor.headers, timeout=30
        )
        assert r.status_code == 200, r.text
        seen.append(r.json()["revealed_by"])
    assert set(seen) == {AUDITOR[0]}, seen

    ev = _last_audit_event(manager_url, auditor, "finding_reveal")
    assert ev["user"] == AUDITOR[0]


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_sql_quoted_user_matches_api(manager_url, auditor):
    """Прямая SQL-проверка: "user" в кавычках == CURRENT_USER? НЕТ.

    Ключевой момент ТЗ: некавыченный `user` в PostgreSQL — это keyword
    CURRENT_USER (роль БД, "dcap"), а не колонка. Здесь сравниваем оба
    значения: колонка должна содержать логин, CURRENT_USER — имя роли.
    """
    psycopg2 = pytest.importorskip("psycopg2")
    if not DB_URL:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL не задана")

    fid = _any_finding_id(manager_url, auditor)
    r = requests.post(
        f"{manager_url}/api/findings/{fid}/reveal", headers=auditor.headers, timeout=30
    )
    assert r.status_code == 200, r.text

    conn = psycopg2.connect(DB_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT "user", user FROM audit_logs '
            "WHERE event_type = 'finding_reveal' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        assert row is not None, "нет записи finding_reveal"
        col_value, current_user = row
        cur.close()
    finally:
        conn.close()

    assert col_value == AUDITOR[0], f"колонка \"user\" = {col_value!r}"
    # Некавыченный user = CURRENT_USER (имя роли БД) — НЕ значение колонки.
    assert current_user != col_value, (
        "ожидалось расхождение: некавыченный user отдаёт CURRENT_USER, "
        "а кавыченный \"user\" — значение колонки"
    )
