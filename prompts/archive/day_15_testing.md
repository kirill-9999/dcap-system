📋 ТЗ: ТЕСТИРОВАНИЕ МОДУЛЯ УПРАВЛЕНИЯ ДОСТУПОМ (ДЕНЬ 15)
Файл: prompts/tz/day_15_testing.md

🎯 ЦЕЛЬ
Провести полное тестирование модуля управления доступом, реализованного в Днях 9-14. Проверить все API эндпоинты, WebUI страницу, корректность сохранения данных в БД и работу коллекторов прав.

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ/ИЗМЕНЕНИЯ
Создать:
text
test_access_management.py          # Основной тестовый скрипт
Проверить (не изменять, только убедиться, что существуют):
text
manager/src/api/permissions.py     # ✅ День 13
manager/src/services/access_service.py  # ✅ Дни 11-12
manager/src/connectors/permissions/local.py  # ✅ День 10
manager/src/db/models.py           # ✅ День 9
webui/static/index.html            # ✅ День 14 (страница "Управление доступом")
webui/static/js/app.js             # ✅ День 14
webui/static/css/style.css         # ✅ День 14
📋 ДЕТАЛЬНОЕ ТЗ
1. Создать тестовый скрипт test_access_management.py
Скрипт должен автоматически проверять все сценарии и выводить результат каждого теста.

1.1. Структура скрипта
python
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

# ... (далее тесты)
1.2. Тест 1: Проверка режима
python
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
1.3. Тест 2: Синхронизация прав
python
def test_sync():
    """Синхронизация прав для тестового ресурса"""
    log_info("Тест 2: Синхронизация прав...")
    
    resp = requests.post(f"{BASE_URL}/api/permissions/sync?resource_id={TEST_RESOURCE_ID}")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"
    
    data = resp.json()
    assert "entries_saved" in data, "Нет поля entries_saved"
    assert data["entries_saved"] > 0, f"Сохранено 0 записей: {data}"
    
    log_ok(f"Синхронизировано: {data['entries_saved']} записей")
    return data
1.4. Тест 3: Просмотр прав
python
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
1.5. Тест 4: Эффективные права
python
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
1.6. Тест 5: Избыточные права
python
def test_excessive_permissions():
    """Поиск избыточных прав"""
    log_info("Тест 5: Избыточные права...")
    
    resp = requests.get(f"{BASE_URL}/api/permissions/resources/{TEST_RESOURCE_ID}/excessive")
    assert resp.status_code == 200, f"Ошибка: {resp.text}"
    
    data = resp.json()
    assert "alerts" in data, "Нет поля alerts"
    
    log_ok(f"Найдено {len(data['alerts'])} избыточных прав")
    
    for alert in data["alerts"][:3]:
        log_info(f"  {alert['type']}: {alert['principal']} — {alert['permission']}")
    
    return data
1.7. Тест 6: Анализ наследования
python
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
1.8. Тест 7: Полный отчет
python
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
1.9. Тест 8: Алерты
python
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
1.10. Тест 9: Обновление статуса алерта
python
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
1.11. Тест 10: Переключение режима
python
def test_switch_mode():
    """Переключение режима сбора прав"""
    log_info("Тест 10: Переключение режима...")
    
    # Получаем текущий режим
    resp = requests.get(f"{BASE_URL}/api/permissions/mode")
    current = resp.json()["current_mode"]
    new_mode = "remote" if current == "local" else "local"
    
    log_info(f"Переключаем {current} → {new_mode}")
    
    resp = requests.post(
        f"{BASE_URL}/api/permissions/mode",
        json={"mode": new_mode}
    )
    assert resp.status_code == 200, f"Ошибка: {resp.text}"
    
    data = resp.json()
    assert data["current_mode"] == new_mode, f"Режим не изменился: {data['current_mode']}"
    
    log_ok(f"Режим: {data['current_mode']}")
    
    # Возвращаем обратно
    resp = requests.post(
        f"{BASE_URL}/api/permissions/mode",
        json={"mode": current}
    )
    assert resp.status_code == 200, f"Ошибка восстановления: {resp.text}"
    log_ok(f"Режим восстановлен: {current}")
    
    return True
1.12. Основная функция
python
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
    log_info("  3. Выбери ресурс D:\Projects\dcap-system\test_files")
    log_info("  4. Проверь таблицу прав, алерты и отчет")

if __name__ == "__main__":
    main()
2. Инструкция по ручному тестированию WebUI
Добавить в конец скрипта или отдельный файл WEBUI_TEST.md:

markdown
# Ручное тестирование WebUI (День 14)

## Проверка страницы "Управление доступом"

### Шаг 1: Запуск
```powershell
# Терминал 1
python -m uvicorn manager.src.main:app --port 8000

# Терминал 2
python run_webui.py
Шаг 2: Открыть страницу
Manager: http://localhost:8000

WebUI: http://localhost:8001

Шаг 3: Перейти на страницу "Управление доступом"
Кликнуть на "🔐 Доступ" в навигации

Шаг 4: Выбрать ресурс
Выбрать D:\Projects\dcap-system\test_files из выпадающего списка

Шаг 5: Проверить вкладки
Вкладка "📋 Права доступа"
□ Отображается таблица с правами
□ Фильтр по пользователю работает
□ Фильтр по типу работает
□ Отображается количество записей
Вкладка "⚠️ Алерты"
□ Отображаются алерты
□ Кнопки "Принять", "Решено", "Игнор" работают
□ Фильтры по severity и status работают
Вкладка "📊 Отчет"
□ Отображается полная статистика
□ Кнопка "Экспорт" скачивает JSON
Общее
□ Кнопка "Синхронизировать" работает
□ Кнопка "Переключить режим" работает
□ Отображается текущий режим (local/remote)
text

---

## ✅ КРИТЕРИИ ПРИЕМКИ

- [ ] Скрипт `test_access_management.py` создан
- [ ] Все 10 тестов проходят успешно
- [ ] Тест обновления алерта работает (статус меняется и восстанавливается)
- [ ] Тест переключения режима работает (меняется и восстанавливается)
- [ ] WebUI страница "Управление доступом" работает корректно
- [ ] Вкладки переключаются
- [ ] Фильтры работают
- [ ] Кнопки синхронизации и переключения режима работают
- [ ] Скрипт выводит понятные сообщения о прохождении тестов

---

## 🧪 ТЕСТОВЫЙ СЦЕНАРИЙ (ДЛЯ ПРОВЕРКИ)

```powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. В другом терминале запустить тесты
python test_access_management.py

# 3. Ожидаемый результат:
#    🧪 ТЕСТИРОВАНИЕ МОДУЛЯ УПРАВЛЕНИЯ ДОСТУПОМ
#    ✅ Manager доступен
#    ✅ Режим: local
#    ✅ Синхронизировано: N записей
#    ✅ Найдено N записей прав
#    ✅ Права для BUILTIN\Users: [...]
#    ✅ Найдено N избыточных прав
#    ✅ Наследуемых: N, прямых: N
#    ✅ Отчет получен
#    ✅ Найдено N алертов
#    ✅ Алерт X → acknowledged
#    ✅ Режим: remote
#    ✅ 🎉 Все тесты пройдены!
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
dcap-system/
├── test_access_management.py      # ✅ Создан
├── WEBUI_TEST.md                  # ✅ (опционально)
├── prompts/
│   ├── tz/
│   │   └── day_15_testing.md      # ✅ Это ТЗ
│   ├── archive/                   # ТЗ перемещаются сюда после завершения
│   └── reports/
│       └── day_15_report.md       # ✅ Отчет от агента
├── manager/
│   └── src/
│       ├── api/permissions.py     # ✅ День 13 (не изменять)
│       ├── services/access_service.py  # ✅ Дни 11-12 (не изменять)
│       └── db/models.py           # ✅ День 9 (не изменять)
└── webui/
    └── static/
        ├── index.html             # ✅ День 14 (не изменять)
        ├── js/app.js              # ✅ День 14 (не изменять)
        └── css/style.css          # ✅ День 14 (не изменять)
📝 ИНСТРУКЦИЯ ДЛЯ АГЕНТА
Важно для кодера (Open Code Desktop):

Создай файл test_access_management.py с кодом из ТЗ

Не изменяй существующие файлы (permissions.py, access_service.py, models.py)

Проверь, что все тесты проходят

Сформируй отчет в prompts/reports/day_15_report.md

Дай команду для коммита:

bash
git checkout -b feature/day_15_testing
git add test_access_management.py
git commit -m "test: День 15 — тестирование модуля управления доступом"
git push -u origin feature/day_15_testing
Разработчик (кодер), приступай! 🚀