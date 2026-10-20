📋 ТЗ v3.14.6 — Хотфикс RBAC Dashboard (53.4h)
Файл: prompts/tz/day_53_4h_dashboard_rbac_fix.md
Дата: 20.10.2026
Версия: v3.14.5 → v3.14.6
Приоритет: 🔴 Блокер v3.0.0
Длительность: 0.5 дня (2–4 часа)

🎯 Цель
Исправить BUG-NEW-4 (критично). Фикс из v3.14.5 (checkAuditAccess() через Auth.me()) не работает: под viewer запросы к /api/audit/* всё ещё уходят, получают 403, спамят консоль и вызывают тосты «Недостаточно прав».

🔍 Диагностика (что нужно проверить)
Открыть 3 файла и найти причину:

1. webui/static/js/main.js — функция RBAC.isAuditor()
Скорее всего, здесь ошибка. Проверить:

Возвращает ли RBAC.isAuditor() true для viewer?

Как хранятся роли? (строки ['viewer'] или объекты [{name: 'viewer'}]?)

Если roles — объекты, то roles.includes('admin') вернёт false для всех (даже для admin), но проверка может быть написана как roles.length > 0 → true для viewer.

2. webui/static/js/auth.js — функция Auth.me()
Проверить:

Что именно возвращает Auth.me(): {username, roles: [...]}?

Формат roles: ['admin', 'auditor'] или [{name: 'admin'}, {name: 'auditor'}]?

Что происходит, если Auth.me() вызывается до готовности сессии? Возвращает null, бросает исключение, возвращает {roles: []}?

3. webui/static/js/dashboard.js — функция checkAuditAccess()
Текущий код (v3.14.5):

javascript
async function checkAuditAccess() {
    try { if (window.whenSessionReady) await window.whenSessionReady(); } catch (e) {}
    if (typeof Auth !== 'undefined' && Auth.me) {
        const me = await Auth.me().catch(() => null);
        const roles = (me && me.roles) || [];
        return roles.includes('admin') || roles.includes('auditor');
    }
    if (typeof RBAC !== 'undefined' && RBAC.isAuditor) return RBAC.isAuditor();
    return false;
}
Возможные причины провала:

Auth.me() возвращает не массив строк, а массив объектов → includes('admin') всегда false → уходит в fallback RBAC.isAuditor() → тот возвращает true для viewer (баг в main.js).

Или Auth.me() на момент вызова возвращает null → roles = [] → return false → но тогда запросы не уходили бы (а они уходят). Значит, canAudit был true.

Значит, fallback RBAC.isAuditor() сработал и вернул true для viewer.

🛠️ Что нужно сделать (порядок действий)
Шаг 1. Диагностика (не менять код)
Выполнить в консоли браузера под viewer:

javascript
await Auth.me()
Ожидание: увидеть реальный формат roles. Прислать вывод в отчёте.

Выполнить под viewer:

javascript
RBAC.isAuditor()
Ожидание: увидеть, что возвращает. Если true — баг в RBAC.isAuditor(). Если false — баг в Auth.me() или в dashboard.js.

Шаг 2. Исправить checkAuditAccess() (fail-safe)
Переписать функцию так, чтобы она не полагалась на RBAC.isAuditor() вообще (он ненадёжен). Только на Auth.me():

javascript
async function checkAuditAccess() {
    try {
        if (window.whenSessionReady) {
            await Promise.race([
                window.whenSessionReady(),
                new Promise(r => setTimeout(r, 2000)), // максимум 2 сек
            ]);
        }
    } catch (e) { /* ignore */ }

    if (typeof Auth === 'undefined' || !Auth.me) return false;

    try {
        const me = await Auth.me();
        if (!me || !Array.isArray(me.roles)) return false;
        // Поддержка и строк, и объектов
        const names = me.roles.map(r => (typeof r === 'string' ? r : r.name));
        return names.includes('admin') || names.includes('auditor');
    } catch (e) {
        return false; // fail-safe: при ошибке — считаем, что прав нет
    }
}
Шаг 3. Исправить RBAC.isAuditor() в main.js (если он багованный)
javascript
isAuditor() {
    const me = (typeof Auth !== 'undefined' && Auth._me) ? Auth._me : null;
    if (!me || !Array.isArray(me.roles)) return false;
    const names = me.roles.map(r => (typeof r === 'string' ? r : r.name));
    return names.includes('admin') || names.includes('auditor');
}
(либо сделать RBAC.isAuditor() просто алиасом на checkAuditAccess())

Шаг 4. Пересборка + смена версии
powershell
# .env
VERSION=3.14.6

docker compose build webui
docker compose up -d webui
🧪 Тесты
Unit — tests/unit/test_hotfix_v3146.py (new)
python
"""BUG-NEW-4 (v3.14.6): checkAuditAccess — fail-safe."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_dashboard_check_audit_no_rbac_fallback():
    """BUG-NEW-4: checkAuditAccess() не использует RBAC.isAuditor() как fallback."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    # Должно быть только Auth.me(), без RBAC.isAuditor()
    assert "Auth.me()" in src
    # Проверяем, что функция не содержит вызова RBAC.isAuditor
    # (проверка грубая, но ловит регресс)
    import re
    m = re.search(r"async function checkAuditAccess\(\)\s*\{.*?\n\}", src, re.S)
    assert m, "checkAuditAccess() не найдена"
    body = m.group(0)
    assert "RBAC.isAuditor" not in body, "RBAC.isAuditor() не должен использоваться в checkAuditAccess()"

def test_dashboard_check_audit_handles_null_me():
    """BUG-NEW-4: при me=null возвращает false (fail-safe)."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    assert "return false" in src
    assert "Array.isArray" in src  # проверка формата roles

def test_rbac_is_auditor_uses_roles_array():
    """BUG-NEW-4: RBAC.isAuditor() проверяет roles через Array.isArray."""
    src = (ROOT / "webui/static/js/main.js").read_text(encoding="utf-8")
    assert "Array.isArray" in src or "roles.map" in src
E2E — tests/e2e/test_hotfix_v3146.py (new)
python
import pytest
import requests

@pytest.mark.e2e
def test_dashboard_viewer_no_audit_requests(webui_url):
    """BUG-NEW-4: HTML дашборда не содержит RBAC.isAuditor() (fallback убран)."""
    html = requests.get(f"{webui_url}/static/js/dashboard.js", timeout=10).text
    assert "RBAC.isAuditor" not in html, "RBAC.isAuditor не должен быть в dashboard.js"
📋 Ручная приёмка (после исправления)
Внимание: обязательно hard refresh (Ctrl+Shift+R) — браузер кеширует JS.

#	Сценарий	Ожидание
1	Viewer (viewer123) → /	Console: 0 ошибок 403
2	Viewer → /	Network (фильтр audit): 0 запросов к /api/audit/*
3	Viewer → /	KPI «Ресурсов»/«Агентов» = «—»
4	Viewer → /	Плашка «Нет прав на аудит» (вместо графиков аудита)
5	Admin (admin123) → /	Console: 0 ошибок, графики аудита отрисованы
6	Auditor (auditor123) → /	Console: 0 ошибок, графики аудита отрисованы
✅ Definition of Done
□ Auth.me() возвращает roles как массив (прислать формат в отчёте).
□ RBAC.isAuditor() для viewer возвращает false.
□ checkAuditAccess() не использует RBAC.isAuditor() (только Auth.me()).
□ checkAuditAccess() при me=null → return false.
□ Unit test_hotfix_v3146.py — 3 passed.
□ E2E test_hotfix_v3146.py — 1 passed.
□ Под viewer: Console = 0 ошибок 403, Network = 0 запросов к /api/audit/*.
□ Под admin/auditor: графики аудита отрисованы, 0 ошибок.
□ docker inspect dcap-webui = dcap/webui:3.14.6.
💾 Коммит
powershell
git add webui/static/js/dashboard.js webui/static/js/main.js webui/static/js/auth.js `
        tests/unit/test_hotfix_v3146.py tests/e2e/test_hotfix_v3146.py `
        .env docker-compose.yml `
        CHANGELOG.md STATE.md STATE_TEST_SESSION.md
git commit -m "fix: 53.4h dashboard RBAC — fail-safe checkAuditAccess (v3.14.6)

BUG-NEW-4: checkAuditAccess() больше не использует RBAC.isAuditor()
как fallback — только Auth.me(). При me=null → return false.
RBAC.isAuditor() исправлен для поддержки roles как массива объектов.

Tests: test_hotfix_v3146.py (3 unit), test_hotfix_v3146.py (1 e2e).
VERSION 3.14.6."