#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create resource and task for E:\much_of_test_files
"""

import sqlite3
from pathlib import Path

def create_resource():
    db_path = Path("manager/src/db/dcap.db")
    
    if not db_path.exists():
        print("❌ Database not found. Start Manager first!")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Проверяем, есть ли ресурс с правильным путём
    cursor.execute("SELECT id FROM resources WHERE path = 'E:\\much_of_test_files'")
    resource = cursor.fetchone()
    
    if not resource:
        print("Creating resource for E:\\much_of_test_files...")
        cursor.execute("""
            INSERT INTO resources (type, path, enabled, created_at)
            VALUES ('FILESYSTEM', 'E:\\much_of_test_files', 1, datetime('now'))
        """)
        resource_id = cursor.lastrowid
        print(f"✅ Resource created: ID={resource_id}")
    else:
        resource_id = resource[0]
        print(f"✅ Resource exists: ID={resource_id}")
    
    # Проверяем, есть ли активные задания
    cursor.execute("""
        SELECT id FROM scan_tasks 
        WHERE resource_id = ? AND status IN ('PENDING', 'ASSIGNED')
    """, (resource_id,))
    active_task = cursor.fetchone()
    
    if active_task:
        print(f"✅ Active task exists: ID={active_task[0]}")
    else:
        # Создаём задание
        cursor.execute("""
            INSERT INTO scan_tasks (resource_id, status, files_total, files_scanned, findings_count, created_at)
            VALUES (?, 'PENDING', 0, 0, 0, datetime('now'))
        """, (resource_id,))
        task_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Task created: ID={task_id}")
    
    # Удаляем старый ресурс E:\test_data если есть
    cursor.execute("DELETE FROM resources WHERE path = 'E:\\test_data'")
    deleted = cursor.rowcount
    if deleted > 0:
        print(f"🗑️ Removed old resource: E:\\test_data")
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 Summary:")
    print(f"   Resource: E:\\much_of_test_files (ID={resource_id})")
    print(f"   Task status: PENDING")
    print(f"\nReady for scanning!")
    return True

if __name__ == "__main__":
    create_resource()