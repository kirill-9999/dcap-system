# НОВОЕ ТЗ ДЛЯ РАЗРАБОТЧИКА

## 📋 ТЕКУЩЕЕ ТЗ

📋 ТЗ: WEBUI УПРАВЛЕНИЕ ДОСТУПОМ (ДЕНЬ 14)
🎯 ЦЕЛЬ
Создать страницу "Управление доступом" в WebUI для взаимодействия с API управления доступом. Страница должна предоставлять:

Просмотр и управление правами доступа к ресурсам

Просмотр и управление алертами

Полный отчет по доступу

Переключение режимов работы (local/remote)

Синхронизацию прав

Все взаимодействия должны использовать созданные в День 13 API эндпоинты.

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ/ИЗМЕНЕНИЯ
Изменить:
text
webui/static/index.html          # Добавить страницу "Управление доступом"
webui/static/js/app.js           # Добавить функции для работы с API
webui/static/css/style.css       # Добавить стили для новой страницы
📋 ДЕТАЛЬНОЕ ТЗ
1. Обновить навигацию (index.html)
Добавить пункт меню "🔐 Доступ" в навигацию:

html
<nav>
    <a href="#resources" class="nav-link" data-page="resources">📁 Ресурсы</a>
    <a href="#findings" class="nav-link" data-page="findings">🔍 Находки</a>
    <a href="#catalog" class="nav-link" data-page="catalog">📂 Каталог</a>
    <a href="#tasks" class="nav-link" data-page="tasks">📋 Задания</a>
    <a href="#permissions" class="nav-link" data-page="permissions">🔐 Доступ</a>
</nav>
2. Создать страницу "Управление доступом" (index.html)
2.1. Структура страницы
html
<!-- Страница: Управление доступом -->
<div id="permissions-page" class="page">
    <div class="page-header">
        <h1>🔐 Управление доступом</h1>
        <div class="header-actions">
            <div class="mode-indicator">
                <span class="mode-label">Режим:</span>
                <span id="current-mode" class="mode-badge mode-local">local</span>
                <button id="switch-mode-btn" class="btn btn-sm btn-outline">Переключить</button>
            </div>
            <button id="sync-permissions-btn" class="btn btn-primary">🔄 Синхронизировать</button>
        </div>
    </div>

    <!-- Выбор ресурса -->
    <div class="resource-selector">
        <label for="permission-resource-select">Ресурс:</label>
        <select id="permission-resource-select" class="form-select">
            <option value="">-- Выберите ресурс --</option>
        </select>
        <span id="permission-status" class="status-text"></span>
    </div>

    <!-- Вкладки -->
    <div class="tabs">
        <button class="tab-btn active" data-tab="permissions-tab">📋 Права доступа</button>
        <button class="tab-btn" data-tab="alerts-tab">⚠️ Алерты <span id="alerts-badge" class="badge">0</span></button>
        <button class="tab-btn" data-tab="report-tab">📊 Отчет</button>
    </div>

    <!-- Вкладка: Права доступа -->
    <div id="permissions-tab" class="tab-content active">
        <div class="permissions-filters">
            <input type="text" id="permissions-search" placeholder="🔍 Поиск по пользователю..." class="form-input">
            <select id="permissions-type-filter" class="form-select">
                <option value="">Все типы</option>
                <option value="user">Пользователи</option>
                <option value="group">Группы</option>
                <option value="system">Системные</option>
            </select>
            <span id="permissions-count" class="filter-count">0 записей</span>
        </div>
        <div id="permissions-table-container">
            <table class="permissions-table">
                <thead>
                    <tr>
                        <th>Субъект</th>
                        <th>Тип</th>
                        <th>Права</th>
                        <th>Наследование</th>
                        <th>Источник</th>
                        <th>Последняя проверка</th>
                    </tr>
                </thead>
                <tbody id="permissions-table-body">
                    <tr><td colspan="6" class="text-center">Выберите ресурс</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Вкладка: Алерты -->
    <div id="alerts-tab" class="tab-content">
        <div class="alerts-filters">
            <select id="alerts-severity-filter" class="form-select">
                <option value="">Все severity</option>
                <option value="critical">🔴 Critical</option>
                <option value="warning">🟡 Warning</option>
                <option value="info">🔵 Info</option>
            </select>
            <select id="alerts-status-filter" class="form-select">
                <option value="">Все статусы</option>
                <option value="open">🟢 Open</option>
                <option value="acknowledged">🟡 Acknowledged</option>
                <option value="resolved">✅ Resolved</option>
                <option value="ignored">⏭️ Ignored</option>
            </select>
        </div>
        <div id="alerts-list">
            <!-- Карточки алертов -->
        </div>
    </div>

    <!-- Вкладка: Отчет -->
    <div id="report-tab" class="tab-content">
        <div id="access-report">
            <!-- Секции отчета -->
        </div>
        <button id="export-report-btn" class="btn btn-secondary">📥 Экспорт отчета</button>
    </div>
</div>
3. Обновить JavaScript (app.js)
3.1. Добавить функции для работы с API
javascript
// ==================== УПРАВЛЕНИЕ ДОСТУПОМ ====================

const PERMISSIONS_API = '/api/permissions';
let currentResourceId = null;

// 3.1.1. Загрузка списка ресурсов
async function loadPermissionResources() {
    const response = await fetch('/api/resources');
    const resources = await response.json();
    const select = document.getElementById('permission-resource-select');
    const currentValue = select.value;
    
    select.innerHTML = '<option value="">-- Выберите ресурс --</option>';
    for (const r of resources) {
        select.innerHTML += `<option value="${r.id}">${r.path}</option>`;
    }
    
    if (currentValue) select.value = currentValue;
}

// 3.1.2. Загрузка режима
async function loadMode() {
    try {
        const response = await fetch(`${PERMISSIONS_API}/mode`);
        const data = await response.json();
        const modeBadge = document.getElementById('current-mode');
        modeBadge.textContent = data.current_mode;
        modeBadge.className = `mode-badge mode-${data.current_mode}`;
        return data;
    } catch (e) {
        console.error('Failed to load mode:', e);
        return null;
    }
}

// 3.1.3. Переключение режима
async function switchMode() {
    const currentMode = document.getElementById('current-mode').textContent;
    const newMode = currentMode === 'local' ? 'remote' : 'local';
    
    try {
        const response = await fetch(`${PERMISSIONS_API}/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode })
        });
        
        if (response.ok) {
            await loadMode();
            showToast(`Режим переключен на ${newMode}`, 'success');
            if (currentResourceId) await loadPermissions(currentResourceId);
        } else {
            const error = await response.json();
            showToast(`Ошибка: ${error.detail || 'Неизвестная ошибка'}`, 'error');
        }
    } catch (e) {
        showToast('Ошибка переключения режима', 'error');
    }
}

// 3.1.4. Загрузка прав доступа
async function loadPermissions(resourceId) {
    currentResourceId = resourceId;
    if (!resourceId) {
        document.getElementById('permissions-table-body').innerHTML = 
            '<tr><td colspan="6" class="text-center">Выберите ресурс</td></tr>';
        return;
    }
    
    const search = document.getElementById('permissions-search').value;
    const typeFilter = document.getElementById('permissions-type-filter').value;
    const params = new URLSearchParams();
    if (search) params.append('principal', search);
    if (typeFilter) params.append('principal_type', typeFilter);
    
    try {
        const response = await fetch(
            `${PERMISSIONS_API}/resources/${resourceId}?${params}`
        );
        const data = await response.json();
        renderPermissions(data);
    } catch (e) {
        showToast('Ошибка загрузки прав доступа', 'error');
    }
}

// 3.1.5. Рендер прав доступа
function renderPermissions(data) {
    const tbody = document.getElementById('permissions-table-body');
    const count = document.getElementById('permissions-count');
    count.textContent = `${data.total || 0} записей`;
    
    if (!data.entries || data.entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">Нет записей</td></tr>';
        return;
    }
    
    let html = '';
    for (const entry of data.entries) {
        const typeBadge = getTypeBadge(entry.principal_type);
        const inheritedIcon = entry.is_inherited ? '📎' : '✏️';
        html += `
            <tr>
                <td><strong>${entry.principal_name}</strong></td>
                <td>${typeBadge}</td>
                <td><span class="permission-badge">${entry.permission_type}</span></td>
                <td>${inheritedIcon} ${entry.is_inherited ? 'Наследуется' : 'Прямое'}</td>
                <td>${entry.inherited_from || '—'}</td>
                <td>${entry.last_verified_at ? new Date(entry.last_verified_at).toLocaleString() : '—'}</td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

// 3.1.6. Загрузка алертов
async function loadAlerts(resourceId) {
    const severity = document.getElementById('alerts-severity-filter').value;
    const status = document.getElementById('alerts-status-filter').value;
    const params = new URLSearchParams();
    if (resourceId) params.append('resource_id', resourceId);
    if (severity) params.append('severity', severity);
    if (status) params.append('status', status);
    
    try {
        const response = await fetch(`${PERMISSIONS_API}/alerts?${params}`);
        const data = await response.json();
        renderAlerts(data);
    } catch (e) {
        showToast('Ошибка загрузки алертов', 'error');
    }
}

// 3.1.7. Рендер алертов
function renderAlerts(data) {
    const container = document.getElementById('alerts-list');
    const badge = document.getElementById('alerts-badge');
    badge.textContent = data.total || 0;
    
    if (!data.alerts || data.alerts.length === 0) {
        container.innerHTML = '<div class="empty-state">✅ Нет алертов</div>';
        return;
    }
    
    let html = '';
    for (const alert of data.alerts) {
        const severityClass = `severity-${alert.severity}`;
        const statusClass = `status-${alert.status}`;
        html += `
            <div class="alert-card ${severityClass}">
                <div class="alert-header">
                    <span class="alert-type">${alert.alert_type}</span>
                    <span class="alert-severity ${severityClass}">${alert.severity.toUpperCase()}</span>
                    <span class="alert-status ${statusClass}">${alert.status}</span>
                </div>
                <div class="alert-body">
                    <p class="alert-description">${alert.description}</p>
                    ${alert.recommendation ? `<p class="alert-recommendation">💡 ${alert.recommendation}</p>` : ''}
                    ${alert.principal_name ? `<p class="alert-principal">👤 ${alert.principal_name}</p>` : ''}
                    <p class="alert-date">${new Date(alert.created_at).toLocaleString()}</p>
                </div>
                <div class="alert-actions">
                    ${alert.status === 'open' ? `
                        <button onclick="updateAlertStatus(${alert.id}, 'acknowledged')" class="btn btn-sm btn-warning">Принять</button>
                        <button onclick="updateAlertStatus(${alert.id}, 'resolved')" class="btn btn-sm btn-success">✅ Решено</button>
                        <button onclick="updateAlertStatus(${alert.id}, 'ignored')" class="btn btn-sm btn-secondary">⏭️ Игнор</button>
                    ` : ''}
                    ${alert.status === 'acknowledged' ? `
                        <button onclick="updateAlertStatus(${alert.id}, 'resolved')" class="btn btn-sm btn-success">✅ Решено</button>
                        <button onclick="updateAlertStatus(${alert.id}, 'ignored')" class="btn btn-sm btn-secondary">⏭️ Игнор</button>
                    ` : ''}
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}

// 3.1.8. Обновление статуса алерта
async function updateAlertStatus(alertId, status) {
    try {
        const response = await fetch(`${PERMISSIONS_API}/alerts/${alertId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        
        if (response.ok) {
            showToast(`Статус алерта обновлен: ${status}`, 'success');
            if (currentResourceId) {
                await loadAlerts(currentResourceId);
                await loadPermissions(currentResourceId);
            }
        } else {
            showToast('Ошибка обновления статуса', 'error');
        }
    } catch (e) {
        showToast('Ошибка обновления статуса', 'error');
    }
}

// 3.1.9. Синхронизация прав
async function syncPermissions() {
    if (!currentResourceId) {
        showToast('Выберите ресурс', 'warning');
        return;
    }
    
    const btn = document.getElementById('sync-permissions-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Синхронизация...';
    
    try {
        const response = await fetch(
            `${PERMISSIONS_API}/sync?resource_id=${currentResourceId}`,
            { method: 'POST' }
        );
        
        if (response.ok) {
            const data = await response.json();
            showToast(`✅ Синхронизировано: ${data.entries_saved || 0} записей`, 'success');
            await loadPermissions(currentResourceId);
            await loadAlerts(currentResourceId);
        } else {
            const error = await response.json();
            showToast(`Ошибка: ${error.detail || 'Неизвестная ошибка'}`, 'error');
        }
    } catch (e) {
        showToast('Ошибка синхронизации', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Синхронизировать';
    }
}

// 3.1.10. Загрузка отчета
async function loadReport(resourceId) {
    if (!resourceId) {
        document.getElementById('access-report').innerHTML = 
            '<p class="text-center">Выберите ресурс для просмотра отчета</p>';
        return;
    }
    
    try {
        const response = await fetch(`${PERMISSIONS_API}/resources/${resourceId}/report`);
        const data = await response.json();
        renderReport(data);
    } catch (e) {
        showToast('Ошибка загрузки отчета', 'error');
    }
}

// 3.1.11. Рендер отчета
function renderReport(data) {
    const container = document.getElementById('access-report');
    
    container.innerHTML = `
        <div class="report-grid">
            <div class="report-card">
                <h4>📋 Сводка</h4>
                <p>Всего записей: ${data.permissions_summary?.total || 0}</p>
                <p>Пользователей: ${data.permissions_summary?.users || 0}</p>
                <p>Групп: ${data.permissions_summary?.groups || 0}</p>
                <p>Наследуемых: ${data.permissions_summary?.inherited || 0}</p>
            </div>
            <div class="report-card">
                <h4>📊 По типам прав</h4>
                ${Object.entries(data.permissions_by_type || {}).map(([key, val]) => 
                    `<p>${key}: ${val}</p>`
                ).join('') || '<p>Нет данных</p>'}
            </div>
            <div class="report-card">
                <h4>⚠️ Избыточные права</h4>
                <p>Найдено: ${data.excessive_permissions?.length || 0}</p>
                <ul>
                    ${data.excessive_permissions?.map(p => 
                        `<li>${p.principal}: ${p.permission} (${p.severity})</li>`
                    ).join('') || '<li>Нет</li>'}
                </ul>
            </div>
            <div class="report-card">
                <h4>🔔 Алерты</h4>
                <p>Всего: ${data.alerts?.total || 0}</p>
                <p>🔴 Critical: ${data.alerts?.critical || 0}</p>
                <p>🟡 Warning: ${data.alerts?.warning || 0}</p>
                <p>🔵 Info: ${data.alerts?.info || 0}</p>
            </div>
            <div class="report-card full-width">
                <h4>📂 Наследование</h4>
                <p>Наследуемых прав: ${data.inheritance_analysis?.inherited_count || 0} (${data.inheritance_analysis?.inherited_percent || 0}%)</p>
                <p>Прямых прав: ${data.inheritance_analysis?.direct_count || 0}</p>
                ${data.inheritance_analysis?.potential_issues?.length ? `
                    <div class="report-issues">
                        ${data.inheritance_analysis.potential_issues.map(issue => 
                            `<span class="issue-tag">${issue}</span>`
                        ).join('')}
                    </div>
                ` : ''}
            </div>
            <div class="report-card full-width">
                <h4>👤 Топ субъектов</h4>
                <ul>
                    ${data.top_principals?.map(p => 
                        `<li>${p.principal}: ${p.permissions.join(', ')} ${p.is_inherited ? '(наследуется)' : ''}</li>`
                    ).join('') || '<li>Нет данных</li>'}
                </ul>
            </div>
        </div>
    `;
}

// 3.1.12. Экспорт отчета
async function exportReport() {
    if (!currentResourceId) {
        showToast('Выберите ресурс', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${PERMISSIONS_API}/resources/${currentResourceId}/report`);
        const data = await response.json();
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_resource_${currentResourceId}_${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Отчет экспортирован', 'success');
    } catch (e) {
        showToast('Ошибка экспорта', 'error');
    }
}

// 3.1.13. Вспомогательные функции
function getTypeBadge(type) {
    const badges = {
        'user': '<span class="badge badge-user">👤 User</span>',
        'local_user': '<span class="badge badge-local">💻 Local</span>',
        'group': '<span class="badge badge-group">👥 Group</span>',
        'system': '<span class="badge badge-system">⚙️ System</span>',
        'ad_user': '<span class="badge badge-ad">🏢 AD User</span>',
        'ad_group': '<span class="badge badge-ad">🏢 AD Group</span>',
    };
    return badges[type] || `<span class="badge badge-unknown">${type}</span>`;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
4. Обновить CSS (style.css)
Добавить стили для новой страницы:

css
/* ==================== УПРАВЛЕНИЕ ДОСТУПОМ ==================== */

/* Режим */
.mode-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
}

.mode-badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: 600;
}

.mode-local {
    background: #d4edda;
    color: #155724;
}

.mode-remote {
    background: #cce5ff;
    color: #004085;
}

/* Таблица прав */
.permissions-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
}

.permissions-table th {
    background: #f8f9fa;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 2px solid #dee2e6;
}

.permissions-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #eee;
}

.permissions-table tr:hover td {
    background: #f5f7fa;
}

.permission-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    background: #e9ecef;
    font-size: 0.8em;
    font-weight: 500;
}

.badge-user { background: #d4edda; color: #155724; }
.badge-local { background: #fff3cd; color: #856404; }
.badge-group { background: #cce5ff; color: #004085; }
.badge-system { background: #f8d7da; color: #721c24; }

/* Алерты */
.alert-card {
    border: 1px solid #dee2e6;
    border-radius: 8px;
    margin-bottom: 12px;
    padding: 16px;
    background: white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.alert-card.severity-critical { border-left: 4px solid #dc3545; }
.alert-card.severity-warning { border-left: 4px solid #ffc107; }
.alert-card.severity-info { border-left: 4px solid #17a2b8; }

.alert-header {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 8px;
}

.alert-type {
    font-weight: 600;
    font-size: 0.9em;
}

.alert-severity {
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 0.7em;
    font-weight: 700;
}

.alert-severity.severity-critical { background: #dc3545; color: white; }
.alert-severity.severity-warning { background: #ffc107; color: #333; }
.alert-severity.severity-info { background: #17a2b8; color: white; }

.alert-status {
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 0.7em;
    font-weight: 600;
}

.alert-status.status-open { background: #28a745; color: white; }
.alert-status.status-acknowledged { background: #ffc107; color: #333; }
.alert-status.status-resolved { background: #6c757d; color: white; }
.alert-status.status-ignored { background: #6c757d; color: white; }

.alert-body {
    font-size: 0.9em;
}

.alert-description { margin: 4px 0; }
.alert-recommendation { color: #28a745; margin: 4px 0; }
.alert-principal { color: #6c757d; font-size: 0.85em; }
.alert-date { color: #6c757d; font-size: 0.8em; margin-top: 4px; }

.alert-actions {
    margin-top: 8px;
    display: flex;
    gap: 8px;
}

/* Отчет */
.report-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin: 16px 0;
}

.report-card {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 16px;
}

.report-card.full-width {
    grid-column: 1 / -1;
}

.report-card h4 {
    margin-top: 0;
    border-bottom: 1px solid #eee;
    padding-bottom: 8px;
}

.report-card p {
    margin: 6px 0;
}

.report-issues {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
}

.issue-tag {
    background: #fff3cd;
    color: #856404;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.8em;
}

/* Toast */
.toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 12px 24px;
    border-radius: 8px;
    color: white;
    font-weight: 500;
    z-index: 9999;
    animation: slideIn 0.3s ease;
}

.toast-success { background: #28a745; }
.toast-error { background: #dc3545; }
.toast-warning { background: #ffc107; color: #333; }
.toast-info { background: #17a2b8; }

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

/* Фильтры */
.permissions-filters, .alerts-filters {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 12px;
    flex-wrap: wrap;
}

.filter-count {
    font-size: 0.9em;
    color: #6c757d;
}

/* Общие */
.text-center { text-align: center; }
.empty-state { padding: 40px; text-align: center; color: #6c757d; }
5. Инициализация страницы в app.js
javascript
// ==================== ИНИЦИАЛИЗАЦИЯ ====================

document.addEventListener('DOMContentLoaded', function() {
    // Навигация
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.dataset.page;
            showPage(page);
        });
    });

    // Страница по умолчанию
    showPage('resources');

    // Обработчики для страницы "Управление доступом"
    const resourceSelect = document.getElementById('permission-resource-select');
    if (resourceSelect) {
        resourceSelect.addEventListener('change', function() {
            const id = this.value;
            if (id) {
                loadPermissions(id);
                loadAlerts(id);
                loadReport(id);
            }
        });
    }

    // Поиск по правам
    const searchInput = document.getElementById('permissions-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            if (currentResourceId) loadPermissions(currentResourceId);
        });
    }

    // Фильтр по типу
    const typeFilter = document.getElementById('permissions-type-filter');
    if (typeFilter) {
        typeFilter.addEventListener('change', function() {
            if (currentResourceId) loadPermissions(currentResourceId);
        });
    }

    // Фильтры алертов
    document.getElementById('alerts-severity-filter')?.addEventListener('change', function() {
        if (currentResourceId) loadAlerts(currentResourceId);
    });
    document.getElementById('alerts-status-filter')?.addEventListener('change', function() {
        if (currentResourceId) loadAlerts(currentResourceId);
    });

    // Кнопка синхронизации
    document.getElementById('sync-permissions-btn')?.addEventListener('click', syncPermissions);

    // Кнопка переключения режима
    document.getElementById('switch-mode-btn')?.addEventListener('click', switchMode);

    // Кнопка экспорта
    document.getElementById('export-report-btn')?.addEventListener('click', exportReport);

    // Загружаем данные
    loadPermissionResources();
    loadMode();
});

// Показ страницы
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const targetPage = document.getElementById(`${page}-page`);
    if (targetPage) targetPage.classList.add('active');

    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    const targetLink = document.querySelector(`.nav-link[data-page="${page}"]`);
    if (targetLink) targetLink.classList.add('active');

    // Если страница "Управление доступом" — загружаем данные
    if (page === 'permissions') {
        loadPermissionResources();
        loadMode();
        if (currentResourceId) {
            loadPermissions(currentResourceId);
            loadAlerts(currentResourceId);
            loadReport(currentResourceId);
        }
    }
}
✅ КРИТЕРИИ ПРИЕМКИ
В навигации появился пункт "🔐 Доступ"

Страница "Управление доступом" отображается корректно

В выпадающем списке отображаются все ресурсы

При выборе ресурса загружаются права доступа

Фильтрация по пользователю и типу работает

Вкладка "Алерты" показывает алерты с возможностью обновления статуса

Вкладка "Отчет" показывает полную статистику

Кнопка "Синхронизировать" работает

Кнопка "Переключить режим" работает

Кнопка "Экспорт отчета" скачивает JSON

Все стили корректно отображаются

🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
javascript
// 1. Проверка навигации
// Открыть страницу "🔐 Доступ" — должна загрузиться

// 2. Проверка выбора ресурса
// Выбрать ресурс — должны загрузиться права, алерты, отчет

// 3. Проверка синхронизации
// Нажать "Синхронизировать" — должен появиться тост об успехе

// 4. Проверка режима
// Нажать "Переключить" — режим должен измениться

// 5. Проверка алертов
// Во вкладке "Алерты" должны быть карточки, кнопки работают

// 6. Проверка отчета
// Во вкладке "Отчет" должна быть статистика
// Нажать "Экспорт" — скачивается JSON
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
webui/
└── static/
    ├── index.html          # ✅ Добавлена страница "Управление доступом"
    ├── css/
    │   └── style.css       # ✅ Добавлены стили
    └── js/
        └── app.js          # ✅ Добавлены функции
Разработчик, приступай! 🚀



## 📝 ПРОЦЕСС РАБОТЫ

1. **Получить и проанализировать ТЗ**
2. **Запросить нужные файлы** — если нужно увидеть текущий код
3. **Сгенерировать код** — полные файлы с изменениями
4. **Исправить ошибки** — по выводу от пользователя
5. **Сформировать отчет** — когда всё работает

## 📊 СОСТАВ ОТЧЕТА

После завершения этапа предоставить:

1. **Реализованный функционал** — что сделано в соответствии с планом
2. **Новая структура проекта** — список новых/измененных модулей, описание их функционала
3. **Оставшийся контекст беседы** — сколько токенов осталось

---

**Приступай!** 🚀