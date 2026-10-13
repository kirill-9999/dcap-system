// webui/static/js/main.js
// Sidebar + footer + модалки + frontend RBAC (BUG-213) + гамбургер (BUG-228/233).

function toggleSidebar() {
    const s = document.getElementById('sidebar');
    const m = document.getElementById('mainContent');
    // ≤768px — офканвас-панель: выкатываем поверх контента (BUG-228).
    if (window.innerWidth <= 768) {
        s.classList.toggle('open');
        const ov = document.getElementById('sidebarOverlay');
        if (ov) ov.classList.toggle('open');
        return;
    }
    // Десктоп — сворачивание «в рельсы».
    s.classList.toggle('collapsed');
    m.classList.toggle('expanded');
    localStorage.setItem('dcap-sidebar', s.classList.contains('collapsed') ? '1' : '0');
}

function closeSidebarMobile() {
    const s = document.getElementById('sidebar');
    const ov = document.getElementById('sidebarOverlay');
    if (s) s.classList.remove('open');
    if (ov) ov.classList.remove('open');
}

function initSidebar() {
    if (localStorage.getItem('dcap-sidebar') === '1' && window.innerWidth > 768) {
        document.getElementById('sidebar')?.classList.add('collapsed');
        document.getElementById('mainContent')?.classList.add('expanded');
    }
}

function updateFooterTime() {
    const el = document.getElementById('footerTime');
    if (el) el.textContent = new Date().toLocaleString('ru-RU');
}

function initFooterVersion() {
    const el = document.getElementById('footerVersion');
    if (!el) return;
    fetch('/api/health', {headers: {'Accept': 'application/json'}, credentials: 'include'})
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(h => { if (h && h.version) el.textContent = 'v' + h.version; })
        .catch(() => { /* Manager недоступен — оставляем v3.0.0 */ });
}

function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('show');
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('show');
}

function showToast(message, type) {
    type = type || 'info';
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.style.cssText = 'padding:12px 18px;border-radius:6px;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.2);font-size:13px;min-width:180px;' +
        (type === 'success' ? 'background:#28a745;' :
         type === 'error'   ? 'background:#dc3545;' :
         type === 'warning' ? 'background:#ffc107;color:#333;' : 'background:#007bff;');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 3500);
}

/* ============================================================
 * Frontend RBAC (BUG-213, v3.14.0)
 * ============================================================ */
// Какие страницы sidebar доступны ролям. admin — все.
const ROLES_PAGES = {
    admin: '*',
    auditor: ['dashboard', 'catalog', 'findings', 'false-positives', 'audit', 'access', 'resources'],
    scanner: ['dashboard', 'catalog', 'findings', 'resources', 'scanners'],
    viewer: ['dashboard', 'catalog', 'findings', 'resources'],
};

const RBAC = {
    roles: [],

    set(roles) {
        this.roles = Array.isArray(roles) ? roles : [];
    },

    has(...needed) {
        return this.roles.some(r => needed.includes(r));
    },

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

// Фильтрация пунктов sidebar по ролям (скрываем недоступные разделы).
function applyRBACNav() {
    document.querySelectorAll('.sidebar-nav .nav-item[data-page]').forEach(el => {
        el.style.display = RBAC.canPage(el.dataset.page) ? '' : 'none';
    });
    const div = document.querySelector('.nav-divider.nav-admin');
    if (div) div.style.display = RBAC.isAdmin() ? '' : 'none';
}

// Инициализация сессии: проверка авторизации, имя/роли, RBAC-фильтр навигации.
async function initSession() {
    if (typeof Auth === 'undefined') return null;
    if (window.location.pathname === '/login') return null;

    let me = null;
    const ok = await Auth.check();
    if (ok) {
        try { me = await Auth.me(); } catch (e) { /* токен протух — /login */ }
    }
    const roles = me && Array.isArray(me.roles) ? me.roles : [];
    RBAC.set(roles);
    applyRBACNav();

    const nameEl = document.getElementById('currentUserName');
    if (nameEl) nameEl.textContent = (me && (me.full_name || me.username)) || 'Пользователь';
    const rolesEl = document.getElementById('currentUserRoles');
    if (rolesEl) rolesEl.textContent = roles.join(', ');
    return me;
}

// Промис готовности сессии — страничные скрипты ждут его, чтобы читать RBAC.
let _sessionPromise = Promise.resolve();
window.whenSessionReady = function () { return _sessionPromise; };

document.addEventListener('DOMContentLoaded', function () {
    initSidebar();
    updateFooterTime();
    initFooterVersion();
    setInterval(updateFooterTime, 10000);

    _sessionPromise = initSession();

    // Гамбургер (BUG-228): клик по кнопке в шапке сайдбара.
    document.getElementById('sidebar-toggle')?.addEventListener('click', toggleSidebar);
    // Клик по пункту меню на мобильном закрывает панель.
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => {
        el.addEventListener('click', function () {
            if (window.innerWidth <= 768) closeSidebarMobile();
        });
    });
    // При выходе за breakpoint сбрасываем оверлей.
    window.addEventListener('resize', function () {
        if (window.innerWidth > 768) closeSidebarMobile();
    });
});