#!/usr/bin/env python3
"""Шаг 2: Запуск Manager"""

import subprocess
import time
import sqlite3
from pathlib import Path

print("🚀 ЗАПУСК MANAGER")
print("=" * 40)

# Запускаем Manager
manager = subprocess.Popen(
    ["python", "-m", "manager.src.main"],
    stdout=None,
    stderr=None
)

print("   Manager запущен (PID: {})".format(manager.pid))
print("   Ожидание инициализации БД...")

# Ждём создания таблиц
db_path = Path("manager/src/db/dcap.db")
for i in range(30):
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resources'")
            if cursor.fetchone():
                conn.close()
                print(f"   ✅ БД инициализирована ({i+1} сек)")
                break
            conn.close()
        except:
            pass
    time.sleep(1)
else:
    print("   ❌ БД не инициализирована за 30 сек")

print("\n✅ Manager готов к работе!")
print("   Health: http://localhost:8000/health")
print("   Для остановки: Ctrl+C")
print("\n   Оставь это окно открытым!")
print("   Переходи к ШАГУ 3 в новом окне")