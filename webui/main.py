from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
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

# Статические файлы
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
        
        query = "SELECT * FROM findings"
        params = []
        conditions = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if file_path:
            conditions.append("file_path LIKE ?")
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
                "file_path": row_dict.get("file_path") or row_dict.get("path") or "",
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
        
        query = "SELECT COUNT(*) FROM findings"
        params = []
        conditions = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if file_path:
            conditions.append("file_path LIKE ?")
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

# === СТРАНИЦЫ ===

@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/findings")
async def findings():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/tasks")
async def tasks():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/scanners")
async def scanners():
    return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════╗
    ║   DCAP WebUI v3.0                          ║
    ║   http://localhost:8001                    ║
    ║   Вкладки: Дашборд | Находки | Задания | Сканеры ║
    ╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(
        "webui.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )