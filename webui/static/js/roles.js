// webui/static/js/roles.js
const ROLES_API = '/api/auth/roles';

let rolesCache = [];

async function loadRoles() {
    try {
        const data = await api.get(ROLES_API);
        rolesCache = (data && data.items) ? data.items : (Array.isArray(data) ? data : []);
    } catch (e) {
        rolesCache = [];
    }
    renderRoles();
}

function renderRoles() {
    const body = document.getElementById('rolesTableBody');
    if (!rolesCache.length) {
        body.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет ролей</td></tr>';
        return;
    }
    body.innerHTML = rolesCache.map(r => {
        const isSystem = (r.is_system === true) || ['admin','auditor','scanner','viewer'].includes(r.name);
        return `<tr>
            <td><b>${r.name}</b>${isSystem ? ' <span class="badge bg-info">системная</span>' : ''}</td>
            <td>${r.description || '—'}</td>
            <td><code>${r.ad_group || '—'}</code></td>
            <td>${r.user_count || 0}</td>
            <td class="text-end" style="white-space:nowrap;">
                <button class="btn btn-sm btn-outline-primary" onclick="editRole(${r.id})" title="Редактировать"><i class="fas fa-edit"></i></button>
                ${isSystem ? '' : `<button class="btn btn-sm btn-outline-danger" onclick="deleteRole(${r.id})" title="Удалить"><i class="fas fa-trash"></i></button>`}
            </td></tr>`;
    }).join('');
}

function showCreateRoleModal() {
    document.getElementById('roleModalTitle').textContent = 'Создание роли';
    document.getElementById('roleId').value = '';
    ['roleName','roleDescription','roleAdGroup'].forEach(id => { document.getElementById(id).value = ''; });
    openModal('roleModal');
}

async function editRole(id) {
    try {
        const r = await api.get(ROLES_API + '/' + id);
        document.getElementById('roleModalTitle').textContent = 'Редактирование роли';
        document.getElementById('roleId').value = r.id;
        document.getElementById('roleName').value = r.name;
        document.getElementById('roleDescription').value = r.description || '';
        document.getElementById('roleAdGroup').value = r.ad_group || '';
        openModal('roleModal');
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

async function saveRole() {
    const id = document.getElementById('roleId').value;
    const name = document.getElementById('roleName').value.trim();
    if (!name) { showToast('Укажите название роли', 'warning'); return; }
    const payload = {
        name,
        description: document.getElementById('roleDescription').value.trim() || null,
        ad_group: document.getElementById('roleAdGroup').value.trim() || null,
    };
    try {
        if (id) {
            await api.put(ROLES_API + '/' + id, payload);
        } else {
            await api.post(ROLES_API, payload);
        }
        showToast('Роль сохранена', 'success');
        closeModal('roleModal');
        loadRoles();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

async function deleteRole(id) {
    if (!confirm('Удалить роль #' + id + '?')) return;
    try {
        await api.delete(ROLES_API + '/' + id);
        showToast('Роль удалена', 'success');
        loadRoles();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', loadRoles);
