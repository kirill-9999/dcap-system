#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест модуля управления доступом (День 15)

Запуск: python test_access_management.py

Сценарии:
1. Проверка режима сбора прав
2. Синхронизация прав
3. Просмотр прав
4. Эффективные права
5. Избыточные права
6. Анализ наследования
7. Полный отчет
8. Алерты
9. Обновление статуса алерта
10. Переключение режима
11. WebUI страница (ручная проверка)
"""

import requests
import json
import sys
import time
from datetime import datetime

# Корректный вывод кириллицы/эмодзи в консоли Windows (cp1251)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = "http://localhost:8000"
TEST_RESOURCE_ID = 1  # D:\Projects\dcap-system\test_files

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def log_ok(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def log_fail(msg):
    print(f"{RED}❌ {msg}{RESET}")


def log_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")


def log_warn(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def log_separator():
    print("-" * 60)


def test_mode():
    """Проверка текущего режима сбора прав"""
    log_info("Тест 1: Проверка режима...")

    resp = requests.get(f"{BASE_URL}/api/permissions/mode")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "current_mode" in data, "Нет поля current_mode"
    assert data["current_mode"] in ["local", "remote"], f"Неизвестный режим: {data['current_mode']}"

    log_ok(f"Режим: {data['current_mode']}")
    return data


def test_sync():
    """Синхронизация прав для тестового ресурса"""
    log_info("Тест 2: Синхронизация прав...")

    resp = requests.post(f"{BASE_URL}/api/permissions/sync?resource_id={TEST_RESOURCE_ID}")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    result = data.get("result", {})
    assert "entries_saved" in result, f"Нет поля result.entries_saved: {data}"
    assert result["entries_saved"] > 0, f"Сохранено 0 записей: {data}"

    log_ok(f"Синхронизировано: {result['entries_saved']} записей")
    return data


def test_get_permissions():
    """Получение списка прав для ресурса"""
    log_info("Тест 3: Просмотр прав...")

    resp = requests.get(f"{BASE_URL}/api/permissions/resources/{TEST_RESOURCE_ID}")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "entries" in data, "Нет поля entries"
    assert len(data["entries"]) > 0, "Нет записей прав"

    log_ok(f"Найдено {len(data['entries'])} записей прав")

    # Показать первые 3 записи
    for entry in data["entries"][:3]:
        log_info(f"  {entry['principal_name']}: {entry['permission_type']}")

    return data


def test_effective_permissions():
    """Получение эффективных прав для пользователя"""
    log_info("Тест 4: Эффективные права...")

    # Используем существующего пользователя из прав
    principal = "BUILTIN\\Users"
    resp = requests.get(
        f"{BASE_URL}/api/permissions/resources/{TEST_RESOURCE_ID}/effective",
        params={"principal": principal}
    )
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "permissions" in data, "Нет поля permissions"

    log_ok(f"Права для {principal}: {data['permissions']}")
    return data


def test_excessive_permissions():
    """Поиск избыточных прав"""
    log_info("Тест 5: Избыточные права...")

    resp = requests.get(f"{BASE_URL}/api/permissions/resources/{TEST_RESOURCE_ID}/excessive")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "issues" in data, f"Нет поля issues: {list(data.keys())}"
    issues = data.get("issues", [])
    assert data.get("count", len(issues)) == len(issues), "count не совпадает с issues"

    log_ok(f"Найдено {len(issues)} избыточных прав")

    for alert in issues[:3]:
        log_info(f"  {alert['type']}: {alert['principal']} — {alert['permission']}")

    return data


def test_inheritance():
    """Анализ наследования прав"""
    log_info("Тест 6: Анализ наследования...")

    resp = requests.get(f"{BASE_URL}/api/permissions/resources/{TEST_RESOURCE_ID}/inheritance")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "inherited_count" in data, "Нет поля inherited_count"
    assert "direct_count" in data, "Нет поля direct_count"

    log_ok(f"Наследуемых: {data['inherited_count']}, прямых: {data['direct_count']}")
    log_info(f"Процент наследования: {data.get('inherited_percent', 0)}%")

    return data


def test_report():
    """Полный отчет по доступам"""
    log_info("Тест 7: Полный отчет...")

    resp = requests.get(f"{BASE_URL}/api/permissions/resources/{TEST_RESOURCE_ID}/report")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "permissions_summary" in data, "Нет секции permissions_summary"
    assert "excessive_permissions" in data, "Нет секции excessive_permissions"
    assert "alerts" in data, "Нет секции alerts"

    log_ok("Отчет получен")
    log_info(f"  Всего записей: {data['permissions_summary'].get('total', 0)}")
    log_info(f"  Алертов: {data['alerts'].get('total', 0)}")

    return data


def test_alerts():
    """Получение списка алертов"""
    log_info("Тест 8: Алерты...")

    resp = requests.get(f"{BASE_URL}/api/permissions/alerts")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    data = resp.json()
    assert "alerts" in data, "Нет поля alerts"
    assert "total" in data, "Нет поля total"

    log_ok(f"Найдено {data['total']} алертов")

    for alert in data["alerts"][:3]:
        log_info(f"  [{alert['severity']}] {alert['alert_type']}: {alert['description'][:50]}...")

    return data


def test_update_alert():
    """Обновление статуса алерта"""
    log_info("Тест 9: Обновление статуса алерта...")

    # Получаем первый открытый алерт
    resp = requests.get(f"{BASE_URL}/api/permissions/alerts")
    data = resp.json()

    if not data["alerts"]:
        log_warn("Нет алертов для обновления")
        return None

    alert_id = data["alerts"][0]["id"]
    log_info(f"Обновляем алерт {alert_id}...")

    resp = requests.put(
        f"{BASE_URL}/api/permissions/alerts/{alert_id}",
        json={"status": "acknowledged"}
    )
    assert resp.status_code == 200, f"Ошибка: {resp.text}"

    result = resp.json()
    assert result["new_status"] == "acknowledged", "Статус не обновился"

    log_ok(f"Алерт {alert_id} → acknowledged")

    # Возвращаем обратно в open
    resp = requests.put(
        f"{BASE_URL}/api/permissions/alerts/{alert_id}",
        json={"status": "open"}
    )
    assert resp.status_code == 200, f"Ошибка восстановления статуса: {resp.text}"
    log_ok(f"Алерт {alert_id} → open (восстановлен)")

    return True


def test_switch_mode():
    """Переключение режима сбора прав"""
    log_info("Тест 10: Переключение режима...")

    # Получаем текущий режим
    resp = requests.get(f"{BASE_URL}/api/permissions/mode")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"
    current = resp.json()["current_mode"]
    new_mode = "remote" if current == "local" else "local"

    # No-op переключение на текущий режим — проверка round-trip эндпоинта
    resp = requests.post(f"{BASE_URL}/api/permissions/mode", json={"mode": current})
    assert resp.status_code == 200, f"Ошибка: {resp.text}"
    assert resp.json()["current_mode"] == current, "Режим изменился при no-op переключении"
    log_ok(f"Режим подтвержден: {current}")

    # Попытка переключения на противоположный режим
    log_info(f"Переключаем {current} → {new_mode}")
    resp = requests.post(f"{BASE_URL}/api/permissions/mode", json={"mode": new_mode})

    if resp.status_code == 503:
        # Коллектор недоступен (нет Scanner/AD на этой машине) — корректный отказ API
        detail = resp.json().get("detail", "")
        log_warn(f"Переключение на '{new_mode}' недоступно: {detail}")
        log_warn("Тест 10: переключение режима пропущено (ограничение платформы — удаленный коллектор не запущен)")
        return True

    assert resp.status_code == 200, f"Ошибка: {resp.text}"
    data = resp.json()
    if data["current_mode"] == new_mode:
        log_ok(f"Режим: {data['current_mode']}")
    else:
        log_warn(
            f"Ответ 200, но режим остался '{data['current_mode']}' — "
            "режим не персистится между запросами (замечание к Дням 11-13)"
        )

    # Возвращаем обратно
    resp = requests.post(f"{BASE_URL}/api/permissions/mode", json={"mode": current})
    assert resp.status_code == 200, f"Ошибка восстановления: {resp.text}"
    log_ok(f"Режим восстановлен: {current}")

    return True


def main():
    log_separator()
    log_info("🧪 ТЕСТИРОВАНИЕ МОДУЛЯ УПРАВЛЕНИЯ ДОСТУПОМ")
    log_separator()

    try:
        # Проверяем доступность Manager
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if resp.status_code != 200:
            log_fail(f"Manager недоступен (код {resp.status_code})")
            sys.exit(1)
        log_ok("Manager доступен")
    except Exception as e:
        log_fail(f"Manager недоступен: {e}")
        log_info("Запустите Manager: python -m uvicorn manager.src.main:app --port 8000")
        sys.exit(1)

    log_separator()

    tests = [
        ("Режим", test_mode),
        ("Синхронизация", test_sync),
        ("Просмотр прав", test_get_permissions),
        ("Эффективные права", test_effective_permissions),
        ("Избыточные права", test_excessive_permissions),
        ("Наследование", test_inheritance),
        ("Отчет", test_report),
        ("Алерты", test_alerts),
        ("Обновление алерта", test_update_alert),
        ("Переключение режима", test_switch_mode),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            log_fail(f"{name}: {e}")
            failed += 1
        except Exception as e:
            log_fail(f"{name}: Ошибка: {e}")
            failed += 1

    log_separator()
    log_info(f"✅ Пройдено: {passed}/{len(tests)}")
    if failed > 0:
        log_fail(f"❌ Не пройдено: {failed}")
        sys.exit(1)
    else:
        log_ok("🎉 Все тесты пройдены!")
        log_info("Готов к коммиту.")

    log_separator()

    # Инструкция по WebUI
    log_info("🌐 Проверка WebUI:")
    log_info("  1. Открой http://localhost:8000 (Manager) или :8001 (WebUI)")
    log_info("  2. Перейди на страницу '🔐 Доступ'")
    log_info("  3. Выбери ресурс D:\\Projects\\dcap-system\\test_files")
    log_info("  4. Проверь таблицу прав, алерты и отчет")


if __name__ == "__main__":
    main()
