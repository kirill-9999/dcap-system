📋 ТЗ — ДЕНЬ 33: ACTIVE DIRECTORY ИНТЕГРАЦИЯ + RBAC WEBUI
Файл: prompts/tz/day_33_ad_integration.md
Дата: 01.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Реализовать полноценную интеграцию с Active Directory и WebUI для управления RBAC:

Аутентификация через AD — SPNEGO + явный логин (пароль)

Сбор прав доступа — NTFS (Windows) и POSIX (Linux) через агентов

Разрешение SID → имя — трансляция через AD

Ролевая модель — маппинг AD групп на роли DCAP

Кэширование — Redis для снижения нагрузки на AD

WebUI управления RBAC — создание/редактирование/удаление пользователей и ролей

Тестирование — через Samba AD DC в Docker

👤 РОЛЕВАЯ МОДЕЛЬ DCAP V3.0.0
Роли и права
Роль	Описание	Права
Admin	Полный доступ	✅ CRUD пользователей, настройки, все данные, управление агентами
Auditor	Аудит и мониторинг	✅ Просмотр аудит-логов, дашборда, каталога, прав доступа
Scanner	Запуск сканирования	✅ Запуск сканирования, просмотр ресурсов и находок
Viewer	Только чтение	✅ Просмотр дашборда, каталога, находок
Матрица доступа
Эндпоинт	Admin	Auditor	Scanner	Viewer
/api/audit/* (чтение)	✅	✅	❌	❌
/api/audit/agents/*	✅	❌	❌	❌
/api/findings/* (чтение)	✅	✅	✅	✅
/api/findings/* (удаление)	✅	❌	❌	❌
/api/catalog/* (чтение)	✅	✅	✅	✅
/api/scanner/* (запуск)	✅	❌	✅	❌
/api/resources/* (чтение)	✅	✅	✅	✅
/api/resources/* (управление)	✅	❌	❌	❌
/api/resources/{id}/scan	✅	❌	✅	❌
/api/permissions/* (чтение)	✅	✅	❌	❌
/api/auth/users/*	✅	❌	❌	❌
/api/settings/*	✅	❌	❌	❌
Маппинг AD групп → роли DCAP
AD группа	Роль DCAP
DCAP_Admins	admin
DCAP_Auditors	auditor
DCAP_Scanners	scanner
(все остальные)	viewer
📁 СТРУКТУРА ИЗМЕНЕНИЙ
text
manager/src/auth/
├── windows_auth.py          # ОБНОВЛЕН: SPNEGO (полная реализация)
├── ad_auth.py               # НОВЫЙ: явный логин через AD (пароль)
├── manager.py               # ОБНОВЛЕН: интеграция AD аутентификации
├── dependencies.py          # ОБНОВЛЕН: получение групп из AD
└── router.py                # ОБНОВЛЕН: /api/auth/* с AD

manager/src/connectors/permissions/
├── ad.py                    # НОВЫЙ: ADConnector (LDAP, SID → имя)
├── cache.py                 # НОВЫЙ: кэширование AD запросов (Redis)
├── factory.py               # НОВЫЙ: фабрика провайдеров
└── base.py                  # ОБНОВЛЕН: AccessEntry модель

manager/src/api/
├── audit.py                 # ОБНОВЛЕН: POST /api/audit/permissions
└── permissions.py           # ОБНОВЛЕН: GET /api/permissions/*

manager/src/db/
└── models.py                # ОБНОВЛЕН: AccessEntry, Resource

audit-agent-windows/src/
├── collector.py             # ОБНОВЛЕН: + collect_permissions()
├── sender.py                # ОБНОВЛЕН: + send_permissions()
└── main.py                  # ОБНОВЛЕН: периодический сбор

audit-agent-linux/src/
├── collector.py             # ОБНОВЛЕН: + collect_permissions()
├── sender.py                # ОБНОВЛЕН: + send_permissions()
└── main.py                  # ОБНОВЛЕН: периодический сбор

scanner/src/
├── managed_scanner.py       # ОБНОВЛЕН: сбор прав (fallback)
└── handlers/
    └── finding_collector.py # ОБНОВЛЕН: + сбор прав

webui/templates/
├── access.html              # ОБНОВЛЕН: отображение прав доступа
├── settings.html            # ОБНОВЛЕН: + управление пользователями
├── users.html               # НОВЫЙ: управление пользователями
├── roles.html               # НОВЫЙ: управление ролями
└── components/
    ├── permissions_table.html  # НОВЫЙ: таблица прав
    ├── user_form.html          # НОВЫЙ: форма пользователя
    └── role_form.html          # НОВЫЙ: форма роли

webui/static/js/
├── users.js                 # НОВЫЙ: управление пользователями
└── roles.js                 # НОВЫЙ: управление ролями

docker-compose.ad.yml        # НОВЫЙ: Samba AD DC
scripts/init_ad_test_data.py # НОВЫЙ: тестовые данные
🔧 ТЕСТОВАЯ СРЕДА
docker-compose.ad.yml
yaml
services:
  samba-ad-dc:
    image: diegogslomp/samba-ad-dc
    container_name: dcap-ad-dc
    privileged: true
    restart: unless-stopped
    environment:
      REALM: 'SAMDOM.EXAMPLE.COM'
      DOMAIN: 'SAMDOM'
      ADMIN_PASS: 'Passw0rd'
    hostname: DC1
    ports:
      - "389:389"
      - "636:636"
      - "88:88"
      - "445:445"
    volumes:
      - samba_data:/var/lib/samba
    networks:
      - dcap-network

  redis:
    image: redis:7-alpine
    container_name: dcap-redis
    ports:
      - "6379:6379"
    networks:
      - dcap-network

volumes:
  samba_data:
init_ad_test_data.py
python
# Скрипт создает:
# Группы: DCAP_Admins, DCAP_Auditors, DCAP_Scanners
# Пользователи: v.petrov (Admins), a.smirnov (Auditors), s.petrov (Scanners)
# Пароль для всех: Passw0rd
🔐 АУТЕНТИФИКАЦИЯ ЧЕРЕЗ AD
1. windows_auth.py — SPNEGO
python
class WindowsAuthenticator:
    """SPNEGO/Kerberos аутентификация"""
    
    def authenticate(self, auth_header: str) -> Optional[str]:
        """Возвращает DOMAIN\username"""
        # Реальная валидация через spnego
        # Mock для разработки (без AD)
    
    def get_user_groups(self, domain_user: str) -> List[str]:
        """Получение групп из AD"""
    
    def get_user_info(self, domain_user: str) -> Optional[dict]:
        """Информация о пользователе"""
2. ad_auth.py — явный логин
python
class ADAuthenticator:
    """Явный логин через AD (пароль)"""
    
    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Проверка через LDAP, возвращает информацию о пользователе"""
3. AuthManager — интеграция
python
class AuthManager:
    async def authenticate(self, request, db, username, password):
        # 1. SPNEGO (Windows Integrated Auth)
        # 2. Явный логин через AD (пароль)
        # 3. Локальный пользователь (JWT + Bcrypt)
        # 4. Fallback в зависимости от режима
📊 СБОР ПРАВ ЧЕРЕЗ АГЕНТОВ
Windows Agent — NTFS права
python
def collect_permissions(self, path: str) -> List[Dict]:
    """Сбор NTFS прав через win32security"""
    sd = win32security.GetFileSecurity(path, ...)
    dacl = sd.GetSecurityDescriptorDacl()
    # Парсинг ACE → AccessEntry
Linux Agent — POSIX права
python
def collect_permissions(self, path: str) -> List[Dict]:
    """Сбор POSIX прав через getfacl"""
    result = subprocess.run(["getfacl", path], ...)
    # Парсинг вывода → AccessEntry
Периодичность
Интервал сбора: настраиваемый (по умолчанию 1 час)

Отправка в Manager: POST /api/audit/permissions

🗄️ МОДЕЛИ БД
python
class Resource(Base):
    id = Column(Integer, primary_key=True)
    path = Column(String(500), unique=True, nullable=False)
    access_entries = relationship("AccessEntry")

class AccessEntry(Base):
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    principal = Column(String(200), nullable=False)      # DOMAIN\User
    principal_type = Column(String(20), nullable=False)  # user, group
    permissions = Column(JSON, nullable=False)           # ["read", "write"]
    is_inherited = Column(Boolean, default=False)
    source = Column(String(50), default="local")         # windows_agent, ad
    collected_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    # ... существующие поля ...
    domain_user = Column(String(200), nullable=True, index=True)  # DOMAIN\username
    auth_source = Column(String(20), default="local")             # local, ad
    roles = relationship("Role", secondary=user_roles)

class Role(Base):
    # ... существующие поля ...
📡 API ЭНДПОИНТЫ
Аутентификация
Метод	Эндпоинт	Назначение
POST	/api/auth/login	Логин (локальный или AD)
POST	/api/auth/refresh	Обновление токена
POST	/api/auth/logout	Выход
GET	/api/auth/me	Информация о пользователе
GET	/api/auth/mode	Режим аутентификации
Управление пользователями (Admin)
Метод	Эндпоинт	Назначение
GET	/api/auth/users	Список пользователей
POST	/api/auth/users	Создание пользователя
GET	/api/auth/users/{id}	Информация о пользователе
PUT	/api/auth/users/{id}	Обновление пользователя
DELETE	/api/auth/users/{id}	Удаление пользователя
PUT	/api/auth/users/{id}/status	Включение/отключение
PUT	/api/auth/users/{id}/roles	Обновление ролей
Управление ролями (Admin)
Метод	Эндпоинт	Назначение
GET	/api/auth/roles	Список ролей
POST	/api/auth/roles	Создание роли
GET	/api/auth/roles/{id}	Информация о роли
PUT	/api/auth/roles/{id}	Обновление роли
DELETE	/api/auth/roles/{id}	Удаление роли
Права доступа
Метод	Эндпоинт	Назначение
POST	/api/audit/permissions	Прием прав от агента
GET	/api/permissions/resources/{id}	Получение прав для ресурса
GET	/api/permissions/resolve/{sid}	Разрешение SID → имя
GET	/api/permissions/mode	Текущий режим (local/ad/mixed)
🌐 WEBUI — УПРАВЛЕНИЕ RBAC
1. Страница управления пользователями — users.html
html
<!-- webui/templates/users.html -->
{% extends "base.html" %}

{% block content %}
<div class="users-page">
    <div class="page-header">
        <h1><i class="fas fa-users"></i> Пользователи</h1>
        <button class="btn btn-primary" onclick="showCreateUserModal()">
            <i class="fas fa-plus"></i> Создать
        </button>
    </div>

    <!-- Фильтры -->
    <div class="filters">
        <input type="text" id="searchUsers" placeholder="Поиск..." oninput="loadUsers()">
        <select id="filterSource" onchange="loadUsers()">
            <option value="">Все источники</option>
            <option value="local">Локальные</option>
            <option value="ad">AD</option>
        </select>
        <select id="filterRole" onchange="loadUsers()">
            <option value="">Все роли</option>
            <option value="admin">Admin</option>
            <option value="auditor">Auditor</option>
            <option value="scanner">Scanner</option>
            <option value="viewer">Viewer</option>
        </select>
    </div>

    <!-- Таблица -->
    <div class="table-container">
        <table class="table">
            <thead>
                <tr>
                    <th>Имя пользователя</th>
                    <th>Полное имя</th>
                    <th>Email</th>
                    <th>Источник</th>
                    <th>Роли</th>
                    <th>Статус</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody id="usersTableBody">
                <!-- Загружается через JS -->
            </tbody>
        </table>
    </div>

    <!-- Пагинация -->
    <div class="pagination">
        <button onclick="prevPage()"><i class="fas fa-chevron-left"></i></button>
        <span id="pageInfo">Страница 1 из 1</span>
        <button onclick="nextPage()"><i class="fas fa-chevron-right"></i></button>
    </div>
</div>

<!-- Модальное окно создания/редактирования пользователя -->
<div class="modal" id="userModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="userModalTitle">Создание пользователя</h3>
            <button class="close" onclick="closeModal('userModal')">&times;</button>
        </div>
        <div class="modal-body">
            <form id="userForm">
                <input type="hidden" id="userId">
                <div class="form-group">
                    <label>Имя пользователя</label>
                    <input type="text" id="username" class="form-control" required>
                </div>
                <div class="form-group">
                    <label>Полное имя</label>
                    <input type="text" id="fullName" class="form-control">
                </div>
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" id="email" class="form-control">
                </div>
                <div class="form-group" id="passwordGroup">
                    <label>Пароль</label>
                    <input type="password" id="password" class="form-control">
                    <small>Оставьте пустым, если не нужно менять</small>
                </div>
                <div class="form-group">
                    <label>Источник</label>
                    <select id="authSource" class="form-control">
                        <option value="local">Локальный</option>
                        <option value="ad">AD</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Роли</label>
                    <div id="rolesCheckboxes">
                        <!-- Загружается через JS -->
                    </div>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="isActive" checked> Активен
                    </label>
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal('userModal')">Отмена</button>
            <button class="btn btn-primary" onclick="saveUser()">Сохранить</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/users.js"></script>
{% endblock %}
2. Страница управления ролями — roles.html
html
<!-- webui/templates/roles.html -->
{% extends "base.html" %}

{% block content %}
<div class="roles-page">
    <div class="page-header">
        <h1><i class="fas fa-lock"></i> Роли</h1>
        <button class="btn btn-primary" onclick="showCreateRoleModal()">
            <i class="fas fa-plus"></i> Создать роль
        </button>
    </div>

    <!-- Таблица ролей -->
    <div class="table-container">
        <table class="table">
            <thead>
                <tr>
                    <th>Название</th>
                    <th>Описание</th>
                    <th>Пользователей</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody id="rolesTableBody">
                <!-- Загружается через JS -->
            </tbody>
        </table>
    </div>
</div>

<!-- Модальное окно создания/редактирования роли -->
<div class="modal" id="roleModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="roleModalTitle">Создание роли</h3>
            <button class="close" onclick="closeModal('roleModal')">&times;</button>
        </div>
        <div class="modal-body">
            <form id="roleForm">
                <input type="hidden" id="roleId">
                <div class="form-group">
                    <label>Название</label>
                    <input type="text" id="roleName" class="form-control" required>
                </div>
                <div class="form-group">
                    <label>Описание</label>
                    <textarea id="roleDescription" class="form-control"></textarea>
                </div>
                <div class="form-group">
                    <label>AD группа (для маппинга)</label>
                    <input type="text" id="roleAdGroup" class="form-control" 
                           placeholder="DCAP_Admins">
                    <small>Если указано, пользователи из этой AD группы будут автоматически получать роль</small>
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal('roleModal')">Отмена</button>
            <button class="btn btn-primary" onclick="saveRole()">Сохранить</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/roles.js"></script>
{% endblock %}
3. WebUI — users.js
javascript
// webui/static/js/users.js

const USERS_API = '/api/auth/users';
const ROLES_API = '/api/auth/roles';

let users = [];
let roles = [];
let currentPage = 0;
const PAGE_SIZE = 20;

async function loadUsers() {
    const search = document.getElementById('searchUsers').value;
    const source = document.getElementById('filterSource').value;
    const role = document.getElementById('filterRole').value;
    
    let params = new URLSearchParams({
        limit: PAGE_SIZE,
        offset: currentPage * PAGE_SIZE
    });
    if (search) params.append('search', search);
    if (source) params.append('source', source);
    if (role) params.append('role', role);
    
    try {
        const response = await api.get(`${USERS_API}?${params}`);
        users = response.items || [];
        renderUsers(users);
        updatePagination(response.total);
    } catch (e) {
        showToast('Ошибка загрузки пользователей', 'error');
    }
}

function renderUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    if (!users.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">Нет пользователей</td></tr>';
        return;
    }
    
    let html = '';
    for (const user of users) {
        const statusBadge = user.is_active ? 'badge-success' : 'badge-danger';
        const statusText = user.is_active ? 'Активен' : 'Отключен';
        const sourceBadge = user.auth_source === 'ad' ? 'badge-info' : 'badge-secondary';
        const rolesText = user.roles.join(', ') || '—';
        
        html += `
            <tr>
                <td><strong>${user.username}</strong></td>
                <td>${user.full_name || '—'}</td>
                <td>${user.email || '—'}</td>
                <td><span class="badge ${sourceBadge}">${user.auth_source}</span></td>
                <td>${rolesText}</td>
                <td><span class="badge ${statusBadge}">${statusText}</span></td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="editUser(${user.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm ${user.is_active ? 'btn-warning' : 'btn-success'}" 
                            onclick="toggleUserStatus(${user.id}, ${!user.is_active})">
                        <i class="fas ${user.is_active ? 'fa-pause' : 'fa-play'}"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteUser(${user.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

async function loadRolesCheckboxes() {
    try {
        const response = await api.get(ROLES_API);
        roles = response.items || [];
        const container = document.getElementById('rolesCheckboxes');
        container.innerHTML = roles.map(role => `
            <label class="checkbox-inline">
                <input type="checkbox" value="${role.id}" class="role-checkbox">
                ${role.name}
                <small class="text-muted">(${role.description || '—'})</small>
            </label>
        `).join('');
    } catch (e) {
        showToast('Ошибка загрузки ролей', 'error');
    }
}

async function showCreateUserModal() {
    document.getElementById('userModalTitle').textContent = 'Создание пользователя';
    document.getElementById('userId').value = '';
    document.getElementById('userForm').reset();
    document.getElementById('passwordGroup').style.display = 'block';
    await loadRolesCheckboxes();
    openModal('userModal');
}

async function editUser(id) {
    try {
        const response = await api.get(`${USERS_API}/${id}`);
        const user = response;
        
        document.getElementById('userModalTitle').textContent = 'Редактирование пользователя';
        document.getElementById('userId').value = user.id;
        document.getElementById('username').value = user.username;
        document.getElementById('fullName').value = user.full_name || '';
        document.getElementById('email').value = user.email || '';
        document.getElementById('authSource').value = user.auth_source || 'local';
        document.getElementById('isActive').checked = user.is_active;
        document.getElementById('passwordGroup').style.display = 'none';
        
        await loadRolesCheckboxes();
        
        // Отметить роли пользователя
        document.querySelectorAll('.role-checkbox').forEach(cb => {
            cb.checked = user.roles.includes(cb.value);
        });
        
        openModal('userModal');
    } catch (e) {
        showToast('Ошибка загрузки пользователя', 'error');
    }
}

async function saveUser() {
    const id = document.getElementById('userId').value;
    const data = {
        username: document.getElementById('username').value,
        full_name: document.getElementById('fullName').value,
        email: document.getElementById('email').value,
        auth_source: document.getElementById('authSource').value,
        is_active: document.getElementById('isActive').checked,
        roles: Array.from(document.querySelectorAll('.role-checkbox:checked')).map(cb => parseInt(cb.value))
    };
    
    const password = document.getElementById('password').value;
    if (password) {
        data.password = password;
    }
    
    try {
        if (id) {
            await api.put(`${USERS_API}/${id}`, data);
            showToast('Пользователь обновлен', 'success');
        } else {
            await api.post(USERS_API, data);
            showToast('Пользователь создан', 'success');
        }
        closeModal('userModal');
        loadUsers();
    } catch (e) {
        showToast(e.message || 'Ошибка сохранения', 'error');
    }
}

async function toggleUserStatus(id, active) {
    try {
        await api.put(`${USERS_API}/${id}/status`, { is_active: active });
        showToast(`Пользователь ${active ? 'активирован' : 'деактивирован'}`, 'success');
        loadUsers();
    } catch (e) {
        showToast('Ошибка изменения статуса', 'error');
    }
}

async function deleteUser(id) {
    if (!confirm('Удалить пользователя?')) return;
    try {
        await api.delete(`${USERS_API}/${id}`);
        showToast('Пользователь удален', 'success');
        loadUsers();
    } catch (e) {
        showToast('Ошибка удаления', 'error');
    }
}
4. WebUI — roles.js
javascript
// webui/static/js/roles.js

const ROLES_API = '/api/auth/roles';

async function loadRoles() {
    try {
        const response = await api.get(ROLES_API);
        const roles = response.items || [];
        renderRoles(roles);
    } catch (e) {
        showToast('Ошибка загрузки ролей', 'error');
    }
}

function renderRoles(roles) {
    const tbody = document.getElementById('rolesTableBody');
    if (!roles.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">Нет ролей</td></tr>';
        return;
    }
    
    let html = '';
    for (const role of roles) {
        html += `
            <tr>
                <td><strong>${role.name}</strong></td>
                <td>${role.description || '—'}</td>
                <td>${role.user_count || 0}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="editRole(${role.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRole(${role.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

function showCreateRoleModal() {
    document.getElementById('roleModalTitle').textContent = 'Создание роли';
    document.getElementById('roleId').value = '';
    document.getElementById('roleForm').reset();
    openModal('roleModal');
}

async function editRole(id) {
    try {
        const response = await api.get(`${ROLES_API}/${id}`);
        const role = response;
        
        document.getElementById('roleModalTitle').textContent = 'Редактирование роли';
        document.getElementById('roleId').value = role.id;
        document.getElementById('roleName').value = role.name;
        document.getElementById('roleDescription').value = role.description || '';
        document.getElementById('roleAdGroup').value = role.ad_group || '';
        
        openModal('roleModal');
    } catch (e) {
        showToast('Ошибка загрузки роли', 'error');
    }
}

async function saveRole() {
    const id = document.getElementById('roleId').value;
    const data = {
        name: document.getElementById('roleName').value,
        description: document.getElementById('roleDescription').value,
        ad_group: document.getElementById('roleAdGroup').value
    };
    
    try {
        if (id) {
            await api.put(`${ROLES_API}/${id}`, data);
            showToast('Роль обновлена', 'success');
        } else {
            await api.post(ROLES_API, data);
            showToast('Роль создана', 'success');
        }
        closeModal('roleModal');
        loadRoles();
    } catch (e) {
        showToast(e.message || 'Ошибка сохранения', 'error');
    }
}

async function deleteRole(id) {
    if (!confirm('Удалить роль?')) return;
    try {
        await api.delete(`${ROLES_API}/${id}`);
        showToast('Роль удалена', 'success');
        loadRoles();
    } catch (e) {
        showToast('Ошибка удаления', 'error');
    }
}
5. Базовый шаблон — обновление навигации
html
<!-- webui/templates/base.html (дополнение) -->
<nav class="sidebar-nav">
    <a href="/" class="nav-item active">Дашборд</a>
    <a href="/catalog" class="nav-item">Каталог</a>
    <a href="/findings" class="nav-item">Находки</a>
    
    {% if user and (user.has_role('auditor') or user.has_role('admin')) %}
    <a href="/audit" class="nav-item">Аудит</a>
    <a href="/access" class="nav-item">Доступ</a>
    {% endif %}
    
    {% if user and (user.has_role('scanner') or user.has_role('admin')) %}
    <a href="/scanners" class="nav-item">Сканеры</a>
    <a href="/resources" class="nav-item">Ресурсы</a>
    {% endif %}
    
    {% if user and user.has_role('admin') %}
    <div class="nav-divider"></div>
    <a href="/users" class="nav-item">
        <i class="fas fa-users"></i> Пользователи
    </a>
    <a href="/roles" class="nav-item">
        <i class="fas fa-lock"></i> Роли
    </a>
    <a href="/settings" class="nav-item">
        <i class="fas fa-cog"></i> Настройки
    </a>
    {% endif %}
</nav>
📋 КРИТЕРИИ ПРИЕМКИ
Аутентификация через AD
□ SPNEGO аутентификация (заглушка для разработки, реальная для AD)
□ Явный логин через AD (пароль) — LDAP
□ Получение групп пользователя из AD
□ Маппинг AD групп → роли DCAP
Сбор прав через агентов
□ Windows Agent: сбор NTFS прав (win32security)
□ Linux Agent: сбор POSIX прав (getfacl)
□ Периодический сбор (настраиваемый интервал)
□ Отправка прав в Manager
AD интеграция
□ Подключение к AD через LDAP
□ Разрешение SID → имя
□ Проверка членства в AD группах
□ Кэширование AD запросов (Redis)
API
□ POST /api/audit/permissions — прием прав
□ GET /api/permissions/resources/{id} — получение прав
□ GET /api/auth/users — список пользователей
□ POST /api/auth/users — создание пользователя
□ PUT /api/auth/users/{id} — обновление пользователя
□ DELETE /api/auth/users/{id} — удаление пользователя
□ GET /api/auth/roles — список ролей
□ POST /api/auth/roles — создание роли
□ PUT /api/auth/roles/{id} — обновление роли
□ DELETE /api/auth/roles/{id} — удаление роли
WebUI
□ Страница управления пользователями
□ Страница управления ролями
□ Создание/редактирование/удаление пользователей
□ Создание/редактирование/удаление ролей
□ Назначение ролей пользователям
□ Фильтрация по источнику и роли
Тестирование
□ Samba AD DC в Docker
□ Тестовые пользователи и группы
□ Тест аутентификации через AD
□ Тест сбора прав через агентов
□ Тест разрешения SID
□ Тест WebUI управления RBAC
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запуск AD + Redis
docker-compose -f docker-compose.ad.yml up -d

# 2. Инициализация тестовых данных
python scripts/init_ad_test_data.py

# 3. Запуск Manager
python run_manager.py

# 4. Запуск WebUI
python run_webui.py

# 5. Тест аутентификации через AD
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"v.petrov","password":"Passw0rd"}'

# 6. Тест управления пользователями (Admin)
curl -X GET http://localhost:8000/api/auth/users \
  -H "Authorization: Bearer <token>"

# 7. WebUI — открыть страницу управления пользователями
open http://localhost:8001/users

# 8. Запуск Windows Agent (сбор прав)
cd audit-agent-windows
python main.py --config config.json

# 9. Проверка прав в WebUI
open http://localhost:8001/access
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_33_ad_integration
git add .
git commit -m "feat: День 33 — Active Directory интеграция + RBAC WebUI

Аутентификация:
- SPNEGO (Windows Integrated Auth) через spnego
- Явный логин через AD (пароль) через LDAP
- Маппинг AD групп → роли DCAP
- Интеграция с AuthManager

Сбор прав:
- Windows Agent: NTFS права (win32security)
- Linux Agent: POSIX права (getfacl)
- Периодический сбор + отправка в Manager

AD интеграция:
- Разрешение SID → имя
- Проверка членства в AD группах
- Кэширование (Redis + memory)

API RBAC:
- GET/POST/PUT/DELETE /api/auth/users
- GET/POST/PUT/DELETE /api/auth/roles
- POST /api/audit/permissions
- GET /api/permissions/resources/{id}

WebUI RBAC:
- Страница управления пользователями (список, создание, редактирование, удаление)
- Страница управления ролями (список, создание, редактирование, удаление)
- Фильтрация по источнику и роли
- Назначение ролей пользователям

Тестирование:
- Samba AD DC в Docker
- Тестовые пользователи и группы (init_ad_test_data.py)"