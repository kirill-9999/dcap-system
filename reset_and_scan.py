#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сброс и запуск сканирования
"""

import os
import sys
import shutil
import subprocess
import time
import sqlite3
from pathlib import Path

def kill_process_on_port(port):
    """Убить процесс на порту"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True,
            capture_output=True,
            text=True
        )
        
        pids = set()
        for line in result.stdout.split('\n'):
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(int(pid))
        
        if pids:
            for pid in pids:
                try:
                    subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
                    print(f"   ✅ Процесс {pid} убит")
                except:
                    pass
    except:
        pass

def reset():
    """Сброс состояния"""
    print("🔄 Сброс состояния...")
    
    # Останавливаем процессы
    print("   Остановка процессов...")
    kill_process_on_port(8000)
    kill_process_on_port(50051)
    time.sleep(2)
    
    # Удаляем файлы
    files_to_delete = [
        Path("state.json"),
        Path("manager/src/db/dcap.db"),
        Path("scanner_data"),
        Path("logs"),
        Path("catalog")
    ]
    
    for item in files_to_delete:
        if item.exists():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                    print(f"   ✅ {item} удалён")
                else:
                    item.unlink()
                    print(f"   ✅ {item} удалён")
            except Exception as e:
                print(f"   ⚠️ Не удалось удалить {item}: {e}")
    
    print("✅ Сброс завершён")

def wait_for_db_tables(timeout: int = 60) -> bool:
    """Ожидание создания таблиц в БД"""
    db_path = Path("manager/src/db/dcap.db")
    print("   Ожидание создания таблиц...")
    
    for i in range(timeout):
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resources'")
                if cursor.fetchone():
                    conn.close()
                    print(f"   ✅ Таблицы созданы ({i+1} сек)")
                    return True
                conn.close()
            except:
                pass
        time.sleep(1)
        if i % 5 == 0 and i > 0:
            print(f"   Ожидание... {i} сек")
    
    print("   ❌ Таблицы не созданы за 30 сек")
    return False

def start_manager():
    """Запуск Manager для создания БД"""
    print("\n🚀 Запуск Manager для создания БД...")
    
    # Запускаем Manager в фоне
    manager_process = subprocess.Popen(
        ["python", "-m", "manager.src.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Ждём создания таблиц
    if wait_for_db_tables():
        return manager_process
    else:
        return None

def create_data():
    """Создание тестовых данных"""
    print("\n📁 Создание тестовых данных...")
    result = subprocess.run(["python", "create_test_data.py"], capture_output=True, text=True)
    if result.returncode == 0:
        print("   ✅ Тестовые данные созданы")
        return True
    else:
        print(f"   ❌ Ошибка: {result.stderr}")
        return False

def scan():
    """Запуск сканирования"""
    print("\n🔍 Запуск Scanner...")
    subprocess.run(["python", "run_scanner.py"], check=True)

def stop_manager(manager_process):
    """Остановка Manager"""
    if manager_process:
        print("\n🛑 Остановка Manager...")
        try:
            manager_process.terminate()
            manager_process.wait(timeout=5)
            print("   ✅ Manager остановлен")
        except:
            try:
                manager_process.kill()
                print("   ✅ Manager остановлен (принудительно)")
            except:
                pass

if __name__ == "__main__":
    manager_process = None
    
    try:
        reset()
        manager_process = start_manager()
        
        if not manager_process:
            print("❌ Не удалось запустить Manager")
            sys.exit(1)
        
        if not create_data():
            print("❌ Не удалось создать тестовые данные")
            sys.exit(1)
        
        scan()
        print("\n✅ Готово!")
        
    except KeyboardInterrupt:
        print("\n⏹️ Прервано")
    finally:
        stop_manager(manager_process)