# webui/main.py
from fastapi import FastAPI
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

app.include_router(router)


# ===== ВЕСЬ HTML В ОДНОМ ФАЙЛЕ (ИСПРАВЛЕННЫЙ) =====
HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>DCAP v3.0</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{background:#f5f7fa;font-family:system-ui,-apple-system,sans-serif;}
.stat-card{background:white;padding:1.5rem;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);height:100%;transition:all 0.2s;}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.1);}
.stat-value{font-size:2rem;font-weight:700;color:#1a202c;}
.stat-label{font-size:0.8rem;color:#718096;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;}
.stat-icon{font-size:1.8rem;margin-bottom:8px;}
.file-path{font-family:'Courier New',monospace;font-size:0.85rem;max-width:200px;display:inline-block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.confidence-high{color:#38a169;font-weight:600;}
.confidence-medium{color:#d69e2e;font-weight:600;}
.confidence-low{color:#e53e3e;font-weight:600;}
.table-hover tbody tr{cursor:pointer;}
.table-hover tbody tr:hover{background-color:#f1f3f5;}
.page-content{display:none;}
.page-content.active{display:block;}
.nav-link{cursor:pointer;}
.nav-link.active{color:#63b3ed!important;font-weight:600;}
.filter-card{background:white;padding:1rem;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:1.5rem;}
.table-wrapper{background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);overflow:hidden;}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;}
.modal.show{display:flex;}
.modal-content{background:white;max-width:500px;width:90%;padding:2rem;border-radius:12px;max-height:90vh;overflow-y:auto;}
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
<div class="container-fluid">
<a class="navbar-brand" href="#"><i class="fas fa-shield-alt text-primary"></i> DCAP v3.0</a>
<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
<span class="navbar-toggler-icon"></span>
</button>
<div class="collapse navbar-collapse" id="navbarNav">
<ul class="navbar-nav me-auto" id="nav-menu">
<li class="nav-item"><a class="nav-link active" data-page="dashboard" onclick="switchPage('dashboard')"><i class="fas fa-chart-pie"></i> Дашборд</a></li>
<li class="nav-item"><a class="nav-link" data-page="findings" onclick="switchPage('findings')"><i class="fas fa-search"></i> Находки</a></li>
<li class="nav-item"><a class="nav-link" data-page="tasks" onclick="switchPage('tasks')"><i class="fas fa-tasks"></i> Задания</a></li>
<li class="nav-item"><a class="nav-link" data-page="scanners" onclick="switchPage('scanners')"><i class="fas fa-server"></i> Сканеры</a></li>
<li class="nav-item"><a class="nav-link" data-page="resources" onclick="switchPage('resources')"><i class="fas fa-folder"></i> Ресурсы</a></li>
<li class="nav-item"><a class="nav-link" data-page="access" onclick="switchPage('access')"><i class="fas fa-user-shield"></i> Управление доступом</a></li>
</ul>
<span class="text-muted small" id="update-time"></span>
</div>
</div>
</nav>

<div class="container-fluid py-4">

<!-- DASHBOARD -->
<div id="page-dashboard" class="page-content active">
<h2 class="mb-4"><i class="fas fa-chart-pie text-primary"></i> Дашборд системы</h2>
<div class="row g-3 mb-4" id="stats-grid">
<div class="col-md-2 col-sm-4"><div class="stat-card text-center"><div class="stat-icon text-primary"><i class="fas fa-file-alt"></i></div><div class="stat-value" id="total-findings">-</div><div class="stat-label">Находок</div></div></div>
<div class="col-md-2 col-sm-4"><div class="stat-card text-center"><div class="stat-icon text-success"><i class="fas fa-server"></i></div><div class="stat-value" id="active-scanners">-</div><div class="stat-label">Сканеров</div></div></div>
<div class="col-md-2 col-sm-4"><div class="stat-card text-center"><div class="stat-icon text-warning"><i class="fas fa-clock"></i></div><div class="stat-value" id="pending-tasks">-</div><div class="stat-label">В очереди</div></div></div>
<div class="col-md-2 col-sm-4"><div class="stat-card text-center"><div class="stat-icon text-success"><i class="fas fa-check-circle"></i></div><div class="stat-value" id="completed-tasks">-</div><div class="stat-label">Завершено</div></div></div>
<div class="col-md-2 col-sm-4"><div class="stat-card text-center"><div class="stat-icon text-danger"><i class="fas fa-exclamation-triangle"></i></div><div class="stat-value" id="failed-tasks">-</div><div class="stat-label">Провалено</div></div></div>
<div class="col-md-2 col-sm-4"><div class="stat-card text-center"><div class="stat-icon text-info"><i class="fas fa-folder-open"></i></div><div class="stat-value" id="total-files">-</div><div class="stat-label">Файлов</div></div></div>
</div>
<div class="row g-3 mb-4">
<div class="col-md-6"><div class="card"><div class="card-header"><i class="fas fa-chart-bar"></i> Находки по категориям</div><div class="card-body"><canvas id="categoryChart" height="250"></canvas></div></div></div>
<div class="col-md-6"><div class="card"><div class="card-header"><i class="fas fa-chart-doughnut"></i> Находки по сканерам</div><div class="card-body"><canvas id="scannerChart" height="250"></canvas></div></div></div>
</div>
<div class="card">
<div class="card-header d-flex justify-content-between align-items-center">
<span><i class="fas fa-history"></i> Последние находки</span>
<a href="#" onclick="switchPage('findings');return false;" class="btn btn-sm btn-outline-primary">Все находки →</a>
</div>
<div class="card-body p-0" id="recent-findings"><div class="text-center p-4 text-muted">Загрузка...</div></div>
</div>
</div>

<!-- FINDINGS -->
<div id="page-findings" class="page-content">
<h2 class="mb-4"><i class="fas fa-search text-primary"></i> Находки <span class="text-muted fs-6" id="findings-total"></span></h2>
<div class="filter-card">
<div class="row g-3 align-items-end">
<div class="col-md-3"><label class="form-label">Категория</label><select class="form-select" id="filter-category"><option value="">Все</option></select></div>
<div class="col-md-4"><label class="form-label">Поиск по файлу</label><input type="text" class="form-control" id="filter-file" placeholder="Часть пути..."></div>
<div class="col-md-2"><label class="form-label">Мин. доверие</label><select class="form-select" id="filter-confidence"><option value="">Любое</option><option value="0.9">90%</option><option value="0.7">70%</option><option value="0.5">50%</option></select></div>
<div class="col-md-3"><button class="btn btn-primary me-2" onclick="loadFindings()"><i class="fas fa-filter"></i> Применить</button><button class="btn btn-outline-secondary" onclick="resetFilters()"><i class="fas fa-undo"></i> Сброс</button></div>
</div>
</div>
<div class="table-wrapper" id="findings-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
<div class="d-flex justify-content-between align-items-center mt-3">
<div><select class="form-select form-select-sm" id="per-page" onchange="loadFindings()" style="width:auto;display:inline-block;"><option value="20">20</option><option value="50" selected>50</option><option value="100">100</option></select><span class="text-muted small ms-2">на страницу</span></div>
<nav><ul class="pagination mb-0" id="pagination"></ul></nav>
</div>
</div>

<!-- TASKS -->
<div id="page-tasks" class="page-content">
<h2 class="mb-4"><i class="fas fa-tasks text-primary"></i> Задания</h2>
<button class="btn btn-primary mb-3" onclick="showModal('create-task-modal')"><i class="fas fa-plus"></i> Создать задание</button>
<div class="filter-card">
<div class="row g-3 align-items-end">
<div class="col-md-3"><label class="form-label">Статус</label><select class="form-select" id="task-status" onchange="loadTasks()"><option value="">Все</option><option value="pending">⏳ Ожидает</option><option value="assigned">🔄 Назначено</option><option value="running">🔍 Сканируется</option><option value="completed">✅ Завершено</option><option value="failed">❌ Провалено</option></select></div>
</div>
</div>
<div class="table-wrapper" id="tasks-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
</div>

<!-- SCANNERS -->
<div id="page-scanners" class="page-content">
<h2 class="mb-4"><i class="fas fa-server text-primary"></i> Сканеры</h2>
<div class="table-wrapper" id="scanners-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
</div>

<!-- RESOURCES -->
<div id="page-resources" class="page-content">
<h2 class="mb-4"><i class="fas fa-folder text-primary"></i> Ресурсы</h2>
<button class="btn btn-primary mb-3" onclick="showModal('create-resource-modal')"><i class="fas fa-plus"></i> Добавить ресурс</button>
<div class="table-wrapper" id="resources-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
</div>

<!-- ACCESS -->
<div id="page-access" class="page-content">
<h2 class="mb-4"><i class="fas fa-user-shield text-primary"></i> Управление доступом</h2>
<div class="row g-3 mb-4">
<div class="col-md-3"><div class="stat-card text-center"><div class="stat-icon text-danger"><i class="fas fa-exclamation-triangle"></i></div><div class="stat-value" id="acc-critical">-</div><div class="stat-label">Критичные алерты</div></div></div>
<div class="col-md-3"><div class="stat-card text-center"><div class="stat-icon text-warning"><i class="fas fa-exclamation-circle"></i></div><div class="stat-value" id="acc-warning">-</div><div class="stat-label">Предупреждения</div></div></div>
<div class="col-md-3"><div class="stat-card text-center"><div class="stat-icon text-info"><i class="fas fa-bell"></i></div><div class="stat-value" id="acc-open">-</div><div class="stat-label">Открытых алертов</div></div></div>
<div class="col-md-3"><div class="stat-card text-center"><div class="stat-icon text-success"><i class="fas fa-folder-open"></i></div><div class="stat-value" id="acc-resources">-</div><div class="stat-label">Ресурсов</div></div></div>
</div>
<ul class="nav nav-tabs mb-3">
<li class="nav-item"><a class="nav-link active" id="tab-resources" href="#" onclick="accessTab('resources');return false;"><i class="fas fa-list"></i> Ресурсы</a></li>
<li class="nav-item"><a class="nav-link" id="tab-alerts" href="#" onclick="accessTab('alerts');return false;"><i class="fas fa-bell"></i> Алерты</a></li>
</ul>
<div id="access-view-resources">
<div class="table-wrapper" id="access-resources-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
</div>
<div id="access-view-alerts" style="display:none;">
<div class="filter-card">
<div class="row g-3 align-items-end">
<div class="col-md-3"><label class="form-label">Важность</label><select class="form-select" id="filter-severity" onchange="loadAccessAlerts()"><option value="">Все</option><option value="critical">Критичные</option><option value="warning">Предупреждения</option><option value="info">Информация</option></select></div>
<div class="col-md-3"><label class="form-label">Статус</label><select class="form-select" id="filter-alert-status" onchange="loadAccessAlerts()"><option value="">Все</option><option value="open">Открыт</option><option value="acknowledged">Подтверждён</option><option value="resolved">Решён</option><option value="ignored">Игнорирован</option></select></div>
<div class="col-md-3"><label class="form-label">Тип</label><select class="form-select" id="filter-alert-type" onchange="loadAccessAlerts()"><option value="">Все</option></select></div>
<div class="col-md-3"><button class="btn btn-outline-secondary" onclick="resetAlertFilters()"><i class="fas fa-undo"></i> Сброс</button></div>
</div>
</div>
<div class="table-wrapper" id="access-alerts-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
</div>
</div>

</div>

<!-- MODAL: Create Task -->
<div class="modal" id="create-task-modal">
<div class="modal-content">
<h4 class="mb-3"><i class="fas fa-plus-circle"></i> Создание задания</h4>
<div class="mb-3"><label class="form-label">Путь к папке *</label><input type="text" class="form-control" id="task-path" placeholder="E:\\data или /home/user/data"><small class="text-muted">Абсолютный путь</small></div>
<div class="mb-3"><label class="form-label">Расширения</label><input type="text" class="form-control" id="task-extensions" value="txt,pdf,docx,xlsx,png,jpg,jpeg"></div>
<div class="mb-3"><label class="form-label">Макс. размер (MB)</label><input type="number" class="form-control" id="task-max-size" value="50"></div>
<div class="mb-3 form-check"><input type="checkbox" class="form-check-input" id="task-recursive" checked><label class="form-check-label">Рекурсивно</label></div>
<div class="d-flex gap-2"><button class="btn btn-primary flex-grow-1" onclick="createTask()"><i class="fas fa-check"></i> Создать</button><button class="btn btn-secondary" onclick="closeModal('create-task-modal')">Отмена</button></div>
</div>
</div>

<!-- MODAL: Create Resource -->
<div class="modal" id="create-resource-modal">
<div class="modal-content">
<h4 class="mb-3"><i class="fas fa-plus-circle"></i> Добавить ресурс</h4>
<div class="mb-3"><label class="form-label">Тип</label><select class="form-select" id="resource-type"><option value="FILESYSTEM">Файловая система</option><option value="S3">S3</option><option value="MINIO">MinIO</option></select></div>
<div class="mb-3"><label class="form-label">Путь</label><div class="input-group"><input type="text" class="form-control" id="resource-path" placeholder="E:\\data"><button type="button" class="btn btn-outline-secondary" onclick="pickFolder('resource-path')" title="Выбрать папку на диске"><i class="fas fa-folder-open"></i></button></div></div>
<div class="mb-3"><label class="form-label">Расширения</label><input type="text" class="form-control" id="resource-extensions" value="txt,pdf,docx,xlsx,png,jpg,jpeg"></div>
<div class="mb-3 form-check"><input type="checkbox" class="form-check-input" id="resource-enabled" checked><label class="form-check-label">Включён</label></div>
<div class="d-flex gap-2"><button class="btn btn-primary flex-grow-1" onclick="createResource()"><i class="fas fa-check"></i> Добавить</button><button class="btn btn-secondary" onclick="closeModal('create-resource-modal')">Отмена</button></div>
</div>
</div>

<!-- MODAL: Resource Permissions -->
<div class="modal" id="permissions-modal">
<div class="modal-content" style="max-width:900px;">
<h4 class="mb-3"><i class="fas fa-user-lock"></i> Права доступа <span id="perm-resource-label" class="text-muted fs-6"></span></h4>
<div class="filter-card">
<div class="row g-3 align-items-end">
<div class="col-md-4"><label class="form-label">Поиск субъекта</label><input type="text" class="form-control" id="filter-principal" placeholder="Часть имени..."></div>
<div class="col-md-3"><label class="form-label">Тип прав</label><select class="form-select" id="filter-perm-type"><option value="">Все</option><option value="read">read</option><option value="write">write</option><option value="modify">modify</option><option value="delete">delete</option><option value="full_control">full_control</option></select></div>
<div class="col-md-3"><label class="form-label">Тип субъекта</label><select class="form-select" id="filter-principal-type"><option value="">Все</option><option value="user">user</option><option value="group">group</option><option value="local_user">local_user</option><option value="system">system</option></select></div>
<div class="col-md-2"><button class="btn btn-primary" onclick="loadAccessEntries()"><i class="fas fa-filter"></i> Применить</button></div>
</div>
</div>
<div class="table-wrapper" id="access-entries-table"><div class="text-center p-4 text-muted">Загрузка...</div></div>
<div class="d-flex justify-content-between align-items-center mt-3">
<div><span class="text-muted small" id="access-entries-total"></span></div>
<nav><ul class="pagination mb-0" id="access-entries-pagination"></ul></nav>
</div>
<div class="d-flex gap-2 mt-3"><button class="btn btn-secondary" onclick="closeModal('permissions-modal')">Закрыть</button></div>
</div>
</div>

<script>
// ===== ГЛОБАЛЬНЫЕ =====
var currentPage = 'dashboard';
var charts = {};
var findingsPage = 0, findingsTotal = 0, perPage = 50;

// ===== НАВИГАЦИЯ =====
function switchPage(page) {
    currentPage = page;
    // Скрываем все страницы
    var pages = document.querySelectorAll('.page-content');
    for (var i = 0; i < pages.length; i++) {
        pages[i].classList.remove('active');
    }
    // Показываем нужную
    var target = document.getElementById('page-' + page);
    if (target) target.classList.add('active');
    
    // Обновляем активную ссылку
    var links = document.querySelectorAll('.nav-link');
    for (var i = 0; i < links.length; i++) {
        links[i].classList.remove('active');
    }
    var activeLink = document.querySelector('.nav-link[data-page="' + page + '"]');
    if (activeLink) activeLink.classList.add('active');
    
    // Загружаем данные
    if (page === 'dashboard') loadDashboard();
    else if (page === 'findings') { loadCategories(); loadFindings(); }
    else if (page === 'tasks') loadTasks();
    else if (page === 'scanners') loadScanners();
    else if (page === 'resources') loadResources();
    else if (page === 'access') loadAccess();
}

function showModal(id) {
    var el = document.getElementById(id);
    if (el) el.classList.add('show');
}

function closeModal(id) {
    var el = document.getElementById(id);
    if (el) el.classList.remove('show');
}

// Закрытие модалки по клику вне
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('show');
    }
});

function updateTime() {
    var now = new Date();
    var time = now.toLocaleTimeString('ru-RU');
    var el = document.getElementById('update-time');
    if (el) el.textContent = '🔄 ' + time;
}
updateTime();

// ===== DASHBOARD =====
async function loadDashboard() {
    try {
        var r = await fetch('/api/stats');
        var s = await r.json();
        
        document.getElementById('total-findings').textContent = s.total_findings || 0;
        document.getElementById('active-scanners').textContent = s.active_scanners || 0;
        document.getElementById('pending-tasks').textContent = s.pending_tasks || 0;
        document.getElementById('completed-tasks').textContent = s.completed_tasks || 0;
        document.getElementById('failed-tasks').textContent = s.failed_tasks || 0;
        document.getElementById('total-files').textContent = s.total_files_scanned || 0;
        
        updateCharts(s);
        await loadRecentFindings();
        updateTime();
    } catch(e) {
        console.error('Dashboard error:', e);
    }
}

function updateCharts(s) {
    var colors = ['#4e79a7','#f28e2b','#e15759','#59a14f','#edc948','#b07aa1'];
    
    if (charts.category) charts.category.destroy();
    var ctx1 = document.getElementById('categoryChart');
    if (ctx1) {
        var cats = Object.keys(s.findings_by_category || {});
        var vals = Object.values(s.findings_by_category || {});
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
    
    if (charts.scanner) charts.scanner.destroy();
    var ctx2 = document.getElementById('scannerChart');
    if (ctx2) {
        var scs = Object.keys(s.findings_by_scanner || {});
        var scv = Object.values(s.findings_by_scanner || {});
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

async function loadRecentFindings() {
    try {
        var r = await fetch('/api/findings?limit=10');
        var f = await r.json();
        var container = document.getElementById('recent-findings');
        if (!f.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>';
            return;
        }
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>';
        for (var i = 0; i < f.length; i++) {
            var item = f[i];
            var conf = (item.confidence * 100).toFixed(0);
            var cls = item.confidence > 0.8 ? 'high' : item.confidence > 0.5 ? 'medium' : 'low';
            var fname = (item.file_path || '').split('\\\\').pop() || item.file_path || 'unknown';
            html += '<tr><td><span class="file-path" title="' + item.file_path + '">' + fname + '</span></td><td><span class="badge bg-info">' + item.category + '</span></td><td>' + item.classifier_name + '</td><td class="confidence-' + cls + '">' + conf + '%</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
    } catch(e) {
        console.error('Recent findings error:', e);
    }
}

// ===== FINDINGS =====
async function loadCategories() {
    try {
        var r = await fetch('/api/categories');
        var cats = await r.json();
        var sel = document.getElementById('filter-category');
        if (!sel) return;
        sel.innerHTML = '<option value="">Все</option>';
        for (var i = 0; i < cats.length; i++) {
            var o = document.createElement('option');
            o.value = cats[i];
            o.textContent = cats[i];
            sel.appendChild(o);
        }
    } catch(e) { console.error(e); }
}

async function loadFindings() {
    var cat = document.getElementById('filter-category')?.value || '';
    var fp = document.getElementById('filter-file')?.value || '';
    var conf = document.getElementById('filter-confidence')?.value || '';
    var perPageEl = document.getElementById('per-page');
    perPage = perPageEl ? parseInt(perPageEl.value) || 50 : 50;
    
    var url = '/api/findings?limit=' + perPage + '&offset=' + (findingsPage * perPage);
    if (cat) url += '&category=' + encodeURIComponent(cat);
    if (fp) url += '&file_path=' + encodeURIComponent(fp);
    if (conf) url += '&min_confidence=' + conf;
    
    try {
        var r = await fetch(url);
        var f = await r.json();
        
        var cr = await fetch('/api/findings/count?' + new URLSearchParams({category: cat, file_path: fp}));
        var cd = await cr.json();
        findingsTotal = cd.count || 0;
        
        var container = document.getElementById('findings-table');
        if (!f.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>';
            return;
        }
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>#</th><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>';
        for (var i = 0; i < f.length; i++) {
            var item = f[i];
            var confPct = (item.confidence * 100).toFixed(0);
            var cls = item.confidence > 0.8 ? 'high' : item.confidence > 0.5 ? 'medium' : 'low';
            var fname = (item.file_path || '').split('\\\\').pop() || item.file_path || 'unknown';
            html += '<tr onclick="showFindingDetail(' + item.id + ')"><td>' + (findingsPage * perPage + i + 1) + '</td><td><span class="file-path" title="' + item.file_path + '">' + fname + '</span></td><td><span class="badge bg-info">' + item.category + '</span></td><td>' + item.classifier_name + '</td><td class="confidence-' + cls + '">' + confPct + '%</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
        
        var totalPages = Math.ceil(findingsTotal / perPage);
        var pag = document.getElementById('pagination');
        if (totalPages <= 1) { pag.innerHTML = ''; return; }
        var ph = '<li class="page-item ' + (findingsPage === 0 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + (findingsPage - 1) + ')">«</a></li>';
        var start = Math.max(0, findingsPage - 2);
        var end = Math.min(totalPages - 1, findingsPage + 2);
        if (start > 0) {
            ph += '<li class="page-item"><a class="page-link" href="#" onclick="goToPage(0)">1</a></li>';
            if (start > 1) ph += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
        for (var i = start; i <= end; i++) {
            ph += '<li class="page-item ' + (i === findingsPage ? 'active' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + i + ')">' + (i + 1) + '</a></li>';
        }
        if (end < totalPages - 1) {
            if (end < totalPages - 2) ph += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            ph += '<li class="page-item"><a class="page-link" href="#" onclick="goToPage(' + (totalPages - 1) + ')">' + totalPages + '</a></li>';
        }
        ph += '<li class="page-item ' + (findingsPage === totalPages - 1 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + (findingsPage + 1) + ')">»</a></li>';
        pag.innerHTML = ph;
        
        var totalEl = document.getElementById('findings-total');
        if (totalEl) totalEl.textContent = '(всего: ' + findingsTotal + ')';
        updateTime();
    } catch(e) {
        console.error('Findings error:', e);
    }
}

function goToPage(page) {
    var totalPages = Math.ceil(findingsTotal / perPage);
    if (page < 0 || page >= totalPages) return;
    findingsPage = page;
    loadFindings();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetFilters() {
    var cat = document.getElementById('filter-category');
    var fp = document.getElementById('filter-file');
    var conf = document.getElementById('filter-confidence');
    if (cat) cat.value = '';
    if (fp) fp.value = '';
    if (conf) conf.value = '';
    findingsPage = 0;
    loadFindings();
}

async function showFindingDetail(id) {
    try {
        var r = await fetch('/api/findings/' + id);
        var d = await r.json();
        alert('📄 Находка #' + d.id + '\n\nФайл: ' + d.file_path + '\nКатегория: ' + d.category + '\nПодкатегория: ' + (d.subcategory || '-') + '\nЗначение: ' + (d.value || '-') + '\nКлассификатор: ' + d.classifier_name + '\nДоверие: ' + (d.confidence * 100).toFixed(0) + '%');
    } catch(e) { console.error(e); }
}

// ===== TASKS =====
async function createTask() {
    var path = document.getElementById('task-path')?.value?.trim();
    if (!path) { alert('⚠️ Укажите путь к папке'); return; }
    var data = {
        resource_path: path,
        resource_type: 'FILESYSTEM',
        extensions: document.getElementById('task-extensions')?.value?.trim() || 'txt,pdf,docx,xlsx,png,jpg,jpeg',
        max_file_size_mb: parseInt(document.getElementById('task-max-size')?.value) || 50,
        recursive: document.getElementById('task-recursive')?.checked || true
    };
    try {
        var r = await fetch('/api/tasks/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var res = await r.json();
        if (res.success) {
            alert('✅ Задание создано!\nID: ' + res.task_id + '\nПуть: ' + res.resource_path);
            closeModal('create-task-modal');
            loadTasks();
        } else {
            alert('❌ Ошибка: ' + (res.detail || 'Неизвестная ошибка'));
        }
    } catch(e) { alert('❌ Ошибка: ' + e.message); }
}

async function loadTasks() {
    var status = document.getElementById('task-status')?.value || '';
    var url = '/api/tasks?limit=50';
    if (status) url += '&status=' + encodeURIComponent(status);
    try {
        var r = await fetch(url);
        var tasks = await r.json();
        var container = document.getElementById('tasks-table');
        if (!tasks.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет заданий</div>';
            return;
        }
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Статус</th><th>Файлов</th><th>Находок</th><th>Прогресс</th><th>Создано</th></tr></thead><tbody>';
        for (var i = 0; i < tasks.length; i++) {
            var t = tasks[i];
            var badges = { 'pending':'secondary','assigned':'primary','running':'warning','completed':'success','failed':'danger' };
            var badge = badges[t.status] || 'secondary';
            var icons = { 'pending':'⏳','assigned':'🔄','running':'🔍','completed':'✅','failed':'❌' };
            var progress = t.progress_percent || 0;
            var created = t.created_at ? new Date(t.created_at).toLocaleString('ru-RU') : '-';
            html += '<tr onclick="showTaskDetail(' + t.id + ')"><td>#' + t.id + '</td><td><span class="badge bg-' + badge + '">' + (icons[t.status] || '') + ' ' + t.status + '</span></td><td>' + (t.files_scanned || 0) + '/' + (t.files_total || 0) + '</td><td>' + (t.findings_count || 0) + '</td><td><div class="progress" style="height:8px;width:100px;"><div class="progress-bar" style="width:' + progress + '%"></div></div> ' + progress + '%</td><td>' + created + '</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
        updateTime();
    } catch(e) { console.error(e); }
}

async function showTaskDetail(id) {
    try {
        var r = await fetch('/api/tasks/' + id);
        var d = await r.json();
        var t = d.task;
        var msg = '📋 Задание #' + t.id + '\n\nСтатус: ' + t.status + '\nФайлов: ' + (t.files_scanned || 0) + '/' + (t.files_total || 0) + '\nНаходок: ' + (t.findings_count || 0) + '\nСоздано: ' + (t.created_at ? new Date(t.created_at).toLocaleString('ru-RU') : '-') + '\nЗавершено: ' + (t.completed_at ? new Date(t.completed_at).toLocaleString('ru-RU') : '-');
        if (d.findings && d.findings.length) {
            msg += '\n\nНаходки:';
            var limit = Math.min(5, d.findings.length);
            for (var i = 0; i < limit; i++) {
                var f = d.findings[i];
                var fname = (f.file_path || '').split('\\\\').pop() || f.file_path || 'unknown';
                msg += '\n- ' + f.category + ': ' + fname + ' (' + (f.confidence * 100).toFixed(0) + '%)';
            }
            if (d.findings.length > 5) msg += '\n... и еще ' + (d.findings.length - 5);
        }
        alert(msg);
    } catch(e) { console.error(e); }
}

// ===== SCANNERS =====
async function loadScanners() {
    try {
        var r = await fetch('/api/scanners');
        var scanners = await r.json();
        var container = document.getElementById('scanners-table');
        if (!scanners.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет сканеров</div>';
            return;
        }
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Имя</th><th>Статус</th><th>Heartbeat</th><th>Файлов</th><th>Находок</th></tr></thead><tbody>';
        for (var i = 0; i < scanners.length; i++) {
            var s = scanners[i];
            var online = s.status === 'ACTIVE' || s.status === 'active';
            var badge = online ? 'success' : 'secondary';
            var statusText = online ? '🟢 Активен' : '⚪ Оффлайн';
            var hb = s.last_heartbeat ? new Date(s.last_heartbeat).toLocaleString('ru-RU') : '-';
            html += '<tr><td>#' + s.id + '</td><td>' + s.name + '</td><td><span class="badge bg-' + badge + '">' + statusText + '</span></td><td>' + hb + '</td><td>' + (s.total_files_scanned || 0) + '</td><td>' + (s.total_findings || 0) + '</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
        updateTime();
    } catch(e) { console.error(e); }
}

// ===== RESOURCES =====
async function pickFolder(inputId) {
    try {
        var r = await fetch('/api/folders/pick', { method: 'POST' });
        var d = await r.json();
        if (d.success && d.path) {
            document.getElementById(inputId).value = d.path;
        }
    } catch(e) { alert('❌ Ошибка выбора папки: ' + e.message); }
}

async function createResource() {
    var path = document.getElementById('resource-path')?.value?.trim();
    if (!path) { alert('⚠️ Укажите путь'); return; }
    var data = {
        type: document.getElementById('resource-type')?.value || 'FILESYSTEM',
        path: path,
        enabled: document.getElementById('resource-enabled')?.checked || true,
        extensions: document.getElementById('resource-extensions')?.value?.trim() || 'txt,pdf,docx,xlsx,png,jpg,jpeg'
    };
    try {
        var r = await fetch('/api/resources/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var res = await r.json();
        if (res.success) {
            alert('✅ Ресурс добавлен!\nID: ' + res.resource_id);
            closeModal('create-resource-modal');
            loadResources();
        } else {
            alert('❌ Ошибка: ' + (res.detail || 'Неизвестная ошибка'));
        }
    } catch(e) { alert('❌ Ошибка: ' + e.message); }
}

async function loadResources() {
    try {
        var r = await fetch('/api/resources');
        var resources = await r.json();
        var container = document.getElementById('resources-table');
        if (!resources.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет ресурсов</div>';
            return;
        }
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Тип</th><th>Путь</th><th>Статус</th><th>Создан</th></tr></thead><tbody>';
        for (var i = 0; i < resources.length; i++) {
            var r = resources[i];
            var status = r.enabled ? '✅ Включён' : '❌ Отключён';
            var created = r.created_at ? new Date(r.created_at).toLocaleString('ru-RU') : '-';
            html += '<tr><td>#' + r.id + '</td><td>' + r.type + '</td><td><code>' + r.path + '</code></td><td>' + status + '</td><td>' + created + '</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
        updateTime();
    } catch(e) { console.error(e); }
}

// ===== УПРАВЛЕНИЕ ДОСТУПОМ =====
var accessCurrentTab = 'resources';
var accessCurrentResource = null;
var accessResourcePaths = {};
var accessEntriesPage = 0, accessEntriesTotal = 0, accessEntriesPerPage = 50;

function accessTab(tab) {
    accessCurrentTab = tab;
    var resTab = document.getElementById('tab-resources');
    var alTab = document.getElementById('tab-alerts');
    var resView = document.getElementById('access-view-resources');
    var alView = document.getElementById('access-view-alerts');
    if (tab === 'alerts') {
        resTab.classList.remove('active');
        alTab.classList.add('active');
        resView.style.display = 'none';
        alView.style.display = '';
        loadAlertTypes();
        loadAccessAlerts();
    } else {
        alTab.classList.remove('active');
        resTab.classList.add('active');
        alView.style.display = 'none';
        resView.style.display = '';
        loadAccessResources();
    }
}

async function loadAccess() {
    loadAccessStats();
    if (accessCurrentTab === 'alerts') { loadAlertTypes(); loadAccessAlerts(); }
    else loadAccessResources();
    updateTime();
}

async function loadAccessStats() {
    try {
        var r = await fetch('/api/access/alerts/stats');
        var s = await r.json();
        document.getElementById('acc-critical').textContent = s.by_severity?.critical || 0;
        document.getElementById('acc-warning').textContent = s.by_severity?.warning || 0;
        document.getElementById('acc-open').textContent = s.by_status?.open || 0;
    } catch(e) { console.error('Access stats error:', e); }
}

async function loadAccessResources() {
    try {
        var r = await fetch('/api/access/resources');
        var d = await r.json();
        document.getElementById('acc-resources').textContent = d.total || 0;
        var container = document.getElementById('access-resources-table');
        if (!d.resources.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет ресурсов</div>';
            return;
        }
        accessResourcePaths = {};
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Путь</th><th>Владелец</th><th>Чувствительность</th><th>Источник</th><th>Синхронизировано</th><th>Прав</th><th>Алертов</th><th></th></tr></thead><tbody>';
        for (var i = 0; i < d.resources.length; i++) {
            var rw = d.resources[i];
            accessResourcePaths[rw.id] = rw.path;
            var sensitive = rw.is_sensitive ? '<span class="badge bg-danger">sensitive</span>' : '<span class="badge bg-secondary">обычный</span>';
            var level = rw.classification_level || 'public';
            var lastSync = rw.permission_last_synced ? new Date(rw.permission_last_synced).toLocaleString('ru-RU') : '-';
            var alertsBadge = rw.open_alerts_count > 0 ? '<span class="badge bg-danger">' + rw.open_alerts_count + ' открыто</span>' : (rw.alerts_count > 0 ? '<span class="badge bg-secondary">' + rw.alerts_count + '</span>' : '<span class="badge bg-light text-muted">0</span>');
            html += '<tr><td>#' + rw.id + '</td><td><code>' + rw.path + '</code></td><td>' + (rw.owner || '-') + '</td><td>' + sensitive + ' <span class="badge bg-info text-dark">' + level + '</span></td><td>' + (rw.permission_source || '-') + '</td><td class="text-muted small">' + lastSync + '</td><td><span class="badge bg-primary">' + (rw.entries_count || 0) + '</span></td><td>' + alertsBadge + '</td><td><button class="btn btn-sm btn-outline-primary" onclick="openPermissions(' + rw.id + ')"><i class="fas fa-user-lock"></i> Права</button></td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
        updateTime();
    } catch(e) { console.error('Access resources error:', e); }
}

function openPermissions(resourceId) {
    accessCurrentResource = resourceId;
    accessEntriesPage = 0;
    document.getElementById('filter-principal').value = '';
    document.getElementById('filter-perm-type').value = '';
    document.getElementById('filter-principal-type').value = '';
    document.getElementById('perm-resource-label').textContent = accessResourcePaths[resourceId] || ('#' + resourceId);
    showModal('permissions-modal');
    loadAccessEntries();
}

async function loadAccessEntries() {
    var principal = document.getElementById('filter-principal').value.trim();
    var permType = document.getElementById('filter-perm-type').value;
    var principalType = document.getElementById('filter-principal-type').value;
    var url = '/api/access/resources/' + accessCurrentResource + '/entries?limit=' + accessEntriesPerPage + '&offset=' + (accessEntriesPage * accessEntriesPerPage);
    if (principal) url += '&principal=' + encodeURIComponent(principal);
    if (permType) url += '&permission_type=' + encodeURIComponent(permType);
    if (principalType) url += '&principal_type=' + encodeURIComponent(principalType);
    try {
        var r = await fetch(url);
        var d = await r.json();
        accessEntriesTotal = d.total || 0;
        document.getElementById('access-entries-total').textContent = 'Всего записей: ' + accessEntriesTotal;
        var container = document.getElementById('access-entries-table');
        if (!d.entries.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет записей прав. Запустите синхронизацию прав на Manager (POST /api/permissions/sync).</div>';
        } else {
            var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>Субъект</th><th>Тип</th><th>Право</th><th>Источник</th><th>Наследование</th><th>Проверено</th></tr></thead><tbody>';
            for (var i = 0; i < d.entries.length; i++) {
                var e = d.entries[i];
                var permBadges = { 'full_control':'danger','modify':'warning','write':'warning','delete':'danger','read':'success' };
                var pcls = permBadges[e.permission_type] || 'secondary';
                var inherited = e.is_inherited ? ('<span class="badge bg-info text-dark">наследуется</span>' + (e.inherited_from ? ' <span class="text-muted small">из ' + e.inherited_from + '</span>' : '')) : '<span class="badge bg-light text-muted">прямые</span>';
                var verified = e.last_verified_at ? new Date(e.last_verified_at).toLocaleString('ru-RU') : '-';
                html += '<tr><td>' + (e.principal_name || '-') + '</td><td><span class="badge bg-secondary">' + (e.principal_type || '-') + '</span></td><td><span class="badge bg-' + pcls + '">' + e.permission_type + '</span></td><td>' + (e.permission_source || '-') + '</td><td>' + inherited + '</td><td class="text-muted small">' + verified + '</td></tr>';
            }
            html += '</tbody></table></div>';
            container.innerHTML = html;
        }
        var totalPages = Math.ceil(accessEntriesTotal / accessEntriesPerPage);
        var pag = document.getElementById('access-entries-pagination');
        if (totalPages <= 1) { pag.innerHTML = ''; return; }
        var ph = '<li class="page-item ' + (accessEntriesPage === 0 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="accessEntriesGo(' + (accessEntriesPage - 1) + ')">«</a></li>';
        for (var p = 0; p < totalPages; p++) {
            if (p === accessEntriesPage) ph += '<li class="page-item active"><a class="page-link" href="#">' + (p + 1) + '</a></li>';
            else ph += '<li class="page-item"><a class="page-link" href="#" onclick="accessEntriesGo(' + p + ')">' + (p + 1) + '</a></li>';
        }
        ph += '<li class="page-item ' + (accessEntriesPage >= totalPages - 1 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="accessEntriesGo(' + (accessEntriesPage + 1) + ')">»</a></li>';
        pag.innerHTML = ph;
    } catch(e) { console.error('Access entries error:', e); }
}

function accessEntriesGo(page) {
    var totalPages = Math.ceil(accessEntriesTotal / accessEntriesPerPage);
    if (page < 0 || page >= totalPages) return;
    accessEntriesPage = page;
    loadAccessEntries();
}

async function loadAlertTypes() {
    try {
        var r = await fetch('/api/access/alerts/stats');
        var s = await r.json();
        var sel = document.getElementById('filter-alert-type');
        if (!sel) return;
        var current = sel.value;
        sel.innerHTML = '<option value="">Все</option>';
        var keys = Object.keys(s.by_type || {});
        for (var i = 0; i < keys.length; i++) {
            var o = document.createElement('option');
            o.value = keys[i];
            o.textContent = keys[i] + ' (' + s.by_type[keys[i]] + ')';
            if (keys[i] === current) o.selected = true;
            sel.appendChild(o);
        }
    } catch(e) { console.error(e); }
}

async function loadAccessAlerts() {
    var severity = document.getElementById('filter-severity').value;
    var status = document.getElementById('filter-alert-status').value;
    var alertType = document.getElementById('filter-alert-type').value;
    var url = '/api/access/alerts?limit=100';
    if (severity) url += '&severity=' + encodeURIComponent(severity);
    if (status) url += '&status=' + encodeURIComponent(status);
    if (alertType) url += '&alert_type=' + encodeURIComponent(alertType);
    try {
        var r = await fetch(url);
        var d = await r.json();
        var container = document.getElementById('access-alerts-table');
        if (!d.alerts.length) {
            container.innerHTML = '<div class="text-center p-4 text-muted">Нет алертов</div>';
            return;
        }
        var sevIcons = { 'critical':['danger','exclamation-triangle'], 'warning':['warning','exclamation-circle'], 'info':['info','info-circle'] };
        var statusBadges = { 'open':'danger','acknowledged':'warning','resolved':'success','ignored':'secondary' };
        var html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>ID</th><th>Важность</th><th>Тип</th><th>Ресурс</th><th>Субъект</th><th>Описание</th><th>Статус</th><th>Создан</th><th>Действия</th></tr></thead><tbody>';
        for (var i = 0; i < d.alerts.length; i++) {
            var a = d.alerts[i];
            var sev = sevIcons[a.severity] || ['secondary','circle'];
            var created = a.created_at ? new Date(a.created_at).toLocaleString('ru-RU') : '-';
            var actions = '';
            if (a.status === 'open') actions += '<button class="btn btn-sm btn-outline-warning me-1" onclick="updateAlertStatus(' + a.id + ',\'acknowledged\')">Подтвердить</button>';
            if (a.status !== 'resolved') actions += '<button class="btn btn-sm btn-outline-success me-1" onclick="updateAlertStatus(' + a.id + ',\'resolved\')">Решить</button>';
            if (a.status !== 'ignored') actions += '<button class="btn btn-sm btn-outline-secondary" onclick="updateAlertStatus(' + a.id + ',\'ignored\')">Игнор</button>';
            html += '<tr><td>#' + a.id + '</td><td><span class="badge bg-' + sev[0] + '"><i class="fas fa-' + sev[1] + '"></i> ' + a.severity + '</span></td><td><span class="badge bg-secondary">' + a.alert_type + '</span></td><td class="small"><code>' + (a.resource_path || ('#' + (a.resource_id || '-'))) + '</code></td><td>' + (a.principal_name || '-') + '</td><td class="small">' + (a.description || '') + '</td><td><span class="badge bg-' + (statusBadges[a.status] || 'secondary') + '">' + a.status + '</span></td><td class="text-muted small">' + created + '</td><td>' + (actions || '<span class="text-muted small">—</span>') + '</td></tr>';
        }
        html += '</tbody></table></div>';
        container.innerHTML = html;
        updateTime();
    } catch(e) { console.error('Access alerts error:', e); }
}

async function updateAlertStatus(id, status) {
    try {
        var r = await fetch('/api/access/alerts/' + id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: status })
        });
        var res = await r.json();
        if (res.status === 'updated') {
            loadAccessAlerts();
            loadAccessStats();
        } else {
            alert('Ошибка: ' + (res.detail || 'Неизвестная ошибка'));
        }
    } catch(e) { alert('Ошибка: ' + e.message); }
}

function resetAlertFilters() {
    document.getElementById('filter-severity').value = '';
    document.getElementById('filter-alert-status').value = '';
    document.getElementById('filter-alert-type').value = '';
    loadAccessAlerts();
}

// ===== АВТООБНОВЛЕНИЕ =====
setInterval(function() {
    if (currentPage === 'dashboard') loadDashboard();
    else if (currentPage === 'findings') loadFindings();
    else if (currentPage === 'tasks') loadTasks();
    else if (currentPage === 'scanners') loadScanners();
    else if (currentPage === 'resources') loadResources();
    else if (currentPage === 'access') loadAccess();
}, 30000);

// ===== ИНИЦИАЛИЗАЦИЯ =====
document.addEventListener('DOMContentLoaded', function() {
    // Убеждаемся, что дашборд активен
    switchPage('dashboard');
});
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.get("/findings", response_class=HTMLResponse)
async def findings_page():
    return HTML


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page():
    return HTML


@app.get("/scanners", response_class=HTMLResponse)
async def scanners_page():
    return HTML


@app.get("/resources", response_class=HTMLResponse)
async def resources_page():
    return HTML


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     🚀 DCAP Distributed v3.0 - WebUI (Full)            ║
    ║     http://localhost:8001                              ║
    ║     Разделы: Дашборд | Находки | Задания | Сканеры | Ресурсы ║
    ║     Для остановки: Ctrl+C                             ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "webui.main:app",
        host=WEBUI_HOST,
        port=WEBUI_PORT,
        reload=DEBUG,
        log_level="info"
    )