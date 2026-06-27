/**
 * Управление заданиями в WebUI
 */

let tasksUpdateInterval = null;
let currentTaskFilter = 'all';

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    loadResources();
    loadTasks();
    
    // Автообновление каждые 5 секунд
    tasksUpdateInterval = setInterval(loadTasks, 5000);
    
    // Фильтр
    document.getElementById('task-filter')?.addEventListener('change', function() {
        currentTaskFilter = this.value;
        loadTasks();
    });
});

/**
 * Загрузка списка ресурсов для формы создания
 */
async function loadResources() {
    try {
        const response = await fetch('/api/resources');
        const resources = await response.json();
        const select = document.getElementById('task-resource');
        
        if (!select) return;
        
        select.innerHTML = '<option value="">Выберите ресурс...</option>';
        resources.forEach(r => {
            const option = document.createElement('option');
            option.value = r.id;
            option.textContent = `${r.path} (${r.type})`;
            select.appendChild(option);
        });
    } catch (e) {
        console.error('Error loading resources:', e);
        showNotification('❌ Ошибка загрузки ресурсов', 'error');
    }
}

/**
 * Создание нового задания
 */
async function createTask() {
    const resourceId = document.getElementById('task-resource')?.value;
    const scanType = document.getElementById('scan-type')?.value || 'full';
    
    if (!resourceId) {
        showNotification('⚠️ Пожалуйста, выберите ресурс', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/tasks/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                resource_id: parseInt(resourceId), 
                scan_type: scanType 
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showNotification(`✅ Задание #${data.task_id} создано!`, 'success');
            
            // Закрываем модальное окно
            const modal = document.getElementById('createTaskModal');
            if (modal) {
                const closeBtn = modal.querySelector('.btn-close');
                if (closeBtn) closeBtn.click();
            }
            
            // Обновляем список
            loadTasks();
        } else {
            showNotification(`❌ Ошибка: ${data.detail || data.message || 'Неизвестная ошибка'}`, 'error');
        }
    } catch (e) {
        showNotification(`❌ Ошибка: ${e.message}`, 'error');
        console.error(e);
    }
}

/**
 * Загрузка списка заданий
 */
async function loadTasks() {
    const filter = currentTaskFilter || 'all';
    let url = '/api/tasks?limit=100';
    if (filter !== 'all') {
        url += `&status=${encodeURIComponent(filter)}`;
    }
    
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const tasks = await response.json();
        renderTasks(tasks);
    } catch (e) {
        console.error('Error loading tasks:', e);
        const container = document.getElementById('tasks-container');
        if (container) {
            container.innerHTML = `
                <div class="text-center p-4 text-danger">
                    ❌ Ошибка загрузки заданий: ${e.message}
                </div>
            `;
        }
    }
}

/**
 * Отображение списка заданий
 */
function renderTasks(tasks) {
    const container = document.getElementById('tasks-container');
    if (!container) return;
    
    if (!tasks || tasks.length === 0) {
        container.innerHTML = `
            <div class="text-center p-4 text-muted">
                <i class="fas fa-inbox fa-2x mb-2 d-block"></i>
                Нет заданий
            </div>
        `;
        return;
    }
    
    let html = '<div class="tasks-grid">';
    tasks.forEach(task => {
        html += renderTaskCard(task);
    });
    html += '</div>';
    container.innerHTML = html;
}

/**
 * Отображение одной карточки задания
 */
function renderTaskCard(task) {
    const progress = task.files_total > 0 ? (task.files_scanned / task.files_total * 100) : 0;
    const statusClass = getStatusClass(task.status);
    const statusIcon = getStatusIcon(task.status);
    const timeAgo = getTimeAgo(task.created_at);
    
    return `
        <div class="task-card" data-task-id="${task.id}" onclick="showTaskDetail(${task.id})">
            <div class="task-header">
                <div class="task-info">
                    <span class="task-id">#${task.id}</span>
                    <span class="task-status ${statusClass}">${statusIcon} ${task.status}</span>
                </div>
                <div class="task-actions">
                    <button class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation(); cancelTask(${task.id})" 
                            title="Отменить задание">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            
            <div class="task-progress-container">
                <div class="task-progress">
                    <div class="progress-bar" style="width: ${Math.min(progress, 100)}%"></div>
                </div>
                <span class="progress-text">${task.files_scanned}/${task.files_total || '?'}</span>
            </div>
            
            <div class="task-stats">
                <span><i class="fas fa-file"></i> ${task.files_scanned || 0} файлов</span>
                <span><i class="fas fa-search"></i> ${task.findings_count || 0} находок</span>
                <span><i class="fas fa-tachometer-alt"></i> ${progress.toFixed(1)}%</span>
            </div>
            
            <div class="task-footer">
                <span class="task-time"><i class="far fa-clock"></i> ${timeAgo}</span>
                ${task.scanner_id ? `<span class="task-scanner"><i class="fas fa-server"></i> Scanner #${task.scanner_id}</span>` : ''}
            </div>
        </div>
    `;
}

/**
 * Получение CSS класса для статуса
 */
function getStatusClass(status) {
    const classes = {
        'PENDING': 'status-pending',
        'ASSIGNED': 'status-assigned',
        'RUNNING': 'status-running',
        'COMPLETED': 'status-completed',
        'FAILED': 'status-failed',
        'CANCELED': 'status-canceled'
    };
    return classes[status] || 'status-pending';
}

/**
 * Получение иконки для статуса
 */
function getStatusIcon(status) {
    const icons = {
        'PENDING': '⏳',
        'ASSIGNED': '📤',
        'RUNNING': '🔄',
        'COMPLETED': '✅',
        'FAILED': '❌',
        'CANCELED': '🚫'
    };
    return icons[status] || '⏳';
}

/**
 * Форматирование времени
 */
function getTimeAgo(dateStr) {
    if (!dateStr) return 'Неизвестно';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return 'Только что';
    if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
    return date.toLocaleString('ru-RU');
}

/**
 * Отмена задания
 */
async function cancelTask(taskId) {
    if (!confirm(`Отменить задание #${taskId}?`)) return;
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/cancel`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (response.ok && data.success) {
            showNotification(`✅ Задание #${taskId} отменено`, 'success');
            loadTasks();
        } else {
            showNotification(`❌ Ошибка: ${data.detail || data.message}`, 'error');
        }
    } catch (e) {
        showNotification(`❌ Ошибка: ${e.message}`, 'error');
    }
}

/**
 * Детали задания
 */
async function showTaskDetail(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        
        // Показываем модальное окно с деталями
        const modal = document.getElementById('taskDetailModal');
        if (!modal) return;
        
        const task = data.task;
        const findings = data.findings || [];
        
        document.getElementById('detail-task-id').textContent = task.id;
        document.getElementById('detail-task-status').textContent = task.status;
        document.getElementById('detail-task-status').className = `badge ${getStatusClass(task.status)}`;
        document.getElementById('detail-files-total').textContent = task.files_total || 0;
        document.getElementById('detail-files-scanned').textContent = task.files_scanned || 0;
        document.getElementById('detail-findings').textContent = task.findings_count || 0;
        document.getElementById('detail-created').textContent = task.created_at ? new Date(task.created_at).toLocaleString() : '-';
        document.getElementById('detail-completed').textContent = task.completed_at ? new Date(task.completed_at).toLocaleString() : '-';
        
        // Находки
        const findingsContainer = document.getElementById('detail-findings-list');
        if (findingsContainer) {
            if (findings.length === 0) {
                findingsContainer.innerHTML = '<div class="text-muted">Нет находок</div>';
            } else {
                let html = '<ul class="list-unstyled">';
                findings.slice(0, 10).forEach(f => {
                    html += `
                        <li class="finding-item">
                            <span class="badge bg-info">${f.category}</span>
                            ${f.value || f.file_path}
                            <span class="confidence">${(f.confidence * 100).toFixed(0)}%</span>
                        </li>
                    `;
                });
                if (findings.length > 10) {
                    html += `<li class="text-muted">... и еще ${findings.length - 10} находок</li>`;
                }
                html += '</ul>';
                findingsContainer.innerHTML = html;
            }
        }
        
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
    } catch (e) {
        showNotification(`❌ Ошибка загрузки деталей: ${e.message}`, 'error');
    }
}

/**
 * Уведомления
 */
function showNotification(message, type = 'info') {
    const colors = {
        success: '#48bb78',
        warning: '#ed8936',
        error: '#fc8181',
        info: '#4299e1'
    };
    
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 24px;
        background: ${colors[type] || colors.info};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        max-width: 400px;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Добавляем CSS для анимаций
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .task-card {
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .task-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .task-progress-container {
        position: relative;
        height: 24px;
        background: #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
        margin: 8px 0;
    }
    .task-progress {
        height: 100%;
        transition: width 0.5s ease;
    }
    .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, #48bb78, #38a169);
        transition: width 0.5s ease;
    }
    .progress-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 0.75rem;
        font-weight: 600;
        color: #2d3748;
    }
    .status-pending { background: #e2e8f0; color: #4a5568; }
    .status-assigned { background: #bee3f8; color: #2b6cb0; }
    .status-running { background: #fefcbf; color: #975a16; }
    .status-completed { background: #c6f6d5; color: #276749; }
    .status-failed { background: #fed7d7; color: #9b2c2c; }
    .status-canceled { background: #e2e8f0; color: #4a5568; }
`;
document.head.appendChild(style);