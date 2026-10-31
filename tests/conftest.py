# tests/conftest.py — общие фикстуры для всех групп тестов (День 40-41).
import os
import sys

import pytest

# Общие хелперы live в tests/fixtures/* — добавляем каталог в sys.path,
# чтобы конфигурация работала независимо от pytest rootdir.
sys.path.insert(0, os.path.dirname(__file__))

from fixtures.auth import login  # noqa: E402
from fixtures.manager import delete_task  # noqa: E402, F401
from fixtures.test_files import make_test_files  # noqa: E402

try:
    from faker import Faker

    _faker = Faker()
except Exception:  # pragma: no cover
    _faker = None

MANAGER_URL = os.getenv("MANAGER_URL", "http://localhost:18000")
WEBUI_PORT = os.getenv("WEBUI_PORT", "18001")
WEBUI_URL = os.getenv("WEBUI_URL", f"http://localhost:{WEBUI_PORT}")
SCANNER_URL = os.getenv("SCANNER_URL", "http://localhost:9101")


@pytest.fixture(scope="session")
def manager_url():
    return MANAGER_URL


@pytest.fixture(scope="session")
def webui_url():
    return WEBUI_URL


@pytest.fixture(scope="session")
def scanner_url():
    return SCANNER_URL


@pytest.fixture
def api_client(manager_url):
    """HTTP-клиент Manager с автоматическим JWT (admin/admin123)."""
    session = login(manager_url)
    yield session
    session.close()


@pytest.fixture
def anon_client():
    """Анонимный HTTP-клиент (без токена)."""
    with pytest.importorskip("requests").Session() as s:
        yield s


@pytest.fixture
def test_files_dir(tmp_path):
    """Генерирует тестовые файлы (PII, credentials, code)."""
    from fixtures.test_files import make_test_files as make

    return make(tmp_path / "scan_data")


@pytest.fixture
def cleanup_tasks(api_client, manager_url):
    """Удаляет созданные задания после теста."""
    from fixtures.db import cleanup_tasks as cleanup

    created = []
    yield created
    cleanup(api_client, manager_url, created)


@pytest.fixture
def faker_data():
    """Лёгкий генератор тестовых строк (без зависимости от Faker)."""
    if _faker is not None:
        return _faker
    return None


# ============================================================
# Авто-skip по маркерам (ТЗ: тесты с requires_* — skip, не fail)
# ============================================================
import shutil  # noqa: E402

import requests as _requests  # noqa: E402

_manager_ok = None
_scanner_ok = None


def _manager_available(url: str = MANAGER_URL) -> bool:
    global _manager_ok
    if _manager_ok is None:
        try:
            _manager_ok = _requests.get(f"{url}/api/health", timeout=3).status_code == 200
        except Exception:
            _manager_ok = False
    return _manager_ok


def _scanner_available(url: str = SCANNER_URL) -> bool:
    global _scanner_ok
    if _scanner_ok is None:
        try:
            _scanner_ok = _requests.get(f"{url}/metrics", timeout=3).status_code == 200
        except Exception:
            _scanner_ok = False
    return _scanner_ok


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def pytest_runtest_setup(item):
    """Пропускаем тесты, если не удовлетворены условия маркеров."""
    marks = {m.name for m in item.iter_markers()}
    if {"e2e", "load", "chaos"} & marks or "requires_manager" in marks:
        if not _manager_available():
            pytest.skip("Manager не запущен (тестовый стек :18000)")
    if "requires_scanner" in marks:
        if not _scanner_available():
            pytest.skip("Scanner не запущен (:9101)")
    if "requires_docker" in marks:
        if not _docker_available():
            pytest.skip("Docker недоступен")