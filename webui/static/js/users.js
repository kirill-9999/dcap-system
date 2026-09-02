// webui/static/js/users.js
const USERS_API = '/api/auth/users';
const ROLES_API = '/api/auth/roles';

let currentPage = 0;
let totalPages = 0;
let usersCache = [];
let rolesCache = [];

const PER_PAGE = 10;

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
        rolesCache = await api.get(ROLES_API);
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
        usersCache = [];
        totalPages = 1;
        document.getElementById('usersTableBody').innerHTML = '<tr><td colspan="7" class="text-center text-muted">Ошибка загрузки: ' + e.message + '</td></tr>';
        return;
    }
    renderUsers();
}

function renderUsers() {
    const body = document.getElementById('usersTableBody');
    if (!usersCache.length) {
        body.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Нет пользователей</td></tr>';
        document.getElementById('pageInfo').textContent = '0 записей';
        return;
    }
    let html = '';
    usersCache.forEach(u => {
        const roles = (u.roles || []).map(r => {
            const name = typeof r === 'string' ? r : (r.name || r);
            return `<span class="badge bg-secondary">${name}</span>`;
        }).join(' ') || '<span class="text-muted">—</span>';
        const active = u.is_active !== false;
        html += `<tr>
            <td>${u.username}</td>
            <td>${u.full_name || '—'}</td>
            <td>${u.email || '—'}</td>
            <td>${u.auth_source || 'local'}</td>
            <td>${roles}</td>
            <td>${active ? '<span class="badge bg-success">Вкл</span>' : '<span class="badge bg-danger">Откл</span>'}</td>
            <td class="text-end" style="white-space:nowrap;">
                <button class="btn btn-sm btn-outline-primary" onclick="editUser(${u.id})" title="Редактировать"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-outline-warning" onclick="toggleUser(${u.id})" title="Вкл/Выкл"><i class="fas fa-power-off"></i></button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteUser(${u.id})" title="Удалить"><i class="fas fa-trash"></i></button>
            </td></tr>`;
    });
    body.innerHTML = html;
    document.getElementById('pageInfo').textContent = `Стр. ${currentPage + 1} из ${Math.max(totalPages, 1)}`;
}

async function showCreateUserModal() {
    await loadRoles();
    document.getElementById('userModalTitle').textContent = 'Создание пользователя';
    document.getElementById('userId').value = '';
    ['username','fullName','email','password'].forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('authSource').value = 'local';
    document.getElementById('passwordGroup').style.display = '';
    document.getElementById('password').required = true;
    document.getElementById('isActive').checked = true;
    renderRolesCheckboxes([]);
    openModal('userModal');
}

async function editUser(id) {
    await loadRoles();
    try {
        const u = await api.get(USERS_API + '/' + id);
        document.getElementById('userModalTitle').textContent = 'Редактирование пользователя';
        document.getElementById('userId').value = u.id;
        document.getElementById('username').value = u.username;
        document.getElementById('fullName').value = u.full_name || '';
        document.getElementById('email').value = u.email || '';
        document.getElementById('password').value = '';
        document.getElementById('authSource').value = u.auth_source || 'local';
        document.getElementById('passwordGroup').style.display = 'none';
        document.getElementById('password').required = false;
        document.getElementById('isActive').checked = u.is_active !== false;
        document.getElementById('username').disabled = true;
        renderRolesCheckboxes((u.roles || []).map(r => typeof r === 'string' ? r : r.name));
        openModal('userModal');
    } catch (e) {
        showToast('Ошибка загрузки: ' + e.message, 'error');
    }
}

function renderRolesCheckboxes(selectedRoles) {
    const cont = document.getElementById('rolesCheckboxes');
    if (!rolesCache.length) { cont.innerHTML = '<span class="text-muted">Нет ролей</span>'; return; }
    cont.innerHTML = rolesCache.map(r => {
        const checked = selectedRoles.includes(r.name) ? 'checked' : '';
        return `<div class="form-check"><input class="form-check-input" type="checkbox" id="rolechk_${r.name}" ${checked}><label class="form-check-label" for="rolechk_${r.name}">${r.name}</label></div>`;
    }).join('');
}

function togglePasswordRequired() {
    const src = document.getElementById('authSource').value;
    document.getElementById('passwordGroup').style.display = src === 'local' ? '' : 'none';
    document.getElementById('password').required = src === 'local' && !document.getElementById('userId').value;
}

function getSelectedRoles() {
    return Array.from(document.querySelectorAll('#rolesCheckboxes input:checked')).map(cb => cb.id.replace('rolechk_', ''));
}

async function saveUser() {
    const id = document.getElementById('userId').value;
    const username = document.getElementById('username').value.trim();
    if (!username) { showToast('Укажите имя пользователя', 'warning'); return; }
    const payload = {
        full_name: document.getElementById('fullName').value.trim() || null,
        email: document.getElementById('email').value.trim() || null,
        roles: getSelectedRoles(),
        is_active: document.getElementById('isActive').checked,
    };
    if (id) {
        payload.username = username;
        const pw = document.getElementById('password').value;
        if (pw) payload.password = pw;
        try {
            await api.put(USERS_API + '/' + id, payload);
            showToast('Пользователь обновлён', 'success');
        } catch (e) {
            showToast('Ошибка: ' + e.message, 'error'); return;
        }
    } else {
        payload.auth_source = document.getElementById('authSource').value;
        const pw = document.getElementById('password').value;
        if (payload.auth_source === 'local' || pw) payload.password = pw || undefined;
        try {
            await api.post(USERS_API, payload);
            showToast('Пользователь создан', 'success');
        } catch (e) {
            showToast('Ошибка: ' + e.message, 'error'); return;
        }
    }
    closeModal('userModal');
    document.getElementById('username').disabled = false;
    loadUsers(0);
}

async function toggleUser(id) {
    const u = usersCache.find(x => x.id === id);
    const newActive = !(u && u.is_active !== false);
    try {
        await api.put(USERS_API + '/' + id + '/status', { is_active: newActive });
        showToast(newActive ? 'Пользователь включён' : 'Пользователь отключён', 'success');
        loadUsers();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

async function deleteUser(id) {
    if (!confirm('Удалить пользователя #' + id + '?')) return;
    try {
        await api.delete(USERS_API + '/' + id);
        showToast('Пользователь удалён', 'success');
        loadUsers(0);
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

function prevPage() { if (currentPage > 0) loadUsers(currentPage - 1); }
function nextPage() { if (currentPage + 1 < totalPages) loadUsers(currentPage + 1); }

document.addEventListener('DOMContentLoaded', () => loadUsers(0));
