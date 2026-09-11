# tests/chaos/conftest.py — фикстуры Chaos (День 40-41).
import subprocess

import pytest

COMPOSE_FILE = "docker-compose.test.yml"


def compose(*args):
    """Выполняет docker compose -f docker-compose.test.yml <args>."""
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class ComposeService:
    """Обёртка над одним сервисом тестового стека (stop/start/status)."""

    def __init__(self, service):
        self.service = service

    def stop(self):
        result = compose("stop", self.service)
        assert result.returncode == 0, result.stderr or result.stdout
        return result

    def start(self):
        result = compose("start", self.service)
        assert result.returncode == 0, result.stderr or result.stdout
        return result

    def is_running(self) -> bool:
        result = compose("ps", "-q", self.service)
        return bool(result.stdout.strip())


@pytest.fixture
def compose_stack():
    """Доступ к docker compose стеке (требует запущенного docker-compose.test.yml)."""
    pytest.importorskip("docker")

    def _service(name):
        return ComposeService(name)

    return _service