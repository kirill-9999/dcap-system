# Отчёт: День 53.4b — WebUI-редизайн, этап 2 (RBAC frontend + Responsive)

- **Дата:** 13.10.2026
- **Версия:** v3.13.41 → **v3.14.0**
- **Статус:** 🟢 Выполнено (docker-стек пересобран, UI отдан из нового образа, скриншоты на 3 разрешениях)
- **ТЗ:** `prompts/tz/day_53_4b_webui_pages_1.md`
- **Источник:** мастер-сессия v3.13.38 (WebUI-редизайн, этап 2)
- **Ветка:** `feature/day_53_4b_webui_pages_1`

---

## Руководящие указания (выполнены)

1. **BACKLOG-119 / BACKLOG-121** — уже закрыты в 53.4a-доп5 (v3.13.41), **пропущены**.
2. **BUG-142** — реализован на фронте через `total_resources` из `/api/audit/stats`
   (бэкенд-часть закрыта в v3.13.39). Принудительная выборка `/api/resources?limit=1` +
   X-Total-Count из ТЗ **не** внедрялась — она даёт лишний запрос, а `/api/audit/stats`
   уже отдаёт `total_resources` и читается дашбордом в том же цикле.
3. **BUG-223** (детали события аудита) — не входит в 53.4b, **в 53.4c**.

---

## 📁 Созданные / изменённые файлы

### Создан

| Файл | Роль |
|------|------|
| `webui/static/js/datetime.js` | BUG-141: `parseUtc`/`formatDate`/`formatDateShort` — UTC от бэкенда без 'Z' приводится к локальной timezone |

### Изменены

| Файл | Роль |
|------|------|
| `webui/static/js/main.js` | BUG-213 (RBAC: `ROLES_PAGES`/`RBAC`/`applyRBACNav`/`initSession`/`whenSessionReady`), BUG-228 (гамбургер/оверлей/сворачивание desktop), модалки вынесены нейтрально |
| `webui/static/js/api.js` | BUG-216 (403 → редирект на `/`, ошибки бэкенда → русские через `errorToRussian`), 401 → `/login` |
| `webui/static/js/auth.js` | BUG-216: реализация `errorToRussian` (нужна и на `/login`, где `api.js` не грузится) |
| `webui/static/css/main.css` | BUG-228/233: `.sidebar-overlay`, `.sidebar-open-btn`, «рельсы» 769–1024px, off-canvas drawer ≤768px |
| `webui/static/css/components.css` | BUG-232: модалки на ≤480px (full-width, radius 0, скролл) |
| `webui/static/css/findings.css` | BUG-205 (placeholder overflow), BUG-206 (кнопки-действия finding-act, `.act-label` скрывается ≤480px) |
| `webui/templates/base.html` | `#sidebar-toggle` без inline onclick, `#sidebarOverlay`, `#mobileSidebarToggle`, подключён `datetime.js`, inline-защита страниц → `initSession()` в main.js |
| `webui/templates/dashboard.html` | BUG-229: 4 canvas обёрнуты в `<div style="position:relative;height:300px;">`, атрибуты `height` убраны |
| `webui/static/js/dashboard.js` | BUG-229 (`maintainAspectRatio:false`, `legendPosition()`), BUG-203 (KPI «Алертов» через `/api/access/alerts/stats`), BUG-141 (`formatDate`/`parseUtc`), BUG-207 (русские статусы), BUG-204 (диаграмма «Находки по ресурсам» — на данных `/api/findings`, проверена) |
| `webui/templates/findings.html` | BUG-205: короткий placeholder «путь или значение» |
| `webui/static/js/findings.js` | BUG-213 (RBAC-гейт: экспорт/массовые/чекбоксы/кнопки статусов — Auditor+; `await whenSessionReady()`), BUG-206 (✓/✗ с подписями Dovetail), BUG-207 (русские badge) |
| `webui/static/js/finding_detail.js` | BUG-141 (`formatDate`), BUG-207 (русский статус), BUG-213 (кнопки reveal/confirm/fp скрыты для не-аудиторов) |
| `webui/static/js/false_positives.js` | BUG-141 (`formatDate` для `reviewed_at`) + фикс битого хвоста в HEAD (`},` дублировался — страница падала) |
| `webui/templates/audit.html` | BUG-141: `formatDate(e.created_at)` |
| `webui/templates/scanners.html` | BUG-141: `formatDate(s/a.last_heartbeat)` |
| `webui/templates/resources.html` | BUG-213 («Добавить ресурс» — только admin; «Сканировать» — только scanner+; `await whenSessionReady()`), BUG-216 (русские ошибки) |
| `webui/templates/login.html` | BUG-146 (mobile: flex + overflow + ограничение ширины), BUG-216 (русская ошибка входа) |
| `.env`, `.env.example`, `docker-compose.yml` | Версия → **3.14.0** |

---

## 🔴 BUG-213 — Frontend RBAC

**Матрица страниц** (в `main.js`, применяется и к sidebar, и к кнопкам):

```js
const ROLES_PAGES = {
    admin: '*',
    auditor: ['dashboard', 'catalog', 'findings', 'false-positives', 'audit', 'access', 'resources'],
    scanner: ['dashboard', 'catalog', 'findings', 'resources', 'scanners'],
    viewer:  ['dashboard', 'catalog', 'findings', 'resources'],
};

const RBAC = {
    roles: [],
    set(roles) { this.roles = Array.isArray(roles) ? roles : []; },
    has(...needed) { return this.roles.some(r => needed.includes(r)); },
    isAdmin()   { return this.has('admin'); },
    isAuditor() { return this.has('admin', 'auditor'); },
    isScanner() { return this.has('admin', 'scanner'); },
    canPage(page) {
        if (this.isAdmin()) return true;
        for (const r of this.roles) {
            const allowed = ROLES_PAGES[r];
            if (allowed && allowed.includes(page)) return true;
        }
        return false;
    },
};

function applyRBACNav() {
    document.querySelectorAll('.sidebar-nav .nav-item[data-page]').forEach(el => {
        el.style.display = RBAC.canPage(el.dataset.page) ? '' : 'none';
    });
    const div = document.querySelector('.nav-divider.nav-admin');
    if (div) div.style.display = RBAC.isAdmin() ? '' : 'none';
}

async function initSession() {
    if (typeof Auth === 'undefined') return null;
    if (window.location.pathname === '/login') return null;
    let me = null;
    const ok = await Auth.check();
    if (ok) { try { me = await Auth.me(); } catch (e) { /* токен протух */ } }
    const roles = me && Array.isArray(me.roles) ? me.roles : [];
    RBAC.set(roles);
    applyRBACNav();
    const nameEl = document.getElementById('currentUserName');
    if (nameEl) nameEl.textContent = (me && (me.full_name || me.username)) || 'Пользователь';
    const rolesEl = document.getElementById('currentUserRoles');
    if (rolesEl) rolesEl.textContent = roles.join(', ');
    return me;
}

// Страничные скрипты ждут сессию, чтобы читать RBAC:
let _sessionPromise = Promise.resolve();
window.whenSessionReady = function () { return _sessionPromise; };
document.addEventListener('DOMContentLoaded', function () {
    ...
    _sessionPromise = initSession();
    ...
});
```

- **Роутер** — при 403 API `api.js` редиректит на `/` (guard `pathname !== '/'`).
- **Кнопки**:
  - `findings.js`: `canAudit = RBAC.isAuditor()` → скрыты `#export-btn` и `#bulk-actions`; чекбоксы и кнопки смены статуса рендерятся только для Auditor+.
  - `resources.html`: «Добавить ресурс» (`RBAC.isAdmin()`, бэкенд `POST /api/resources` = `require_admin`), «Сканировать» (`RBAC.isScanner()`, бэкенд = `require_scanner`).
  - `finding_detail.js`: reveal/confirm/fp — только Auditor+.
- **Сообщения** — `errorToRussian` (см. BUG-216).

Проверено в живом браузере (CDP): `viewer` → `[dashboard,catalog,findings,resources]`, `auditor+scanner` → `[dashboard,catalog,findings,false-positives,resources,audit,access,scanners]`, admin → все 11 пунктов.

---

## 🔴 BUG-228 / 233 — Sidebar + гамбургер

`webui/static/css/main.css`:

```css
/* desktop rails 1025px+ */
.sidebar { width: var(--sidebar-width); transition: width .25s, left .3s; }
.sidebar.collapsed { width: 60px; }
.sidebar.collapsed .nav-label, .sidebar.collapsed .hide-on-collapse { display: none; }

/* планшет: рельсы (769–1024) */
@media (max-width: 1024px) {
    .sidebar { width: 60px; }
    .sidebar .nav-label, .sidebar .hide-on-collapse { display: none; }
    .sidebar .nav-item { justify-content: center; }
}

/* мобильный: off-canvas drawer (≤768) */
@media (max-width: 768px) {
    .sidebar { position: fixed; left: -250px; width: 250px; z-index: 1000; transition: left .3s; }
    .sidebar.open { left: 0; }
    .sidebar-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 999; display: none; }
    .sidebar-overlay.open { display: block; }
    .main-content { margin-left: 0 !important; }
    .page-header { position: sticky; top: 0; z-index: 900; }
    .sidebar-open-btn { display: inline-flex; }
}
.sidebar-open-btn { display: none; }
```

`main.js`:

```js
function toggleSidebar() {
    const s = document.getElementById('sidebar');
    const m = document.getElementById('mainContent');
    if (window.innerWidth <= 768) {
        s.classList.toggle('open');
        document.getElementById('sidebarOverlay')?.classList.toggle('open');
        return;
    }
    s.classList.toggle('collapsed');
    m.classList.toggle('expanded');
    localStorage.setItem('dcap-sidebar', s.classList.contains('collapsed') ? '1' : '0');
}
function closeSidebarMobile() {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('open');
}
```

`base.html`: у `#sidebar-toggle` убран inline onclick (слушатель в main.js), добавлен
`#sidebarOverlay` (onclick → `closeSidebarMobile`) и мобильный гамбургер
`#mobileSidebarToggle` в `header-left`. Проверено на 393px: до клика `left:-250px`,
после `toggleSidebar()` класс `.open` + оверлей, `closeSidebarMobile()` снимает оба.

---

## 🔴 BUG-229 — Chart.js адаптив

`webui/static/js/dashboard.js`:

```js
function legendPosition() { return window.innerWidth < 768 ? 'bottom' : 'right'; }

options: { responsive: true, maintainAspectRatio: false, aspectRatio: 1,
           plugins: { legend: { position: legendPosition() } } }
```

`dashboard.html`: все 4 canvas обёрнуты:

```html
<div style="position:relative;height:300px;"><canvas id="auditChart"></canvas></div>
```

CDP-проверка: все 4 чарта инстанцированы (`Chart.getChart(id)` truthy), `clientHeight=300`
на desktop. Раскладка KPI/чартов на ≤768 — `grid-template-columns: 1fr`.

---

## 🔴 BUG-232 — Модалки на mobile

`webui/static/css/components.css` (блок добавлен перед секцией Utilities,
безопасно перебивает `@import modals.css` в main.css повышенной специфичностью):

```css
/* BUG-232 (v3.14.0): модалки на мобильных */
@media (max-width: 480px) {
    .modal-dialog { max-width: 100%; margin: 0; }
    .modal .modal-content,
    .modal-dialog .modal-content { width: 100%; max-width: 100%; border-radius: 0; max-height: 100vh; }
    .modal .modal-body { max-height: calc(100vh - 200px); overflow-y: auto; }
}
```

---

## 🟡 BUG-216 — Ошибки RBAC на русском

`webui/static/js/auth.js` (реализация; `api.js` и `/login` используют её):

```js
function errorToRussian(detail) {
    if (detail === null || detail === undefined || detail === '') return detail;
    const msg = String(detail);
    const map = {
        'Invalid credentials': 'Неверный логин или пароль',
        'Current password is incorrect': 'Неверный текущий пароль',
        'Passwords do not match': 'Пароли не совпадают',
        'Cannot delete yourself': 'Вы не можете удалить себя',
        'Cannot disable yourself': 'Вы не можете заблокировать себя',
    };
    if (map[msg]) return map[msg];
    if (/^Required roles:/i.test(msg)) return 'Недостаточно прав. Обратитесь к администратору';
    return msg;
}
```

`api.js`:

```js
_handleErrors(r) {
    if (r.status === 401) {
        if (typeof Auth !== 'undefined') Auth.setToken(null);
        if (window.location.pathname !== '/login') window.location.href = '/login';
    }
    if (r.status === 403 && window.location.pathname !== '/') {
        window.location.href = '/';
    }
    return r;
}
```

Применено в `api.request`/`getWithMeta`, экспорте findings, создании ресурса, ошибке входа.

---

## 🟡 BUG-142 — Dashboard KPI «Ресурсов» (frontend)

`updateKPIs` в `dashboard.js` берёт `s.total_resources` из `/api/audit/stats`
(бэкенд закрыт BUG-142 в v3.13.39, `manager/src/api/audit.py:360`). Отдельный запрос
`/api/resources?limit=1` не добавлялся — `total_resources` уже в ответе статистики.
Проверено: `kpiResources = 127`.

---

## 🟡 BUG-141 — Время UTC → локализовать

Новый `webui/static/js/datetime.js` (полный код):

```js
// webui/static/js/datetime.js
// BUG-141 (v3.14.0): бэкенд отдаёт UTC-строки без временной зоны и без 'Z'
// (например "2026-10-13T10:20:30"). parseUtc/formatDate принудительно
// трактуют строку как UTC и локализуют вывод в timezone браузера (ru-RU).

function parseUtc(isoStr) {
    if (!isoStr) return NaN;
    let s = String(isoStr).trim();
    if (s && !/[Zz]$|[+-]\d{2}:\d{2}$/.test(s)) s += 'Z';
    const t = new Date(s).getTime();
    return isNaN(t) ? NaN : t;
}

function formatDate(isoStr) {
    if (isoStr === null || isoStr === undefined || isoStr === '') return '—';
    const t = parseUtc(isoStr);
    if (isNaN(t)) return String(isoStr);
    return new Date(t).toLocaleString('ru-RU');
}

function formatDateShort(isoStr) {
    if (isoStr === null || isoStr === undefined || isoStr === '') return '—';
    const t = parseUtc(isoStr);
    if (isNaN(t)) return String(isoStr);
    return new Date(t).toLocaleDateString('ru-RU');
}
```

Подключён в `base.html`. Использован в: `/audit` (created_at), `/scanners`
(last_heartbeat), `/findings/{id}` (first/last_seen_at), `/false-positives`
(reviewed_at), дашборд (recent events/findings, heartbeat-스канеров через `parseUtc`).

---

## 🟡 BUG-205 / 206 / 207 — Findings UI

- **BUG-205** — placeholder фильтра: `placeholder="путь или значение"` (было
  «путь к файлу или значение (маскированное)» — переполнялся). Плюс CSS:

```css
.form-control-sm::placeholder { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
```

- **BUG-206** — кнопки стиля Dovetail, иконка + подпись:

```html
<button class="btn btn-sm btn-success finding-act" data-action="confirm" data-id="${f.id}" title="Подтвердить"><i class="fas fa-check"></i><span class="act-label">Подтвердить</span></button>
<button class="btn btn-sm btn-danger finding-act" data-action="fp" data-id="${f.id}" title="Ложное срабатывание"><i class="fas fa-times"></i><span class="act-label">Ложное</span></button>
```

```css
.finding-act { gap: 6px; }
.finding-act i { font-size: 12px; width: 12px; text-align: center; }
@media (max-width: 480px) { .finding-act .act-label { display: none; } }
```

- **BUG-207** — статусы на русском:

```js
const statusBadge = {
  new: '<span class="badge bg-primary">🆕 Новое</span>',
  confirmed: '<span class="badge bg-success">✅ Подтверждено</span>',
  false_positive: '<span class="badge bg-danger">❌ Ложное</span>',
  archived: '<span class="badge bg-secondary">📦 Архив</span>',
  duplicate: '<span class="badge bg-warning text-dark">♻️ Дубликат</span>',
}[f.status] || escapeHtml(f.status);
```

То же на дашборде (`statusName`) и в `finding_detail.js` (`statusName`/`statusColor`).

---

## 🟡 BUG-146 — Login наезжает

`webui/templates/login.html`:

```css
@media (max-width: 480px) {
    body.login-body { align-items: flex-start; justify-content: flex-start;
                      padding: 24px 16px; overflow-y: auto; }
    .login-card { max-width: 100%; margin: 0 auto; display: flex; flex-direction: column; }
    .login-card .card-body { padding: 16px 20px 28px; }
    .login-card .card-header { padding: 24px 20px 12px; display: flex; flex-direction: column;
                               align-items: center; gap: 4px; }
}
```

---

## 🟡 BUG-203 / 204 — Dashboard KPI

- **BUG-203** — KPI «Алертов» реализован: `updateKPIs`-блок в `loadDashboard`:

```js
const alerts = await api.get('/api/access/alerts/stats');
document.getElementById('kpiAlerts').textContent = (alerts && alerts.total != null) ? alerts.total : 0;
```

  Недоступность API — не ломает дашборд (try/catch). Проверено: `kpiAlerts = 0`.

- **BUG-204** — «Находки по ресурсам»: источник `/api/findings` (`renderFindingsCharts`,
  группировка по `file_path`, топ-10 горизонтальным bar). Проверено — чарт строится
  (находок в БД 1509).

---

## ✅ Definition of Done

| Критерий | Результат |
|----------|-----------|
| RBAC на frontend (sidebar, router, кнопки) | ✅ `viewer`/`auditor`/`scanner`/`admin` — фильтр навигации (см. CDP-пробы), кнопки по ролям, 403 → `/` |
| Sidebar адаптивна (768 / 393) | ✅ рельсы 769–1024, off-canvas drawer ≤768 |
| Гамбургер работает | ✅ `toggleSidebar()` + оверлей, на 393px класс `.open` и overlay подтверждены |
| Chart.js адаптивен | ✅ `maintainAspectRatio:false` + обёртки `height:300px`, `legendPosition()` |
| Модалки адаптивны | ✅ ≤480px full-width/скролл |
| Ошибки на русском | ✅ `errorToRussian` во всех точках API |
| /login, /, /findings в Dovetail | ✅ скриншоты |
| Скриншоты 1920 / 768 / 393 | ✅ 9 файлов (login/dashboard/findings × 3) |

Скриншоты: `E:\Temp\opencode\shots\v3_14\{login,dashboard,findings}_{1920,768,393}.png`
(не коммитятся — временная директория вне репо).

---

## 📊 Проверка (CDP, Chrome headless, живой docker-стенд :8001)

```
login http: 200, user: admin ['admin']
login 1920/768/393  -> /login, loginCard: true
dashboard 1920/768/393 -> /, RBAC=admin, kpiResources=127, kpiFindings=1509,
        kpiAgents=1, kpiAlerts=0, все 4 Chart.getChart()===true, w=754/h=300
findings 1920/768/393 -> /findings, RBAC=admin
mobile-before @393: sidebar left=-250px, burger display=inline-flex
toggleSidebar()  -> .open on, overlay on
closeSidebarMobile() -> оба сняты
rbac-viewer:    [dashboard, catalog, findings, resources]
rbac-audit+scan:[dashboard, catalog, findings, false-positives, resources, audit, access, scanners]
node --check: main.js, api.js, auth.js, datetime.js, dashboard.js, findings.js,
              finding_detail.js, false_positives.js — OK
docker compose config -q — OK; /api/health → {"status":"healthy","version":"3.14.0"}
```

---

## ⚠️ Ограничения / заметки

- WebUI-код в docker-образе запекается при сборке (`docker compose build webui`),
  bind-mount кода нет — после правок образ пересобран, контейнер пересоздан.
- Версия в футере приходит из `GET /api/health` (`VERSION` env). Manager пере-тегирован
  `dcap/manager:3.14.0` без пересборки (код менеджера не менялся), chemistry worker/beat
  остались на 3.13.41-образе (изменений не требовали).
- `webui/static/js/false_positives.js`: в HEAD был битый хвост (`},` дублировался) —
  страница не работала; в 53.4b починено вместе с BUG-141 (формат даты).
- `conftest_dump.txt` в корне — мусор от прошлых прогонов, **не коммитить**.
- Скриншоты из `E:\Temp\opencode\` — за пределами репозитория.

---

## 🚀 Как проверить (пользователю)

```powershell
docker compose build webui
docker compose up -d manager webui          # менеджер пере-тегирован 3.14.0 (без пересборки)
# открыть http://127.0.0.1:8001
# admin / admin123  (или пользователь с ролью viewer/scanner/auditor)
```

1. `/login` — mobile (393px) не «наезжает», без скролла-переноса.
2. `/` — 4 графика ресайзятся, KPI «Ресурсов»=127, «Алертов» заполнен.
3. `/findings` — русские бейджи, кнопки ✓/✗ с подписями; под 393px подписи скрываются.
4. Sidebar: 1920 — кнопка «≡» сворачивает в рельсы; ≤768 — выкатывается поверх + оверлей.
5. Вход под `viewer` — в меню только Дашборд/Каталог/Находки/Ресурсы, на /findings нет
   кнопок экспорта и статусов.

---

## ✅ Команда для коммита

```powershell
git add .env.example docker-compose.yml webui/static/js/main.js webui/static/js/auth.js webui/static/js/api.js webui/static/js/datetime.js webui/static/js/dashboard.js webui/static/js/findings.js webui/static/js/finding_detail.js webui/static/js/false_positives.js webui/static/css/main.css webui/static/css/components.css webui/static/css/findings.css webui/templates/base.html webui/templates/login.html webui/templates/dashboard.html webui/templates/findings.html webui/templates/audit.html webui/templates/scanners.html webui/templates/resources.html prompts/tz/day_53_4b_webui_pages_1.md prompts/archive/day_53_4b_webui_pages_1.md prompts/reports/day_53_4b_webui_pages_1_report.md
git commit -m "feat: День 53.4b — WebUI-редизайн этап 2: RBAC frontend + Responsive (v3.14.0)

- BUG-213: frontend RBAC — ROLES_PAGES/RBAC/applyRBACNav/initSession/whenSessionReady; 403 → редирект на '/', кнопки по ролям (export/bulk/статусы — Auditor+, добавление ресурса — admin, скан — scanner+)
- BUG-228/233: sidebar адаптив — рельсы 769-1024px, off-canvas drawer ≤768px + оверлей + гамбургер
- BUG-229: Chart.js — maintainAspectRatio:false, обёртки height:300px, legendPosition()
- BUG-232: модалки ≤480px — full-width, radius 0, скролл
- BUG-216: errorToRussian() — ошибки RBAC/входа на русском
- BUG-142: KPI «Ресурсов» через total_resources из /api/audit/stats
- BUG-141: datetime.js (UTC→local), применён в /audit, /scanners, /findings/{id}, /false-positives, дашборд
- BUG-205/206/207: findings — placeholder, кнопки-действия Dovetail, статусы на русском
- BUG-146: login mobile (flex+gap+overflow)
- BUG-203: KPI «Алертов» через /api/access/alerts/stats
- фикс false_positives.js (битый хвост `},` в HEAD — страница не работала)
- версия → v3.14.0 (.env, .env.example, docker-compose); отчёт + архив ТЗ

docs: обновлён STATE.md (v3.14.0)" 
```

> ⚠️ `conftest_dump.txt` в коммит НЕ входит.