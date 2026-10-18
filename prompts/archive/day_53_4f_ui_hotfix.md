📋 ТЗ v3.14.4 — UI-фиксы (Responsive + Viewer)
Файл: prompts/tz/day_53_4f_ui_hotfix.md
Дата: 17.10.2026
Версия: v3.14.3 → v3.14.4
Приоритет: 🔴 Блокер v3.0.0 (UX / Responsive / RBAC)
Длительность: 0.5–1 день
Источник: Верификация WebUI (блоки 15, 17)
Отчёт: prompts/reports/day_53_4f_ui_hotfix_report.md

🎯 Цель — 6 задач
ID	Название	Severity
BUG-265	dashboard.js → /api/audit/* для viewer → 403-спам	🟡
BUG-266	api.js console.error на 403 → спам	🟢
BUG-267	dashboard.js не обрабатывает 403 → KPI «—»	🟡
BUG-270	/users (393px) — таблица невидима	🔴
BUG-271	/users (768px) — таблица обрезается	🟡
BACKLOG-324	/findings (393px) — фильтры full-screen	🟡
Плюс backlog (nice-to-have, если успеешь):

BACKLOG-320 — [DOM] password a11y (скрытое username в #passwordForm).

BACKLOG-321 — [DOM] inputs без autocomplete (8–10 полей).

BACKLOG-325 — Overlay без затемнения (mobile).

📋 Задачи
🟡 BUG-265/267 — dashboard.js: RBAC-проверка (viewer → 403-спам + KPI «—»)
Файл: webui/static/js/dashboard.js

Проблема: loadDashboard() безусловно вызывает /api/audit/stats?days=7 и /api/audit?limit=10. Для viewer/scanner — 403 → console.error + KPI «—» + пустые графики.

Фикс:

javascript
async function loadDashboard() {
    // BUG-265/267 (v3.14.4): viewer/scanner не имеют прав на /api/audit/* — не вызывать
    const canAudit = (typeof Auth !== 'undefined') &&
        (Auth.hasRole?.('admin') || Auth.hasRole?.('auditor'));

    // ... (KPI «Находок», «Сканеры», «Последние находки» — как раньше)

    if (canAudit) {
        try {
            const stats = await api.get('/api/audit/stats?days=7');
            document.getElementById('kpiResources').textContent = stats.total_resources ?? '—';
            document.getElementById('kpiAgents').textContent =
                (stats.active_agents ?? '—') + ' из ' + (stats.total_agents ?? '—');
        } catch (e) { /* fail-safe */ }

        try {
            const events = await api.get('/api/audit?limit=10');
            // рендер «События по типам» / «по источнику»
        } catch (e) { /* fail-safe */ }
    } else {
        // BUG-267: «Нет прав» вместо пустых графиков
        document.getElementById('kpiResources').textContent = '—';
        document.getElementById('kpiAgents').textContent = '—';
        const chartsEl = document.getElementById('auditCharts');
        if (chartsEl) {
            chartsEl.innerHTML =
                '<div class="text-muted text-center p-4">Нет прав на аудит</div>';
        }
    }
}
⚠️ Проверить Auth.hasRole:

powershell
Select-String -Path webui/static/js/auth.js -Pattern "hasRole|me\.roles|getRoles" -Context 0,3
Если hasRole отсутствует — добавить в auth.js:

javascript
hasRole(role) {
    const me = this.me?.() || {};
    return (me.roles || []).includes(role);
}
Если Auth.me() — sync/async — учесть в dashboard.js (await Auth.me()).

Файл: webui/templates/dashboard.html

Убедиться, что блок графиков аудита имеет id="auditCharts" (или два контейнера #chartAuditTypes / #chartAuditSources — обернуть).

🟢 BUG-266 — api.js: не спамить на 403
Файл: webui/static/js/api.js

Проблема: catch (e) { console.error('Ошибка:', e.message); } — на каждый 403 → спам в консоли.

Фикс (строка ~38):

javascript
// Было:
catch (e) {
    console.error('Ошибка:', e.message);
    throw e;
}

// Стало (BUG-266):
catch (e) {
    if (e.status !== 403) {
        console.warn('API error:', e.status || '', e.message);
    }
    throw e;
}
Проверить, что e.status — реально заполняется (в api.js — при !r.ok). Если нет — добавить:

javascript
if (!r.ok) {
    const err = new Error(data.detail || `HTTP ${r.status}`);
    err.status = r.status;   // ← для BUG-266
    throw err;
}
🔴 BUG-270 — /users (393px): таблица невидима
Файл: webui/templates/users.html + webui/static/css/tables.css

Проблема: на 393px таблица (7 колонок: ИМЯ, ФИО, EMAIL, ТИП, РОЛИ, СТАТУС, СОЗДАН) не влезает, нет горизонтального скролла, колонки обрезаются.

Вариант A — CSS (быстро, 1 час):

css
/* webui/static/css/tables.css */
@media (max-width: 768px) {
    .table-responsive-users {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
    .table-responsive-users table {
        min-width: 900px;   /* чтобы 7 колонок влезли */
    }
}
В users.html:

html
<div class="table-responsive-users">
    <table class="table">
        <!-- ... -->
    </table>
</div>
⚠️ Минус: горизонтальный скролл — не самый UX-дружелюбный, но работает (быстро, безопасно).

Вариант B — карточки (правильно, 3 часа):

На 393px — скрыть таблицу, показать карточки (<div class="user-card">):

css
@media (max-width: 480px) {
    .users-table { display: none; }
    .users-cards { display: block; }
}
@media (min-width: 481px) {
    .users-cards { display: none; }
}
В users.html:

html
<table class="users-table"> ... </table>
<div class="users-cards">
    <!-- Рендерится из JS по data — карточки: ИМЯ (жирным), РОЛИ (бейдж), СТАТУС (цвет) -->
</div>
JS — рендерить и таблицу, и карточки из одного users-массива.

Рекомендация: Вариант A (CSS, 1 час) — быстро, безопасно, работает. Вариант B — в BACKLOG-326 (v3.1.0).

🟡 BUG-271 — /users (768px): таблица обрезается
Файл: webui/static/css/tables.css

Проблема: на 768px — таблица обрезается справа (последняя колонка «Создан» не видна).

Фикс — тот же overflow-x: auto (см. выше), но с меньшим min-width:

css
@media (min-width: 481px) and (max-width: 900px) {
    .table-responsive-users {
        overflow-x: auto;
    }
    .table-responsive-users table {
        min-width: 700px;   /* 7 колонок влезают на 768px */
    }
}
🟡 BACKLOG-324 — /findings (393px): фильтры full-screen
Файл: webui/templates/findings.html + webui/static/css/findings.css

Проблема: на 393px фильтры (Поиск, Категория, Детектор, Фрагмент, Задание, Статус, Тип, Severity, Применить, Сброс) занимают весь экран — контент (находки) под фильтрами.

Фикс (аккордеон / collapsible):

html
<!-- findings.html -->
<button class="btn btn-outline-secondary d-md-none mb-2" type="button"
        data-bs-toggle="collapse" data-bs-target="#filtersCollapse">
    <i class="fas fa-filter"></i> Фильтры
</button>

<div class="collapse d-md-block" id="filtersCollapse">
    <!-- существующий блок фильтров -->
</div>
CSS:

css
@media (max-width: 480px) {
    #filtersCollapse:not(.show) { display: none; }
    #filtersCollapse.show { display: block; }
}
JS — data-bs-toggle="collapse" (Bootstrap 5). На 480px — фильтры свернуты (кнопка «Фильтры» → открыть). На ≥ 481px — всегда видны.

🟢 BACKLOG-320 — [DOM] password a11y (опционально)
Файл: webui/templates/settings.html

Проблема: #passwordForm без <input name="username"> → Chrome warn.

Фикс:

html
<form id="passwordForm" onsubmit="...">
    <!-- BACKLOG-320: скрытое username для a11y / autofill -->
    <input type="text" name="username" autocomplete="username"
           value="admin" style="display:none" readonly>
    <!-- существующие поля -->
</form>
🟢 BACKLOG-321 — [DOM] inputs без autocomplete (опционально)
Файлы: users.html, findings.html, settings.html

Найти inputs без autocomplete:

powershell
Select-String -Path webui/templates/*.html -Pattern "<input" | Select-String -NotMatch "autocomplete"
Добавить autocomplete="off" / "username" / "new-password" — по контексту.

🟢 BACKLOG-325 — Overlay без затемнения (опционально)
Файл: webui/static/css/sidebar.css

Фикс:

css
.sidebar-overlay.active {
    background: rgba(0, 0, 0, 0.5);
    /* ... существующие стили */
}
Проверить, что sidebar-overlay — реально в DOM (_openSidebar / _closeSidebar в main.js / sidebar.js).

🧪 Тесты
Unit — tests/unit/test_dashboard_v3144.py (new, 3 теста)
python
"""Tests for BUG-265/266/267 (v3.14.4)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_js_checks_role():
    """BUG-265: dashboard.js содержит RBAC-проверку canAudit."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    assert "canAudit" in src, "dashboard.js должен проверять роль"
    assert "Auth.hasRole" in src or "Auth.me" in src


def test_api_js_skips_403_in_console():
    """BUG-266: api.js не логирует 403 в console."""
    src = (ROOT / "webui/static/js/api.js").read_text(encoding="utf-8")
    assert "status !== 403" in src or "status === 403" in src


def test_users_responsive_css():
    """BUG-270/271: users table обёрнута в .table-responsive-users."""
    tpl = (ROOT / "webui/templates/users.html").read_text(encoding="utf-8")
    assert "table-responsive-users" in tpl, "users.html: .table-responsive-users"


def test_dashboard_has_audit_charts_id():
    """BUG-267: dashboard.html содержит #auditCharts."""
    tpl = (ROOT / "webui/templates/dashboard.html").read_text(encoding="utf-8")
    assert 'id="auditCharts"' in tpl or 'chartAuditTypes' in tpl
E2E — tests/e2e/test_responsive_v3144.py (new, 4 теста)
python
"""Tests for BUG-270/271 + BACKLOG-324 (v3.14.4)."""
import pytest
import requests


@pytest.mark.e2e
def test_users_has_table_responsive(webui_url):
    """BUG-270/271: users.html содержит .table-responsive-users."""
    tpl = requests.get(f"{webui_url}/users", timeout=10).text
    assert "table-responsive-users" in tpl


@pytest.mark.e2e
def test_findings_filters_collapse(webui_url):
    """BACKLOG-324: findings.html содержит #filtersCollapse."""
    tpl = requests.get(f"{webui_url}/findings", timeout=10).text
    assert 'id="filtersCollapse"' in tpl
    assert "data-bs-toggle=\"collapse\"" in tpl


@pytest.mark.e2e
def test_dashboard_audit_charts(webui_url):
    """BUG-267: dashboard.html содержит #auditCharts."""
    tpl = requests.get(f"{webui_url}/", timeout=10).text
    assert 'id="auditCharts"' in tpl or 'chartAuditTypes' in tpl


@pytest.mark.e2e
def test_api_js_handles_403(webui_url):
    """BUG-266: api.js содержит проверку status !== 403."""
    js = requests.get(f"{webui_url}/static/js/api.js", timeout=10).text
    assert "403" in js
DoD: Unit 520+ passed (было 517) + E2E +4.

📋 Ручная проверка
1. Rebuild
powershell
docker compose build webui
docker compose up -d webui
2. Viewer → / (Console)
Login viewer / viewer123.

F12 → Console — 403-спам?

Ожидание: 0 (только [DOM] warn, если есть).

KPI «Ресурсов» / «Агентов» — «—» (без спама).

Графики «События» — «Нет прав» вместо пустого.

3. Admin → /
Login admin / admin123.

F12 → Console — 0 ошибок.

KPI «Ресурсов» = 127, «Агентов» = 3/7 — как раньше.

Графики — работают.

4. /users (768px, admin)
Таблица не обрезается (скролл или fit).

Последняя колонка «Создан» — видна (или скролл).

5. /users (393px, admin)
Таблица скроллится (или карточки).

Все 7 колонок доступны.

6. /findings (393px, admin)
Кнопка «Фильтры» (сверху) → открывает collapse.

Фильтры не закрывают контент (когда свернуты).

7. /settings — [DOM] warn
F12 → Console — 3 проблемы (a11y), если BACKLOG-320/321 сделаны → 0–1.

Пароль в <input type="password"> — не warn про форму (username скрыт).

✅ Definition of Done
#	Проверка	Статус
1	Viewer / — 0 403 в Console	⏳
2	Viewer / — KPI «—», графики «Нет прав» (без спама)	⏳
3	Admin / — 0 ошибок, KPI 127/3-из-7	⏳
4	/users (768px) — таблица не обрезается	⏳
5	/users (393px) — таблица скроллится / карточки	⏳
6	/findings (393px) — фильтры collapse	⏳
7	Unit 520+ passed	⏳
8	E2E +4 (responsive)	⏳
9	Скриншоты: viewer / (Console), /users 393/768, /findings 393	⏳
💾 Коммит
powershell
git add webui/static/js/dashboard.js webui/static/js/api.js `
        webui/templates/dashboard.html webui/templates/users.html `
        webui/templates/findings.html webui/static/css/tables.css `
        webui/static/css/findings.css webui/static/css/sidebar.css `
        tests/unit/test_dashboard_v3144.py tests/e2e/test_responsive_v3144.py `
        docker-compose.yml `
        ARCHITECTURE.md ROADMAP.md STATE.md STATE_TEST_SESSION.md CHANGELOG.md `
        prompts/tz/day_53_4f_ui_hotfix.md `
        prompts/reports/day_53_4f_ui_hotfix_report.md
git commit -m "fix: 53.4f UI hotfix — dashboard RBAC + responsive /users//findings (v3.14.4)

BUG-265: dashboard.js — RBAC-проверка (canAudit) для /api/audit/*;
         viewer/scanner не вызывают (403-спам убран)
BUG-266: api.js — console.warn только для status !== 403
BUG-267: dashboard.js — KPI «—» + «Нет прав» вместо пустых графиков
BUG-270: /users (393px) — .table-responsive-users (overflow-x: auto)
BUG-271: /users (768px) — .table-responsive-users (min-width: 700px)
BACKLOG-324: /findings (393px) — фильтры collapse (Bootstrap 5)

Tests: test_dashboard_v3144.py (4 unit), test_responsive_v3144.py (4 e2e).
Unit 520+ passed. E2E +4.
VERSION 3.14.4."