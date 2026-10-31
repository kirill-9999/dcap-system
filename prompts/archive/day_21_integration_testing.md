📋 ТЗ: ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ (ДЕНЬ 21)
Файл: prompts/tz/day_21_integration_testing.md

🎯 ЦЕЛЬ
Провести полное интеграционное тестирование всего Windows-стека DCAP. Проверить взаимодействие всех компонентов, API эндпоинтов, работу агентов и корректность сохранения данных.

📋 ОБЪЕМ ТЕСТИРОВАНИЯ
№	Компонент	Что проверяем
1	Manager API	Все эндпоинты (ресурсы, задачи, находки, сканеры, права, аудит)
2	Scanner	Регистрация, heartbeat, получение заданий, отправка результатов
3	Audit Agent	Регистрация, heartbeat, сбор событий, отправка в Manager
4	WebUI	Дашборд, страницы (ресурсы, находки, задания, доступ, аудит)
5	БД	Корректность сохранения данных во всех таблицах
6	E2E	Полный цикл: создание ресурса → сканирование → находки → аудит → отчет
📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ
Создать:
text
tests/integration/test_windows_stack.py     # Основной тест-скрипт
tests/integration/test_audit_agent.py       # Тесты агента аудита
tests/integration/test_scanner.py           # Тесты сканера
tests/integration/test_webui.py             # Тесты WebUI
tests/integration/conftest.py               # Фикстуры pytest
tests/integration/README.md                 # Инструкция по запуску
📋 ДЕТАЛЬНОЕ ТЗ
1. Структура тестов
text
tests/integration/
├── conftest.py                 # Фикстуры: db, client, manager_url
├── test_api.py                 # Тесты Manager API
├── test_scanner.py             # Тесты Scanner (регистрация, heartbeat, задания)
├── test_audit.py               # Тесты Audit Agent (регистрация, heartbeat, события)
├── test_webui.py               # Тесты WebUI (дашборд, страницы)
├── test_e2e.py                 # Сквозные тесты
└── README.md                   # Инструкция
2. Фикстуры (conftest.py)
python
import pytest
import requests
import sqlite3
from pathlib import Path

@pytest.fixture(scope="session")
def manager_url():
    """URL менеджера"""
    return "http://localhost:8000"

@pytest.fixture(scope="session")
def webui_url():
    """URL WebUI"""
    return "http://localhost:8001"

@pytest.fixture(scope="session")
def db_path():
    """Путь к БД"""
    return Path("manager/dcap.db")

@pytest.fixture
def db_conn(db_path):
    """Подключение к БД"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

@pytest.fixture(scope="session")
def test_resource(manager_url):
    """Создать тестовый ресурс"""
    resp = requests.post(
        f"{manager_url}/api/resources",
        params={"path": "D:/Projects/dcap-system/test_files", "type": "FILESYSTEM"}
    )
    data = resp.json()
    yield data["id"]
    # cleanup
    requests.delete(f"{manager_url}/api/resources/{data['id']}")
3. Тесты API (test_api.py)
python
import requests

def test_health(manager_url):
    """Проверка health-эндпоинта"""
    resp = requests.get(f"{manager_url}/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"

def test_resources_crud(manager_url):
    """CRUD ресурсов"""
    # CREATE
    resp = requests.post(
        f"{manager_url}/api/resources",
        params={"path": "D:/test", "type": "FILESYSTEM"}
    )
    assert resp.status_code == 200
    resource_id = resp.json()["id"]

    # READ
    resp = requests.get(f"{manager_url}/api/resources")
    assert resp.status_code == 200
    assert len(resp.json()) > 0

    # DELETE
    resp = requests.delete(f"{manager_url}/api/resources/{resource_id}")
    assert resp.status_code == 200

def test_permissions_api(manager_url):
    """Тест API прав доступа"""
    # Получить режим
    resp = requests.get(f"{manager_url}/api/permissions/mode")
    assert resp.status_code == 200
    assert "current_mode" in resp.json()

    # Синхронизация прав
    resp = requests.post(
        f"{manager_url}/api/permissions/sync",
        params={"resource_id": 1}
    )
    assert resp.status_code == 200
    assert "entries_saved" in resp.json()

def test_audit_api(manager_url):
    """Тест API аудита"""
    # Статистика
    resp = requests.get(f"{manager_url}/api/audit/stats")
    assert resp.status_code == 200
    assert "total" in resp.json()

    # Список событий
    resp = requests.get(f"{manager_url}/api/audit")
    assert resp.status_code == 200
    assert "events" in resp.json()
4. Тесты Scanner (test_scanner.py)
python
import requests
import time

def test_scanner_register(manager_url):
    """Регистрация сканера"""
    resp = requests.post(
        f"{manager_url}/api/scanner/register",
        json={"name": "test-scanner", "hostname": "TEST-PC"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data

def test_scanner_heartbeat(manager_url):
    """Heartbeat сканера"""
    # Сначала зарегистрировать
    resp = requests.post(
        f"{manager_url}/api/scanner/register",
        json={"name": "test-scanner-2", "hostname": "TEST-PC"}
    )
    scanner_id = resp.json()["id"]

    # Отправить heartbeat
    resp = requests.post(
        f"{manager_url}/api/scanner/heartbeat",
        json={"scanner_id": scanner_id, "status": "idle"}
    )
    assert resp.status_code == 200

def test_scanner_task_flow(manager_url, test_resource):
    """Полный цикл задания"""
    # Создать задание
    resp = requests.post(
        f"{manager_url}/api/resources/{test_resource}/scan"
    )
    assert resp.status_code == 200
    task_id = resp.json()["id"]

    # Получить задание (имитация Scanner)
    resp = requests.get(
        f"{manager_url}/api/scanner/tasks/pending",
        params={"scanner_id": 1}
    )
    if resp.status_code == 200:
        task = resp.json().get("task")
        if task:
            # Отправить результаты (имитация)
            results = {
                "findings": [
                    {"file_path": "test.txt", "category": "pii", "value": "test@mail.com", "confidence": 0.95}
                ],
                "failed_files": [],
                "stats": {"files_scanned": 1, "files_failed": 0}
            }
            resp = requests.post(
                f"{manager_url}/api/scanner/tasks/{task['id']}/results",
                json=results
            )
            assert resp.status_code == 200
5. Тесты Audit Agent (test_audit.py)
python
import requests
import time

def test_audit_agent_register(manager_url):
    """Регистрация агента аудита"""
    resp = requests.post(
        f"{manager_url}/api/audit/agents/register",
        json={"name": "test-audit-agent", "hostname": "TEST-PC"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "agent_id" in data

def test_audit_agent_heartbeat(manager_url):
    """Heartbeat агента аудита"""
    # Регистрация
    resp = requests.post(
        f"{manager_url}/api/audit/agents/register",
        json={"name": "test-audit-agent-2", "hostname": "TEST-PC"}
    )
    agent_id = resp.json()["agent_id"]

    # Heartbeat
    resp = requests.post(
        f"{manager_url}/api/audit/agents/heartbeat",
        json={"agent_id": agent_id, "status": "online"}
    )
    assert resp.status_code == 200

def test_audit_ingest_events(manager_url):
    """Прием событий от агента"""
    # Регистрация
    resp = requests.post(
        f"{manager_url}/api/audit/agents/register",
        json={"name": "test-audit-agent-3", "hostname": "TEST-PC"}
    )
    agent_id = resp.json()["agent_id"]

    # Отправить события
    events = [
        {"event_type": "read", "user": "test", "file_path": "D:\\test.txt"},
        {"event_type": "write", "user": "test", "file_path": "D:\\test2.txt"}
    ]
    resp = requests.post(
        f"{manager_url}/api/audit/events",
        json={"agent_id": agent_id, "events": events}
    )
    assert resp.status_code == 200
    assert resp.json()["saved"] == 2

    # Проверить, что события сохранились
    resp = requests.get(f"{manager_url}/api/audit")
    assert resp.status_code == 200
    assert len(resp.json()["events"]) >= 2
6. Сквозной тест (test_e2e.py)
python
import requests
import time

def test_e2e_full_cycle(manager_url, webui_url):
    """Полный сквозной тест"""
    results = []

    # 1. Проверка Manager
    resp = requests.get(f"{manager_url}/api/health")
    results.append(("Manager health", resp.status_code == 200))

    # 2. Проверка WebUI
    resp = requests.get(webui_url)
    results.append(("WebUI доступен", resp.status_code == 200))

    # 3. Регистрация агента аудита
    resp = requests.post(
        f"{manager_url}/api/audit/agents/register",
        json={"name": "e2e-agent", "hostname": "E2E-TEST"}
    )
    agent_id = resp.json().get("agent_id")
    results.append(("Audit agent registered", agent_id is not None))

    # 4. Отправка события
    if agent_id:
        resp = requests.post(
            f"{manager_url}/api/audit/events",
            json={"agent_id": agent_id, "events": [{"event_type": "read", "user": "e2e", "file_path": "D:\\e2e.txt"}]}
        )
        results.append(("Audit event ingested", resp.status_code == 200))

    # 5. Проверка аудита через WebUI API
    resp = requests.get(f"{webui_url}/api/audit")
    results.append(("WebUI audit API", resp.status_code == 200))

    # 6. Проверка статистики
    resp = requests.get(f"{webui_url}/api/audit/stats")
    results.append(("WebUI audit stats", resp.status_code == 200))

    # 7. Отчет
    resp = requests.post(
        f"{webui_url}/api/audit/report/preview",
        json={"days": 7}
    )
    results.append(("Audit report preview", resp.status_code == 200))

    # Итог
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"E2E тест: {passed}/{total} пройдено")

    # Очистка
    if agent_id:
        # Удалить тестового агента (через прямой SQL или API)
        pass

    assert passed == total, f"Не пройдено {total - passed} тестов"
✅ КРИТЕРИИ ПРИЕМКИ
№	Критерий	Статус
1	Все API эндпоинты Manager отвечают 200	⬜
2	WebUI доступен на :8001	⬜
3	Редирект :8000 → :8001 работает	⬜
4	Сканер регистрируется и отправляет heartbeat	⬜
5	Сканер получает задание	⬜
6	Агент аудита регистрируется	⬜
7	Агент аудита отправляет события	⬜
8	События сохраняются в БД	⬜
9	WebUI отображает события	⬜
10	Отчеты (Excel/PDF) генерируются	⬜
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Установить зависимости
pip install pytest requests

# 2. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 3. Запустить WebUI
python run_webui.py

# 4. Запустить Audit Agent (для тестов)
cd audit-agent
python main.py

# 5. Запустить Scanner (для тестов)
cd ..
python run_scanner.py

# 6. Запустить тесты
pytest tests/integration/ -v
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
dcap-system/
├── tests/
│   └── integration/
│       ├── conftest.py          # ✅ фикстуры
│       ├── test_api.py          # ✅ тесты API
│       ├── test_scanner.py      # ✅ тесты сканера
│       ├── test_audit.py        # ✅ тесты аудита
│       ├── test_webui.py        # ✅ тесты WebUI
│       ├── test_e2e.py          # ✅ сквозные тесты
│       └── README.md            # ✅ инструкция
└── ...
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_21_integration_testing
git add tests/
git commit -m "test: День 21 — интеграционное тестирование Windows-стека"
Разработчик (кодер), приступай! 🚀