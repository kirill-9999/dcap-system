from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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
    conn.row_factory = sqlite3.Row
    return conn

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
        
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(findings)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Колонки в таблице findings: {columns}")
        
        # Определяем имя колонки для пути
        path_col = None
        for col in ['file_path', 'path', 'filepath', 'full_path']:
            if col in columns:
                path_col = col
                break
        if not path_col:
            path_col = 'file_path'
        
        query = f"SELECT * FROM findings"
        params = []
        conditions = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if file_path:
            conditions.append(f"{path_col} LIKE ?")
            params.append(f"%{file_path}%")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        findings = []
        for row in rows:
            row_dict = dict(row)
            findings.append({
                "id": row_dict.get("id"),
                "file_path": row_dict.get(path_col) or "",
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
        
        cursor.execute("PRAGMA table_info(findings)")
        columns = [row[1] for row in cursor.fetchall()]
        path_col = 'file_path' if 'file_path' in columns else 'path' if 'path' in columns else 'filepath'
        
        query = "SELECT COUNT(*) FROM findings"
        params = []
        conditions = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if file_path:
            conditions.append(f"{path_col} LIKE ?")
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
        
        cursor.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return {"error": "Finding not found"}
        
        row_dict = dict(row)
        return {
            "finding": {
                "id": row_dict.get("id"),
                "file_path": row_dict.get("file_path") or row_dict.get("path") or "",
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
        
        cursor.execute("SELECT * FROM findings WHERE task_id = ? LIMIT 100", (task_id,))
        findings_rows = cursor.fetchall()
        
        findings = []
        for row in findings_rows:
            row_dict = dict(row)
            findings.append({
                "id": row_dict.get("id"),
                "file_path": row_dict.get("file_path") or row_dict.get("path") or "",
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
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DCAP Distributed v3.0</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; }
        .navbar { background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
        .navbar-brand { font-size: 1.5rem; font-weight: bold; }
        .navbar-brand span { color: #4fc3f7; }
        .nav-links { display: flex; gap: 1rem; flex-wrap: wrap; }
        .nav-links a { color: #aaa; text-decoration: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; }
        .nav-links a:hover, .nav-links a.active { color: white; background: #2d2d44; }
        .container { max-width: 1400px; margin: 0 auto; padding: 2rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
        .stat-value { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; }
        .stat-label { color: #666; font-size: 0.85rem; text-transform: uppercase; margin-top: 4px; }
        .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }
        .chart-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .chart-card h3 { margin-bottom: 1rem; font-size: 1rem; color: #333; }
        .chart-card canvas { width: 100% !important; height: 250px !important; }
        .table-card { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; }
        .table-card .header { padding: 1rem 1.5rem; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
        .table-card .header a { color: #4fc3f7; text-decoration: none; font-size: 0.9rem; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 0.75rem 1.5rem; background: #f8f9fa; font-weight: 600; color: #555; font-size: 0.85rem; }
        td { padding: 0.75rem 1.5rem; border-bottom: 1px solid #eee; font-size: 0.9rem; }
        tr:hover { background: #f8f9fa; cursor: pointer; }
        .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .badge-info { background: #e3f2fd; color: #0d47a1; }
        .badge-success { background: #e8f5e9; color: #1b5e20; }
        .badge-warning { background: #fff3e0; color: #e65100; }
        .badge-danger { background: #ffebee; color: #b71c1c; }
        .badge-secondary { background: #f5f5f5; color: #616161; }
        .confidence-high { color: #2e7d32; font-weight: 600; }
        .confidence-medium { color: #f57c00; font-weight: 600; }
        .confidence-low { color: #c62828; font-weight: 600; }
        .page { display: none; }
        .page.active { display: block; }
        .error-box { background: #ffebee; border: 1px solid #ef9a9a; color: #c62828; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; display: none; }
        .filter-card { background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1.5rem; display: flex; gap: 1rem; flex-wrap: wrap; align-items: end; }
        .filter-card label { font-size: 0.8rem; color: #666; display: block; margin-bottom: 4px; }
        .filter-card select, .filter-card input { padding: 0.4rem 0.8rem; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; }
        .filter-card button { padding: 0.4rem 1.2rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
        .btn-primary { background: #4fc3f7; color: white; }
        .btn-primary:hover { background: #29b6f6; }
        .btn-secondary { background: #e0e0e0; color: #333; }
        .btn-secondary:hover { background: #bdbdbd; }
        .pagination { display: flex; gap: 0.5rem; margin-top: 1rem; justify-content: center; flex-wrap: wrap; }
        .pagination a { padding: 0.3rem 0.8rem; border: 1px solid #ddd; border-radius: 4px; text-decoration: none; color: #333; cursor: pointer; }
        .pagination a.active { background: #4fc3f7; color: white; border-color: #4fc3f7; }
        .pagination a:hover:not(.active) { background: #f0f0f0; }
        .pagination span { padding: 0.3rem 0.8rem; color: #999; }
        .update-time { color: #888; font-size: 0.8rem; }
        .file-path { font-family: 'Courier New', monospace; font-size: 0.8rem; max-width: 200px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .page-title { margin-bottom: 1.5rem; }
        @media (max-width: 768px) {
            .charts-grid { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: repeat(3, 1fr); }
            .filter-card { flex-direction: column; align-items: stretch; }
            .container { padding: 1rem; }
            .navbar { flex-direction: column; align-items: stretch; text-align: center; }
            .nav-links { justify-content: center; }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="navbar-brand">🛡️ <span>DCAP</span> v3.0</div>
        <div class="nav-links">
            <a class="active" data-page="dashboard" onclick="switchPage('dashboard')">📊 Дашборд</a>
            <a data-page="findings" onclick="switchPage('findings')">🔍 Находки</a>
            <a data-page="tasks" onclick="switchPage('tasks')">📋 Задания</a>
            <a data-page="scanners" onclick="switchPage('scanners')">🖥️ Сканеры</a>
        </div>
        <div class="update-time" id="update-time"></div>
    </nav>

    <div class="container">
        <div id="error-message" class="error-box"></div>

        <!-- Dashboard -->
        <div id="page-dashboard" class="page active">
            <h2 class="page-title">📊 Дашборд системы</h2>
            <div class="stats-grid" id="stats-grid"></div>
            <div class="charts-grid">
                <div class="chart-card"><h3>Находки по категориям</h3><canvas id="categoryChart"></canvas></div>
                <div class="chart-card"><h3>Находки по сканерам</h3><canvas id="scannerChart"></canvas></div>
            </div>
            <div class="table-card">
                <div class="header"><span>📋 Последние находки</span><a onclick="switchPage('findings')">Все находки →</a></div>
                <div id="recent-findings"></div>
            </div>
        </div>

        <!-- Findings -->
        <div id="page-findings" class="page">
            <h2 class="page-title">🔍 Находки <span style="font-size: 0.9rem; color: #666;" id="findings-total"></span></h2>
            <div class="filter-card">
                <div><label>Категория</label><select id="filter-category"><option value="">Все</option></select></div>
                <div><label>Поиск по файлу</label><input type="text" id="filter-file" placeholder="Часть пути..."></div>
                <div><label>Мин. доверие</label><select id="filter-confidence"><option value="">Любое</option><option value="0.9">90%</option><option value="0.7">70%</option><option value="0.5">50%</option></select></div>
                <div style="display:flex; gap:0.5rem;"><button class="btn-primary" onclick="loadFindings()">🔍 Применить</button><button class="btn-secondary" onclick="resetFilters()">↺ Сброс</button></div>
                <div style="margin-left:auto;"><label>На страницу</label><select id="per-page" onchange="loadFindings()" style="padding:0.4rem;"><option value="20">20</option><option value="50" selected>50</option><option value="100">100</option></select></div>
            </div>
            <div class="table-card" id="findings-table"></div>
            <div class="pagination" id="pagination"></div>
        </div>

        <!-- Tasks -->
        <div id="page-tasks" class="page">
            <h2 class="page-title">📋 Задания</h2>
            <div class="filter-card">
                <div><label>Статус</label><select id="task-status" onchange="loadTasks()"><option value="">Все</option><option value="PENDING">⏳ Ожидает</option><option value="ASSIGNED">🔄 Назначено</option><option value="SCANNING">🔍 Сканируется</option><option value="COMPLETED">✅ Завершено</option><option value="FAILED">❌ Провалено</option></select></div>
            </div>
            <div class="table-card" id="tasks-table"></div>
        </div>

        <!-- Scanners -->
        <div id="page-scanners" class="page">
            <h2 class="page-title">🖥️ Сканеры</h2>
            <div class="table-card" id="scanners-table"></div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <script>
        let currentPage = 'dashboard';
        let charts = {};
        let findingsPage = 0;
        let findingsTotal = 0;
        let perPage = 50;

        function switchPage(page) {
            currentPage = page;
            document.querySelectorAll('.page').forEach(function(el) { el.classList.remove('active'); });
            document.getElementById('page-' + page).classList.add('active');
            document.querySelectorAll('.nav-links a').forEach(function(el) { el.classList.remove('active'); });
            document.querySelector('.nav-links a[data-page="' + page + '"]').classList.add('active');
            
            if (page === 'dashboard') loadDashboard();
            else if (page === 'findings') { loadCategories(); loadFindings(); }
            else if (page === 'tasks') loadTasks();
            else if (page === 'scanners') loadScanners();
        }

        function showError(msg) {
            var el = document.getElementById('error-message');
            el.style.display = 'block';
            el.textContent = '❌ ' + msg;
        }

        function hideError() {
            document.getElementById('error-message').style.display = 'none';
        }

        function updateTime() {
            document.getElementById('update-time').textContent = '🔄 ' + new Date().toLocaleTimeString('ru-RU');
        }

        // === DASHBOARD ===
        async function loadDashboard() {
            try {
                var r = await fetch('/api/stats');
                var stats = await r.json();
                if (stats.error) { showError(stats.error); return; }
                hideError();
                updateStats(stats);
                updateCharts(stats);
                await loadRecentFindings();
                updateTime();
            } catch(e) { showError(e.message); console.error(e); }
        }

        function updateStats(stats) {
            document.getElementById('stats-grid').innerHTML = 
                '<div class="stat-card"><div class="stat-value">' + stats.total_findings + '</div><div class="stat-label">Находок</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + stats.active_scanners + '</div><div class="stat-label">Сканеров</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + stats.pending_tasks + '</div><div class="stat-label">В очереди</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + stats.completed_tasks + '</div><div class="stat-label">Завершено</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + (stats.failed_tasks || 0) + '</div><div class="stat-label">Провалено</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + stats.total_files_scanned + '</div><div class="stat-label">Файлов</div></div>';
        }

        function updateCharts(stats) {
            var colors = ['#4e79a7','#f28e2b','#e15759','#59a14f','#edc948','#b07aa1'];
            
            var ctx1 = document.getElementById('categoryChart');
            if (ctx1) {
                if (charts.category) { charts.category.destroy(); }
                var cats = Object.keys(stats.findings_by_category || {});
                var vals = Object.values(stats.findings_by_category || {});
                charts.category = new Chart(ctx1, {
                    type: 'bar',
                    data: {
                        labels: cats.length ? cats : ['Нет данных'],
                        datasets: [{ label: 'Находки', data: cats.length ? vals : [0], backgroundColor: colors.slice(0, cats.length || 1) }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
                });
            }
            
            var ctx2 = document.getElementById('scannerChart');
            if (ctx2) {
                if (charts.scanner) { charts.scanner.destroy(); }
                var scs = Object.keys(stats.findings_by_scanner || {});
                var scv = Object.values(stats.findings_by_scanner || {});
                charts.scanner = new Chart(ctx2, {
                    type: 'doughnut',
                    data: {
                        labels: scs.length ? scs : ['Нет данных'],
                        datasets: [{ data: scs.length ? scv : [1], backgroundColor: colors.slice(0, scs.length || 1) }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
                });
            }
        }

        async function loadRecentFindings() {
            try {
                var r = await fetch('/api/findings?limit=10');
                var findings = await r.json();
                var container = document.getElementById('recent-findings');
                if (findings.error) { container.innerHTML = '<div style="padding:1rem;color:red;">' + findings.error + '</div>'; return; }
                if (!findings.length) { container.innerHTML = '<div style="padding:1rem;color:#888;">Нет находок</div>'; return; }
                var html = '<table><thead><tr><th>Файл