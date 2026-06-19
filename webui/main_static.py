from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import sqlite3
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

app = FastAPI(title="DCAP WebUI", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Путь к БД
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manager", "src", "db", "dcap.db")
print(f"🔍 Путь к БД: {DB_PATH}")
print(f"✅ БД существует: {os.path.exists(DB_PATH)}")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Чтобы получать доступ по имени колонки
    return conn

# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ===
def get_column_names(cursor, table_name):
    """Получить список колонок таблицы"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

# === API ЭНДПОИНТЫ ===

@app.get("/api/stats")
async def get_stats():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        total_findings = cursor.execute("SELECT COUNT(*) FROM findings").fetchone()[0] or 0
        active_scanners = cursor.execute(
            "SELECT COUNT(*) FROM scanners WHERE last_heartbeat > datetime('now', '-60 seconds')"
        ).fetchone()[0] or 0
        pending_tasks = cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'PENDING'").fetchone()[0] or 0
        completed_tasks = cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'COMPLETED'").fetchone()[0] or 0
        failed_tasks = cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'FAILED'").fetchone()[0] or 0
        total_files = cursor.execute("SELECT COALESCE(SUM(files_scanned), 0) FROM scan_tasks").fetchone()[0] or 0
        
        findings_by_category = {}
        rows = cursor.execute("SELECT category, COUNT(*) FROM findings GROUP BY category").fetchall()
        for row in rows:
            findings_by_category[row[0]] = row[1]
        
        findings_by_scanner = {}
        rows = cursor.execute(
            "SELECT scanners.name, COUNT(findings.id) FROM findings LEFT JOIN scanners ON scanners.id = findings.scanner_id GROUP BY scanners.name"
        ).fetchall()
        for row in rows:
            if row[0]:
                findings_by_scanner[row[0]] = row[1]
        
        conn.close()
        
        return {
            "total_findings": total_findings,
            "active_scanners": active_scanners,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "total_files_scanned": total_files,
            "findings_by_category": findings_by_category,
            "findings_by_scanner": findings_by_scanner
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/api/findings")
async def get_findings(limit: int = 50, offset: int = 0, category: str = None, file_path: str = None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Определяем название колонки с путём
        columns = get_column_names(cursor, "findings")
        path_column = "file_path" if "file_path" in columns else "path" if "path" in columns else "filepath"
        print(f"📁 Найдена колонка пути: {path_column}")
        
        query = f"SELECT * FROM findings"
        params = []
        conditions = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if file_path:
            conditions.append(f"{path_column} LIKE ?")
            params.append(f"%{file_path}%")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY id DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        findings = []
        for row in rows:
            # Преобразуем Row в словарь
            row_dict = dict(row)
            findings.append({
                "id": row_dict.get("id"),
                "file_path": row_dict.get(path_column) or row_dict.get("file_path") or row_dict.get("path") or "",
                "classifier_name": row_dict.get("classifier_name") or row_dict.get("classifier") or "",
                "category": row_dict.get("category") or "",
                "subcategory": row_dict.get("subcategory") or "",
                "value": row_dict.get("value") or "",
                "confidence": float(row_dict.get("confidence") or 0.0),
                "task_id": row_dict.get("task_id"),
                "scanner_id": row_dict.get("scanner_id")
            })
        
        conn.close()
        return findings
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/api/findings/count")
async def get_findings_count(category: str = None, file_path: str = None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Определяем название колонки с путём
        columns = get_column_names(cursor, "findings")
        path_column = "file_path" if "file_path" in columns else "path" if "path" in columns else "filepath"
        
        query = "SELECT COUNT(*) FROM findings"
        params = []
        conditions = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if file_path:
            conditions.append(f"{path_column} LIKE ?")
            params.append(f"%{file_path}%")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        count = cursor.execute(query, params).fetchone()[0] or 0
        conn.close()
        return {"count": count}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/findings/{finding_id}")
async def get_finding(finding_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        columns = get_column_names(cursor, "findings")
        path_column = "file_path" if "file_path" in columns else "path" if "path" in columns else "filepath"
        
        cursor.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return {"error": "Finding not found"}
        
        row_dict = dict(row)
        return {
            "finding": {
                "id": row_dict.get("id"),
                "file_path": row_dict.get(path_column) or row_dict.get("file_path") or row_dict.get("path") or "",
                "classifier_name": row_dict.get("classifier_name") or row_dict.get("classifier") or "",
                "category": row_dict.get("category") or "",
                "subcategory": row_dict.get("subcategory") or "",
                "value": row_dict.get("value") or "",
                "confidence": float(row_dict.get("confidence") or 0.0),
                "task_id": row_dict.get("task_id"),
                "scanner_id": row_dict.get("scanner_id")
            }
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/tasks")
async def get_tasks(limit: int = 50, status: str = None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = "SELECT * FROM scan_tasks"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        tasks = []
        for row in rows:
            row_dict = dict(row)
            tasks.append({
                "id": row_dict.get("id"),
                "resource_id": row_dict.get("resource_id"),
                "scanner_id": row_dict.get("scanner_id"),
                "status": row_dict.get("status") or "",
                "files_scanned": row_dict.get("files_scanned") or 0,
                "findings_count": row_dict.get("findings_count") or 0,
                "created_at": row_dict.get("created_at"),
                "started_at": row_dict.get("started_at"),
                "completed_at": row_dict.get("completed_at")
            })
        
        conn.close()
        return tasks
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM scan_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {"error": "Task not found"}
        
        row_dict = dict(row)
        task = {
            "task": {
                "id": row_dict.get("id"),
                "resource_id": row_dict.get("resource_id"),
                "scanner_id": row_dict.get("scanner_id"),
                "status": row_dict.get("status") or "",
                "files_scanned": row_dict.get("files_scanned") or 0,
                "findings_count": row_dict.get("findings_count") or 0,
                "created_at": row_dict.get("created_at"),
                "started_at": row_dict.get("started_at"),
                "completed_at": row_dict.get("completed_at")
            }
        }
        
        # Определяем колонку пути
        columns = get_column_names(cursor, "findings")
        path_column = "file_path" if "file_path" in columns else "path" if "path" in columns else "filepath"
        
        cursor.execute("SELECT * FROM findings WHERE task_id = ? LIMIT 100", (task_id,))
        findings_rows = cursor.fetchall()
        
        findings = []
        for row in findings_rows:
            row_dict = dict(row)
            findings.append({
                "id": row_dict.get("id"),
                "file_path": row_dict.get(path_column) or row_dict.get("file_path") or row_dict.get("path") or "",
                "classifier_name": row_dict.get("classifier_name") or row_dict.get("classifier") or "",
                "category": row_dict.get("category") or "",
                "subcategory": row_dict.get("subcategory") or "",
                "value": row_dict.get("value") or "",
                "confidence": float(row_dict.get("confidence") or 0.0),
                "task_id": row_dict.get("task_id"),
                "scanner_id": row_dict.get("scanner_id")
            })
        task["findings"] = findings
        
        conn.close()
        return task
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/scanners")
async def get_scanners():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM scanners ORDER BY id")
        rows = cursor.fetchall()
        
        scanners = []
        for row in rows:
            row_dict = dict(row)
            scanners.append({
                "id": row_dict.get("id"),
                "name": row_dict.get("name") or "",
                "endpoint": row_dict.get("endpoint") or "",
                "status": row_dict.get("status") or "",
                "last_heartbeat": row_dict.get("last_heartbeat"),
                "total_files_scanned": row_dict.get("total_files_scanned") or 0,
                "total_findings": row_dict.get("total_findings") or 0
            })
        
        conn.close()
        return scanners
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/categories")
async def get_categories():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        rows = cursor.execute("SELECT DISTINCT category FROM findings ORDER BY category").fetchall()
        categories = [row[0] for row in rows]
        
        conn.close()
        return categories
    except Exception as e:
        return {"error": str(e)}

# === HTML СТРАНИЦА ===

HTML = """<!DOCTYPE html>
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
        .navbar-brand { font-weight: bold; }
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
        .filter-card { background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 1.5rem; }
        .findings-table-wrapper { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden; }
        .error-box { background: #fff5f5; border: 1px solid #fc8181; color: #c53030; padding: 1rem; border-radius: 8px; margin: 1rem 0; display: none; }
        .page-content { display: none; }
        .page-content.active { display: block; }
        .nav-link { cursor: pointer; }
        .nav-link.active { font-weight: bold; }
        pre { background: #f8f9fa; padding: 10px; border-radius: 5px; font-size: 12px; max-height: 200px; overflow: auto; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-shield-alt text-primary"></i> DCAP v3.0
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item"><a class="nav-link active" data-page="dashboard" onclick="switchPage('dashboard')"><i class="fas fa-chart-pie"></i> Дашборд</a></li>
                    <li class="nav-item"><a class="nav-link" data-page="findings" onclick="switchPage('findings')"><i class="fas fa-search"></i> Находки</a></li>
                    <li class="nav-item"><a class="nav-link" data-page="tasks" onclick="switchPage('tasks')"><i class="fas fa-tasks"></i> Задания</a></li>
                    <li class="nav-item"><a class="nav-link" data-page="scanners" onclick="switchPage('scanners')"><i class="fas fa-server"></i> Сканеры</a></li>
                </ul>
                <span class="text-muted small" id="update-time"></span>
            </div>
        </div>
    </nav>

    <main class="container-fluid py-4">
        <div id="error-message" class="error-box"></div>
        
        <!-- Дашборд -->
        <div id="page-dashboard" class="page-content active">
            <h2 class="mb-4"><i class="fas fa-chart-pie text-primary"></i> Дашборд системы</h2>
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
                    <a href="#" onclick="switchPage('findings'); return false;" class="btn btn-sm btn-outline-primary">Все находки →</a>
                </div>
                <div class="card-body p-0" id="recent-findings"></div>
            </div>
        </div>

        <!-- Находки -->
        <div id="page-findings" class="page-content">
            <h2 class="mb-4"><i class="fas fa-search text-primary"></i> Находки <span class="text-muted fs-6" id="findings-total"></span></h2>
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
                <div>
                    <select class="form-select form-select-sm" id="per-page" onchange="loadFindings()" style="width:auto;display:inline-block;">
                        <option value="20">20</option>
                        <option value="50" selected>50</option>
                        <option value="100">100</option>
                    </select>
                    <span class="text-muted small ms-2">на страницу</span>
                </div>
                <nav><ul class="pagination mb-0" id="pagination"></ul></nav>
            </div>
        </div>

        <!-- Задания -->
        <div id="page-tasks" class="page-content">
            <h2 class="mb-4"><i class="fas fa-tasks text-primary"></i> Задания</h2>
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
        </div>

        <!-- Сканеры -->
        <div id="page-scanners" class="page-content">
            <h2 class="mb-4"><i class="fas fa-server text-primary"></i> Сканеры</h2>
            <div class="findings-table-wrapper" id="scanners-table"></div>
        </div>
    </main>

    <script>
        let currentPage = 'dashboard';
        let charts = {};
        let findingsPage = 0;
        let findingsTotal = 0;
        let perPage = 50;

        function switchPage(page) {
            currentPage = page;
            document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
            document.getElementById('page-' + page).classList.add('active');
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            document.querySelector('.nav-link[data-page="' + page + '"]').classList.add('active');
            
            if (page === 'dashboard') loadDashboard();
            else if (page === 'findings') { loadCategories(); loadFindings(); }
            else if (page === 'tasks') loadTasks();
            else if (page === 'scanners') loadScanners();
        }

        // === ДАШБОРД ===
        async function loadDashboard() {
            try {
                const r = await fetch('/api/stats');
                const stats = await r.json();
                if (stats.error) { showError(stats.error); return; }
                hideError();
                updateStats(stats);
                updateCharts(stats);
                await loadRecentFindings();
                updateTime();
            } catch(e) { showError(e.message); console.error(e); }
        }

        function updateStats(stats) {
            document.getElementById('stats-grid').innerHTML = `
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-primary"><i class="fas fa-file-alt"></i></div><div class="stat-value">${stats.total_findings}</div><div class="stat-label">Находок</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-success"><i class="fas fa-server"></i></div><div class="stat-value">${stats.active_scanners}</div><div class="stat-label">Сканеров</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-warning"><i class="fas fa-clock"></i></div><div class="stat-value">${stats.pending_tasks}</div><div class="stat-label">В очереди</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-success"><i class="fas fa-check-circle"></i></div><div class="stat-value">${stats.completed_tasks}</div><div class="stat-label">Завершено</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-danger"><i class="fas fa-exclamation-triangle"></i></div><div class="stat-value">${stats.failed_tasks || 0}</div><div class="stat-label">Провалено</div></div></div>
                <div class="col-md-2 col-sm-4"><div class="stat-card"><div class="stat-icon text-info"><i class="fas fa-folder-open"></i></div><div class="stat-value">${stats.total_files_scanned}</div><div class="stat-label">Файлов</div></div></div>
            `;
        }

        function updateCharts(stats) {
            const colors = ['#4e79a7','#f28e2b','#e15759','#59a14f','#edc948','#b07aa1'];
            if (charts.category) charts.category.destroy();
            const ctx1 = document.getElementById('categoryChart')?.getContext('2d');
            if (ctx1) {
                const cats = Object.keys(stats.findings_by_category || {});
                const vals = Object.values(stats.findings_by_category || {});
                charts.category = new Chart(ctx1, {
                    type: 'bar',
                    data: { labels: cats.length ? cats : ['Нет данных'], datasets: [{ label: 'Находки', data: cats.length ? vals : [0], backgroundColor: colors.slice(0, cats.length || 1) }] },
                    options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
                });
            }
            if (charts.scanner) charts.scanner.destroy();
            const ctx2 = document.getElementById('scannerChart')?.getContext('2d');
            if (ctx2) {
                const scs = Object.keys(stats.findings_by_scanner || {});
                const scv = Object.values(stats.findings_by_scanner || {});
                charts.scanner = new Chart(ctx2, {
                    type: 'doughnut',
                    data: { labels: scs.length ? scs : ['Нет данных'], datasets: [{ data: scs.length ? scv : [1], backgroundColor: colors.slice(0, scs.length || 1) }] },
                    options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom' } } }
                });
            }
        }

        async function loadRecentFindings() {
            try {
                const r = await fetch('/api/findings?limit=10');
                const findings = await r.json();
                const container = document.getElementById('recent-findings');
                if (findings.error) { container.innerHTML = '<div class="text-center p-4 text-danger">' + findings.error + '</div>'; return; }
                if (!findings.length) { container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>'; return; }
                let html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>';
                findings.forEach(f => {
                    const conf = (f.confidence * 100).toFixed(0);
                    const cls = f.confidence > 0.8 ? 'high' : f.confidence > 0.5 ? 'medium' : 'low';
                    const fname = (f.file_path || '').split('\\\\').pop() || f.file_path || 'unknown';
                    html += '<tr><td><span class="file-path" title="' + f.file_path + '">' + fname + '</span></td><td><span class="badge bg-info">' + f.category + '</span></td><td>' + f.classifier_name + '</td><td class="confidence-' + cls + '">' + conf + '%</td></tr>';
                });
                html += '</tbody></table></div>';
                container.innerHTML = html;
            } catch(e) { console.error(e); }
        }

        // === НАХОДКИ ===
        async function loadCategories() {
            try {
                const r = await fetch('/api/categories');
                const cats = await r.json();
                const select = document.getElementById('filter-category');
                if (cats.error) return;
                select.innerHTML = '<option value="">Все</option>';
                cats.forEach(c => { const opt = document.createElement('option'); opt.value = c; opt.textContent = c; select.appendChild(opt); });
            } catch(e) { console.error(e); }
        }

        async function loadFindings() {
            const category = document.getElementById('filter-category')?.value || '';
            const filePath = document.getElementById('filter-file')?.value || '';
            const confidence = document.getElementById('filter-confidence')?.value || '';
            perPage = parseInt(document.getElementById('per-page')?.value || 50);
            
            let url = '/api/findings?limit=' + perPage + '&offset=' + (findingsPage * perPage);
            if (category) url += '&category=' + encodeURIComponent(category);
            if (filePath) url += '&file_path=' + encodeURIComponent(filePath);
            if (confidence) url += '&min_confidence=' + confidence;
            
            try {
                const r = await fetch(url);
                const findings = await r.json();
                if (findings.error) { showError(findings.error); return; }
                hideError();
                
                const countUrl = '/api/findings/count?' + new URLSearchParams({ category, file_path });
                const countR = await fetch(countUrl);
                const countData = await countR.json();
                findingsTotal = countData.count || 0;
                
                renderFindingsTable(findings);
                renderPagination();
                document.getElementById('findings-total').textContent = '(всего: ' + findingsTotal + ')';
                updateTime();
            } catch(e) { showError(e.message); console.error(e); }
        }

        function renderFindingsTable(findings) {
            const container = document.getElementById('findings-table');
            if (!findings.length) { container.innerHTML = '<div class="text-center p-4 text-muted">Нет находок</div>'; return; }
            let html = '<div class="table-responsive"><table class="table table-hover table-sm mb-0"><thead class="table-light"><tr><th>#</th><th>Файл</th><th>Категория</th><th>Классификатор</th><th>Доверие</th></tr></thead><tbody>';
            findings.forEach((f, i) => {
                const conf = (f.confidence * 100).toFixed(0);
                const cls = f.confidence > 0.8 ? 'high' : f.confidence > 0.5 ? 'medium' : 'low';
                const fname = (f.file_path || '').split('\\\\').pop() || f.file_path || 'unknown';
                html += '<tr><td>' + (findingsPage * perPage + i + 1) + '</td><td><span class="file-path" title="' + f.file_path + '">' + fname + '</span></td><td><span class="badge bg-info">' + f.category + '</span></td><td>' + f.classifier_name + '</td><td class="confidence-' + cls + '">' + conf + '%</td></tr>';
            });
            html += '</tbody></table></div>';
            container.innerHTML = html;
        }

        function renderPagination() {
            const totalPages = Math.ceil(findingsTotal / perPage);
            const pagination = document.getElementById('pagination');
            if (totalPages <= 1) { pagination.innerHTML = ''; return; }
            let html = '<li class="page-item ' + (findingsPage === 0 ? 'disabled' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + (findingsPage - 1) + ')">«</a></li>';
            let start = Math.max(0, findingsPage - 2), end = Math.min(totalPages - 1, findingsPage + 2);
            if (start > 0) { html += '<li class="page-item"><a class="page-link" href="#" onclick="goToPage(0)">1</a></li>'; if (start > 1) html += '<li class="page-item disabled"><span class="page-link">...</span></li>'; }
            for (let i = start; i <= end; i++) html += '<li class="page-item ' + (i === findingsPage ? 'active' : '') + '"><a class="page-link" href="#" onclick="goToPage(' + i + ')">' + (i+1) + '</a></li>';
            if (end < totalPages - 1) { if (end < totalPages - 2) html += '<li class="page-item disabled"><span class="page-link">...</span></li>'; html += '<li class="page-item"><a class="page-link" href="#" onclick="goToPage(' + (totalPages - 1) + ')">' + totalPages + '</a></li>'; }
            html += '<li class="page-item ' + (