# test_models.py (в корне проекта)

import sys
import os

# Добавляем путь к manager/src в PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
manager_src = os.path.join(project_root, 'manager', 'src')
sys.path.insert(0, manager_src)

# Теперь импорты работают
from db.models import (
    Resource, AccessEntry, PermissionChange, AccessAlert,
    Scanner, ScanTask, Finding, CatalogEntry
)
from db.session import init_db, get_db
from datetime import datetime
import json

def test_create_tables():
    """Тест 1: Создание таблиц"""
    print("[X] Тест 1: Создание таблиц...")
    try:
        init_db()
        print("[OK] Таблицы созданы успешно")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def test_resource_extension():
    """Тест 2: Расширение модели Resource"""
    print("\n[X] Тест 2: Расширение Resource...")
    try:
        resource = Resource(
            path="/test/path",
            owner="LOCAL\\admin",
            owner_sid="S-1-5-21-123456789-123456789-123456789-500",
            permissions={"admin": "full_control", "user": "read"},
            is_sensitive=True,
            classification_level="confidential",
            permission_source="local",
            domain="WORKGROUP"
        )
        
        # Проверяем, что все поля установлены
        assert resource.owner == "LOCAL\\admin"
        assert resource.is_sensitive is True
        assert resource.classification_level == "confidential"
        assert resource.permissions == {"admin": "full_control", "user": "read"}
        
        print("[OK] Модель Resource расширена корректно")
        print(f"   - Owner: {resource.owner}")
        print(f"   - Sensitive: {resource.is_sensitive}")
        print(f"   - Classification: {resource.classification_level}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def test_access_entry_model():
    """Тест 3: Создание AccessEntry"""
    print("\n[X] Тест 3: Создание AccessEntry...")
    try:
        entry = AccessEntry(
            resource_id=1,
            principal_type="local_user",
            principal_name="LOCAL\\john_doe",
            principal_sid="S-1-5-21-123456789-123456789-123456789-1000",
            permission_type="read",
            permission_source="direct",
            is_inherited=False,
            granted_by="LOCAL\\admin"
        )
        
        assert entry.principal_name == "LOCAL\\john_doe"
        assert entry.permission_type == "read"
        assert entry.is_inherited is False
        
        # Проверка to_dict
        data = entry.to_dict()
        assert data["principal_name"] == "LOCAL\\john_doe"
        assert data["permission_type"] == "read"
        
        print("[OK] Модель AccessEntry работает корректно")
        print(f"   - Principal: {entry.principal_name}")
        print(f"   - Permission: {entry.permission_type}")
        print(f"   - Inherited: {entry.is_inherited}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def test_permission_change_model():
    """Тест 4: Создание PermissionChange"""
    print("\n[X] Тест 4: Создание PermissionChange...")
    try:
        change = PermissionChange(
            resource_id=1,
            change_type="modify",
            principal_name="LOCAL\\john_doe",
            permission_type="read",
            old_value="read",
            new_value="write",
            changed_by="LOCAL\\admin",
            change_source="manual"
        )
        
        assert change.change_type == "modify"
        assert change.old_value == "read"
        assert change.new_value == "write"
        assert change.change_source == "manual"
        
        # Проверка to_dict
        data = change.to_dict()
        assert data["change_type"] == "modify"
        assert data["old_value"] == "read"
        
        print("[OK] Модель PermissionChange работает корректно")
        print(f"   - Change: {change.change_type}")
        print(f"   - From: {change.old_value} → To: {change.new_value}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def test_access_alert_model():
    """Тест 5: Создание AccessAlert"""
    print("\n[X] Тест 5: Создание AccessAlert...")
    try:
        alert = AccessAlert(
            resource_id=1,
            alert_type="excessive_permissions",
            severity="critical",
            principal_name="LOCAL\\john_doe",
            description="User has full control on sensitive folder",
            recommendation="Revoke full control, grant read-only",
            status="open"
        )
        
        assert alert.alert_type == "excessive_permissions"
        assert alert.severity == "critical"
        assert alert.status == "open"
        
        # Проверка to_dict
        data = alert.to_dict()
        assert data["alert_type"] == "excessive_permissions"
        assert data["severity"] == "critical"
        
        print("[OK] Модель AccessAlert работает корректно")
        print(f"   - Type: {alert.alert_type}")
        print(f"   - Severity: {alert.severity}")
        print(f"   - Status: {alert.status}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def test_relationships():
    """Тест 6: Проверка связей между моделями"""
    print("\n[X] Тест 6: Проверка связей...")
    try:
        # Создаем ресурс с дочерними объектами
        resource = Resource(
            path="/test/secure",
            owner="LOCAL\\admin",
            is_sensitive=True
        )
        
        # Добавляем AccessEntry через связь
        entry = AccessEntry(
            resource_id=1,  # В реальности будет ID из БД
            principal_type="user",
            principal_name="LOCAL\\test_user",
            permission_type="read"
        )
        resource.access_entries.append(entry)
        
        # Добавляем Alert
        alert = AccessAlert(
            alert_type="sensitive_access",
            severity="warning",
            description="Sensitive folder accessed",
            status="open"
        )
        resource.access_alerts.append(alert)
        
        # Проверяем, что связи работают
        assert len(resource.access_entries) == 1
        assert len(resource.access_alerts) == 1
        assert resource.access_entries[0].principal_name == "LOCAL\\test_user"
        
        print("[OK] Связи между моделями настроены корректно")
        print(f"   - AccessEntries: {len(resource.access_entries)}")
        print(f"   - AccessAlerts: {len(resource.access_alerts)}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def test_imports():
    """Тест 0: Проверка импортов"""
    print("[X] Тест 0: Проверка импортов...")
    try:
        from db.models import __all__
        print("[OK] Все модели импортируются корректно")
        print(f"   - Доступные модели: {', '.join(__all__)}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False

def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("[X] ТЕСТИРОВАНИЕ МОДЕЛЕЙ УПРАВЛЕНИЯ ДОСТУПОМ")
    print("=" * 60)
    print(f"Project root: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Manager src: {manager_src}")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_create_tables,
        test_resource_extension,
        test_access_entry_model,
        test_permission_change_model,
        test_access_alert_model,
        test_relationships,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("[X] РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    print(f"[OK] Пройдено: {passed}/{total}")
    
    if passed == total:
        print("[X] ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n[X] Модели готовы к использованию:")
        print("   [OK] Resource (расширен)")
        print("   [OK] AccessEntry")
        print("   [OK] PermissionChange")
        print("   [OK] AccessAlert")
    else:
        print("[WARN] НЕ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("   Проверьте настройки базы данных и зависимости")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)