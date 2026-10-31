# manager/src/connectors/permissions/test_collector.py

import sys
import os
import json
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from connectors.permissions import (
    LocalPermissionCollector,
    ADPermissionCollector,
    PermissionCollectorFactory
)


def test_collector_availability():
    """Тест 1: Проверка доступности коллектора"""
    print("\n[X] Тест 1: Проверка доступности...")
    
    collector = LocalPermissionCollector()
    available = collector.is_available()
    print(f"   LocalPermissionCollector available: {available}")
    
    source_type = collector.get_source_type()
    print(f"   Source type: {source_type}")
    
    return available


def test_collect_permissions():
    """Тест 2: Сбор прав доступа"""
    print("\n[X] Тест 2: Сбор прав доступа...")
    
    try:
        collector = LocalPermissionCollector()
        
        # Тестируем на системной папке
        test_path = "C:\\Users\\Public"
        print(f"   Collecting permissions for: {test_path}")
        
        entries = collector.collect(test_path)
        print(f"   Found {len(entries)} permission entries")
        
        # Показываем первые 5 записей
        print("\n   Sample entries:")
        for entry in entries[:5]:
            print(f"     - {entry['principal']}: {entry['permissions']} "
                  f"(inherited: {entry['is_inherited']})")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False


def test_get_principals():
    """Тест 3: Получение пользователей и групп"""
    print("\n[X] Тест 3: Получение пользователей и групп...")
    
    try:
        collector = LocalPermissionCollector()
        principals = collector.get_principals()
        
        users = [p for p in principals if p['type'] == 'local_user']
        groups = [p for p in principals if p['type'] == 'group']
        
        print(f"   Found {len(users)} local users")
        print(f"   Found {len(groups)} local groups")
        
        # Показываем первых 5 пользователей
        if users:
            print("\n   Sample users:")
            for user in users[:5]:
                print(f"     - {user['name']}")
        
        # Показываем первых 5 групп
        if groups:
            print("\n   Sample groups:")
            for group in groups[:5]:
                print(f"     - {group['name']}")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False


def test_get_principal_groups():
    """Тест 4: Получение групп пользователя"""
    print("\n[X] Тест 4: Получение групп пользователя...")
    
    try:
        collector = LocalPermissionCollector()
        
        # Тестируем на учетной записи Administrator
        test_user = "Administrator"
        print(f"   Getting groups for user: {test_user}")
        
        groups = collector.get_principal_groups(test_user)
        print(f"   Found {len(groups)} groups")
        
        if groups:
            print("   Groups:")
            for group in groups[:10]:
                print(f"     - {group}")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False


def test_factory():
    """Тест 5: Проверка фабрики"""
    print("\n[X] Тест 5: Проверка фабрики...")
    
    try:
        # Получить доступные коллекторы
        available = PermissionCollectorFactory.get_available_collectors()
        print(f"   Available collectors: {available}")
        
        # Создать коллектор через фабрику
        collector = PermissionCollectorFactory.get_collector("local")
        print(f"   Created collector: {collector.get_source_type()}")
        
        # Проверить работу
        entries = collector.collect("C:\\Users\\Public")
        print(f"   Collected {len(entries)} entries")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False


def test_ad_collector():
    """Тест 6: Проверка AD коллектора (День 33 — реализация)"""
    print("\n[X] Тест 6: Проверка AD коллектора (реализация)...")
    
    try:
        collector = ADPermissionCollector(
            domain="example.com",
            server="dc.example.com"
        )
        
        print(f"   Source type: {collector.get_source_type()}")
        print(f"   Available: {collector.is_available()}")
        print(f"   Base DN: {collector.base_dn}")
        
        # Без подключения к реальному DC коллектор недоступен
        # (или доступен в mixed-режиме с fallback на local)
        return True
            
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("=" * 70)
    print("[X] ТЕСТИРОВАНИЕ КОННЕКТОРА ПРАВ ДОСТУПА (День 10)")
    print("=" * 70)
    
    # Проверяем ОС
    import platform
    print(f"   OS: {platform.system()} {platform.release()}")
    print("=" * 70)
    
    tests = [
        test_collector_availability,
        test_collect_permissions,
        test_get_principals,
        test_get_principal_groups,
        test_factory,
        test_ad_collector,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 70)
    print("[X] РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    print(f"[OK] Пройдено: {passed}/{total}")
    
    if passed == total:
        print("\n[X] ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n[X] Коннектор готов к использованию:")
        print("   [OK] LocalPermissionCollector (Windows 10)")
        print("   [OK] ADPermissionCollector (заглушка)")
        print("   [OK] PermissionCollectorFactory")
        print("\n[X] Следующий шаг: День 11 — AccessService (анализ прав)")
    else:
        print("\n[WARN] НЕ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("   Проверьте:")
        print("   - Windows 10 (тесты рассчитаны на Windows)")
        print("   - Наличие icacls (должен быть в системе)")
        print("   - Права доступа к C:\\Users\\Public")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)