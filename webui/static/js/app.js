// ==================== НАВИГАЦИЯ ====================

function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`${page}-page`);
    if (target) target.classList.add('active');
    
    document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
    document.querySelectorAll('nav a').forEach(a => {
        if (a.textContent.includes({
            'resources': 'Ресурсы',
            'findings': 'Находки',
            'catalog': 'Каталог',
            'tasks': 'Задания'
        }[page])) {
            a.classList.add('active');
        }
    });
    
    if (page === 'resources') {
        loadResources();
    } else if (page === 'findings') {
        loadFindings();
        loadFindingResources();
    } else if (page === 'catalog') {
        loadCatalog();
        loadCatalogStats();
    } else if (page === 'tasks') {
        loadTasks();
    }
}

// ==================== РЕСУРСЫ ====================

async function loadResources() {
    try {
        const response = await fetch('/api/resources');
        if (!response.ok) throw new Error('Failed to load resources');
        const resources = await response.json();
        renderResourcesTable(resources);
    } catch (error) {
        console.error('Error loading resources:', error);
        document.getElementById('resources-table').innerHTML = 
            '<div class="error">❌ Ошибка загрузки ресурсов</div>';
    }
}

function renderResourcesTable(resources) {
    const container = document.getElementById('resources-table');
    
    if (!resources || resources.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>📭 Нет ресурсов</p>
                <p class="hint">Нажмите "+ Добавить ресурс" чтобы создать первый ресурс</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Путь</th>
                    <th>Тип</th>
                    <th>Статус</th>
                    <th>Последний скан</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    for (const r of resources) {
        const lastScan = r.last_scanned_at ? new Date(r.last_scanned_at).toLocaleString() : 'никогда';
        const statusClass = r.status ? r.status.toLowerCase() : 'unknown';
        
        html += `
            <tr>
                <td>${r.id}</td>
                <td title="${r.path}">${r.path}</td>
                <td>${r.type}</td>
                <td><span class="status status-${statusClass}">${r.status || 'ACTIVE'}</span></td>
                <td>${lastScan}</td>
                <td>
                    <button onclick="showConfigResource(${r.id})" title="Настройки">⚙️</button>
                    <button onclick="scanResource(${r.id})" title="Запустить сканирование">▶️</button>
                    <button onclick="deleteResource(${r.id})" title="Удалить">🗑️</button>
                </td>
            </tr>
        `;
    }
    
    html += `</tbody></table>`;
    container.innerHTML = html;
}

function showAddResourceModal() {
    document.getElementById('add-resource-modal').style.display = 'block';
    document.getElementById('resource-path').focus();
}

async function pickFolder() {
    try {
        const response = await fetch('/api/folders/pick', { method: 'POST' });
        const data = await response.json();
        if (data.success && data.path) {
            document.getElementById('resource-path').value = data.path;
        }
    } catch (error) {
        alert('Ошибка выбора папки: ' + error.message);
        console.error(error);
    }
}

async function addResource(event) {
    event.preventDefault();
    
    const path = document.getElementById('resource-path').value.trim();
    const type = document.getElementById('resource-type').value;
    
    if (!path) {
        alert('Пожалуйста, введите путь к ресурсу');
        return;
    }
    
    try {
        const response = await fetch(`/api/resources?path=${encodeURIComponent(path)}&type=${type}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            closeModal('add-resource-modal');
            document.getElementById('add-resource-form').reset();
            loadResources();
        } else {
            const error = await response.json();
            alert(`Ошибка при создании ресурса: ${error.detail || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        alert('Ошибка при создании ресурса');
        console.error(error);
    }
}

async function deleteResource(id) {
    if (!confirm('Удалить ресурс? Это действие нельзя отменить.')) return;
    
    try {
        const response = await fetch(`/api/resources/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadResources();
        } else {
            const error = await response.json();
            alert(`Ошибка при удалении: ${error.detail || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        alert('Ошибка при удалении ресурса');
        console.error(error);
    }
}

async function scanResource(id) {
    try {
        const response = await fetch(`/api/resources/${id}/scan`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const data = await response.json();
            alert(`✅ Сканирование запущено!\nID задания: ${data.task_id}`);
            loadResources();
        } else {
            const error = await response.json();
            alert(`Ошибка при запуске сканирования: ${error.detail || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        alert('Ошибка при запуске сканирования');
        console.error(error);
    }
}

// ==================== КОНФИГ РЕСУРСА ====================

async function showConfigResource(id) {
    try {
        const response = await fetch(`/api/resources/${id}/config`);
        if (!response.ok) throw new Error('Failed to load config');
        
        const config = await response.json();
        
        document.getElementById('config-resource-path').textContent = config.path || '';
        document.getElementById('config-scan-interval').value = config.scan_interval || 3600;
        document.getElementById('config-schedule-enabled').checked = config.schedule_enabled || false;
        document.getElementById('config-cron-expression').value = config.cron_expression || '';
        
        const sc = config.scan_config || {};
        document.getElementById('config-pii-enabled').checked = sc.classifiers?.pii?.enabled ?? true;
        document.getElementById('config-pii-confidence').value = sc.classifiers?.pii?.min_confidence ?? 0.5;
        document.getElementById('config-pii-ocr').checked = sc.classifiers?.pii?.ocr_enabled ?? true;
        document.getElementById('config-creds-enabled').checked = sc.classifiers?.credentials?.enabled ?? true;
        document.getElementById('config-code-enabled').checked = sc.classifiers?.code?.enabled ?? true;
        
        const extensions = sc.scan?.extensions || ['txt', 'pdf', 'docx'];
        document.getElementById('config-extensions').value = extensions.join(',');
        document.getElementById('config-recursive').checked = sc.scan?.recursive ?? true;
        document.getElementById('config-max-size').value = sc.scan?.max_file_size_mb ?? 50;
        
        document.getElementById('config-resource-form').dataset.resourceId = id;
        document.getElementById('config-resource-modal').style.display = 'block';
    } catch (error) {
        alert('Ошибка загрузки конфигурации');
        console.error(error);
    }
}

async function saveResourceConfig(event) {
    event.preventDefault();
    
    const id = document.getElementById('config-resource-form').dataset.resourceId;
    
    const config = {
        scan_config: {
            classifiers: {
                pii: {
                    enabled: document.getElementById('config-pii-enabled').checked,
                    min_confidence: parseFloat(document.getElementById('config-pii-confidence').value) || 0.5,
                    ocr_enabled: document.getElementById('config-pii-ocr').checked
                },
                credentials: {
                    enabled: document.getElementById('config-creds-enabled').checked
                },
                code: {
                    enabled: document.getElementById('config-code-enabled').checked
                }
            },
            scan: {
                extensions: document.getElementById('config-extensions').value.split(',').map(s => s.trim()).filter(Boolean),
                recursive: document.getElementById('config-recursive').checked,
                max_file_size_mb: parseInt(document.getElementById('config-max-size').value) || 50
            },
            reporting: {
                collect_catalog: true,
                include_context: true,
                context_lines: 3
            }
        },
        scan_interval: parseInt(document.getElementById('config-scan-interval').value) || 3600,
        schedule_enabled: document.getElementById('config-schedule-enabled').checked,
        cron_expression: document.getElementById('config-cron-expression').value || null
    };
    
    try {
        const response = await fetch(`/api/resources/${id}/config`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            closeModal('config-resource-modal');
            alert('✅ Конфигурация сохранена');
            loadResources();
        } else {
            const error = await response.json();
            alert(`Ошибка при сохранении: ${error.detail || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        alert('Ошибка при сохранении конфигурации');
        console.error(error);
    }
}

// ==================== НАХОДКИ ====================

async function loadFindings() {
    const resourceId = document.getElementById('finding-resource-filter').value;
    const category = document.getElementById('finding-category-filter').value;
    
    let url = '/api/findings?limit=100';
    if (resourceId) url += `&resource_id=${resourceId}`;
    if (category) url += `&category=${category}`;
    
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load findings');
        const findings = await response.json();
        renderFindings(findings);
    } catch (error) {
        console.error('Error loading findings:', error);
        document.getElementById('findings-list').innerHTML = 
            '<div class="error">❌ Ошибка загрузки находок</div>';
    }
}

function renderFindings(findings) {
    const container = document.getElementById('findings-list');
    
    if (!findings || findings.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>🔍 Нет находок</p></div>';
        return;
    }
    
    let html = '<div class="findings-grid">';
    for (const f of findings) {
        const categoryEmoji = {
            'pii': '👤',
            'credentials': '🔑',
            'code': '💻'
        }[f.category] || '📌';
        
        html += `
            <div class="finding-card">
                <div class="finding-header">
                    <span class="finding-category">${categoryEmoji} ${f.category}</span>
                    <span class="finding-confidence">${Math.round(f.confidence * 100)}%</span>
                </div>
                <div class="finding-file">📄 ${f.file_path}</div>
                <div class="finding-value">${f.value}</div>
                ${f.context ? `<div class="finding-context">${f.context}</div>` : ''}
                <div class="finding-meta">Строка ${f.line_number}</div>
            </div>
        `;
    }
    html += '</div>';
    container.innerHTML = html;
}

async function loadFindingResources() {
    try {
        const response = await fetch('/api/resources');
        if (!response.ok) throw new Error('Failed to load resources');
        const resources = await response.json();
        
        const select = document.getElementById('finding-resource-filter');
        select.innerHTML = '<option value="">Все ресурсы</option>';
        
        for (const r of resources) {
            select.innerHTML += `<option value="${r.id}">${r.path}</option>`;
        }
    } catch (error) {
        console.error('Error loading resources for findings:', error);
    }
}

// ==================== КАТАЛОГ (ГЛОБАЛЬНЫЙ - ПАПКИ С НАХОДКАМИ) ====================

async function loadCatalog() {
    const searchQuery = document.getElementById('catalog-search')?.value || '';
    
    let url = '/api/catalog/tree';
    if (searchQuery) {
        url += `?search=${encodeURIComponent(searchQuery)}`;
    }
    
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load catalog');
        
        const tree = await response.json();
        renderCatalogTree(tree);
    } catch (error) {
        console.error('Error loading catalog:', error);
        document.getElementById('catalog-tree').innerHTML = 
            '<div class="error">❌ Ошибка загрузки каталога</div>';
    }
}

async function loadCatalogStats() {
    try {
        const response = await fetch('/api/catalog/stats');
        if (!response.ok) throw new Error('Failed to load stats');
        
        const stats = await response.json();
        document.getElementById('total-entries').textContent = stats.total_folders || 0;
        
        // Показываем статистику по классификаторам
        const classifierStats = stats.classifier_stats || {};
        let statsHtml = '';
        for (const [cat, data] of Object.entries(classifierStats)) {
            const emoji = cat === 'pii' ? '👤' : cat === 'credentials' ? '🔑' : '💻';
            statsHtml += `<span>${emoji} ${cat}: ${data.folders} папок, ${data.total_findings} находок</span>`;
        }
        document.getElementById('classifier-stats').innerHTML = statsHtml || 'Нет данных';
    } catch (error) {
        console.error('Error loading catalog stats:', error);
    }
}

function renderCatalogTree(tree) {
    const container = document.getElementById('catalog-tree');
    
    if (!tree || Object.keys(tree).length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>📭 Каталог папок с находками пуст</p>
                <p class="hint">Запустите сканирование для обнаружения данных</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = renderTreeHTML(tree);
}

function renderTreeHTML(tree, level = 0) {
    let html = '<ul class="tree">';
    
    const sortedKeys = Object.keys(tree).sort();
    
    for (const key of sortedKeys) {
        const node = tree[key];
        const icon = node.is_folder ? '📁' : '📄';
        const hasFindings = node.has_findings || false;
        const classifiers = node.classifiers || {};
        const totalFindings = node.total_findings || 0;
        
        let folderClass = '';
        let badges = '';
        
        if (hasFindings && classifiers) {
            if (classifiers.pii) {
                folderClass = 'has-pii';
                badges += `<span class="badge badge-pii">👤 PII: ${classifiers.pii.count || 0}</span> `;
            }
            if (classifiers.credentials) {
                folderClass = 'has-creds';
                badges += `<span class="badge badge-creds">🔑 Creds: ${classifiers.credentials.count || 0}</span> `;
            }
            if (classifiers.code) {
                folderClass = 'has-code';
                badges += `<span class="badge badge-code">💻 Code: ${classifiers.code.count || 0}</span> `;
            }
        }
        
        html += `<li class="${folderClass}">`;
        html += `<span onclick="toggleFolder(event)" class="folder-item">${icon} ${key}</span>`;
        
        if (hasFindings) {
            html += ` <span class="findings-info">🔴 ${totalFindings} находок</span>`;
            html += ` <span class="badges">${badges}</span>`;
        }
        
        if (!node.is_folder && Object.keys(node.children).length > 0) {
            html += renderTreeHTML(node.children, level + 1);
        }
        
        html += `</li>`;
    }
    
    html += '</ul>';
    return html;
}

function toggleFolder(event) {
    const li = event.target.closest('li');
    if (!li) return;
    const ul = li.querySelector('ul');
    if (ul) {
        ul.style.display = ul.style.display === 'none' ? 'block' : 'none';
    }
}

function searchCatalog() {
    loadCatalog();
}

function clearCatalogSearch() {
    document.getElementById('catalog-search').value = '';
    loadCatalog();
}

// ==================== ЗАДАНИЯ ====================

async function loadTasks() {
    try {
        const response = await fetch('/api/tasks?limit=100');
        if (!response.ok) throw new Error('Failed to load tasks');
        const tasks = await response.json();
        renderTasks(tasks);
    } catch (error) {
        console.error('Error loading tasks:', error);
        document.getElementById('tasks-list').innerHTML = 
            '<div class="error">❌ Ошибка загрузки заданий</div>';
    }
}

function renderTasks(tasks) {
    const container = document.getElementById('tasks-list');
    
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>📋 Нет заданий</p></div>';
        return;
    }
    
    let html = '<table class="tasks-table"><thead><tr>';
    html += '<th>ID</th><th>Ресурс</th><th>Статус</th><th>Находки</th><th>Файлы</th><th>Создан</th><th>Завершен</th>';
    html += '</tr></thead><tbody>';
    
    for (const t of tasks) {
        const statusEmoji = {
            'pending': '⏳',
            'assigned': '🔄',
            'completed': '✅',
            'failed': '❌'
        }[t.status] || '❓';
        
        const created = t.created_at ? new Date(t.created_at).toLocaleString() : '-';
        const completed = t.completed_at ? new Date(t.completed_at).toLocaleString() : '-';
        
        html += `<tr>
            <td>${t.id}</td>
            <td>${t.resource_id}</td>
            <td><span class="status status-${t.status}">${statusEmoji} ${t.status}</span></td>
            <td>${t.findings_count || 0}</td>
            <td>${t.files_scanned || 0} / ${t.files_failed || 0}</td>
            <td>${created}</td>
            <td>${completed}</td>
        </tr>`;
    }
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// ==================== ASSIGNED ЗАДАНИЯ ====================

async function loadAssignedTasks() {
    try {
        const response = await fetch('/api/scanner/tasks/assigned');
        if (!response.ok) throw new Error('Failed to load assigned tasks');
        const tasks = await response.json();
        renderAssignedTasks(tasks);
    } catch (error) {
        console.error('Error loading assigned tasks:', error);
    }
}

function renderAssignedTasks(tasks) {
    const container = document.getElementById('assigned-tasks');
    if (!container) return;
    
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<span class="empty-hint">Нет активных заданий</span>';
        return;
    }
    
    let html = '';
    for (const t of tasks) {
        const assignedAt = t.assigned_at ? new Date(t.assigned_at).toLocaleString() : 'неизвестно';
        html += `
            <div class="assigned-task">
                <span>Задание #${t.id} → Сканер #${t.assigned_to}</span>
                <span class="task-time">${assignedAt}</span>
                <button onclick="releaseTask(${t.id})" class="btn-small btn-danger" title="Освободить задание">🔓</button>
            </div>
        `;
    }
    container.innerHTML = html;
}

async function releaseTask(taskId) {
    if (!confirm(`Освободить задание #${taskId}?`)) return;
    
    try {
        const response = await fetch(`/api/scanner/tasks/${taskId}/release`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('✅ Задание освобождено');
            loadAssignedTasks();
        } else {
            const error = await response.json();
            alert(`Ошибка: ${error.detail || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        alert('Ошибка при освобождении задания');
        console.error(error);
    }
}

// ==================== ВСПОМОГАТЕЛЬНЫЕ ====================

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

// ==================== ИНИЦИАЛИЗАЦИЯ ====================

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('add-resource-form').addEventListener('submit', addResource);
    document.getElementById('config-resource-form').addEventListener('submit', saveResourceConfig);
    
    loadResources();
    loadFindingResources();
    loadCatalog();
    loadCatalogStats();
    loadTasks();
    loadFindings();
    loadAssignedTasks();
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
        }
    });
});