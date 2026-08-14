from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import sqlite3
import json

from webui.api.schemas import (
    FindingResponse, TaskResponse, ScannerResponse, 
    ResourceResponse, StatsResponse, CreateTaskRequest,
    CreateResourceRequest, UpdateResourceRequest, UpdateAlertStatusRequest
)
from webui.config import DATABASE_URL

router = APIRouter(prefix="/api")


def get_db():
    """Получение соединения с БД"""
    db_path = Path("manager/dcap.db")
    if not db_path.exists():
        raise HTTPException(status_code=500, detail="Database not found")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ==================== СТАТИСТИКА ====================

@router.get("/stats")
async def get_stats():
    """Получить общую статистику системы"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Общее количество находок
    total_findings = cursor.execute("SELECT COUNT(*) FROM findings").fetchone()[0] or 0
    
    # Активные сканеры (heartbeat < 60 секунд)
    active_scanners = cursor.execute(
        "SELECT COUNT(*) FROM scanners WHERE last_heartbeat > datetime('now', '-60 seconds')"
    ).fetchone()[0] or 0
    
    # Задания по статусам
    pending_tasks = cursor.execute(
        "SELECT COUNT(*) FROM scan_tasks WHERE status = 'pending'"
    ).fetchone()[0] or 0
    
    running_tasks = cursor.execute(
        "SELECT COUNT(*) FROM scan_tasks WHERE status = 'running'"
    ).fetchone()[0] or 0
    
    completed_tasks = cursor.execute(
        "SELECT COUNT(*) FROM scan_tasks WHERE status = 'completed'"
    ).fetchone()[0] or 0
    
    failed_tasks = cursor.execute(
        "SELECT COUNT(*) FROM scan_tasks WHERE status = 'failed'"
    ).fetchone()[0] or 0
    
    # Всего отсканированных файлов
    total_files = cursor.execute(
        "SELECT COALESCE(SUM(files_scanned), 0) FROM scan_tasks"
    ).fetchone()[0] or 0
    
    # Всего ресурсов
    total_resources = cursor.execute(
        "SELECT COUNT(*) FROM resources"
    ).fetchone()[0] or 0
    
    # Находки по категориям
    findings_by_category = {}
    rows = cursor.execute(
        "SELECT category, COUNT(*) FROM findings GROUP BY category"
    ).fetchall()
    for row in rows:
        findings_by_category[row[0]] = row[1]
    
    # Находки по сканерам
    findings_by_scanner = {}
    rows = cursor.execute(
        "SELECT scanners.name, COUNT(findings.id) FROM findings "
        "LEFT JOIN scan_tasks ON scan_tasks.id = findings.task_id "
        "LEFT JOIN scanners ON scanners.id = scan_tasks.scanner_id "
        "GROUP BY scanners.name"
    ).fetchall()
    for row in rows:
        if row[0]:
            findings_by_scanner[row[0]] = row[1]
    
    # Задания по статусам
    tasks_by_status = {
        "pending": pending_tasks,
        "running": running_tasks,
        "completed": completed_tasks,
        "failed": failed_tasks
    }
    
    conn.close()
    
    return StatsResponse(
        total_findings=total_findings,
        active_scanners=active_scanners,
        pending_tasks=pending_tasks,
        running_tasks=running_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        total_files_scanned=total_files,
        total_resources=total_resources,
        findings_by_category=findings_by_category,
        findings_by_scanner=findings_by_scanner,
        tasks_by_status=tasks_by_status
    )


# ==================== НАХОДКИ ====================

@router.get("/findings")
async def get_findings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None,
    task_id: Optional[int] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1)
):
    """Получить список находок с фильтрацией"""
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
    if scanner_id:
        conditions.append("task_id IN (SELECT id FROM scan_tasks WHERE scanner_id = ?)")
        params.append(scanner_id)
    if task_id:
        conditions.append("task_id = ?")
        params.append(task_id)
    if min_confidence is not None:
        conditions.append("confidence >= ?")
        params.append(min_confidence)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


@router.get("/findings/count")
async def get_findings_count(
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None,
    task_id: Optional[int] = None
):
    """Получить количество находок с фильтрацией"""
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
    if scanner_id:
        conditions.append("task_id IN (SELECT id FROM scan_tasks WHERE scanner_id = ?)")
        params.append(scanner_id)
    if task_id:
        conditions.append("task_id = ?")
        params.append(task_id)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    count = cursor.execute(query, params).fetchone()[0] or 0
    conn.close()
    return {"count": count}


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: int):
    """Получить детальную информацию о находке"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    return dict(row)


@router.get("/categories")
async def get_categories():
    """Получить список всех уникальных категорий находок"""
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute(
        "SELECT DISTINCT category FROM findings ORDER BY category"
    ).fetchall()
    conn.close()
    
    return [row[0] for row in rows]


# ==================== ЗАДАНИЯ ====================

@router.get("/tasks")
async def get_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    resource_id: Optional[int] = None
):
    """Получить список заданий"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT t.*, r.path as resource_path, s.name as scanner_name
        FROM scan_tasks t
        LEFT JOIN resources r ON r.id = t.resource_id
        LEFT JOIN scanners s ON s.id = t.scanner_id
    """
    params = []
    conditions = []
    
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if resource_id:
        conditions.append("t.resource_id = ?")
        params.append(resource_id)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY t.created_at DESC LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        task = dict(row)
        # Вычисляем прогресс
        if task.get('files_total', 0) > 0:
            task['progress_percent'] = round(
                task.get('files_scanned', 0) / task.get('files_total', 1) * 100, 1
            )
        else:
            task['progress_percent'] = 0.0
        tasks.append(task)
    
    return tasks


@router.post("/tasks/create")
async def create_task(request: CreateTaskRequest):
    """Создание нового задания"""
    # Проверяем путь
    if request.resource_type == "FILESYSTEM":
        if not Path(request.resource_path).exists():
            raise HTTPException(
                status_code=400,
                detail=f"Папка не существует: {request.resource_path}"
            )
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Создаём или находим ресурс
    cursor.execute(
        "SELECT id FROM resources WHERE type = ? AND path = ?",
        (request.resource_type, request.resource_path)
    )
    row = cursor.fetchone()
    
    if row:
        resource_id = row[0]
    else:
        config = {
            "extensions": request.extensions.split(",") if request.extensions else [],
            "max_file_size_mb": request.max_file_size_mb,
            "recursive": request.recursive
        }
        cursor.execute(
            """
            INSERT INTO resources (type, path, enabled, scan_config, created_at)
            VALUES (?, ?, 1, ?, datetime('now'))
            """,
            (request.resource_type, request.resource_path, json.dumps(config))
        )
        resource_id = cursor.lastrowid
    
    # Создаём задание
    cursor.execute(
        """
        INSERT INTO scan_tasks (resource_id, source_path, status, files_scanned, files_failed, findings_count, created_at)
        VALUES (?, ?, 'pending', 0, 0, 0, datetime('now'))
        """,
        (resource_id, request.resource_path)
    )
    task_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "task_id": task_id,
        "resource_id": resource_id,
        "resource_path": request.resource_path,
        "message": f"Задание создано для {request.resource_path}"
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: int):
    """Отмена задания"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE scan_tasks 
        SET status = 'failed', completed_at = datetime('now')
        WHERE id = ? AND status IN ('pending', 'assigned')
        """,
        (task_id,)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Задание не может быть отменено (уже выполняется или завершено)"
        )
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Задание отменено"}


@router.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """Получить детальную информацию о задании"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT t.*, r.path as resource_path, s.name as scanner_name
        FROM scan_tasks t
        LEFT JOIN resources r ON r.id = t.resource_id
        LEFT JOIN scanners s ON s.id = t.scanner_id
        WHERE t.id = ?
        """,
        (task_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = dict(row)
    
    # Находки для этого задания
    cursor.execute(
        "SELECT * FROM findings WHERE task_id = ? LIMIT 100",
        (task_id,)
    )
    findings = cursor.fetchall()
    conn.close()
    
    return {
        "task": task,
        "findings": [dict(f) for f in findings],
        "findings_count": len(findings)
    }


# ==================== СКАНЕРЫ ====================

@router.get("/scanners")
async def get_scanners():
    """Получить список всех сканеров"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM scanners ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


@router.get("/scanners/{scanner_id}")
async def get_scanner(scanner_id: int):
    """Получить информацию о сканере"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM scanners WHERE id = ?", (scanner_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Scanner not found")
    
    return dict(row)


@router.post("/scanners/{scanner_id}/ping")
async def ping_scanner(scanner_id: int):
    """Проверить доступность сканера"""
    # TODO: Реализовать реальную проверку через gRPC
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE scanners SET status = 'ACTIVE', last_heartbeat = datetime('now') WHERE id = ?",
        (scanner_id,)
    )
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Scanner pinged"}


# ==================== РЕСУРСЫ ====================

@router.get("/resources")
async def get_resources(enabled_only: bool = False):
    """Получить список ресурсов"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM resources"
    params = []
    
    if enabled_only:
        query += " WHERE enabled = 1"
    
    query += " ORDER BY id"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


@router.post("/resources/create")
async def create_resource(request: CreateResourceRequest):
    """Создать новый ресурс"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Проверяем существование
    cursor.execute(
        "SELECT id FROM resources WHERE type = ? AND path = ?",
        (request.type, request.path)
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Resource already exists")
    
    config = {
        "extensions": request.extensions.split(",") if request.extensions else [],
        "max_file_size_mb": request.max_file_size_mb,
        "recursive": request.recursive
    }
    
    cursor.execute(
        """
        INSERT INTO resources (type, path, enabled, scan_config, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (request.type, request.path, request.enabled, json.dumps(config))
    )
    resource_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "resource_id": resource_id,
        "message": f"Resource {request.path} created"
    }


@router.put("/resources/{resource_id}")
async def update_resource(resource_id: int, request: UpdateResourceRequest):
    """Обновить ресурс"""
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if request.enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if request.enabled else 0)
    
    if request.config is not None:
        updates.append("scan_config = ?")
        params.append(json.dumps(request.config))
    
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.append(resource_id)
    cursor.execute(
        f"UPDATE resources SET {', '.join(updates)} WHERE id = ?",
        params
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Resource not found")
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Resource updated"}


@router.delete("/resources/{resource_id}")
async def delete_resource(resource_id: int, force: bool = False):
    """Удалить ресурс"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Проверяем, есть ли задания
    cursor.execute(
        "SELECT COUNT(*) FROM scan_tasks WHERE resource_id = ? AND status IN ('pending', 'assigned', 'running')",
        (resource_id,)
    )
    if cursor.fetchone()[0] > 0 and not force:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Resource has active tasks. Use force=true to delete anyway"
        )
    
    cursor.execute("DELETE FROM scan_tasks WHERE resource_id = ?", (resource_id,))
    cursor.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Resource not found")
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Resource deleted"}


# ==================== КЛАССИФИКАТОРЫ ====================

@router.get("/classifiers")
async def get_classifiers():
    """Получить список всех уникальных классификаторов"""
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute(
        "SELECT DISTINCT category FROM findings ORDER BY category"
    ).fetchall()
    conn.close()
    
    return [row[0] for row in rows]


# ==================== ВЫБОР ПАПКИ ====================

@router.post("/folders/pick")
def pick_folder():
    """Открыть нативный диалог выбора папки (Windows)"""
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Выбор папки для сканирования")
        root.destroy()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Невозможно открыть диалог выбора папки: {e}")
    if not path:
        return {"success": False, "path": None}
    return {"success": True, "path": path}


# ==================== УПРАВЛЕНИЕ ДОСТУПОМ ====================

@router.get("/access/resources")
async def get_access_resources():
    """Список ресурсов с информацией о правах доступа"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.id, r.type, r.path, r.enabled,
               r.owner, r.owner_sid,
               r.is_sensitive, r.classification_level,
               r.permission_source, r.permission_last_synced,
               (SELECT COUNT(*) FROM access_entries ae
                 WHERE ae.resource_id = r.id AND ae.is_active = 1) as entries_count,
               (SELECT COUNT(*) FROM access_alerts aa
                 WHERE aa.resource_id = r.id) as alerts_count,
               (SELECT COUNT(*) FROM access_alerts aa2
                 WHERE aa2.resource_id = r.id AND aa2.status = 'open') as open_alerts_count
        FROM resources r
        ORDER BY r.path
    """)
    rows = cursor.fetchall()
    conn.close()

    return {"total": len(rows), "resources": [dict(row) for row in rows]}


@router.get("/access/resources/{resource_id}/entries")
async def get_access_entries(
    resource_id: int,
    principal: Optional[str] = None,
    principal_type: Optional[str] = None,
    permission_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Права доступа к ресурсу с фильтрацией и пагинацией"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT path FROM resources WHERE id = ?", (resource_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resource not found")
    resource_path = row[0]

    query = """
        SELECT * FROM access_entries
        WHERE resource_id = ? AND is_active = 1
    """
    params = [resource_id]
    conditions = []

    if principal:
        conditions.append("principal_name LIKE ?")
        params.append(f"%{principal}%")
    if principal_type:
        conditions.append("principal_type = ?")
        params.append(principal_type)
    if permission_type:
        conditions.append("permission_type = ?")
        params.append(permission_type)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    total = cursor.execute(
        "SELECT COUNT(*) FROM (" + query + ")",
        params
    ).fetchone()[0] or 0

    query += " ORDER BY principal_name LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)

    rows = cursor.execute(query, params).fetchall()
    conn.close()

    return {
        "resource_id": resource_id,
        "resource_path": resource_path,
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [dict(row) for row in rows]
    }


@router.get("/access/alerts")
async def get_access_alerts(
    resource_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Список алертов по доступам с фильтрацией"""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT aa.*, r.path as resource_path
        FROM access_alerts aa
        LEFT JOIN resources r ON r.id = aa.resource_id
        WHERE 1 = 1
    """
    params = []
    conditions = []

    if resource_id:
        conditions.append("aa.resource_id = ?")
        params.append(resource_id)
    if severity:
        conditions.append("aa.severity = ?")
        params.append(severity)
    if status:
        conditions.append("aa.status = ?")
        params.append(status)
    if alert_type:
        conditions.append("aa.alert_type = ?")
        params.append(alert_type)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    total = cursor.execute(
        "SELECT COUNT(*) FROM (" + query + ")",
        params
    ).fetchone()[0] or 0

    query += """
        ORDER BY
            CASE aa.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            aa.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.append(limit)
    params.append(offset)

    rows = cursor.execute(query, params).fetchall()
    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": [dict(row) for row in rows]
    }


@router.get("/access/alerts/stats")
async def get_access_alerts_stats():
    """Статистика по алертам доступа"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {"total": 0, "by_severity": {}, "by_status": {}, "by_type": {}}

    stats["total"] = cursor.execute(
        "SELECT COUNT(*) FROM access_alerts"
    ).fetchone()[0] or 0

    for severity in ["critical", "warning", "info"]:
        stats["by_severity"][severity] = cursor.execute(
            "SELECT COUNT(*) FROM access_alerts WHERE severity = ? AND status = 'open'",
            (severity,)
        ).fetchone()[0] or 0

    for status in ["open", "acknowledged", "resolved", "ignored"]:
        stats["by_status"][status] = cursor.execute(
            "SELECT COUNT(*) FROM access_alerts WHERE status = ?",
            (status,)
        ).fetchone()[0] or 0

    rows = cursor.execute(
        "SELECT alert_type, COUNT(*) as cnt FROM access_alerts "
        "WHERE status = 'open' GROUP BY alert_type ORDER BY cnt DESC LIMIT 5"
    ).fetchall()
    stats["by_type"] = {r[0]: r[1] for r in rows}

    conn.close()
    return stats


@router.put("/access/alerts/{alert_id}")
async def update_access_alert_status(alert_id: int, request: UpdateAlertStatusRequest):
    """Обновить статус алерта (open/acknowledged/resolved/ignored)"""
    if request.status not in ["open", "acknowledged", "resolved", "ignored"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {request.status}. Supported: open, acknowledged, resolved, ignored"
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM access_alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Alert not found")

    old_status = row["status"]

    if request.status == "resolved" or request.status == "ignored":
        cursor.execute(
            "UPDATE access_alerts SET status = ?, resolved_at = datetime('now') WHERE id = ?",
            (request.status, alert_id)
        )
    else:
        cursor.execute(
            "UPDATE access_alerts SET status = ? WHERE id = ?",
            (request.status, alert_id)
        )

    conn.commit()
    conn.close()

    return {
        "status": "updated",
        "alert_id": alert_id,
        "old_status": old_status,
        "new_status": request.status
    }