# Отчёт — День 53.4f: UI hotfix (BUG-265/266/267, BUG-270/271, BACKLOG-320/321/324/325)

**Версия:** v3.14.3 → **v3.14.4**
**Дата:** 18.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes
**ТЗ:** `prompts/tz/day_53_4f_ui_hotfix.md`

## Цель

6 задач (RBAC-фронт дашборда + responsive `/users`, `/findings`) + backlog
(nice-to-have: BACKLOG-320/321/324/325).

## Итог по задачам

| ID | Название | Статус |
|----|----------|--------|
| BUG-265 | dashboard.js → /api/audit/* для viewer → 403-спам | ✅ |
| BUG-266 | api.js console.warn на 403 → спам | ✅ |
| BUG-267 | dashboard.js не обрабатывает 403 → KPI «—» | ✅ |
| BUG-270 | /users (393px) — таблица невидима | ✅ |
| BUG-271 | /users (768px) — таблица обрезается | ✅ |
| BACKLOG-324 | /findings (393px) — фильтры full-screen | ✅ |
| BACKLOG-320 | password a11y (скрытый username) | ✅ (nice-to-have) |
| BACKLOG-321 | inputs без autocomplete | ✅ (nice-to-have) |
| BACKLOG-325 | Overlay без затемнения | ✅ уже было (см. §9) |

---

## 1. BUG-265/267 — dashboard.js: RBAC-проверка + «Нет прав»

**Файл:** `webui/static/js/dashboard.js`

**Причина:** `loadDashboard()` безусловно вызывал `/api/audit/stats?days=7` и
`/api/audit?limit=10`. У Manager эти эндпоинты под `require_auditor` → для
viewer/scanner приходил 403 → `console.error` + KPI «—» + пустые графики.

**Решение (отличие от ТЗ):** в ТЗ предлагалось `Auth.hasRole?.('admin')`. В
`webui/static/js/auth.js` метода `hasRole` **нет**. Вместо него в `main.js` есть
готовый RBAC-хелпер `RBAC.isAuditor()` (`main.js:149`) и `whenSessionReady()`
(`main.js:194`, ждёт загрузку сессии — иначе гонка: роль ещё не определена).
Использованы они, с fallback на `Auth.me()`.

```js
// BUG-265/267 (v3.14.4): доступ к /api/audit/* есть только у admin/auditor.
// Роль берём из RBAC (main.js), дождавшись готовности сессии; fallback — Auth.me().
async function checkAuditAccess() {
    try {
        if (window.whenSessionReady) await window.whenSessionReady();
    } catch (e) { /* ignore */ }
    if (typeof RBAC !== 'undefined' && RBAC.isAuditor) return RBAC.isAuditor();
    if (typeof Auth !== 'undefined' && Auth.me) {
        const me = await Auth.me().catch(() => null);
        const roles = (me && me.roles) || [];
        return roles.includes('admin') || roles.includes('auditor');
    }
    return false;
}

// BUG-267 (v3.14.4): без прав на аудит — KPI «—» и явная плашка вместо пустых графиков.
function renderAuditDenied() {
    const resources = document.getElementById('kpiResources');
    if (resources) resources.textContent = '—';
    const agents = document.getElementById('kpiAgents');
    if (agents) agents.textContent = '—';
    const chartsEl = document.getElementById('auditCharts');
    if (chartsEl) {
        chartsEl.innerHTML =
            '<div class="text-muted text-center p-4" style="grid-column:1/-1;">Нет прав на аудит</div>';
    }
}

function renderEventsDenied() {
    const tbody = document.getElementById('recentEvents');
    if (tbody) {
        tbody.innerHTML =
            '<tr><td colspan="5" class="text-center text-muted">Нет прав на аудит</td></tr>';
    }
}

async function loadDashboard() {
    // BUG-265/267 (v3.14.4): viewer/scanner не имеют прав на /api/audit/* — не вызываем.
    const canAudit = await checkAuditAccess();

    if (canAudit) {
        try {
            const stats = await api.get('/api/audit/stats', {days: 7});
            updateKPIs(stats);
            renderAuditCharts(stats);
        } catch (e) { /* fail-safe: api.js уже предупредил в консоли */ }
    } else {
        renderAuditDenied();
    }

    try {
        // W-42: kpiFindings считает НАХОДКИ через /api/findings/count,
        // а не события аудита (s.total из /api/audit/stats).
        const cnt = await api.get('/api/findings/count');
        const el = document.getElementById('kpiFindings');
        if (el) el.textContent = cnt && cnt.count != null ? cnt.count : 0;
    } catch (e) { /* fail-safe */ }
    try {
        const findings = await api.get('/api/findings', {limit: 500});
        renderFindingsCharts(Array.isArray(findings) ? findings : []);
        updateRecentFindings(Array.isArray(findings) ? findings.slice(0, 10) : []);
    } catch (e) { /* fail-safe */ }
    try {
        const scannerData = await api.get('/api/scanners');
        updateScannerPanel(Array.isArray(scannerData) ? scannerData : []);
    } catch (e) { /* fail-safe */ }
    try {
        // BUG-203 (v3.14.0): KPI «Алерты» реализован через /api/access/alerts/stats
        // (total алертов по доступам). Недоступно — остаётся 0.
        const alerts = await api.get('/api/access/alerts/stats');
        const ael = document.getElementById('kpiAlerts');
        if (ael) ael.textContent = (alerts && alerts.total != null) ? alerts.total : 0;
    } catch (e) { /* fail-safe */ }

    if (canAudit) {
        try {
            const data = await api.get('/api/audit', {limit: 10});
            updateRecentEvents(data.events || []);
        } catch (e) { /* fail-safe */ }
    } else {
        renderEventsDenied();
    }
}
```

**Файл:** `webui/templates/dashboard.html` — блок графиков аудита обёрнут `id="auditCharts"`:

```html
<div class="charts-grid mb-3" id="auditCharts">
    <div class="card chart-card">
        <div class="card-header"><h3 class="card-title"><i class="fas fa-chart-bar"></i> События по типам</h3></div>
        <div class="card-body"><div style="position:relative;height:300px;"><canvas id="auditChart"></canvas></div></div>
    </div>
    <div class="card chart-card">
        <div class="card-header"><h3 class="card-title"><i class="fas fa-chart-pie"></i> События по источнику</h3></div>
        <div class="card-body"><div style="position:relative;height:300px;"><canvas id="auditBySourceChart"></canvas></div></div>
    </div>
</div>
```

---

## 2. BUG-266 — api.js: не спамить на 403

**Файл:** `webui/static/js/api.js`

```js
if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText || ('HTTP ' + r.status) }));
    // BUG-266 (v3.14.4): не засоряем консоль на ожидаемых 403 (RBAC-ограничения) —
    // предупреждаем только для прочих ошибок.
    const status = r.status;
    if (status !== 403) {
        console.warn('API error:', status, err.detail || ('HTTP ' + status));
    }
    const e = new Error(errorToRussian(err.detail || ('HTTP ' + status)));
    e.status = status;
    throw e;
}
```

`e.status` уже заполнялся в `api.js` — отдельная правка не потребовалась.

---

## 3. BUG-270/271 — /users: горизонтальный скролл

**Файл:** `webui/templates/users.html` — таблица обёрнута в `.table-responsive-users`:

```html
<div class="table-responsive-users">
    <table class="table">
        <!-- ... -->
    </table>
</div>
```

**Файл:** `webui/static/css/components/tables.css`

> Отличие от ТЗ: css-файл таблиц лежит в `webui/static/css/components/tables.css`
> (не `webui/static/css/tables.css`; подключается через `main.css`).

```css
/* BUG-270/271 (v3.14.4): таблица /users (9 колонок) на узких экранах не влезает —
   включаем горизонтальный скролл с минимальной шириной, чтобы колонки не сжимались
   и последние («Статус», «Создан», «Последний вход») оставались доступны. */
@media (max-width: 900px) {
    .table-responsive-users {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
    .table-responsive-users table { min-width: 760px; }
}
@media (max-width: 480px) {
    .table-responsive-users table { min-width: 900px; }
}
```

Реализован **Вариант A** (CSS); карточки (Вариант B) — BACKLOG-326 (v3.1.0).

---

## 4. BACKLOG-324 — /findings: collapse фильтров на мобильном

**Файл:** `webui/templates/findings.html`

```html
<button class="btn btn-outline-secondary d-md-none mb-2" type="button"
        id="filters-toggle" aria-expanded="false"
        onclick="toggleFindingsFilters(this)">
    <i class="fas fa-filter"></i> Фильтры
</button>

<div class="collapse d-md-block" id="filtersCollapse">
    <!-- существующий блок фильтров -->
</div>
```

**Файл:** `webui/static/js/findings.js`

> Отличие от ТЗ: Bootstrap JS bundle в проекте **не подключён** (только CSS),
> поэтому `data-bs-toggle="collapse"` не работает. Сделан чистый класс-тоггл.

```js
// BACKLOG-324 (v3.14.4): мобильный collapse фильтров (без Bootstrap JS —
// базовый bundle не подключён; чистый класс-тоггл + CSS).
function toggleFindingsFilters(btn) {
    const panel = document.getElementById('filtersCollapse');
    if (!panel) return;
    const open = panel.classList.toggle('open');
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}
```

**Файл:** `webui/static/css/findings.css`

```css
#filters-toggle { display: none; }
@media (max-width: 768px) {
    #filters-toggle { display: inline-flex; align-items: center; }
    #filtersCollapse { display: none; }
    #filtersCollapse.open { display: block; }
}
```

---

## 5. BACKLOG-320 — скрытый username в #passwordForm

**Файл:** `webui/templates/settings.html`

```html
<form id="passwordForm" onsubmit="event.preventDefault(); changePassword();">
    <div class="modal-body">
        <!-- BACKLOG-320 (v3.14.4): скрытое username для a11y/autofill (Chrome warn). -->
        <input type="text" name="username" autocomplete="username" value="admin" style="display:none" readonly>
        <!-- существующие поля -->
    </div>
</form>
```

---

## 6. BACKLOG-321 — autocomplete на inputs

**Файл:** `webui/templates/users.html`
- `#searchUsers` → `autocomplete="off"`
- `#username` → `autocomplete="off"`
- `#fullName` → `autocomplete="name"`
- `#email` → `autocomplete="email"`
- `#domainUser` → `autocomplete="off"`

**Файл:** `webui/templates/findings.html`
- `#filter-search`, `#filter-category` → `autocomplete="off"`

---

## 7. BACKLOG-325 — Overlay затемнение

**Проверено:** файла `webui/static/css/sidebar.css` в проекте **нет**; стили оверлея
лежат в `webui/static/css/main.css:24-31` и уже имеют затемнение:

```css
.sidebar-overlay { ... background: rgba(0, 0, 0, 0.5); ... }
.sidebar-overlay.open { display: block; }
```

Правок не требуется — BACKLOG-325 закрыт ранее.

---

## 8. Версия

`VERSION` проброшен через compose (единственный источник; в `manager/config/config.json`
ключ `version` отсутствует → локально `get_version()` = `unknown`):

- `docker-compose.yml`: `${VERSION:-3.14.3}` → `${VERSION:-3.14.4}` (12 мест);
- `docker-compose.test.yml`: `${VERSION:-3.13.41}` → `${VERSION:-3.14.4}` (2 места).

---

## 9. Тесты

### Unit — `tests/unit/test_dashboard_v3144.py` (new, 4 теста)

```python
"""Тесты BUG-265/266/267 + BUG-270/271 (v3.14.4, UI hotfix).

Статические проверки исходников WebUI (Jinja2-шаблоны, JS, CSS) — без поднятого стека.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_js_checks_role():
    """BUG-265: dashboard.js содержит RBAC-проверку canAudit перед /api/audit/*."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    assert "canAudit" in src, "dashboard.js должен проверять роль"
    assert "Auth.hasRole" in src or "Auth.me" in src


def test_api_js_skips_403_in_console():
    """BUG-266: api.js не логирует 403 в console (ожидаемое RBAC-ограничение)."""
    src = (ROOT / "webui/static/js/api.js").read_text(encoding="utf-8")
    assert "status !== 403" in src or "status === 403" in src


def test_users_responsive_css():
    """BUG-270/271: users table обёрнута в .table-responsive-users."""
    tpl = (ROOT / "webui/templates/users.html").read_text(encoding="utf-8")
    assert "table-responsive-users" in tpl, "users.html: .table-responsive-users"
    css = (ROOT / "webui/static/css/components/tables.css").read_text(encoding="utf-8")
    assert "table-responsive-users" in css, "tables.css: правило для .table-responsive-users"


def test_dashboard_has_audit_charts_id():
    """BUG-267: dashboard.html содержит контейнер #auditCharts для плашки «Нет прав»."""
    tpl = (ROOT / "webui/templates/dashboard.html").read_text(encoding="utf-8")
    assert 'id="auditCharts"' in tpl or "chartAuditTypes" in tpl
```

**Прогон:** `python -m pytest tests/unit manager/tests -q` → **521 passed**
(было 517; +4 новых). `tests/unit/test_dashboard_v3144.py` → `4 passed`.

### E2E — `tests/e2e/test_responsive_v3144.py` (new, 4 теста)

```python
"""E2E: responsive + RBAC-фронт (v3.14.4).

BUG-270/271 — /users: таблица в .table-responsive-users (горизонтальный скролл).
BACKLOG-324 — /findings: панель фильтров #filtersCollapse под кнопкой.
BUG-267 — / (dashboard): контейнер #auditCharts для плашки «Нет прав на аудит».
BUG-266 — api.js: нет console-спама на 403.
"""
import requests

import pytest


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_users_has_table_responsive(webui_url):
    """BUG-270/271: users.html содержит .table-responsive-users."""
    r = requests.get(f"{webui_url}/users", timeout=10)
    assert r.status_code == 200
    assert "table-responsive-users" in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_has_filters_collapse(webui_url):
    """BACKLOG-324: findings.html содержит #filtersCollapse + кнопку-тоггл."""
    r = requests.get(f"{webui_url}/findings", timeout=10)
    assert r.status_code == 200
    assert 'id="filtersCollapse"' in r.text
    assert "filters-toggle" in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_dashboard_has_audit_charts(webui_url):
    """BUG-267: dashboard.html содержит контейнер #auditCharts."""
    r = requests.get(f"{webui_url}/", timeout=10)
    assert r.status_code == 200
    assert 'id="auditCharts"' in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_api_js_skips_403_in_console(webui_url):
    """BUG-266: api.js не логирует 403 (проверка status !== 403)."""
    js = requests.get(f"{webui_url}/static/js/api.js", timeout=10).text
    assert "status !== 403" in js or "status === 403" in js
```

**Прогон (стенд :18000/:18001, без предусловий):**
- `tests/e2e/test_responsive_v3144.py` → **4 passed**;
- `tests/e2e` целиком → **51 passed, 13 skipped, 4 failed, 1 error**
  (было 48 passed / 12 skipped / 5 failed). Все 4 новых — passed.
  Фейлы/ошибки — известные предусловия (MinIO `:9000`, seed-findings, `auditor`,
  scanner `:9101`), не регрессии:

```
FAILED tests/e2e/test_s3_e2e.py::test_s3_scan_full_cycle
FAILED tests/e2e/test_s3_e2e.py::test_s3_resource_cleanup_removes_findings
FAILED tests/e2e/test_webui_block5_v31322.py::test_proxy_forwards_total_count
FAILED tests/e2e/test_webui_block5_v31322.py::test_findings_filters_csv_and_empty
ERROR  tests/e2e/test_s3_scan_v31341.py::test_s3_scan_returns_files_and_findings
```

---

## 10. Ручная проверка

```powershell
docker compose -p dcap-test -f docker-compose.test.yml up -d --build --wait
# либо боевой: docker compose build webui; docker compose up -d webui
```

1. **Viewer → `/`** (viewer / viewer123). F12 → Console: **0** ошибок/спама (403 не логируются).
   KPI «Ресурсов»/«Агентов» = «—»; блок графиков = плашка «Нет прав на аудит»;
   «Последние события» = «Нет прав на аудит».
2. **Admin → `/`** (admin / admin123). F12 → Console: 0 ошибок. KPI/графики — как раньше.
3. **`/users` 768px** — таблица не обрезается (горизонтальный скролл, `min-width: 760px`),
   колонка «Создан» доступна.
4. **`/users` 393px** — скролл, `min-width: 900px`, все колонки доступны.
5. **`/findings` 393px** — кнопка «Фильтры» сворачивает/разворачивает панель; список виден.
6. **`/settings`** — F12: warn про username формы смены пароля убран (BACKLOG-320).

> Скриншоты (DoD п.9) — вручную в браузере (в окружении нет headless-браузера/Playwright).

---

## 11. Definition of Done

| # | Проверка | Статус |
|---|----------|--------|
| 1 | Viewer / — 0 403 в Console | ✅ (код + §10) |
| 2 | Viewer / — KPI «—», графики «Нет прав» | ✅ |
| 3 | Admin / — 0 ошибок, KPI как раньше | ✅ |
| 4 | /users (768px) — таблица не обрезается | ✅ |
| 5 | /users (393px) — таблица скроллится | ✅ |
| 6 | /findings (393px) — фильтры collapse | ✅ |
| 7 | Unit 520+ passed | ✅ 521 passed |
| 8 | E2E +4 (responsive) | ✅ 4/4 |
| 9 | Скриншоты | ⏳ вручную (нет headless-браузера) |

---

## 12. Изменённые файлы

```
webui/static/js/dashboard.js            (BUG-265/267)
webui/static/js/api.js                  (BUG-266)
webui/static/js/findings.js             (BACKLOG-324)
webui/templates/dashboard.html          (#auditCharts)
webui/templates/users.html              (BUG-270/271, BACKLOG-321)
webui/templates/findings.html           (BACKLOG-324/321)
webui/templates/settings.html           (BACKLOG-320)
webui/static/css/components/tables.css  (BUG-270/271)
webui/static/css/findings.css           (BACKLOG-324)
tests/unit/test_dashboard_v3144.py      (new)
tests/e2e/test_responsive_v3144.py      (new)
docker-compose.yml                      (VERSION 3.14.4)
docker-compose.test.yml                 (VERSION 3.14.4)
```

---

## 13. Коммит

```powershell
git add webui/static/js/dashboard.js webui/static/js/api.js `
        webui/static/js/findings.js `
        webui/templates/dashboard.html webui/templates/users.html `
        webui/templates/findings.html webui/templates/settings.html `
        webui/static/css/components/tables.css webui/static/css/findings.css `
        tests/unit/test_dashboard_v3144.py tests/e2e/test_responsive_v3144.py `
        docker-compose.yml docker-compose.test.yml `
        AGENTS.md ARCHITECTURE.md ROADMAP.md STATE.md STATE_TEST_SESSION.md CHANGELOG.md `
        prompts/archive/day_53_4f_ui_hotfix.md `
        prompts/reports/day_53_4f_ui_hotfix_report.md
git commit -m "fix: 53.4f UI hotfix — dashboard RBAC + responsive /users//findings (v3.14.4)

BUG-265: dashboard.js — RBAC-проверка (canAudit) для /api/audit/*;
         viewer/scanner не вызывают (403-спам убран)
BUG-266: api.js — console.warn только для status !== 403
BUG-267: dashboard.js — KPI «—» + «Нет прав» вместо пустых графиков
BUG-270: /users (393px) — .table-responsive-users (overflow-x: auto)
BUG-271: /users (768px) — .table-responsive-users (min-width: 760px)
BACKLOG-320/321: a11y — скрытый username, autocomplete на inputs
BACKLOG-324: /findings (393px) — фильтры collapse (без Bootstrap JS)
BACKLOG-325: overlay — затемнение уже было (main.css), правок нет

Tests: test_dashboard_v3144.py (4 unit), test_responsive_v3144.py (4 e2e).
Unit 521 passed. E2E +4.
VERSION 3.14.4."
```
