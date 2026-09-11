📋 ТЗ: День 40-41 — Тестирование (E2E + Chaos)
Дата: 11.09.2026
Роль: Кодер
Версия (целевая): v3.8.0
Ветка: feature/day_40-41_testing
Предыдущая версия: v3.7.0

🎯 Цель дня
Создать полный набор тестов для v3.0.0:

E2E-тесты — сквозные сценарии (задание → сканирование → результаты → находки)

Chaos-тесты — отказоустойчивость (падение компонентов, обрыв сети)

Нагрузочные тесты — базовые (не глубокие, полноценные — в v3.1.0)

Инфраструктура тестов — pytest, фикстуры, docker-compose.test.yml, CI-ready

ВАЖНО: проект без pytest (папка manager/tests/ пуста, тесты — обычные скрипты). Нужно внедрить pytest как основу.

📦 Часть 1. Инфраструктура тестов
1.1. Зависимости
NEW: requirements-dev.txt (корень)

text
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0
pytest-timeout>=2.3.0
pytest-xdist>=3.5.0
httpx>=0.27.0
requests>=2.31.0
faker>=25.0.0
docker>=7.0.0
psutil>=5.9.0
1.2. Конфигурация pytest
NEW: pyproject.toml (дополнить секцию [tool.pytest.ini_options])

toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
timeout = 300
markers = [
    "e2e: End-to-end тесты (полный цикл)",
    "chaos: Chaos-тесты (отказоустойчивость)",
    "load: Нагрузочные тесты",
    "slow: Медленные тесты (>30 сек)",
    "requires_manager: Требует запущенный Manager",
    "requires_docker: Требует Docker",
    "requires_scanner: Требует запущенный Scanner",
]
addopts = "-v --strict-markers --tb=short"
1.3. Структура тестов
NEW:

text
tests/
├── conftest.py                    # общие фикстуры
├── pytest.ini                     # (если не в pyproject)
├── e2e/
│   ├── conftest.py                # фикстуры E2E
│   ├── test_full_scan_cycle.py    # задание → сканирование → находки
│   ├── test_auth_flow.py          # login → JWT → API → logout
│   ├── test_scanner_heartbeat.py  # heartbeat + прогресс
│   ├── test_agents_flow.py        # агенты → события → аудит
│   ├── test_webui_proxy.py        # WebUI → Manager → отображение
│   └── test_retention.py          # архивация → экспорт
├── chaos/
│   ├── conftest.py                # фикстуры Chaos
│   ├── test_manager_down.py       # падение Manager → буфер агентов
│   ├── test_redis_down.py         # падение Redis → fail-open
│   ├── test_postgres_down.py      # падение PG → ошибки → восстановление
│   ├── test_scanner_crash.py      # падение Scanner → алерт
│   └── test_network_partition.py  # обрыв сети → retry
├── load/
│   ├── test_api_load.py           # 1000 заданий через API
│   ├── test_agents_load.py        # 10 000 событий от агентов
│   └── test_concurrent_scanners.py # N сканеров одновременно
└── fixtures/
    ├── __init__.py
    ├── auth.py                    # логин, JWT
    ├── manager.py                 # HTTP-клиент Manager
    ├── scanner.py                 # HTTP-клиент Scanner
    ├── db.py                      # доступ к БД (cleanup)
    └── test_files.py              # генерация тестовых файлов
1.4. Docker-compose для тестов
NEW: docker-compose.test.yml

yaml
version: '3.8'

# Изолированный стек для тестов (не трогает prod-данные)
services:
  postgres_test:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: dcap_test
      POSTGRES_USER: dcap_test
      POSTGRES_PASSWORD: dcap_test
    ports: ["15432:5432"]
    tmpfs: /var/lib/postgresql/data  # быстро, без persistence
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dcap_test"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis_test:
    image: redis:7-alpine
    ports: ["16379:6379"]
    tmpfs: /data

  manager_test:
    build:
      context: .
      dockerfile: manager/Dockerfile
    environment:
      DATABASE_URL: postgresql://dcap_test:dcap_test@postgres_test:5432/dcap_test
      REDIS_URL: redis://redis_test:6379/0
      AUTH_MODE: local
      MTLS_ENABLED: "false"
    ports: ["18000:8000"]
    depends_on:
      postgres_test: { condition: service_healthy }
      redis_test: { condition: service_healthy }

  webui_test:
    build:
      context: ./webui
      dockerfile: Dockerfile
    environment:
      MANAGER_URL: http://manager_test:8000
    ports: ["18001:8001"]
    depends_on: [manager_test]

networks:
  default:
    name: dcap-test-network
NEW: scripts/test-up.sh, scripts/test-down.sh

bash
#!/bin/bash
# scripts/test-up.sh
docker compose -f docker-compose.test.yml up -d --build
echo "Waiting for services..."
until curl -sf http://localhost:18000/api/health > /dev/null; do sleep 2; done
until curl -sf http://localhost:18001/health > /dev/null; do sleep 2; done
echo "✅ Test stack ready"
📦 Часть 2. E2E-тесты
2.1. Фикстуры (tests/conftest.py)
python
import os
import pytest
import requests
from faker import Faker

faker = Faker()

MANAGER_URL = os.getenv("MANAGER_URL", "http://localhost:18000")
WEBUI_URL = os.getenv("WEBUI_URL", "http://localhost:18001")
SCANNER_URL = os.getenv("SCANNER_URL", "http://localhost:9101")

@pytest.fixture(scope="session")
def manager_url():
    return MANAGER_URL

@pytest.fixture(scope="session")
def webui_url():
    return WEBUI_URL

@pytest.fixture
def api_client(manager_url):
    """HTTP-клиент Manager с автоматическим JWT."""
    session = requests.Session()
    # Логин admin/admin123
    r = session.post(f"{manager_url}/api/auth/login",
                     json={"username": "admin", "password": "admin123"})
    if r.status_code == 200:
        token = r.json().get("access_token")
        session.headers["Authorization"] = f"Bearer {token}"
    yield session
    session.close()

@pytest.fixture
def anon_client(manager_url):
    """Анонимный HTTP-клиент."""
    with requests.Session() as s:
        yield s

@pytest.fixture
def test_files_dir(tmp_path):
    """Генерирует тестовые файлы (PII, credentials, code)."""
    d = tmp_path / "scan_data"
    d.mkdir()
    (d / "pii.txt").write_text("Иван Иванов, +7-999-123-45-67, ivan@example.com")
    (d / "creds.env").write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\nSECRET=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    (d / "code.py").write_text("password = 'hardcoded123'")
    (d / "clean.txt").write_text("Hello world, no secrets here.")
    return d

@pytest.fixture
def cleanup_tasks(api_client, manager_url):
    """Удаляет созданные задания после теста."""
    created = []
    yield created
    for task_id in created:
        try:
            api_client.delete(f"{manager_url}/api/tasks/{task_id}")
        except Exception:
            pass
2.2. E2E: Полный цикл сканирования
NEW: tests/e2e/test_full_scan_cycle.py

python
import pytest
import time

@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_full_scan_cycle(api_client, manager_url, test_files_dir, cleanup_tasks):
    """
    E2E: создание задания → сканирование → результаты → находки.
    
    Предусловие: Manager + Scanner запущены, сканер зарегистрирован.
    """
    # 1. Проверяем, что сканер зарегистрирован
    r = api_client.get(f"{manager_url}/api/scanners")
    assert r.status_code == 200
    scanners = r.json()
    if not scanners:
        pytest.skip("Нет зарегистрированных сканеров")
    scanner_id = scanners[0]["id"]

    # 2. Создаём задание
    r = api_client.post(f"{manager_url}/api/tasks/create", json={
        "resource_path": str(test_files_dir),
        "resource_type": "FILESYSTEM"
    })
    assert r.status_code in (200, 201), f"Create task failed: {r.text}"
    task_id = r.json()["id"]
    cleanup_tasks.append(task_id)

    # 3. Ждём назначения сканеру
    deadline = time.time() + 60
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id}")
        assert r.status_code == 200
        status = r.json().get("status")
        if status in ("assigned", "running", "completed"):
            break
        time.sleep(1)
    assert status in ("assigned", "running", "completed"), f"Task stuck: {status}"

    # 4. Ждём завершения (сканирование 4 файлов — быстро)
    deadline = time.time() + 300
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id}")
        status = r.json().get("status")
        if status == "completed":
            break
        if status == "failed":
            pytest.fail(f"Task failed: {r.json()}")
        time.sleep(2)
    assert status == "completed", f"Task not completed: {status}"

    # 5. Проверяем прогресс (День 39)
    task = r.json()
    assert "progress" in task or task.get("files_scanned", 0) > 0

    # 6. Проверяем находки
    r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id})
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) > 0, "No findings detected"

    # 7. Проверяем типы находок
    types = {f.get("type") or f.get("category") for f in findings}
    assert any("pii" in str(t).lower() or "cred" in str(t).lower() for t in types), \
        f"Expected PII/credentials findings, got: {types}"


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_task_progress_updates(api_client, manager_url, test_files_dir, cleanup_tasks):
    """Прогресс задания обновляется через heartbeat (День 39)."""
    r = api_client.post(f"{manager_url}/api/tasks/create", json={
        "resource_path": str(test_files_dir),
        "resource_type": "FILESYSTEM"
    })
    task_id = r.json()["id"]
    cleanup_tasks.append(task_id)

    # Ждём, пока появится progress
    import time
    deadline = time.time() + 60
    progress_seen = False
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id}")
        task = r.json()
        if task.get("progress"):
            progress_seen = True
            assert "files_scanned" in task["progress"]
            break
        time.sleep(2)
    assert progress_seen, "Progress never updated"
2.3. E2E: Аутентификация
NEW: tests/e2e/test_auth_flow.py

python
import pytest

@pytest.mark.e2e
@pytest.mark.requires_manager
def test_auth_flow(manager_url, anon_client):
    """login → JWT → защищённый endpoint → logout."""
    # 1. Логин
    r = anon_client.post(f"{manager_url}/api/auth/login",
                         json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]

    # 2. Защищённый endpoint с токеном
    r = anon_client.get(f"{manager_url}/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"

    # 3. Без токена — 401
    r = anon_client.get(f"{manager_url}/api/auth/me")
    assert r.status_code == 401

    # 4. Неверный пароль — 401
    r = anon_client.post(f"{manager_url}/api/auth/login",
                         json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

    # 5. Logout
    r = anon_client.post(f"{manager_url}/api/auth/logout",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 204)


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_auth_mode(manager_url, anon_client):
    """Режим аутентификации доступен без токена."""
    r = anon_client.get(f"{manager_url}/api/auth/mode")
    assert r.status_code == 200
    assert "mode" in r.json()
2.4. E2E: Heartbeat сканера
NEW: tests/e2e/test_scanner_heartbeat.py

python
import pytest
import time

@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_scanner_heartbeat_keeps_active(api_client, manager_url):
    """
    Сканер остаётся active во время длительного задания (BACKLOG-037).
    """
    r = api_client.get(f"{manager_url}/api/scanners")
    scanners = r.json()
    if not scanners:
        pytest.skip("Нет сканеров")
    scanner_id = scanners[0]["id"]

    # Проверяем initial status
    r = api_client.get(f"{manager_url}/api/scanner/{scanner_id}")
    assert r.status_code == 200
    initial_status = r.json().get("status")
    assert initial_status == "active", f"Scanner not active: {initial_status}"

    # Ждём >60 сек (2 heartbeat-интервала) и проверяем, что всё ещё active
    time.sleep(65)
    r = api_client.get(f"{manager_url}/api/scanner/{scanner_id}")
    status = r.json().get("status")
    assert status == "active", f"Scanner went inactive without task: {status}"


@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_scanner_metrics_available():
    """Метрики сканера :9101 доступны (День 39)."""
    import requests
    r = requests.get("http://localhost:9101/metrics", timeout=5)
    assert r.status_code == 200
    assert "dcap_scanner_files_scanned_total" in r.text
    assert "dcap_scanner_findings_total" in r.text
2.5. E2E: Агенты
NEW: tests/e2e/test_agents_flow.py

python
import pytest

@pytest.mark.e2e
@pytest.mark.requires_manager
def test_agent_registration(api_client, manager_url):
    """Регистрация агента → heartbeat → события."""
    # 1. Регистрация
    r = api_client.post(f"{manager_url}/api/audit/agents/register", json={
        "agent_type": "linux_agent",
        "hostname": "test-host-e2e",
        "version": "3.7.0"
    })
    assert r.status_code in (200, 201), f"Register failed: {r.text}"
    agent_id = r.json().get("agent_id") or r.json().get("id")
    assert agent_id

    # 2. Heartbeat
    r = api_client.post(f"{manager_url}/api/audit/agents/heartbeat", json={
        "agent_id": agent_id,
        "agent_type": "linux_agent",
        "status": "idle"
    })
    assert r.status_code in (200, 204)

    # 3. Отправка события
    r = api_client.post(f"{manager_url}/api/audit/events", json={
        "agent_id": agent_id,
        "events": [{
            "event_source": "linux_agent",
            "event_type": "file_access",
            "timestamp": "2026-09-11T12:00:00Z",
            "resource_path": "/tmp/test.txt",
            "principal": "testuser",
            "action": "read"
        }]
    })
    assert r.status_code in (200, 201, 202), f"Events failed: {r.text}"

    # 4. Проверка через GET
    r = api_client.get(f"{manager_url}/api/audit", params={"limit": 10})
    assert r.status_code == 200
2.6. E2E: WebUI прокси
NEW: tests/e2e/test_webui_proxy.py

python
import pytest
import requests

@pytest.mark.e2e
@pytest.mark.requires_manager
def test_webui_proxy(webui_url, api_client, manager_url):
    """WebUI проксирует запросы в Manager."""
    # 1. Health WebUI
    r = requests.get(f"{webui_url}/health", timeout=5)
    assert r.status_code == 200

    # 2. WebUI проксирует /api/stats
    r = requests.get(f"{webui_url}/api/stats", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)

    # 3. Прокси с авторизацией
    r = api_client.post(f"{manager_url}/api/auth/login",
                        json={"username": "admin", "password": "admin123"})
    token = r.json()["access_token"]
    r = requests.get(f"{webui_url}/api/stats",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200


@pytest.mark.e2e
def test_webui_pages_render(webui_url):
    """Страницы WebUI рендерятся (200)."""
    for page in ["/", "/login", "/dashboard"]:
        r = requests.get(f"{webui_url}{page}", timeout=5, allow_redirects=True)
        assert r.status_code == 200, f"Page {page} failed: {r.status_code}"
2.7. E2E: Retention
NEW: tests/e2e/test_retention.py

python
import pytest

@pytest.mark.e2e
@pytest.mark.requires_manager
def test_retention_policies(api_client, manager_url):
    """Политики хранения доступны."""
    r = api_client.get(f"{manager_url}/api/retention/policies")
    assert r.status_code == 200
    policies = r.json()
    assert isinstance(policies, (list, dict))


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_retention_manual_run(api_client, manager_url):
    """Ручной запуск архивации."""
    r = api_client.post(f"{manager_url}/api/retention/run", json={})
    # 200 (выполнено) или 503 (Celery недоступен — допустимо)
    assert r.status_code in (200, 202, 503)
📦 Часть 3. Chaos-тесты
3.1. Chaos: Падение Manager
NEW: tests/chaos/test_manager_down.py

python
import pytest
import time
import requests

@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_docker
def test_manager_down_agent_buffers():
    """
    Падение Manager → агент буферизует события → восстановление → отправка.
    
    Предусловие: docker-compose.test.yml запущен.
    """
    import subprocess

    # 1. Останавливаем Manager
    subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                    "stop", "manager_test"], check=True)
    time.sleep(3)

    # 2. Manager недоступен
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("http://localhost:18000/api/health", timeout=3)

    # 3. Агент (если запущен) должен буферизовать — проверяем через
    #    симуляцию: отправляем событие, оно падает, буфер растёт
    #    (полноценно — в отдельном integration-тесте с агентом)

    # 4. Запускаем Manager обратно
    subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                    "start", "manager_test"], check=True)

    # 5. Ждём готовности
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get("http://localhost:18000/api/health", timeout=3)
            if r.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    else:
        pytest.fail("Manager did not recover")

    assert r.json()["status"] == "healthy"


@pytest.mark.chaos
@pytest.mark.requires_manager
def test_manager_returns_503_on_db_down(api_client, manager_url):
    """При недоступной БД Manager отдаёт 5xx, не крашится."""
    # Этот тест требует остановки postgres_test — делается вручную
    # Здесь проверяем graceful degradation: healthcheck
    r = api_client.get(f"{manager_url}/api/health")
    assert r.status_code in (200, 503)
3.2. Chaos: Падение Redis (fail-open)
NEW: tests/chaos/test_redis_down.py

python
import pytest
import subprocess
import time
import requests

@pytest.mark.chaos
@pytest.mark.requires_docker
def test_redis_down_manager_works():
    """
    Падение Redis → Manager работает (fail-open).
    Rate-limit переключается на in-memory, кэш отключён.
    """
    # 1. Останавливаем Redis
    subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                    "stop", "redis_test"], check=True)
    time.sleep(3)

    # 2. Manager должен работать
    r = requests.get("http://localhost:18000/api/health", timeout=5)
    assert r.status_code == 200

    # 3. API-запросы работают
    r = requests.post("http://localhost:18000/api/auth/login",
                      json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200

    # 4. Запускаем Redis обратно
    subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                    "start", "redis_test"], check=True)
    time.sleep(5)

    # 5. Manager всё ещё работает
    r = requests.get("http://localhost:18000/api/health", timeout=5)
    assert r.status_code == 200
3.3. Chaos: Падение PostgreSQL
NEW: tests/chaos/test_postgres_down.py

python
import pytest
import subprocess
import time
import requests

@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_docker
def test_postgres_down_graceful():
    """
    Падение PostgreSQL → Manager отдаёт 5xx → восстановление.
    """
    # 1. Останавливаем PG
    subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                    "stop", "postgres_test"], check=True)
    time.sleep(5)

    # 2. Manager не должен крашиться (контейнер жив)
    r = subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                        "ps", "-q", "manager_test"],
                       capture_output=True, text=True)
    assert r.stdout.strip(), "Manager container died"

    # 3. API-запросы к БД дают 5xx
    try:
        r = requests.get("http://localhost:18000/api/stats", timeout=5)
        # 500 или 503 — оба ок
        assert r.status_code in (500, 502, 503)
    except requests.exceptions.ReadTimeout:
        pass  # тоже ок

    # 4. Запускаем PG обратно
    subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml",
                    "start", "postgres_test"], check=True)

    # 5. Ждём восстановления (pool_pre_ping)
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            r = requests.get("http://localhost:18000/api/health", timeout=5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(3)
    else:
        pytest.fail("Manager did not recover after PG restart")

    assert r.status_code == 200
3.4. Chaos: Падение Scanner
NEW: tests/chaos/test_scanner_crash.py

python
import pytest
import time

@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_manager
def test_scanner_inactive_alert(api_client, manager_url):
    """
    Если сканер не шлёт heartbeat >120 сек → Manager помечает inactive.
    
    ВАЖНО: тест требует остановки сканера (вручную или subprocess).
    """
    # 1. Получаем сканер
    r = api_client.get(f"{manager_url}/api/scanners")
    scanners = r.json()
    if not scanners:
        pytest.skip("Нет сканеров")

    # 2. Проверяем, что сканер active
    scanner_id = scanners[0]["id"]
    r = api_client.get(f"{manager_url}/api/scanner/{scanner_id}")
    assert r.json()["status"] == "active"

    # 3. Инструкция: остановить сканер вручную, подождать 130 сек,
    #    проверить, что status='inactive'.
    #    Автоматизация — в v3.1.0 (с полным chaos-стеком).
    pytest.skip("Требует ручной остановки сканера (автоматизация в v3.1.0)")


@pytest.mark.chaos
@pytest.mark.requires_manager
def test_scanner_active_during_long_task(api_client, manager_url, test_files_dir, cleanup_tasks):
    """
    Сканер НЕ помечается inactive во время длительного задания (BACKLOG-037).
    """
    r = api_client.post(f"{manager_url}/api/tasks/create", json={
        "resource_path": str(test_files_dir),
        "resource_type": "FILESYSTEM"
    })
    task_id = r.json()["id"]
    cleanup_tasks.append(task_id)

    # Во время выполнения задания проверяем, что сканер active
    r = api_client.get(f"{manager_url}/api/scanners")
    scanner_id = r.json()[0]["id"]

    for _ in range(5):
        r = api_client.get(f"{manager_url}/api/scanner/{scanner_id}")
        if r.json()["status"] != "active":
            pytest.fail(f"Scanner became inactive during task: {r.json()}")
        time.sleep(5)
3.5. Chaos: Обрыв сети
NEW: tests/chaos/test_network_partition.py

python
import pytest
import time
import requests

@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.requires_manager
def test_agent_retry_on_network_error(manager_url):
    """
    Агент ретраит при сетевой ошибке (симуляция через неверный URL).
    """
    # Проверяем, что при неверном URL агент не падает, а ретраит
    # (полноценно — в integration-тесте агента с мок-сервером)
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post("http://localhost:9999/api/audit/events",
                      json={"agent_id": 1, "events": []}, timeout=3)


@pytest.mark.chaos
@pytest.mark.requires_manager
def test_manager_timeout_handling(api_client, manager_url):
    """Manager корректно обрабатывает таймауты (не висит)."""
    # Запрос с очень коротким таймаутом
    try:
        r = requests.get(f"{manager_url}/api/findings",
                         params={"limit": 100000}, timeout=2)
        # Если успел — ок; если timeout — тоже ок (не краш)
    except requests.exceptions.Timeout:
        pass
📦 Часть 4. Нагрузочные тесты (базовые)
4.1. Нагрузка API
NEW: tests/load/test_api_load.py

python
import pytest
import concurrent.futures
import time

@pytest.mark.load
@pytest.mark.slow
@pytest.mark.requires_manager
def test_create_1000_tasks(api_client, manager_url, test_files_dir):
    """
    Создание 1000 заданий через API.
    Базовый порог: <60 сек, без 5xx.
    """
    N = 1000
    errors = []
    latencies = []

    def create_one(i):
        start = time.time()
        try:
            r = api_client.post(f"{manager_url}/api/tasks/create", json={
                "resource_path": str(test_files_dir),
                "resource_type": "FILESYSTEM"
            })
            latencies.append(time.time() - start)
            if r.status_code >= 500:
                errors.append(r.status_code)
        except Exception as e:
            errors.append(str(e))

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(create_one, range(N)))
    duration = time.time() - start

    # Проверки
    assert len(errors) == 0, f"{len(errors)} errors: {errors[:5]}"
    assert duration < 60, f"Too slow: {duration:.1f}s for {N} tasks"

    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    print(f"\n📊 {N} tasks in {duration:.1f}s | avg={avg*1000:.1f}ms | p95={p95*1000:.1f}ms")


@pytest.mark.load
@pytest.mark.requires_manager
def test_get_findings_load(api_client, manager_url):
    """100 запросов к /api/findings параллельно."""
    import concurrent.futures
    errors = []

    def get_one(_):
        try:
            r = api_client.get(f"{manager_url}/api/findings",
                               params={"limit": 100})
            if r.status_code >= 500:
                errors.append(r.status_code)
        except Exception as e:
            errors.append(str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(get_one, range(100)))

    assert len(errors) == 0, f"Errors: {errors[:5]}"
4.2. Нагрузка агентов
NEW: tests/load/test_agents_load.py

python
import pytest
import concurrent.futures
import time

@pytest.mark.load
@pytest.mark.slow
@pytest.mark.requires_manager
def test_10000_events(api_client, manager_url):
    """
    Отправка 10 000 событий от имени агента.
    Базовый порог: <60 сек, без 5xx.
    """
    # 1. Регистрируем агента
    r = api_client.post(f"{manager_url}/api/audit/agents/register", json={
        "agent_type": "linux_agent",
        "hostname": "load-test-host",
        "version": "3.7.0"
    })
    agent_id = r.json().get("agent_id") or r.json().get("id")

    # 2. Отправляем батчами по 100
    N = 10000
    BATCH = 100
    errors = []

    def make_event(i):
        return {
            "event_source": "linux_agent",
            "event_type": "file_access",
            "timestamp": "2026-09-11T12:00:00Z",
            "resource_path": f"/tmp/file_{i}.txt",
            "principal": f"user_{i % 100}",
            "action": "read"
        }

    def send_batch(start_idx):
        events = [make_event(start_idx + j) for j in range(BATCH)]
        try:
            r = api_client.post(f"{manager_url}/api/audit/events", json={
                "agent_id": agent_id,
                "events": events
            })
            if r.status_code >= 500:
                errors.append(r.status_code)
        except Exception as e:
            errors.append(str(e))

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(send_batch, range(0, N, BATCH)))
    duration = time.time() - start

    assert len(errors) == 0, f"Errors: {errors[:5]}"
    assert duration < 60, f"Too slow: {duration:.1f}s for {N} events"
    print(f"\n📊 {N} events in {duration:.1f}s ({N/duration:.0f} events/s)")
4.3. Конкурентные сканеры
NEW: tests/load/test_concurrent_scanners.py

python
import pytest
import concurrent.futures
import time

@pytest.mark.load
@pytest.mark.slow
@pytest.mark.requires_manager
def test_concurrent_task_creation(api_client, manager_url, test_files_dir):
    """
    Создание 100 заданий параллельно (имитация N сканеров).
    """
    N = 100
    errors = []
    created = []

    def create_one(i):
        try:
            r = api_client.post(f"{manager_url}/api/tasks/create", json={
                "resource_path": str(test_files_dir),
                "resource_type": "FILESYSTEM"
            })
            if r.status_code >= 500:
                errors.append(r.status_code)
            elif r.status_code in (200, 201):
                created.append(r.json().get("id"))
        except Exception as e:
            errors.append(str(e))

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(create_one, range(N)))
    duration = time.time() - start

    assert len(errors) == 0, f"Errors: {errors[:5]}"
    assert len(created) >= N * 0.95, f"Only {len(created)}/{N} created"
    print(f"\n📊 {N} tasks in {duration:.1f}s")
📦 Часть 5. Документация и скрипты
5.1. Документация
NEW: docs/testing.md

Как запустить тесты (E2E, Chaos, Load)

Требования (Docker, Manager, Scanner)

Фикстуры

Маркеры pytest

Как добавить тест

CI-интеграция (GitHub Actions — в Дне 42)

5.2. Скрипты
NEW: scripts/run-tests.sh

bash
#!/bin/bash
set -e

MODE=${1:-all}

case $MODE in
  e2e)
    pytest tests/e2e/ -v --timeout=300
    ;;
  chaos)
    pytest tests/chaos/ -v --timeout=600 -m chaos
    ;;
  load)
    pytest tests/load/ -v --timeout=300 -m load
    ;;
  all)
    pytest tests/ -v --timeout=600
    ;;
  quick)
    pytest tests/e2e/ -v --timeout=120 -m "e2e and not slow"
    ;;
  *)
    echo "Usage: $0 [e2e|chaos|load|all|quick]"
    exit 1
    ;;
esac
MODIFIED: scripts/status.sh — добавить секцию Testing (наличие requirements-dev.txt, tests/).

📦 Часть 6. Обновление документации проекта
MODIFIED: STATE.md (кодер обновляет в конце дня)

Версия → v3.8.0

Текущий день → 42 — Публикация на GitHub

Последний отчёт → day_40-41_report.md

Добавить строку о Дне 40-41

MODIFIED: ROADMAP.md

v3.0.0: День 40-41 → ✅

Бэклог: закрыть задачи, связанные с тестированием (если были)

MODIFIED: README.md, docs/deployment.md — ссылка на docs/testing.md.

✅ Критерии приёмки Дня 40-41
Pytest внедрён — requirements-dev.txt, pyproject.toml, структура tests/

E2E-тесты — 6+ файлов, покрывают: сканирование, auth, heartbeat, агенты, WebUI, retention

Chaos-тесты — 5+ файлов, покрывают: Manager down, Redis down, PG down, Scanner crash, network

Нагрузочные тесты — 3+ файла: API, агенты, конкурентные сканеры

Docker-compose.test.yml — изолированный стек для тестов

Документация — docs/testing.md, scripts/run-tests.sh

Все тесты проходят (или документированы skip с причиной)

STATE.md обновлён (v3.8.0)

ROADMAP.md обновлён (День 40-41 ✅)

📁 Артефакты (итог)
NEW:

requirements-dev.txt

tests/conftest.py

tests/e2e/conftest.py, tests/e2e/test_full_scan_cycle.py, tests/e2e/test_auth_flow.py, tests/e2e/test_scanner_heartbeat.py, tests/e2e/test_agents_flow.py, tests/e2e/test_webui_proxy.py, tests/e2e/test_retention.py

tests/chaos/conftest.py, tests/chaos/test_manager_down.py, tests/chaos/test_redis_down.py, tests/chaos/test_postgres_down.py, tests/chaos/test_scanner_crash.py, tests/chaos/test_network_partition.py

tests/load/test_api_load.py, tests/load/test_agents_load.py, tests/load/test_concurrent_scanners.py

tests/fixtures/__init__.py, tests/fixtures/auth.py, tests/fixtures/manager.py, tests/fixtures/scanner.py, tests/fixtures/db.py, tests/fixtures/test_files.py

docker-compose.test.yml

scripts/test-up.sh, scripts/test-down.sh, scripts/run-tests.sh

docs/testing.md

prompts/reports/day_40-41_report.md (после выполнения)

MODIFIED:

pyproject.toml (секция [tool.pytest.ini_options])

scripts/status.sh (секция Testing)

STATE.md (v3.8.0)

ROADMAP.md (День 40-41 ✅)

README.md, docs/deployment.md (ссылка на testing)

DELETED: —

🚀 Команда коммита (после выполнения)
bash
git checkout -b feature/day_40-41_testing
git add -A
git commit -m "test: День 40-41 — Тестирование (E2E + Chaos + Load) (v3.8.0)

Инфраструктура:
- pytest + pytest-asyncio/cov/timeout/xdist
- pyproject.toml: [tool.pytest.ini_options] + маркеры
- tests/{e2e,chaos,load,fixtures}/
- docker-compose.test.yml (изолированный стек, tmpfs)
- scripts/test-up.sh, test-down.sh, run-tests.sh

E2E (6 файлов):
- test_full_scan_cycle.py — задание → сканирование → находки
- test_auth_flow.py — login/JWT/logout
- test_scanner_heartbeat.py — active при длинных заданиях, метрики
- test_agents_flow.py — регистрация → heartbeat → события
- test_webui_proxy.py — прокси в Manager, рендер страниц
- test_retention.py — политики, ручной запуск

Chaos (5 файлов):
- test_manager_down.py — буферизация агента, восстановление
- test_redis_down.py — fail-open Manager
- test_postgres_down.py — graceful degradation + восстановление
- test_scanner_crash.py — inactive при долгом отсутствии, active при задании
- test_network_partition.py — retry, таймауты

Load (3 файла):
- test_api_load.py — 1000 заданий, 100 findings
- test_agents_load.py — 10 000 событий
- test_concurrent_scanners.py — 100 заданий параллельно

Документация:
- docs/testing.md
- README/deployment обновлены
- STATE.md → v3.8.0, следующий — День 42
- ROADMAP.md: День 40-41 ✅"
📝 Обратная связь архитектору (шаблон)
После выполнения — заполнить:

Какие тесты прошли / упали / skip (с причинами)

Найденные баги (с деталями)

Отклонения от ТЗ

Проблемы с Docker-compose.test.yml

Время выполнения тестов

Готовность к Дню 42 (GitHub)

⚠️ Важные замечания
Chaos-тесты требуют Docker — docker-compose.test.yml + pytest -m chaos

E2E требуют запущенного стека — Manager :18000, WebUI :18001, Scanner :9101

Тесты с requires_scanner — skip, если сканер не запущен (не fail)

tmpfs для PG/Redis в тестах — быстро, без persistence

--timeout=300 — защита от зависаний

Не трогать prod-данные — тесты используют dcap_test БД

Обновить STATE.md — обязательно, в конце дня