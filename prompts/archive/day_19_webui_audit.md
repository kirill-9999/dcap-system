📋 ТЗ: WEBUI ДЛЯ АУДИТА (ДЕНЬ 19)
Файл: prompts/tz/day_19_webui_audit.md

🎯 ЦЕЛЬ
Создать страницу в WebUI для просмотра аудит-событий, собранных агентами аудита. Страница должна предоставлять:

Просмотр всех событий с фильтрацией

Статистику по аудиту

Детали каждого события

Поиск по пользователю, файлу, типу события

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Изменить:
text
webui/main.py                 # Добавить страницу "Аудит"
webui/static/js/app.js        # Добавить функции для работы с API аудита
webui/static/css/style.css    # Добавить стили для страницы аудита
Создать (опционально):
text
webui/static/js/audit.js      # Вынести функции аудита в отдельный файл
📋 ДЕТАЛЬНОЕ ТЗ
1. Обновить навигацию (webui/main.py)
Добавить пункт меню "📋 Аудит" в навигацию:

html
<nav>
    <a href="#resources" class="nav-link" data-page="resources">📁 Ресурсы</a>
    <a href="#findings" class="nav-link" data-page="findings">🔍 Находки</a>
    <a href="#catalog" class="nav-link" data-page="catalog">📂 Каталог</a>
    <a href="#tasks" class="nav-link" data-page="tasks">📋 Задания</a>
    <a href="#permissions" class="nav-link" data-page="permissions">🔐 Доступ</a>
    <a href="#audit" class="nav-link" data-page="audit">📋 Аудит</a>
</nav>
2. Создать страницу "Аудит" (webui/main.py)
Добавить HTML-структуру страницы:

html
<!-- Страница: Аудит -->
<div id="audit-page" class="page">
    <div class="page-header">
        <h1>📋 Аудит файловой системы</h1>
        <div class="header-actions">
            <button id="refresh-audit-btn" class="btn btn-primary">🔄 Обновить</button>
            <span class="audit-status" id="audit-status">Загрузка...</span>
        </div>
    </div>

    <!-- Фильтры -->
    <div class="audit-filters">
        <div class="filter-row">
            <div class="filter-group">
                <label>📅 Период:</label>
                <select id="audit-days-filter" class="form-select">
                    <option value="1">Последний день</option>
                    <option value="7" selected>Последние 7 дней</option>
                    <option value="30">Последние 30 дней</option>
                    <option value="90">Последние 90 дней</option>
                </select>
            </div>
            <div class="filter-group">
                <label>📋 Тип события:</label>
                <select id="audit-type-filter" class="form-select">
                    <option value="">Все типы</option>
                    <option value="read">📖 Чтение</option>
                    <option value="write">✏️ Запись</option>
                    <option value="delete">🗑️ Удаление</option>
                    <option value="move">📦 Перемещение</option>
                    <option value="rename">📝 Переименование</option>
                </select>
            </div>
        </div>
        <div class="filter-row">
            <div class="filter-group">
                <label>👤 Пользователь:</label>
                <input type="text" id="audit-user-filter" placeholder="Введите имя пользователя..." class="form-input">
            </div>
            <div class="filter-group">
                <label>📁 Файл/путь:</label>
                <input type="text" id="audit-path-filter" placeholder="Поиск по пути..." class="form-input">
            </div>
            <div class="filter-group">
                <button id="apply-audit-filters" class="btn btn-secondary">🔍 Применить</button>
                <button id="reset-audit-filters" class="btn btn-outline">↺ Сбросить</button>
            </div>
        </div>
    </div>

    <!-- Статистика -->
    <div class="audit-stats" id="audit-stats">
        <div class="stat-card">
            <span class="stat-value" id="stat-total">0</span>
            <span class="stat-label">Всего событий</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="stat-read">0</span>
            <span class="stat-label">📖 Чтение</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="stat-write">0</span>
            <span class="stat-label">✏️ Запись</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="stat-delete">0</span>
            <span class="stat-label">🗑️ Удаление</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="stat-move">0</span>
            <span class="stat-label">📦 Перемещение</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="stat-top-user">—</span>
            <span class="stat-label">👤 Топ-пользователь</span>
        </div>
    </div>

    <!-- Таблица событий -->
    <div class="audit-table-container">
        <div class="table-header">
            <span class="table-count" id="audit-count">Показано: 0</span>
            <div class="table-pagination">
                <button class="btn btn-sm" id="audit-prev-page" disabled>◀</button>
                <span id="audit-page-info">Страница 1</span>
                <button class="btn btn-sm" id="audit-next-page">▶</button>
            </div>
        </div>
        <table class="audit-table">
            <thead>
                <tr>
                    <th>⏱️ Время</th>
                    <th>📋 Тип</th>
                    <th>👤 Пользователь</th>
                    <th>📁 Файл/путь</th>
                    <th>💻 Источник</th>
                    <th>🔄 Действие</th>
                </tr>
            </thead>
            <tbody id="audit-table-body">
                <tr><td colspan="6" class="text-center">Загрузка событий...</td></tr>
            </tbody>
        </table>
    </div>

    <!-- Детали события (модальное окно) -->
    <div id="audit-event-modal" class="modal">
        <div class="modal-content">
            <h2>📋 Детали события</h2>
            <div id="audit-event-details">
                <!-- Заполняется JS -->
            </div>
            <button onclick="closeAuditModal()" class="btn btn-secondary">Закрыть</button>
        </div>
    </div>
</div>
3. JavaScript функции (webui/static/js/app.js)
Добавить функции для работы с API аудита:

javascript
// ==================== АУДИТ ====================

const AUDIT_API = '/api/audit';
let auditCurrentPage = 0;
const AUDIT_PAGE_SIZE = 50;

// 3.1. Загрузка событий
async function loadAuditEvents() {
    const days = document.getElementById('audit-days-filter').value;
    const eventType = document.getElementById('audit-type-filter').value;
    const user = document.getElementById('audit-user-filter').value;
    const filePath = document.getElementById('audit-path-filter').value;

    // Вычисляем дату "since"
    const since = new Date();
    since.setDate(since.getDate() - parseInt(days));
    const sinceStr = since.toISOString();

    const params = new URLSearchParams({
        limit: AUDIT_PAGE_SIZE,
        offset: auditCurrentPage * AUDIT_PAGE_SIZE,
        since: sinceStr
    });
    if (eventType) params.append('event_type', eventType);
    if (user) params.append('user', user);
    if (filePath) params.append('file_path', filePath);

    try {
        const response = await fetch(`${AUDIT_API}?${params}`);
        const data = await response.json();
        renderAuditTable(data);
        return data;
    } catch (e) {
        console.error('Ошибка загрузки аудита:', e);
        showToast('Ошибка загрузки событий', 'error');
    }
}

// 3.2. Загрузка статистики
async function loadAuditStats() {
    const days = document.getElementById('audit-days-filter').value;

    try {
        const response = await fetch(`${AUDIT_API}/stats?days=${days}`);
        const stats = await response.json();
        renderAuditStats(stats);
        return stats;
    } catch (e) {
        console.error('Ошибка загрузки статистики:', e);
    }
}

// 3.3. Рендер статистики
function renderAuditStats(stats) {
    document.getElementById('stat-total').textContent = stats.total || 0;

    const byType = stats.by_type || [];
    const typeMap = {};
    byType.forEach(item => { typeMap[item.type] = item.count; });

    document.getElementById('stat-read').textContent = typeMap['read'] || 0;
    document.getElementById('stat-write').textContent = typeMap['write'] || 0;
    document.getElementById('stat-delete').textContent = typeMap['delete'] || 0;
    document.getElementById('stat-move').textContent = typeMap['move'] || 0;

    const topUser = stats.top_users && stats.top_users.length > 0 ? stats.top_users[0].user : '—';
    document.getElementById('stat-top-user').textContent = topUser;
}

// 3.4. Рендер таблицы
function renderAuditTable(data) {
    const tbody = document.getElementById('audit-table-body');
    const count = document.getElementById('audit-count');
    const total = data.total || 0;
    const events = data.events || [];

    count.textContent = `Показано: ${events.length} из ${total}`;

    // Пагинация
    const totalPages = Math.ceil(total / AUDIT_PAGE_SIZE);
    document.getElementById('audit-page-info').textContent = `Страница ${auditCurrentPage + 1} из ${totalPages || 1}`;
    document.getElementById('audit-prev-page').disabled = auditCurrentPage === 0;
    document.getElementById('audit-next-page').disabled = auditCurrentPage >= totalPages - 1;

    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">Нет событий за выбранный период</td></tr>';
        return;
    }

    let html = '';
    for (const event of events) {
        const typeIcon = getEventTypeIcon(event.event_type);
        const time = event.created_at ? new Date(event.created_at).toLocaleString() : '—';
        const user = event.user || '—';
        const source = event.source_host || '—';
        const filePath = event.file_path || '—';
        const eventType = event.event_type || 'unknown';

        html += `
            <tr onclick="showAuditDetail(${event.id})" style="cursor:pointer;">
                <td>${time}</td>
                <td><span class="event-type-${eventType}">${typeIcon} ${eventType}</span></td>
                <td>${user}</td>
                <td class="file-path-cell" title="${filePath}">${truncatePath(filePath, 50)}</td>
                <td>${source}</td>
                <td><button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); showAuditDetail(${event.id})">📋</button></td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

// 3.5. Показать детали события
async function showAuditDetail(eventId) {
    try {
        // Получаем конкретное событие
        const response = await fetch(`${AUDIT_API}?limit=1&offset=0`);
        const data = await response.json();
        const event = data.events.find(e => e.id === eventId);
        if (!event) {
            showToast('Событие не найдено', 'error');
            return;
        }

        const container = document.getElementById('audit-event-details');
        container.innerHTML = `
            <div class="detail-row"><strong>ID:</strong> ${event.id}</div>
            <div class="detail-row"><strong>⏱️ Время:</strong> ${event.created_at ? new Date(event.created_at).toLocaleString() : '—'}</div>
            <div class="detail-row"><strong>📋 Тип:</strong> ${getEventTypeIcon(event.event_type)} ${event.event_type}</div>
            <div class="detail-row"><strong>👤 Пользователь:</strong> ${event.user || '—'}</div>
            <div class="detail-row"><strong>📁 Файл:</strong> ${event.file_path || '—'}</div>
            <div class="detail-row"><strong>📦 Старый путь:</strong> ${event.old_path || '—'}</div>
            <div class="detail-row"><strong>💻 Источник:</strong> ${event.source_host || '—'}</div>
            <div class="detail-row"><strong>📊 Метаданные:</strong> <pre>${JSON.stringify(event.metadata || {}, null, 2)}</pre></div>
        `;
        document.getElementById('audit-event-modal').style.display = 'block';
    } catch (e) {
        console.error('Ошибка загрузки деталей:', e);
        showToast('Ошибка загрузки деталей события', 'error');
    }
}

// 3.6. Закрыть модальное окно
function closeAuditModal() {
    document.getElementById('audit-event-modal').style.display = 'none';
}

// 3.7. Вспомогательные функции
function getEventTypeIcon(type) {
    const icons = {
        'read': '📖',
        'write': '✏️',
        'delete': '🗑️',
        'move': '📦',
        'rename': '📝'
    };
    return icons[type] || '📋';
}

function truncatePath(path, maxLen) {
    if (!path) return '—';
    if (path.length <= maxLen) return path;
    return '...' + path.slice(-maxLen);
}

// 3.8. Инициализация аудита
function initAuditPage() {
    // Загружаем при первом показе
    loadAuditStats();
    loadAuditEvents();

    // Обработчики фильтров
    document.getElementById('apply-audit-filters').addEventListener('click', function() {
        auditCurrentPage = 0;
        loadAuditStats();
        loadAuditEvents();
    });

    document.getElementById('reset-audit-filters').addEventListener('click', function() {
        document.getElementById('audit-days-filter').value = '7';
        document.getElementById('audit-type-filter').value = '';
        document.getElementById('audit-user-filter').value = '';
        document.getElementById('audit-path-filter').value = '';
        auditCurrentPage = 0;
        loadAuditStats();
        loadAuditEvents();
    });

    document.getElementById('refresh-audit-btn').addEventListener('click', function() {
        loadAuditStats();
        loadAuditEvents();
        showToast('Обновлено', 'success');
    });

    document.getElementById('audit-prev-page').addEventListener('click', function() {
        if (auditCurrentPage > 0) {
            auditCurrentPage--;
            loadAuditEvents();
        }
    });

    document.getElementById('audit-next-page').addEventListener('click', function() {
        auditCurrentPage++;
        loadAuditEvents();
    });

    // Enter в полях фильтров
    document.getElementById('audit-user-filter').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('apply-audit-filters').click();
        }
    });
    document.getElementById('audit-path-filter').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('apply-audit-filters').click();
        }
    });
}

// 3.9. Показ страницы аудита
function showPage(page) {
    // ... существующий код ...

    if (page === 'audit') {
        initAuditPage();
    }
}
4. Стили (webui/static/css/style.css)
css
/* ==================== СТРАНИЦА АУДИТА ==================== */

/* Статистика */
.audit-stats {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin: 16px 0;
}

.stat-card {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.stat-value {
    display: block;
    font-size: 1.8em;
    font-weight: 700;
    color: #2c3e50;
}

.stat-label {
    display: block;
    font-size: 0.85em;
    color: #6c757d;
    margin-top: 4px;
}

/* Фильтры */
.audit-filters {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}

.filter-row {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    align-items: flex-end;
    margin-bottom: 8px;
}

.filter-row:last-child {
    margin-bottom: 0;
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-width: 150px;
}

.filter-group label {
    font-size: 0.85em;
    font-weight: 500;
    color: #495057;
}

/* Таблица */
.audit-table-container {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    overflow: hidden;
}

.table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #f8f9fa;
    border-bottom: 1px solid #dee2e6;
}

.table-pagination {
    display: flex;
    align-items: center;
    gap: 8px;
}

.audit-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
}

.audit-table th {
    background: #f8f9fa;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 2px solid #dee2e6;
    font-weight: 600;
}

.audit-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #eee;
}

.audit-table tr:hover td {
    background: #f5f7fa;
}

.audit-table .file-path-cell {
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Типы событий */
.event-type-read { color: #17a2b8; }
.event-type-write { color: #28a745; }
.event-type-delete { color: #dc3545; }
.event-type-move { color: #ffc107; }
.event-type-rename { color: #6f42c1; }

/* Детали события */
.detail-row {
    padding: 6px 0;
    border-bottom: 1px solid #eee;
}

.detail-row pre {
    background: #f8f9fa;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 0.85em;
    overflow-x: auto;
    max-height: 200px;
}

/* Toast сообщения */
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
.toast-info { background: #17a2b8; }

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
✅ КРИТЕРИИ ПРИЕМКИ
□ В навигации появился пункт "📋 Аудит"
□ Страница аудита отображается корректно
□ Статистика загружается и обновляется
□ Таблица событий показывает данные
□ Фильтры работают (период, тип, пользователь, путь)
□ Пагинация работает
□ Клик по событию открывает детали
□ Кнопка "Обновить" работает
□ Кнопка "Сбросить" работает
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Открыть в браузере
# http://localhost:8001

# 4. Перейти на страницу "📋 Аудит"
# Проверить:
# - Статистика загрузилась
# - Таблица заполнена
# - Фильтры работают
# - Клик по событию показывает детали
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
webui/
├── main.py                 # ✅ + страница "Аудит"
├── static/
│   ├── index.html          # (генерируется из main.py)
│   ├── css/style.css       # ✅ + стили аудита
│   └── js/app.js           # ✅ + функции аудита
└── run_webui.py            # ✅
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_19_webui_audit
git add webui/
git commit -m "feat: День 19 — WebUI для аудита (страница, таблица, фильтры, статистика)"
Разработчик (кодер), приступай! 🚀


