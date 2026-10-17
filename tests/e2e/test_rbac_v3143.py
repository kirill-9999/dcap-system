# tests/e2e/test_rbac_v3143.py — RBAC Hotfix & Security (ТЗ 53.4e, v3.14.3)
#
# Live-проверка против поднятого WebUI (и Manager):
#   BUG-253  — при редактировании себя чекбокс admin disabled.
#   BUG-254  — создание пользователя без ролей → валидация.
#   BUG-258  — кнопка «Создать роль» disabled (кастомные роли отключены).
#   BACKLOG-316 — модалка создания пользователя не показывает машинную роль scanner.
"""53.4e (v3.14.3): E2E-проверки RBAC-правок в WebUI.

Без браузера проверяются реально отдаваемые WebUI шаблоны/статика.
"""
import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def _users_js(webui_url):
    r = requests.get(f"{webui_url}/static/js/users.js", timeout=15)
    assert r.status_code == 200, r.text
    return r.text


def test_create_user_modal_hides_scanner(webui_url):
    """BACKLOG-316: машинная роль scanner не отображается в /users."""
    js = _users_js(webui_url)
    assert "r.name !== 'scanner'" in js, "users.js не фильтрует машинную роль scanner"
    assert "humanRoles" in js


def test_edit_self_admin_disabled(webui_url):
    """BUG-253: чекбокс роли admin блокируется при редактировании себя."""
    js = _users_js(webui_url)
    assert "isSelf && r.name === 'admin'" in js, "нет защиты admin-from-self"
    assert "Нельзя снять роль admin с себя" in js
    assert "{ isSelf }" in js, "флаг isSelf не передаётся в renderRolesCheckboxes"


def test_create_user_requires_role(webui_url):
    """BUG-254: создание пользователя без ролей блокируется на клиенте."""
    js = _users_js(webui_url)
    assert "roles.length === 0" in js
    assert "Выберите хотя бы одну роль" in js


def test_roles_create_button_disabled(webui_url):
    """BUG-258: кнопка «Создать роль» отключена (до v3.1.0)."""
    r = requests.get(f"{webui_url}/roles", timeout=15)
    assert r.status_code == 200, r.text
    html = r.text
    assert "Создать роль" in html
    assert "disabled" in html, "кнопка создания роли должна быть disabled"
    assert "BACKLOG-258" in html
