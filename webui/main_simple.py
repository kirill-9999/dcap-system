from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from webui.api.routes import router
from webui.config import WEBUI_HOST, WEBUI_PORT, DEBUG

app = FastAPI(title="DCAP WebUI", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Подключаем API
app.include_router(router)

# Полный HTML интерфейс
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DCAP Distributed v3.0</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #f5f7fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: all 0.2s; height: 100%; }
        .stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2rem; font-weight: 700; color: #1a202c; line-height: 1.2; }
        .stat-label { font-size: 0.8rem; color: #718096; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
        .stat-icon { font-size: 1.8rem; margin-bottom: 8px; }
        .file-path { font-family: 'Courier New', monospace; font-size: 0.85rem; max-width: 200px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .confidence-high { color: #38a169; font-weight: 600; }
        .confidence-medium { color: #d69e2e; font-weight: 600; }
        .confidence-low { color: #e53e3e; font-weight: 600; }
        .table-hover tbody tr { cursor: pointer; }
        .table-hover tbody tr:hover { background-color: #f1f3f5; }
        .navbar-dark .navbar-nav .nav-link.active { color: #63b3ed; }
        .badge-status { font-size: 0.9rem; }
        .page-title { margin-bottom: 1.5rem; }
        .filter-card { background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 1.5rem; }
        .findings-table-wrapper { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <i class="fas fa-shield-alt text-primary"></i> DCAP v3.0
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link active" href="/" data-page="dashboard">
                            <i class="fas fa-chart-pie"></i> Дашборд
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/findings" data-page="findings">
                            <i class="fas fa-search"></i> Находки
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/tasks" data-page="tasks">
                            <i class="fas fa-tasks"></i> Задания
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/scanners" data-page="scanners">
                            <i class="fas fa-server"></i> Сканеры
                        </a>
                    </li>
                </ul>
                <div class="d-flex align-items-center">
                    <span class="badge bg-success me-2 badge-status">
                        <i class="fas fa-circle text-success"></i> Онлайн
                    </span>
                    <span class="text-muted small" id="update-time"></span>
                </div>
            </div>
        </div>
    </nav>

    <main class="container-fluid py-4">
        <div id="page-content">
            <!-- Контент загружается через JavaScript -->
            <div class="text-center p-5">
                <i class="fas fa-spinner fa-spin fa-2x text-primary"></i>
                <p class="mt-3 text-muted">Загрузка...</p>
            </div>
        </div>
    </main>

    <script>
        // Глобальное состояние
        let currentPage = 'dashboard';
        let charts = {};
        
        // Навигация
        document.querySelectorAll('[data-page]').forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const page = this.getAttribute('data-page');
                navigateTo(page);
            });
        });

        function navigateTo(page) {
            currentPage = page;
            // Обновляем активную ссылку
            document.querySelectorAll('[data-page]').forEach(el => el.classList.remove('active'));
            document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
            // Загружаем страницу
            loadPage(page);
        }

        function loadPage(page) {
            const container = document.getElementById('page-content');
            switch(page) {
                case 'dashboard':
                    renderDashboard(container);
                    break;
                case 'findings':
                    renderFindings(container);
                    break;
                case 'tasks':
                    renderTasks(container);
                    break;
                case 'scanners':
                    renderScanners(container);
                    break;
                default:
                    container.innerHTML = '<h2>Страница не найдена</h2>';
            }
        }

        // === ДАШБОРД ===
        function renderDashboard(container) {
            container.innerHTML = `
                <h2 class="page-title"><i class="fas fa-chart-pie text-primary"></i> Дашборд системы</h2>
                <div class="row g-3 mb-4" id="stats-grid"></div>
                <div class="row g-3 mb-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header"><i class="fas fa-chart-bar"></i> Находки по категориям</div>
                            <div class="card-body"><canvas id="categoryChart" height="250"></canvas></div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header"><i class="fas fa-chart-doughnut"></i> Находки по сканерам</div>
                            <div class="card-body"><canvas id="scannerChart" height="250"></canvas></div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><i class="fas fa-history"></i> Последние находки</span>
                        <a href="#" onclick="navigateTo('findings'); return false;" class="btn btn-sm btn-outline-primary">Все находки →</a>
                    </div>
                    <div class="card-body p-0" id="recent-findings"></div>
                </div>
            `;
            loadDashboardData();
        }

        async function loadDashboardData() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                updateStats(stats);
                updateCharts(stats);
                await loadRecentFindings();
                updateTime();
            } catch(e) {
                console.error('Ошибка загрузки дашборда:', e);
            }
        }

        function updateStats(stats) {
            const grid = document.getElementById('stats-grid');
            grid.innerHTML = `
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-primary"><i class="fas fa-file-alt"></i></div><div class="stat-value">${stats.total_findings}</div><div class="stat-label">Находок</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-success"><i class="fas fa-server"></i></div><div class="stat-value">${stats.active_scanners}</div><div class="stat-label">Сканеров</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-warning"><i class="fas fa-clock"></i></div><div class="stat-value">${stats.pending_tasks}</div><div class="stat-label">В очереди</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-success"><i class="fas fa-check-circle"></i></div><div class="stat-value">${stats.completed_tasks}</div><div class="stat-label">Завершено</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-danger"><i class="fas fa-exclamation-triangle"></i></div><div class="stat-value">${stats.failed_tasks || 0}</div><div class="stat-label">Провалено</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-info"><i class="fas fa-folder-open"></i></div><div class="stat-value">${stats.total_files_scanned}</div><div class="stat-label">Файлов</div></div></div>
            `;
        }

        function updateCharts(stats) {
            const colors = ['#4e79a7','#f28e2b','#e15759','#59a14f','#edc948','#b07aa1','#9c755f','#bab0ac'];
            
            // Категории
            if (charts.category) charts.category.destroy();
            const ctx1 = document.getElementById('categoryChart')?.getContext('2d');
            if (ctx1) {
                const cats = Object.keys(stats.findings_by_category || {});
                const vals = Object.values(stats.findings_by_category || {});
                charts.category = new Chart(ctx1, {
                    type: 'bar',
                    data: {
                        labels: cats.length ? cats : ['Нет данных'],
                        datasets: [{
                            label: 'Находки',
                            data: cats.length ? vals : [0],
                            backgroundColor: colors.slice(0, cats.length || 1)
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                    }
                });
            }
            
            // Сканеры
            if (charts.scanner) charts.scanner.destroy();
            const ctx2 = document.getElementById('scannerChart')?.getContext('2d');
            if (ctx2) {
                const scs = Object.keys(stats.findings_by_scanner || {});
                const scv = Object.values(stats.findings_by_scanner || {});
                charts.scanner = new Chart(ctx2, {
                    type: 'doughnut',
                    data: {
                        labels: scs.length ? scs : ['Нет данных'],
                        datasets: [{
                            data: scs.length ? scv : [1],
                            backgroundColor: colors.slice(0, scs.length || 1)
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: { legend: { position: 'bottom' } }
                    }
                });
            }
        }

        async function loadRecentFindings() {
            try {
                const response = await fetch('/api/findings?limit=10');
                const findings = await response.json();
                const container = document.getElementById('recent-findings');
                
                if (!findings.length) {
                    container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>';
                    return;
                }
                
                let html = `<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>`;
                findings.forEach(f => {
                    const conf = (f.confidence * 100).toFixed(0);
                    const cls = f.confidence > 0.8 ? 'high' : f.confidence > 0.5 ? 'medium' : 'low';
                    const fname = f.file_path.split('\\\\').pop() || f.file_path;
                    html += `<tr onclick="showFindingDetail(${f.id})"><td><span class="file-path" title="${f.file_path}">${fname}</span></td><td><span class="badge bg-info">${f.category}</span></td><td>${f.classifier_name}</td><td class="confidence-${cls}">${conf}%</td></tr>`;
                });
                html += '</tbody></table></div>';
                container.innerHTML = html;
            } catch(e) {
                console.error('Ошибка загрузки находок:', e);
            }
        }

        // === НАХОДКИ ===
        function renderFindings(container) {
            container.innerHTML = `
                <h2 class="page-title"><i class="fas fa-search text-primary"></i> Находки <span class="text-muted fs-6" id="findings-total"></span></h2>
                <div class="filter-card">
                    <div class="row g-3 align-items-end">
                        <div class="col-md-3">
                            <label class="form-label">Категория</label>
                            <select class="form-select" id="filter-category"><option value="">Все</option></select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Поиск по файлу</label>
                            <input type="text" class="form-control" id="filter-file" placeholder="Часть пути...">
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Мин. доверие</label>
                            <select class="form-select" id="filter-confidence"><option value="">Любое</option><option value="0.9">90%</option><option value="0.7">70%</option><option value="0.5">50%</option></select>
                        </div>
                        <div class="col-md-3">
                            <button class="btn btn-primary me-2" onclick="loadFindings()"><i class="fas fa-filter"></i> Применить</button>
                            <button class="btn btn-outline-secondary" onclick="resetFilters()"><i class="fas fa-undo"></i> Сброс</button>
                        </div>
                    </div>
                </div>
                <div class="findings-table-wrapper" id="findings-table"></div>
                <div class="d-flex justify-content-between align-items-center mt-3">
                    <div><select class="form-select form-select-sm" id="per-page" onchange="loadFindings()" style="width:auto;display:inline-block;"><option value="20">20</option><option value="50" selected>50</option><option value="100">100</option></select><span class="text-muted small ms-2">на страницу</span></div>
                    <nav><ul class="pagination mb-0" id="pagination"></ul></nav>
                </div>
            `;
            loadCategories();
            loadFindings();
        }

        async function loadCategories() {
            try {
                const r = await fetch('/api/categories');
                const cats = await r.json();
                const select = document.getElementById('filter-category');
                cats.forEach(c => { const opt = document.createElement('option'); opt.value = c; opt.textContent = c; select.appendChild(opt); });
            } catch(e) { console.error(e); }
        }

        let findingsPage = 0;
        let findingsTotal = 0;
        let perPage = 50;

        async function loadFindings() {
            const category = document.getElementById('filter-category')?.value || '';
            const filePath = document.getElementById('filter-file')?.value || '';
            const confidence = document.getElementById('filter-confidence')?.value || '';
            perPage = parseInt(document.getElementById('per-page')?.value || 50);
            
            let url = `/api/findings?limit=${perPage}&offset=${findingsPage * perPage}`;
            if (category) url += `&category=${encodeURIComponent(category)}`;
            if (filePath) url += `&file_path=${encodeURIComponent(filePath)}`;
            if (confidence) url += `&min_confidence=${confidence}`;
            
            try {
                const r = await fetch(url);
                const findings = await r.json();
                
                const countUrl = `/api/findings/count?${new URLSearchParams({ category, file_path })}`;
                const countR = await fetch(countUrl);
                const countData = await countR.json();
                findingsTotal = countData.count || 0;
                
                renderFindingsTable(findings);
                renderPagination();
                document.getElementById('findings-total').textContent = `(всего: ${findingsTotal})`;
                updateTime();
            } catch(e) { console.error(e); }
        }

        function renderFindingsTable(findings) {
            const container = document.getElementById('findings-table');
            if (!findings.length) {
                container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>';
                return;
            }
            let html = `<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>#</th><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>`;
            findings.forEach((f, i) => {
                const conf = (f.confidence * 100).toFixed(0);
                const cls = f.confidence > 0.8 ? 'high' : f.confidence > 0.5 ? 'medium' : 'low';
                const fname = f.file_path.split('\\\\').pop() || f.file_path;
                html += `<tr onclick="showFindingDetail(${f.id})"><td>${findingsPage * perPage + i + 1}</td><td><span class="file-path" title="${f.file_path}">${fname}</span></td><td><span class="badge bg-info">${f.category}</span></td><td>${f.classifier_name}</td><td class="confidence-${cls}">${conf}%</td></tr>`;
            });
            html += '</tbody></table></div>';
            container.innerHTML = html;
        }

        function renderPagination() {
            const totalPages = Math.ceil(findingsTotal / perPage);
            const pagination = document.getElementById('pagination');
            if (totalPages <= 1) { pagination.innerHTML = ''; return; }
            let html = `<li class="page-item ${findingsPage === 0 ? 'disabled' : ''}"><a class="page-link" href="#" onclick="goToPage(${findingsPage - 1})">«</a></li>`;
            let start = Math.max(0, findingsPage - 2), end = Math.min(totalPages - 1, findingsPage + 2);
            if (start > 0) { html += `<li class="page-item"><a class="page-link" href="#" onclick="goToPage(0)">1</a></li>`; if (start > 1) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`; }
            for (let i = start; i <= end; i++) html += `<li class="page-item ${i === findingsPage ? 'active' : ''}"><a class="page-link" href="#" onclick="goToPage(${i})">${i+1}</a></li>`;
            if (end < totalPages - 1) { if (end < totalPages - 2) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`; html += `<li class="page-item"><a class="page-link" href="#" onclick="goToPage(${totalPages - 1})">${totalPages}</a></li>`; }
            html += `<li class="page-item ${findingsPage === totalPages - 1 ? 'disabled' : ''}"><a class="page-link" href="#" onclick="goToPage(${findingsPage + 1})">»</a></li>`;
            pagination.innerHTML = html;
        }

        function goToPage(page) {
            const totalPages = Math.ceil(findingsTotal / perPage);
            if (page < 0 || page >= totalPages) return;
            findingsPage = page;
            loadFindings();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function resetFilters() {
            document.getElementById('filter-category').value = '';
            document.getElementById('filter-file').value = '';
            document.getElementById('filter-confidence').value = '';
            findingsPage = 0;
            loadFindings();
        }

        // === ЗАДАНИЯ ===
        function renderTasks(container) {
            container.innerHTML = `
                <h2 class="page-title"><i class="fas fa-tasks text-primary"></i> Задания</h2>
                <div class="filter-card">
                    <div class="row g-3 align-items-end">
                        <div class="col-md-3">
                            <label class="form-label">Статус</label>
                            <select class="form-select" id="task-status" onchange="loadTasks()">
                                <option value="">Все</option>
                                <option value="PENDING">⏳ Ожидает</option>
                                <option value="ASSIGNED">🔄 Назначено</option>
                                <option value="SCANNING">🔍 Сканируется</option>
                                <option value="COMPLETED">✅ Завершено</option>
                                <option value="FAILED">❌ Провалено</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="findings-table-wrapper" id="tasks-table"></div>
            `;
            loadTasks();
        }

        async function loadTasks() {
            const status = document.getElementById('task-status')?.value || '';
            let url = '/api/tasks?limit=50';
            if (status) url += `&status=${encodeURIComponent(status)}`;
            try {
                const r = await fetch(url);
                const tasks = await r.json();
                const container = document.getElementById('tasks-table');
                if (!tasks.length) { container.innerHTML = '<div class="text-center p-4 text-muted">Нет заданий</div>'; return; }
                let html = `<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Статус</th><th>Файлов</th><th>Находок</th><th>Создано</th><th>Завершено</th></tr></thead><tbody>`;
                tasks.forEach(t => {
                    const badge = { 'PENDING':'secondary','ASSIGNED':'primary','SCANNING':'warning','COMPLETED':'success','FAILED':'danger' }[t.status] || 'secondary';
                    const icons = { 'PENDING':'⏳','ASSIGNED':'🔄','SCANNING':'🔍','COMPLETED':'✅','FAILED':'❌' };
                    const created = t.created_at ? new Date(t.created_at).toLocaleString('ru-RU') : '-';
                    const completed = t.completed_at ? new Date(t.completed_at).toLocaleString('ru-RU') : '-';
                    html += `<tr onclick="showTaskDetail(${t.id})"><td><strong>#${t.id}</strong></td><td><span class="badge bg-${badge}">${icons[t.status]||''} ${t.status}</span></td><td>${t.files_scanned||0}</td><td>${t.findings_count||0}</td><td>${created}</td><td>${completed}</td></tr>`;
                });
                html += '</tbody></table></div>';
                container.innerHTML = html;
                updateTime();
            } catch(e) { console.error(e); }
        }

        // === СКАНЕРЫ ===
        function renderScanners(container) {
            container.innerHTML = `
                <h2 class="page-title"><i class="fas fa-server text-primary"></i> Сканеры</h2>
                <div class="findings-table-wrapper" id="scanners-table"></div>
            `;
            loadScanners();
        }

        async function loadScanners() {
            try {
                const r = await fetch('/api/scanners');
                const scanners = await r.json();
                const container = document.getElementById('scanners-table');
                if (!scanners.length) { container.innerHTML = '<div class="text-center p-4 text-muted">Нет сканеров</div>'; return; }
                let html = `<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Имя</th><th>Статус</th><th>Endpoint</th><th>Heartbeat</th><th>Файлов</th><th>Находок</th></tr></thead><tbody>`;
                scanners.forEach(s => {
                    const online = s.status === 'active';
                    const badge = online ? 'success' : 'secondary';
                    const statusText = online ? '🟢 Активен' : '⚪ Оффлайн';
                    const heartbeat = s.last_heartbeat ? new Date(s.last_heartbeat).toLocaleString('ru-RU') : '-';
                    html += `<tr><td><strong>#${s.id}</strong></td><td>${s.name}</td><td><span class="badge bg-${badge}">${statusText}</span></td><td><code>${s.endpoint}</code></td><td>${heartbeat}</td><td>${s.total_files_scanned||0}</td><td>${s.total_findings||0}</td></tr>`;
                });
                html += '</tbody></table></div>';
                container.innerHTML = html;
                updateTime();
            } catch(e) { console.error(e); }
        }

        // === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
        async function showFindingDetail(id) {
            try {
                const r = await fetch(`/api/findings/${id}`);
                const data = await r.json();
                const f = data.finding;
                alert(`📄 Находка #${f.id}\n\nФайл: ${f.file_path}\nКатегория: ${f.category}\nПодкатегория: ${f.subcategory || '-'}\nЗначение: ${f.value || '-'}\nКлассификатор: ${f.classifier_name}\nДоверие: ${(f.confidence * 100).toFixed(0)}%`);
            } catch(e) { console.error(e); }
        }

        async function showTaskDetail(id) {
            try {
                const r = await fetch(`/api/tasks/${id}`);
                const data = await r.json();
                const t = data.task;
                let msg = `📋 Задание #${t.id}\n\nСтатус: ${t.status}\nФайлов: ${t.files_scanned||0}\nНаходок: ${t.findings_count||0}\nСоздано: ${t.created_at ? new Date(t.created_at).toLocaleString('ru-RU') : '-'}\nЗавершено: ${t.completed_at ? new Date(t.completed_at).toLocaleString('ru-RU') : '-'}`;
                if (data.findings?.length) {
                    msg += '\n\nПоследние находки:';
                    data.findings.slice(0,5).forEach(f => msg += `\n- ${f.category}: ${f.file_path.split('\\\\').pop()} (${(f.confidence*100).toFixed(0)}%)`);
                    if (data.findings.length > 5) msg += `\n... и еще ${data.findings.length - 5}`;
                }
                alert(msg);
            } catch(e) { console.error(e); }
        }

        function updateTime() {
            const now = new Date().toLocaleTimeString('ru-RU');
            document.getElementById('update-time').textContent = '🔄 ' + now;
        }

        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            loadPage('dashboard');
            setInterval(() => {
                if (currentPage === 'dashboard') loadDashboardData();
                else if (currentPage === 'findings') loadFindings();
                else if (currentPage === 'tasks') loadTasks();
                else if (currentPage === 'scanners') loadScanners();
            }, 30000);
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML_CONTENT

@app.get("/findings", response_class=HTMLResponse)
async def findings():
    return HTML_CONTENT

@app.get("/tasks", response_class=HTMLResponse)
async def tasks():
    return HTML_CONTENT

@app.get("/scanners", response_class=HTMLResponse)
async def scanners():
    return HTML_CONTENT

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════╗
    ║   DCAP WebUI v3.0 (Simple)                 ║
    ║   http://localhost:8001                    ║
    ║   Документация: /docs                     ║
    ╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(
        "webui.main_simple:app",
        host=WEBUI_HOST,
        port=WEBUI_PORT,
        reload=DEBUG,
        log_level="info"
    )