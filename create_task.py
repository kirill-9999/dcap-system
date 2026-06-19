#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание задания для Scanner
"""

import sqlite3
import uuid
from pathlib import Path

db_path = Path(__file__).parent / "manager" / "src" / "db" / "dcap.db"

if not db_path.exists():
    print(f"❌ База данных не найдена: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Проверяем ресурс
cursor.execute("SELECT id, path FROM resources")
resources = cursor.fetchall()

if not resources:
    print("❌ Ресурсы не найдены. Сначала запустите test_resources.py")
    conn.close()
    exit(1)

resource_id = resources[0][0]
resource_path = resources[0][1]

# Создаём задание
task_id = str(uuid.uuid4())

cursor.execute("""
    INSERT INTO scan_tasks (id, resource_id, status, files_total, files_scanned, findings_count, created_at)
    VALUES (?, ?, 'PENDING', 0, 0, 0, datetime('now'))
""", (task_id, resource_id))

conn.commit()
conn.close()

print(f"✅ Задание создано!")
print(f"   ID: {task_id}")
print(f"   Ресурс: {resource_path}")
print(f"\nЗапустите Scanner: python run_scanner.py")