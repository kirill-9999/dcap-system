#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Инициализация базы данных начальными данными
Запуск: D:\dev\anaconda3\python.exe init_db_data.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import os

DB_PATH = Path("manager/src/db/dcap.db")

def init_database():
    """Создание и заполнение БД начальными данными"""
    
    # Проверяем существование БД
    if DB_PATH.exists():
        print(f"⚠️ База данных уже существует: {DB_PATH}")
        response = input("Удалить существующую БД и создать новую? (y/N): ")
        if response.lower() != 'y':
            print("❌ Отменено")
            return False
        DB_PATH.unlink()
        print(f"🗑️ Старая БД удалена")
    
    # Создаем директорию если её нет
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Создание БД: {DB_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # ===== СОЗДАНИЕ ТАБЛИЦ =====
        print("\n📋 Создание таблиц...")
        
        # Таблица resources
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path VARCHAR(500) UNIQUE NOT NULL,
                type VARCHAR(50) DEFAULT 'filesystem',
                status VARCHAR(20) DEFAULT 'active',
                last_scan DATETIME,
                enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✅ resources")
        
        # Таблица scanners
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scanners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'offline',
                last_heartbeat DATETIME,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                hostname VARCHAR(100),
                ip_address VARCHAR(45),
                scan_interval INTEGER DEFAULT 10
            )
        """)
        print("  ✅ scanners")
        
        # Таблица scan_tasks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_id INTEGER NOT NULL,
                scanner_id INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                assigned_at DATETIME,
                started_at DATETIME,
                completed_at DATETIME,
                error_message TEXT,
                files_scanned INTEGER DEFAULT 0,
                files_failed INTEGER DEFAULT 0,
                findings_count INTEGER DEFAULT 0,
                FOREIGN KEY (resource_id) REFERENCES resources(id),
                FOREIGN KEY (scanner_id) REFERENCES scanners(id)
            )
        """)
        print("  ✅ scan_tasks")
        
        # Таблица findings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                line_number INTEGER,
                category VARCHAR(100) NOT NULL,
                subcategory VARCHAR(100),
                value TEXT NOT NULL,
                confidence FLOAT DEFAULT 0.0,
                context TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES scan_tasks(id)
            )
        """)
        print("  ✅ findings")
        
        # Таблица catalog_entries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalog_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path VARCHAR(500) UNIQUE NOT NULL,
                classifiers TEXT DEFAULT '[]',
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✅ catalog_entries")
        
        # Таблица failed_files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                error TEXT NOT NULL,
                error_type VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES scan_tasks(id)
            )
        """)
        print("  ✅ failed_files")
        
        # Таблица schedules
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_id INTEGER NOT NULL,
                cron_expression VARCHAR(100) NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                priority INTEGER DEFAULT 0,
                max_files_per_batch INTEGER DEFAULT 500,
                last_run DATETIME,
                next_run DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resource_id) REFERENCES resources(id)
            )
        """)
        print("  ✅ schedules")
        
        # ===== ЗАПОЛНЕНИЕ НАЧАЛЬНЫМИ ДАННЫМИ =====
        print("\n📝 Заполнение начальными данными...")
        
        # 1. Создаем сканер
        cursor.execute("""
            INSERT INTO scanners (name, status, scan_interval, registered_at)
            VALUES (?, ?, ?, ?)
        """, (
            "scanner-1",
            "idle",
            10,
            datetime.utcnow().isoformat()
        ))
        scanner_id = cursor.lastrowid
        print(f"  ✅ Сканер создан: ID={scanner_id}, name=scanner-1")
        
        # 2. Создаем тестовый ресурс
        cursor.execute("""
            INSERT INTO resources (path, type, status, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "D:/Projects/dcap-system/test_files",
            "FILESYSTEM",  # Верхний регистр, как в Enum
            "active",
            1,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        resource_id = cursor.lastrowid
        print(f"  ✅ Ресурс создан: ID={resource_id}, path=D:/Projects/dcap-system/test_files")
        
        # 3. Создаем тестовое задание
        cursor.execute("""
            INSERT INTO scan_tasks (
                resource_id, 
                status, 
                created_at, 
                updated_at,
                files_scanned,
                findings_count
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            resource_id,
            "pending",
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            0,
            0
        ))
        task_id = cursor.lastrowid
        print(f"  ✅ Тестовое задание создано: ID={task_id}, status=pending")
        
        # 4. Создаем тестовые находки (для демонстрации)
        test_findings = [
            {
                "file_path": "D:/Projects/dcap-system/test_files/sample1.txt",
                "line_number": 15,
                "category": "email",
                "subcategory": "personal",
                "value": "test@example.com",
                "confidence": 0.95,
                "context": "Contact email: test@example.com for support"
            },
            {
                "file_path": "D:/Projects/dcap-system/test_files/sample1.txt",
                "line_number": 42,
                "category": "phone",
                "subcategory": "mobile",
                "value": "+7 (999) 123-45-67",
                "confidence": 0.89,
                "context": "Phone: +7 (999) 123-45-67"
            },
            {
                "file_path": "D:/Projects/dcap-system/test_files/sample2.txt",
                "line_number": 8,
                "category": "passport",
                "subcategory": "ru",
                "value": "1234 567890",
                "confidence": 0.92,
                "context": "Passport: 1234 567890"
            },
            {
                "file_path": "D:/Projects/dcap-system/test_files/sample2.txt",
                "line_number": 23,
                "category": "snils",
                "subcategory": "ru",
                "value": "123-456-789 00",
                "confidence": 0.88,
                "context": "SNILS: 123-456-789 00"
            }
        ]
        
        for finding in test_findings:
            cursor.execute("""
                INSERT INTO findings (
                    task_id,
                    file_path,
                    line_number,
                    category,
                    subcategory,
                    value,
                    confidence,
                    context,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                finding["file_path"],
                finding["line_number"],
                finding["category"],
                finding["subcategory"],
                finding["value"],
                finding["confidence"],
                finding["context"],
                datetime.utcnow().isoformat()
            ))
        print(f"  ✅ Тестовые находки созданы: {len(test_findings)} шт.")
        
        # 5. Создаем записи в каталоге
        catalog_entries = [
            "D:/Projects/dcap-system/test_files",
            "D:/Projects/dcap-system/test_files/subfolder1",
            "D:/Projects/dcap-system/test_files/subfolder2"
        ]
        
        for folder in catalog_entries:
            cursor.execute("""
                INSERT OR IGNORE INTO catalog_entries (folder_path, classifiers, first_seen, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                folder,
                '["contains_emails", "contains_phones"]',
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))
        print(f"  ✅ Каталог создан: {len(catalog_entries)} записей")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ БАЗА ДАННЫХ УСПЕШНО ИНИЦИАЛИЗИРОВАНА!")
        print("=" * 60)
        print(f"📁 Путь: {DB_PATH}")
        print(f"📊 Данные:")
        print(f"   - Сканеров: 1")
        print(f"   - Ресурсов: 1")
        print(f"   - Заданий: 1 (pending)")
        print(f"   - Находок: {len(test_findings)}")
        print(f"   - Каталог: {len(catalog_entries)}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_database():
    """Проверка содержимого БД"""
    if not DB_PATH.exists():
        print(f"❌ БД не найдена: {DB_PATH}")
        return
    
    print("\n📊 Проверка содержимого БД:")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Сканеры
        cursor.execute("SELECT id, name, status, scan_interval FROM scanners")
        scanners = cursor.fetchall()
        print(f"\n🔍 Сканеры ({len(scanners)}):")
        for s in scanners:
            print(f"   ID={s[0]}, name={s[1]}, status={s[2]}, interval={s[3]}с")
        
        # Ресурсы
        cursor.execute("SELECT id, path, status, enabled FROM resources")
        resources = cursor.fetchall()
        print(f"\n📁 Ресурсы ({len(resources)}):")
        for r in resources:
            print(f"   ID={r[0]}, path={r[1]}, status={r[2]}, enabled={r[3]}")
        
        # Задания
        cursor.execute("SELECT id, resource_id, status, created_at FROM scan_tasks")
        tasks = cursor.fetchall()
        print(f"\n📋 Задания ({len(tasks)}):")
        for t in tasks:
            print(f"   ID={t[0]}, resource_id={t[1]}, status={t[2]}, created={t[3][:19]}")
        
        # Находки
        cursor.execute("SELECT COUNT(*) FROM findings")
        findings_count = cursor.fetchone()[0]
        print(f"\n🔎 Находки: {findings_count}")
        
        if findings_count > 0:
            cursor.execute("SELECT id, category, value, confidence FROM findings LIMIT 3")
            findings = cursor.fetchall()
            for f in findings:
                print(f"   ID={f[0]}, category={f[1]}, value={f[2][:30]}, conf={f[3]}")
        
        # Каталог
        cursor.execute("SELECT COUNT(*) FROM catalog_entries")
        catalog_count = cursor.fetchone()[0]
        print(f"\n📂 Каталог: {catalog_count} записей")
        
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ DCAP")
    print("=" * 60)
    
    if init_database():
        check_database()
        print("\n✅ Готово! Теперь можно запускать Manager.")
        print("   D:\\dev\\anaconda3\\python.exe -m manager.src.main")
    else:
        print("\n❌ Инициализация не удалась")