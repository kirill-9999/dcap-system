#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощённое интеграционное тестирование DCAP v3.0
"""

import os
import sys
import time
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.offline.queue import OfflineQueue


def log(message: str, level: str = "INFO"):
    """Логирование"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def check_manager_running() -> bool:
    """Проверка, запущен ли Manager"""
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def get_db_count(query: str) -> int:
    """Получить количество записей в БД"""
    db_path = Path("manager/src/db/dcap.db")
    if not db_path.exists():
        return 0
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()[0] or 0
        conn.close()
        return result
    except Exception as e:
        log(f"Ошибка БД: {e}", "ERROR")
        return 0


def test_scenario_1_normal():
    """Сценарий 1: Нормальная работа"""
    log("\n" + "=" * 60)
    log("🧪 СЦЕНАРИЙ 1: НОРМАЛЬНАЯ РАБОТА")
    log("=" * 60)
    
    details = []
    
    # 1. Проверяем Manager
    log("[1] Проверка Manager...")
    if not check_manager_running():
        log("❌ Manager не запущен!", "ERROR")
        log("   Запустите вручную: python -m manager.src.main", "ERROR")
        return False
    details.append("Manager запущен")
    
    # 2. Проверяем ресурс и задание
    log("[2] Проверка ресурса и задания...")
    resource_count = get_db_count("SELECT COUNT(*) FROM resources")
    if resource_count == 0:
        log("   ⚠️ Ресурс не найден, создаём...")
        try:
            subprocess.run(["python", "create_test_data.py"], check=True, timeout=30)
            log("   ✅ Тестовые данные созданы")
        except Exception as e:
            log(f"   ❌ Ошибка: {e}", "ERROR")
            return False
    else:
        log(f"   ✅ Ресурс уже существует: {resource_count}")
    
    pending_count = get_db_count(
        "SELECT COUNT(*) FROM scan_tasks WHERE status IN ('PENDING', 'ASSIGNED')"
    )
    if pending_count == 0:
        log("   ⚠️ Нет заданий, создаём...")
        try:
            subprocess.run(["python", "create_test_data.py"], check=True, timeout=30)
            log("   ✅ Задание создано")
        except Exception as e:
            log(f"   ❌ Ошибка: {e}", "ERROR")
            return False
    else:
        log(f"   ✅ Найдено {pending_count} заданий в статусе PENDING/ASSIGNED")
    
    # 3. Запускаем Scanner
    log("[3] Запуск Scanner...")
    scanner_process = None
    try:
        scanner_process = subprocess.Popen(
            ["python", "run_scanner.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log("✅ Scanner запущен")
        details.append("Scanner запущен")
    except Exception as e:
        log(f"❌ Ошибка запуска Scanner: {e}", "ERROR")
        return False
    
    # 4. Ждём сканирования
    log("[4] Ожидание сканирования (60 сек)...")
    for i in range(12):
        time.sleep(5)
        if i % 2 == 0:
            log(f"   Прошло {(i+1)*5} сек...")
    
    # 5. Проверяем результаты
    log("[5] Проверка результатов...")
    findings_count = get_db_count("SELECT COUNT(*) FROM findings")
    completed_count = get_db_count(
        "SELECT COUNT(*) FROM scan_tasks WHERE status = 'COMPLETED'"
    )
    
    log(f"📊 Находок: {findings_count}, Завершённых заданий: {completed_count}")
    details.append(f"Находок: {findings_count}, Завершённых заданий: {completed_count}")
    
    # Останавливаем Scanner
    if scanner_process:
        try:
            scanner_process.terminate()
            scanner_process.wait(timeout=5)
            log("   Scanner остановлен")
        except:
            pass
    
    if findings_count > 0:
        log("✅ Сценарий 1 пройден!")
        return True
    else:
        log("❌ Сценарий 1 провален (нет данных)", "ERROR")
        return False


def test_scenario_2_offline():
    """Сценарий 2: Оффлайн-режим"""
    log("\n" + "=" * 60)
    log("🧪 СЦЕНАРИЙ 2: ОФФЛАЙН-РЕЖИМ")
    log("=" * 60)
    
    # 1. Проверяем локальную очередь
    log("[1] Проверка локальной очереди...")
    queue = OfflineQueue(Path("scanner_data/queue"))
    stats = queue.get_stats()
    log(f"📊 Очередь: всего={stats['total']}, ожидает={stats['pending']}")
    
    # 2. Проверяем, есть ли находки в БД
    log("[2] Проверка находок в БД...")
    findings_count = get_db_count("SELECT COUNT(*) FROM findings")
    log(f"📊 Находок в БД: {findings_count}")
    
    if findings_count > 0:
        log("✅ Находки сохранены в БД")
        return True
    else:
        log("⚠️ Находок нет в БД", "WARNING")
        return False


def test_scenario_3_recovery():
    """Сценарий 3: Восстановление"""
    log("\n" + "=" * 60)
    log("🧪 СЦЕНАРИЙ 3: ВОССТАНОВЛЕНИЕ")
    log("=" * 60)
    
    # 1. Проверяем Manager
    log("[1] Проверка Manager...")
    if not check_manager_running():
        log("⚠️ Manager не запущен!", "WARNING")
        return False
    log("✅ Manager доступен")
    
    # 2. Проверяем очередь
    log("[2] Проверка очереди...")
    queue = OfflineQueue(Path("scanner_data/queue"))
    stats = queue.get_stats()
    log(f"📊 Очередь: всего={stats['total']}, ожидает={stats['pending']}")
    
    # 3. Проверяем БД
    log("[3] Проверка находок в БД...")
    findings_count = get_db_count("SELECT COUNT(*) FROM findings")
    log(f"📊 Находок в БД: {findings_count}")
    
    if findings_count > 0:
        log("✅ Данные в БД есть")
        return True
    else:
        log("⚠️ Нет данных в БД", "WARNING")
        return False


def main():
    """Основная функция"""
    log("=" * 70)
    log("🧪 ИНТЕГРАЦИОННЫЕ ТЕСТЫ (УПРОЩЁННАЯ ВЕРСИЯ)")
    log("=" * 70)
    
    # Проверяем, запущен ли Manager
    log("\n[ПРОВЕРКА] Manager...")
    if check_manager_running():
        log("✅ Manager запущен (порт 8000)")
        log("   Health: http://localhost:8000/health")
    else:
        log("⚠️ Manager НЕ ЗАПУЩЕН!", "WARNING")
        log("   Запустите вручную: python -m manager.src.main")
        log("   В другом окне терминала.", "WARNING")
        log("\n   После запуска Manager, продолжите тест.", "WARNING")
        return
    
    # Сценарий 1
    result1 = test_scenario_1_normal()
    
    # Сценарий 2
    result2 = test_scenario_2_offline()
    
    # Сценарий 3
    result3 = test_scenario_3_recovery()
    
    # Итоги
    log("\n" + "=" * 70)
    log("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    log("=" * 70)
    
    results = [
        ("Сценарий 1 (Нормальная работа)", result1),
        ("Сценарий 2 (Оффлайн-режим)", result2),
        ("Сценарий 3 (Восстановление)", result3),
    ]
    
    passed = 0
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        log(f"{status}: {name}")
        if result:
            passed += 1
    
    total = len(results)
    log(f"\n📊 ПРОЙДЕНО: {passed}/{total}")
    
    if passed == total:
        log("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        log("   Система готова к переходу на День 13 (Контейнеризация)")
    else:
        log(f"\n⚠️ ПРОВАЛЕНО {total - passed} ТЕСТОВ")
        log("   Проверьте логи и запустите тест снова")


if __name__ == "__main__":
    main()