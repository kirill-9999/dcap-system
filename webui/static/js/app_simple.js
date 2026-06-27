// ============================================================
// DCAP WEBUI - ПРОСТАЯ РАБОЧАЯ ВЕРСИЯ
// ============================================================

(function() {
    'use strict';

    // --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
    var currentPage = 'dashboard';
    var charts = {};
    var findingsPage = 0;
    var findingsTotal = 0;
    var perPage = 50;
    var currentTaskFilter = 'all';

    // --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
    function getElement(id) {
        return document.getElementById(id);
    }

    function showError(msg) {
        var el = getElement('error-message');
        if (el) {
            el.style.display = 'block';
            el.textContent = '❌ ' + msg;
        }
    }

    function hideError() {
        var el = getElement('error-message');
        if (el) el.style.display = 'none';
    }

    function updateTime() {
        var el = getElement('update-time');
        if (el) {
            el.textContent = '🔄 ' + new Date().toLocaleTimeString('ru-RU');
        }
    }

    function showNotification(message, type) {
        var colors = {
            success: '#48bb78',
            warning: '#ed8936',
            error: '#fc8181',
            info: '#4299e1'
        };
        var div = document.createElement('div');
        div.className = 'notification';
        div.style.background = colors[type] || colors.info;
        div.style.padding = '12px 24px';
        div.style.borderRadius = '8px';
        div.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        div.style.zIndex = '9999';
        div.style.maxWidth = '400px';
        div.style.position = 'fixed';
        div.style.bottom = '20px';
        div.style.right = '20px';
        div.textContent = message;
        document.body.appendChild(div);
        setTimeout(function() {
            div.style.animation = 'slideOut 0.3s ease';
            setTimeout(function() { div.remove(); }, 300);
        }, 3000);
    }

    // --- НАВИГАЦИЯ ---
    function switchPage(page) {
        currentPage = page;
        
        var pages = document.querySelectorAll('.page-content');
        for (var i = 0; i < pages.length; i++) {
            pages[i].classList.remove('active');
        }
        
        var target = getElement('page-' + page);
        if (target) target.classList.add('active');
        
        var links = document.querySelectorAll('.nav-link');
        for (var i = 0; i < links.length; i++) {
            links[i].classList.remove('active');
            if (links[i].getAttribute('data-page') === page) {
                links[i].classList.add('active');
            }
        }
        
        if (page === 'dashboard') loadDashboard();
        else if (page === 'findings') { loadCategories(); loadFindings(); }
        else if (page === 'tasks') { loadResources(); loadTasks(); }
        else if (page === 'scanners') loadScanners();
    }
    window.switchPage = switchPage;

    // --- ДАШБОРД ---
    function loadDashboard() {
        fetch('/api/stats')
            .then(function(r) { return r.json(); })
            .then(function(stats) {
                if (stats.error) { showError(stats.error); return; }
                hideError();
                updateStats(stats);
                updateCharts(stats);
                loadRecentFindings();
                updateTime();
            })
            .catch(function(e) { showError(e.message); console.error(e); });
    }

    function updateStats(stats) {
        var grid = getElement('stats-grid');
        if (!grid) return;
        grid.innerHTML = 
            '<div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-primary"><i class="fas fa-file-alt"></i></div><div class="stat-value">' + stats.total_findings + '</div><div class="stat-label">Находок</div></div></div>' +
            '<div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-success"><i class="fas fa-server"></i></div><div class="stat-value">' + stats.active_scanners + '</div><div class="stat-label">Сканеров</div></div></div>' +
            '<div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-warning"><i class="fas fa-clock"></i></div><div class="stat-value">' + stats.pending_tasks + '</div><div class="stat-label">В очереди</div></div></div>' +
            '<div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-success"><i class="fas fa-check-circle"></i></div><div class="stat-value">' + stats.completed_tasks + '</div><div class="stat-label">Завершено</div></div></div>' +
            '<div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-danger"><i class="fas fa-exclamation-triangle"></i></div><div class="stat-value">' + (stats.failed_tasks || 0) + '</div><div class="stat-label">Провалено</div></div></div>' +
            '<div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-info"><i class="fas fa-folder-open"></i></div><div class="stat-value">' + stats.total_files_scanned + '</div><div class="stat-label">Файлов</div></div></div>';
    }

    function updateCharts(stats) {
        var colors = ['#4e79a7','#f28e2b','#e15759','#59a14f','#edc948','#b07aa1'];
        
        var ctx1 = document.getElementById('categoryChart');
        if (ctx1) {
            if (charts.category) charts.category.destroy();
            var cats = Object.keys(stats.findings_by_category || {});
            var vals = Object.values(stats.findings_by_category || {});
            charts.category = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: cats.length ? cats : ['Нет данных'],
                    datasets: [{ label: 'Находки', data: cats.length ? vals : [0], backgroundColor: colors.slice(0, cats.length || 1) }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                }
            });
        }
        
        var ctx2 = document.getElementById('scannerChart');
        if (ctx2) {
            if (charts.scanner) charts.scanner.destroy();
            var scs = Object.keys(stats.findings_by_scanner || {});
            var scv = Object.values(stats.findings_by_scanner || {});
            charts.scanner = new Chart(ctx2, {
                type: 'doughnut',
                data: {
                    labels: scs.length ? scs : ['Нет данных'],
                    datasets: [{ data: scs.length ? scv : [1], backgroundColor: colors.slice(0, scs.length || 1) }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        }
    }

    function loadRecentFindings() {
        fetch('/api/findings?limit=10')
            .then(function(r) { return r.json(); })
            .then(function(findings) {
                var container = getElement('recent-findings');
                if (!container) return;
                if (findings.error) {
                    container.innerHTML = '<div class="text-center p-4 text-danger">' + findings.error + '</div>';
                    return;
                }
                if (!findings.length) {
                    container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>';
                    return;
                }
                var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>';
                for (var i = 0; i < findings.length; i++) {
                    var f = findings[i];
                    var conf = (f.confidence * 100).toFixed(0);
                    var cls = f.confidence > 0.8 ? 'high' : f.confidence > 0.5 ? 'medium' : 'low';
                    var fname = (f.file_path || '').split('\\').pop() || f.file_path || 'unknown';
                    html += '<tr><td><span class="file-path" title="' + f.file_path + '">' + fname + '</span></td><td><span class="badge bg-info">' + f.category + '</span></td><td>' + f.classifier_name + '</td><td class="confidence-' + cls + '">' + conf + '%</td></tr>';
                }
                html += '</tbody></table></div>';
                container.innerHTML = html;
            })
            .catch(function(e) { console.error(e); });
    }

    // --- НАХОДКИ ---
    function loadCategories() {
        fetch('/api/categories')
            .then(function(r) { return r.json(); })
            .then(function(cats) {
                var select = getElement('filter-category');
                if (!select || cats.error) return;
                select.innerHTML = '<option value="">Все</option>';
                for (var i = 0; i < cats.length; i++) {
                    var opt = document.createElement('option');
                    opt.value = cats[i];
                    opt.textContent = cats[i];
                    select.appendChild(opt);
                }
            })
            .catch(function(e) { console.error(e); });
    }

    function loadFindings() {
        var category = getElement('filter-category') ? getElement('filter-category').value : '';
        var filePath = getElement('filter-file') ? getElement('filter-file').value : '';
        var confidence = getElement('filter-confidence') ? getElement('filter-confidence').value : '';
        var perPageEl = getElement('per-page');
        if (perPageEl) perPage = parseInt(perPageEl.value) || 50;
        
        var url = '/api/findings?limit=' + perPage + '&offset=' + (findingsPage * perPage);
        if (category) url += '&category=' + encodeURIComponent(category);
        if (filePath) url += '&file_path=' + encodeURIComponent(filePath);
        if (confidence) url += '&min_confidence=' + confidence;
        
        var countUrl = '/api/findings/count';
        var params = [];
        if (category) params.push('category=' + encodeURIComponent(category));
        if (filePath) params.push('file_path=' + encodeURIComponent(filePath));
        if (params.length) countUrl += '?' + params.join('&');
        
        Promise.all([
            fetch(url).then(function(r) { return r.json(); }),
            fetch(countUrl).then(function(r) { return r.json(); })
        ])
        .then(function(results) {
            var findings = results[0];
            var countData = results[1];
            if (findings.error) { showError(findings.error); return; }
            hideError();
            findingsTotal = countData.count || 0;
            renderFindingsTable(findings);
            renderPagination();
            var totalEl = getElement('findings-total');
            if (totalEl) totalEl.textContent = '(всего: ' + findingsTotal + ')';
            updateTime();
        })
        .catch(function(e) { showError(e.message); console.error(e); });
    }

    function renderFindingsTable(findings) {
        var container = getElement('findings-table');
        if (!container) return;
        if (!findings || !findings.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>';
            return;
        }
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>#</th><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>';
        for (var i = 0; i < findings.length; i++) {
            var f = findings[i];
            var conf = (f.confidence * 100).toFixed(0);
            var cls = f.confidence > 0.8 ? 'high' : f.confidence > 0.5 ? 'medium' : 'low';
            var fname = (f.file_path || '').split('\\').pop() || f.file_path || 'unknown';
            html += '<tr><td>' + (findingsPage * perPage + i + 1) + '</td><td><span class="file-path" title="' + f.file_path + '">' + fname + '</span></td><td><span class="badge bg-info">' + f.category + '</span></td><td>' + f.classifier_name + '</td><td class="confidence-' + cls + '">' + conf + '%</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
    }

    function renderPagination() {
        var totalPages = Math.ceil(findingsTotal / perPage);
        var pagination = getElement('pagination');
        if (!pagination) return;
        if (totalPages <= 1) { pagination.innerHTML = ''; return; }
        var html = '<li class="page-item ' + (findingsPage === 0 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + (findingsPage - 1) + ')">«</a></li>';
        var start = Math.max(0, findingsPage - 2);
        var end = Math.min(totalPages - 1, findingsPage + 2);
        if (start > 0) {
            html += '<li class="page-item"><a class="page-link" href="#" onclick="goToPage(0)">1</a></li>';
            if (start > 1) html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
        for (var i = start; i <= end; i++) {
            html += '<li class="page-item ' + (i === findingsPage ? 'active' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + i + ')">' + (i+1) + '</a></li>';
        }
        if (end < totalPages - 1) {
            if (end < totalPages - 2) html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            html += '<li class="page-item"><a class="page-link" href="#" onclick="goToPage(' + (totalPages - 1) + ')">' + totalPages + '</a></li>';
        }
        html += '<li class="page-item ' + (findingsPage === totalPages - 1 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + (findingsPage + 1) + ')">»</a></li>';
        pagination.innerHTML = html;
    }

    function goToPage(page) {
        var totalPages = Math.ceil(findingsTotal / perPage);
        if (page < 0 || page >= totalPages) return;
        findingsPage = page;
        loadFindings();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    window.goToPage = goToPage;

    function resetFilters() {
        var cat = getElement('filter-category');
        var file = getElement('filter-file');
        var conf = getElement('filter-confidence');
        if (cat) cat.value = '';
        if (file) file.value = '';
        if (conf) conf.value = '';
        findingsPage = 0;
        loadFindings();
    }

    // --- ЗАДАНИЯ ---
    function loadResources() {
        fetch('/api/resources')
            .then(function(r) { return r.json(); })
            .then(function(resources) {
                var select = getElement('task-resource');
                if (!select) return;
                select.innerHTML = '<option value="">Выберите ресурс...</option>';
                for (var i = 0; i < resources.length; i++) {
                    var r = resources[i];
                    var opt = document.createElement('option');
                    opt.value = r.id;
                    opt.textContent = r.path + ' (' + r.type + ')';
                    select.appendChild(opt);
                }
            })
            .catch(function(e) { console.error(e); });
    }

    function createTask() {
        var resourceId = getElement('task-resource') ? getElement('task-resource').value : '';
        var scanType = getElement('scan-type') ? getElement('scan-type').value : 'full';
        if (!resourceId) { showNotification('Выберите ресурс', 'warning'); return; }
        fetch('/api/tasks/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resource_id: parseInt(resourceId), scan_type: scanType })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                showNotification('Задание #' + data.task_id + ' создано!', 'success');
                var modal = document.getElementById('createTaskModal');
                if (modal) {
                    var btn = modal.querySelector('.btn-close');
                    if (btn) btn.click();
                }
                loadTasks();
            } else {
                showNotification('Ошибка: ' + (data.detail || data.message), 'error');
            }
        })
        .catch(function(e) { showNotification('Ошибка: ' + e.message, 'error'); });
    }

    function loadTasks() {
        var filterEl = getElement('task-filter');
        var filter = filterEl ? filterEl.value : 'all';
        var url = '/api/tasks?limit=100';
        if (filter !== 'all') url += '&status=' + encodeURIComponent(filter);
        fetch(url)
            .then(function(r) { return r.json(); })
            .then(function(tasks) {
                renderTasks(tasks);
            })
            .catch(function(e) { console.error(e); });
    }

    function renderTasks(tasks) {
        var container = getElement('tasks-container');
        if (!container) return;
        if (!tasks || !tasks.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет заданий</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < tasks.length; i++) {
            var task = tasks[i];
            var progress = task.files_total > 0 ? (task.files_scanned / task.files_total * 100) : 0;
            var statusClass = 'pending';
            var statusIcon = '⏳';
            if (task.status === 'ASSIGNED') { statusClass = 'assigned'; statusIcon = '📤'; }
            else if (task.status === 'RUNNING') { statusClass = 'running'; statusIcon = '🔄'; }
            else if (task.status === 'COMPLETED') { statusClass = 'completed'; statusIcon = '✅'; }
            else if (task.status === 'FAILED') { statusClass = 'failed'; statusIcon = '❌'; }
            var timeAgo = task.created_at ? new Date(task.created_at).toLocaleString('ru-RU') : '-';
            html += '<div class="task-card" onclick="showTaskDetail(' + task.id + ')">' +
                '<div class="d-flex justify-content-between align-items-center">' +
                    '<div><strong>#' + task.id + '</strong> <span class="task-status status-' + statusClass + '">' + statusIcon + ' ' + task.status + '</span></div>' +
                    '<small class="text-muted">' + timeAgo + '</small>' +
                '</div>' +
                '<div class="progress-container">' +
                    '<div class="progress-bar" style="width: ' + Math.min(progress, 100) + '%"></div>' +
                    '<span class="progress-text">' + task.files_scanned + '/' + (task.files_total || '?') + '</span>' +
                '</div>' +
                '<div class="d-flex gap-3 text-muted small">' +
                    '<span><i class="fas fa-file"></i> ' + (task.files_scanned || 0) + '</span>' +
                    '<span><i class="fas fa-search"></i> ' + (task.findings_count || 0) + '</span>' +
                    '<span>' + progress.toFixed(1) + '%</span>' +
                '</div>' +
            '</div>';
        }
        container.innerHTML = html;
    }

    function showTaskDetail(taskId) {
        fetch('/api/tasks/' + taskId)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var task = data.task;
                getElement('detail-task-id').textContent = task.id;
                getElement('detail-status').textContent = task.status;
                getElement('detail-files').textContent = (task.files_scanned || 0) + '/' + (task.files_total || 0);
                getElement('detail-findings').textContent = task.findings_count || 0;
                getElement('detail-created').textContent = task.created_at ? new Date(task.created_at).toLocaleString() : '-';
                getElement('detail-completed').textContent = task.completed_at ? new Date(task.completed_at).toLocaleString() : '-';
                var list = getElement('detail-findings-list');
                if (list) {
                    if (data.findings && data.findings.length) {
                        var html = '<ul class="list-unstyled">';
                        for (var i = 0; i < Math.min(data.findings.length, 20); i++) {
                            var f = data.findings[i];
                            html += '<li class="py-1 border-bottom"><span class="badge bg-info me-2">' + f.category + '</span> ' + (f.value || f.file_path) + ' <span class="float-end text-success">' + (f.confidence * 100).toFixed(0) + '%</span></li>';
                        }
                        html += '</ul>';
                        list.innerHTML = html;
                    } else {
                        list.innerHTML = '<div class="text-muted">Нет находок</div>';
                    }
                }
                var modal = new bootstrap.Modal(document.getElementById('taskDetailModal'));
                modal.show();
            })
            .catch(function(e) { showNotification('Ошибка: ' + e.message, 'error'); });
    }
    window.showTaskDetail = showTaskDetail;

    function cancelTaskFromDetail() {
        var idEl = getElement('detail-task-id');
        var id = idEl ? parseInt(idEl.textContent) : 0;
        if (!id || !confirm('Отменить задание #' + id + '?')) return;
        fetch('/api/tasks/' + id + '/cancel', { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    showNotification('Задание #' + id + ' отменено', 'success');
                    var modal = document.getElementById('taskDetailModal');
                    if (modal) {
                        var btn = modal.querySelector('.btn-close');
                        if (btn) btn.click();
                    }
                    loadTasks();
                } else {
                    showNotification('Ошибка: ' + (data.detail || data.message), 'error');
                }
            })
            .catch(function(e) { showNotification('Ошибка: ' + e.message, 'error'); });
    }

    // --- СКАНЕРЫ ---
    function loadScanners() {
        fetch('/api/scanners')
            .then(function(r) { return r.json(); })
            .then(function(scanners) {
                var container = getElement('scanners-table');
                if (!container) return;
                if (!scanners || !scanners.length) {
                    container.innerHTML = '<div class="text-center p-4 text-muted">Нет сканеров</div>';
                    return;
                }
                var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Имя</th><th>Статус</th><th>Endpoint</th><th>Heartbeat</th><th>Файлов</th><th>Находок</th></tr></thead><tbody>';
                for (var i = 0; i < scanners.length; i++) {
                    var s = scanners[i];
                    var online = s.status === 'active';
                    var badge = online ? 'success' : 'secondary';
                    var statusText = online ? 'Активен' : 'Оффлайн';
                    var heartbeat = s.last_heartbeat ? new Date(s.last_heartbeat).toLocaleString('ru-RU') : '-';
                    html += '<tr><td><strong>#' + s.id + '</strong></td><td>' + s.name + '</td><td><span class="badge bg-' + badge + '">' + statusText + '</span></td><td><code>' + s.endpoint + '</code></td><td>' + heartbeat + '</td><td>' + (s.total_files_scanned || 0) + '</td><td>' + (s.total_findings || 0) + '</td></tr>';
                }
                html += '</tbody></table></div>';
                container.innerHTML = html;
                updateTime();
            })
            .catch(function(e) { console.error(e); });
    }

    // --- ИНИЦИАЛИЗАЦИЯ ---
    document.addEventListener('DOMContentLoaded', function() {
        // Навигация
        var navLinks = document.querySelectorAll('.nav-link');
        for (var i = 0; i < navLinks.length; i++) {
            navLinks[i].addEventListener('click', function(e) {
                e.preventDefault();
                var page = this.getAttribute('data-page');
                if (page) switchPage(page);
            });
        }
        
        // Кнопки находок
        var applyBtn = getElement('apply-findings');
        if (applyBtn) applyBtn.addEventListener('click', function() { findingsPage = 0; loadFindings(); });
        
        var resetBtn = getElement('reset-findings');
        if (resetBtn) resetBtn.addEventListener('click', resetFilters);
        
        var perPageEl = getElement('per-page');
        if (perPageEl) perPageEl.addEventListener('change', function() { findingsPage = 0; loadFindings(); });
        
        // Кнопки заданий
        var refreshBtn = getElement('refresh-tasks');
        if (refreshBtn) refreshBtn.addEventListener('click', loadTasks);
        
        var filterEl = getElement('task-filter');
        if (filterEl) filterEl.addEventListener('change', loadTasks);
        
        var createBtn = getElement('create-task-btn');
        if (createBtn) createBtn.addEventListener('click', createTask);
        
        var cancelBtn = getElement('cancel-task-btn');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelTaskFromDetail);
        
        var showAllBtn = getElement('show-all-findings');
        if (showAllBtn) showAllBtn.addEventListener('click', function(e) { e.preventDefault(); switchPage('findings'); });
        
        // Загрузка
        loadDashboard();
        
        // Автообновление
        setInterval(function() {
            if (currentPage === 'dashboard') loadDashboard();
            else if (currentPage === 'findings') loadFindings();
            else if (currentPage === 'tasks') loadTasks();
            else if (currentPage === 'scanners') loadScanners();
        }, 30000);
        
        setInterval(function() {
            if (currentPage === 'tasks') loadTasks();
        }, 5000);
    });

})();