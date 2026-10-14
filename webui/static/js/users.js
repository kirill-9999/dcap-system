// webui/static/js/users.js
// 53.4d: форма в <form>, подтверждение пароля, привязка AD, валідация username,
// self-защита, читаемый статус, русские ошибки, created_at/last_login.
const USERS_API = '/api/auth/users';
const ROLES_API = '/api/auth/roles';

let currentPage = 0;
let totalPages = 0;
let usersCache = [];
let rolesCache = [];
let CURRENT_USER_ID = null;

const PER_PAGE = 10;
const AUTH_SOURCE_RU = { local: 'Локальная', ad: 'AD' };

function getParams() {
    const params = {
        limit: PER_PAGE,
        offset: currentPage * PER_PAGE,
        search: document.getElementById('searchUsers').value.trim(),
    };
    const src = document.getElementById('filterSource').value;
    const role = document.getElementById('filterRole').value;
    if (src) params.source = src;
    if (role) params.role = role;
    return params;
}

async function loadRoles() {
    try {
        const data = await api.get(ROLES_API);
        rolesCache = (data && data.items) ? data.items : (Array.isArray(data) ? data : []);
    } catch (e) {
        rolesCache = [];
    }
}

async function loadUsers(page) {
    if (page !== undefined) currentPage = page;
    try {
        const data = await api.get(USERS_API, getParams());
        const users = (data && data.items) ? data.items : (Array.isArray(data) ? data : []);
        usersCache = users;
        const total = (data && data.total !== undefined) ? data.total : users.length;
        totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
    } catch (e) {
        document.getElementById('usersTableBody').innerHTML =
            `<tr><td colspan="9" class="text-center text-danger">Не удалось загрузить: ${escapeHtml(errorToRussian(e.message))}</td></tr>`;
        return;
    }
    renderUsers();
}

function roleBadges(roles) {
    if (!roles || !roles.length) return '<span class="text-muted">—</span>';
    return roles.map(r => {
        const name = typeof r === 'string' ? r : (r.name || '');
        return `<span class="badge badge-primary me-1">${escapeHtml(name)}</span>`;
    }).join('');
}

function renderUsers() {
    const body = document.getElementById('usersTableBody');
    if (!usersCache.length) {
        body.innerHTML = '<tr><td colspan="9" class="text-center text-muted">Пользователи не найдены</td></tr>';
        document.getElementById('pageInfo').textContent = '';
        return;
    }
    body.innerHTML = usersCache.map(u => {
        const active = u.is_active !== false;
        const isSelf = u.id === CURRENT_USER_ID;
        // BACKLOG-131: понятные статусы.
        const status = active
            ? '<span class="badge badge-success">Активен</span>'
            : '<span class="badge badge-danger">Заблокирован</span>';
        // BUG-164/BACKLOG-145: для себя деструктивные действия недоступны.
        const editBtn = `<button class="btn btn-sm btn-outline-primary" onclick="editUser(${u.id})" title="Редактировать"><i class="fas fa-edit"></i></button>`;
        const toggleBtn = isSelf ? '' :
            `<button class="btn btn-sm btn-outline-warning" onclick="toggleUser(${u.id})" title="${active ? 'Заблокировать' : 'Разблокировать'}"><i class="fas fa-power-off"></i></button>`;
        const delBtn = isSelf ? '' :
            `<button class="btn btn-sm btn-outline-danger" onclick="deleteUser(${u.id})" title="Удалить"><i class="fas fa-trash"></i></button>`;
        return `<tr>
            <td>${escapeHtml(u.username)}${isSelf ? ' <span class="badge badge-secondary" title="Это вы">вы</span>' : ''}</td>
            <td>${escapeHtml(u.full_name || '—')}</td>
            <td>${escapeHtml(u.email || '—')}</td>
            <td>${escapeHtml(u.auth_source === 'ad' ? 'AD' : 'Локальная')}${u.domain_user ? `<div class="text-muted small">${escapeHtml(u.domain_user)}</div>` : ''}</td>
            <td>${roleBadges(u.roles)}</td>
            <td>${status}</td>
            <td class="text-nowrap">${u.created_at ? formatDate(u.created_at) : '—'}</td>
            <td class="text-nowrap">${u.last_login ? formatDate(u.last_login) : '—'}</td>
            <td class="text-end" style="white-space:nowrap;">${editBtn} ${toggleBtn} ${delBtn}</td>
        </tr>`;
    }).join('');
    document.getElementById('pageInfo').textContent = `Стр. ${currentPage + 1} из ${Math.max(totalPages, 1)}`;
}

// ===== Модалка =====

function _isEditMode() {
    return !!document.getElementById('userId').value;
}

function toggleAuthSource() {
    const src = document.getElementById('authSource').value;
    const isEdit = _isEditMode();
    document.getElementById('domainUserGroup').style.display = src === 'ad' ? '' : 'none';
    // Для AD пароль не нужен.
    document.getElementById('passwordGroup').style.display = src === 'local' ? '' : 'none';
    if (isEdit) {
        // В режиме редактирования пароль скрыт до «Сбросить пароль».
        document.getElementById('passwordGroup').style.display = 'none';
        document.getElementById('resetPasswordWrap').style.display = (src === 'local') ? '' : 'none';
    }
}

function showResetPassword() {
    document.getElementById('passwordGroup').style.display = '';
    document.getElementById('passwordLabel').textContent = 'Новый пароль';
    document.getElementById('passwordHint').textContent = 'Оставьте пустым, чтобы не менять.';
    document.getElementById('passwordConfirmGroup').style.display = '';
    document.getElementById('resetPasswordWrap').style.display = 'none';
}

async function showCreateUserModal() {
    await loadRoles();
    document.getElementById('userModalTitle').textContent = 'Создание пользователя';
    document.getElementById('userId').value = '';
    ['username', 'fullName', 'email', 'password', 'passwordConfirm', 'domainUser']
        .forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('username').disabled = false;
    document.getElementById('authSource').disabled = false;
    document.getElementById('authSource').value = 'local';
    document.getElementById('passwordGroup').style.display = '';
    document.getElementById('passwordLabel').textContent = 'Пароль *';
    document.getElementById('passwordHint').textContent = 'Рекомендуется не менее 8 символов.';
    document.getElementById('passwordConfirmGroup').style.display = '';
    document.getElementById('resetPasswordWrap').style.display = 'none';
    document.getElementById('domainUserGroup').style.display = 'none';
    document.getElementById('isActive').checked = true;  // BUG-159: активен по умолчанию.
    document.getElementById('isActive').disabled = false;
    renderRolesCheckboxes(['viewer']);
    openModal('userModal');
}

async function editUser(id) {
    await loadRoles();
    try {
        const u = await api.get(USERS_API + '/' + id);
        const isSelf = u.id === CURRENT_USER_ID;
        document.getElementById('userModalTitle').textContent = `Редактирование: ${u.username}`;
        document.getElementById('userId').value = u.id;
        document.getElementById('username').value = u.username;
        document.getElementById('username').disabled = true;  // BACKLOG-141: логин не редактируется.
        document.getElementById('fullName').value = u.full_name || '';
        document.getElementById('email').value = u.email || '';
        document.getElementById('authSource').value = u.auth_source || 'local';
        document.getElementById('authSource').disabled = true;  // BACKLOG-142: тип учётки read-only.
        document.getElementById('domainUser').value = u.domain_user || '';
        document.getElementById('domainUserGroup').style.display = (u.auth_source === 'ad') ? '' : 'none';
        // Пароль: скрыт, доступен через «Сбросить пароль» (BACKLOG-143).
        ['password', 'passwordConfirm'].forEach(x => { document.getElementById(x).value = ''; });
        document.getElementById('passwordGroup').style.display = 'none';
        document.getElementById('passwordLabel').textContent = 'Новый пароль';
        document.getElementById('passwordHint').textContent = '';
        document.getElementById('resetPasswordWrap').style.display = (u.auth_source === 'ad') ? 'none' : '';
        // BUG-162/BACKLOG-145: корректно грузим роли и активность; себя нельзя заблокировать.
        document.getElementById('isActive').checked = u.is_active !== false;
        document.getElementById('isActive').disabled = isSelf;
        renderRolesCheckboxes((u.roles || []).map(r => typeof r === 'string' ? r : r.name));
        openModal('userModal');
    } catch (e) {
        showToast('Ошибка загрузки: ' + errorToRussian(e.message), 'error');
    }
}

function renderRolesCheckboxes(selectedRoles) {
    const cont = document.getElementById('rolesCheckboxes');
    if (!rolesCache.length) { cont.innerHTML = '<span class="text-muted">Нет ролей</span>'; return; }
    cont.innerHTML = rolesCache.map(r => {
        const id = 'rolechk_' + r.name.replace(/[^A-Za-z0-9_]/g, '_');
        const checked = selectedRoles.includes(r.name) ? 'checked' : '';
        return `<div class="form-check"><input class="form-check-input" type="checkbox" id="${id}" data-role="${escapeHtml(r.name)}" ${checked}><label class="form-check-label" for="${id}">${escapeHtml(r.name)}</label></div>`;
    }).join('');
}

function getSelectedRoles() {
    return Array.from(document.querySelectorAll('#rolesCheckboxes input:checked')).map(cb => cb.dataset.role);
}

async function saveUser() {
    const id = document.getElementById('userId').value;
    const isEdit = !!id;
    const username = document.getElementById('username').value.trim();
    const authSource = document.getElementById('authSource').value;
    const pw = document.getElementById('password').value;
    const pw2 = document.getElementById('passwordConfirm').value;

    // BACKLOG-137: валидация username на клиенте (для создания).
    if (!isEdit) {
        if (!/^[A-Za-z0-9_.-]{3,50}$/.test(username)) {
            showToast('Имя пользователя: 3–50 символов, латиница, цифры, _ . -', 'warning');
            return;
        }
    }
    // BACKLOG-135/196: подтверждение пароля.
    const passwordVisible = document.getElementById('passwordGroup').style.display !== 'none';
    if (authSource === 'local' && !isEdit && !pw) {
        showToast('Введите пароль', 'warning'); return;
    }
    if (passwordVisible && pw && pw !== pw2) {
        showToast('Пароли не совпадают', 'warning'); return;
    }
    if (pw && pw.length < 6) {
        showToast('Пароль слишком короткий (минимум 6 символов)', 'warning'); return;
    }

    const payload = {
        full_name: document.getElementById('fullName').value.trim() || null,
        email: document.getElementById('email').value.trim() || null,
        roles: getSelectedRoles(),
        is_active: document.getElementById('isActive').checked,
    };

    try {
        if (isEdit) {
            if (authSource === 'ad') payload.domain_user = document.getElementById('domainUser').value.trim() || null;
            if (pw) payload.password = pw;
            await api.put(USERS_API + '/' + id, payload);
            showToast('Пользователь обновлён', 'success');
        } else {
            payload.username = username;
            payload.auth_source = authSource;
            if (authSource === 'ad') payload.domain_user = document.getElementById('domainUser').value.trim() || null;
            if (authSource === 'local') payload.password = pw;
            await api.post(USERS_API, payload);
            showToast('Пользователь создан', 'success');
        }
        closeModal('userModal');
        loadUsers(isEdit ? currentPage : 0);
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

async function toggleUser(id) {
    const u = usersCache.find(x => x.id === id);
    const active = u && u.is_active !== false;
    const username = u ? u.username : ('#' + id);
    if (!confirm(active ? `Заблокировать пользователя «${username}»?` : `Разблокировать пользователя «${username}»?`)) return;
    try {
        await api.put(USERS_API + '/' + id + '/status', { is_active: !active });
        showToast(!active ? 'Пользователь разблокирован' : 'Пользователь заблокирован', 'success');
        loadUsers();
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

async function deleteUser(id) {
    const u = usersCache.find(x => x.id === id);
    const username = u ? u.username : ('#' + id);
    // BUG-164: подтверждение с именем, а не с внутренним ID.
    if (!confirm(`Удалить пользователя «${username}»? Действие необратимо.`)) return;
    try {
        await api.delete(USERS_API + '/' + id);
        showToast(`Пользователь «${username}» удалён`, 'success');
        loadUsers(0);
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

function prevPage() { if (currentPage > 0) loadUsers(currentPage - 1); }
function nextPage() { if (currentPage + 1 < totalPages) loadUsers(currentPage + 1); }

let _searchTimerRef = null;
function debouncedSearch() {
    clearTimeout(_searchTimerRef);
    _searchTimerRef = setTimeout(() => loadUsers(0), 350);
}

document.addEventListener('DOMContentLoaded', async function () {
    try {
        const me = (typeof Auth !== 'undefined') ? await Auth.me() : null;
        if (me && me.id) CURRENT_USER_ID = me.id;
    } catch (e) { /* без self-защиты */ }
    loadUsers(0);
});
