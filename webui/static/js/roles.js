// webui/static/js/roles.js
// 53.4d: единый стиль бейджей, различиe системных/кастомных ролей, удаление
// из модалки, локализация, тосты Dovetail с именем роли.
const ROLES_API = '/api/auth/roles';
const SYSTEM_ROLE_NAMES = ['admin', 'auditor', 'scanner', 'viewer'];

// BACKLOG-150: локализованные описания системных ролей (если в БД пусто).
const SYSTEM_ROLE_DESC = {
    admin: 'Полный доступ ко всем разделам и настройкам',
    auditor: 'Аудит находок, событий и прав доступа',
    scanner: 'Управление сканированием и сканерами',
    viewer: 'Просмотр дашборда, каталога и находок',
};

let rolesCache = [];

function isSystemRole(r) {
    return r.is_system === true || SYSTEM_ROLE_NAMES.includes(r.name);
}

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
        const sys = isSystemRole(r);
        // BUG-171/BACKLOG-146/152: понятный бейдж с подсказкой, единый стиль.
        const badge = sys
            ? '<span class="badge badge-info" title="Системная роль: нельзя переименовать, удалить или изменить AD-группу">системная</span>'
            : '<span class="badge badge-secondary" title="Пользовательская роль: можно изменить и удалить">пользовательская</span>';
        // BUG-167/150: AD-группа может отсутствовать — показываем «—» с подсказкой.
        const adGroup = r.ad_group
            ? `<code>${escapeHtml(r.ad_group)}</code>`
            : '<span class="text-muted" title="AD-группа не привязана">—</span>';
        const desc = r.description || SYSTEM_ROLE_DESC[r.name] || '—';
        return `<tr class="${sys ? '' : 'table-active'}">
            <td><b>${escapeHtml(r.name)}</b> ${badge}</td>
            <td>${escapeHtml(desc)}</td>
            <td>${adGroup}</td>
            <td>${r.user_count || 0}</td>
            <td class="text-end" style="white-space:nowrap;">
                <button class="btn btn-sm btn-outline-primary" onclick="editRole(${r.id})" title="Редактировать"><i class="fas fa-edit"></i></button>
                ${sys ? '' : `<button class="btn btn-sm btn-outline-danger" onclick="deleteRole(${r.id}, '${escapeHtml(r.name)}')" title="Удалить роль"><i class="fas fa-trash"></i></button>`}
            </td></tr>`;
    }).join('');
}

function showCreateRoleModal() {
    document.getElementById('roleModalTitle').textContent = 'Создание роли';
    document.getElementById('roleId').value = '';
    ['roleName', 'roleDescription', 'roleAdGroup'].forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('roleName').disabled = false;
    document.getElementById('roleAdGroup').disabled = false;
    document.getElementById('roleDeleteBtn').style.display = 'none';
    openModal('roleModal');
}

async function editRole(id) {
    try {
        const r = await api.get(ROLES_API + '/' + id);
        const sys = isSystemRole(r);
        document.getElementById('roleModalTitle').textContent = 'Редактирование роли: ' + r.name;
        document.getElementById('roleId').value = r.id;
        document.getElementById('roleName').value = r.name;
        document.getElementById('roleDescription').value = r.description || SYSTEM_ROLE_DESC[r.name] || '';
        document.getElementById('roleAdGroup').value = r.ad_group || '';
        // BUG-168 (backend): системные роли нельзя переименовать/сменить AD-группу.
        document.getElementById('roleName').disabled = sys;
        document.getElementById('roleAdGroup').disabled = sys;
        // BACKLOG-149: удаление прямо из модалки (только для кастомных ролей).
        document.getElementById('roleDeleteBtn').style.display = sys ? 'none' : '';
        openModal('roleModal');
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

async function saveRole() {
    const id = document.getElementById('roleId').value;
    const name = document.getElementById('roleName').value.trim();
    if (!name) { showToast('Укажите название роли', 'warning'); return; }
    // BACKLOG-137-подобная валидация имени роли.
    if (!/^[A-Za-z0-9_.-]{3,50}$/.test(name)) {
        showToast('Название: 3–50 символов, латиница, цифры, _ . -', 'warning');
        return;
    }
    const payload = {
        name,
        description: document.getElementById('roleDescription').value.trim() || null,
        ad_group: document.getElementById('roleAdGroup').value.trim() || null,
    };
    try {
        if (id) {
            await api.put(ROLES_API + '/' + id, payload);
            showToast(`Роль «${name}» сохранена`, 'success');
        } else {
            await api.post(ROLES_API, payload);
            showToast(`Роль «${name}» создана`, 'success');
        }
        closeModal('roleModal');
        loadRoles();
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

function deleteRoleFromModal() {
    const id = document.getElementById('roleId').value;
    if (id) deleteRole(parseInt(id, 10), document.getElementById('roleName').value);
}

async function deleteRole(id, name) {
    const label = name ? `«${name}»` : ('#' + id);
    if (!confirm('Удалить роль ' + label + '? Действие необратимо.')) return;
    try {
        await api.delete(ROLES_API + '/' + id);
        showToast(`Роль ${label} удалена`, 'success');
        closeModal('roleModal');
        loadRoles();
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

function showCreateRoleModalCompat() { showCreateRoleModal(); }

document.addEventListener('DOMContentLoaded', loadRoles);
