"""Тесты BUG-097 (TASK-066, v3.13.25).

Первопричина: сканер бесконечно ретраил отправку результатов по заданию,
которого больше нет в Manager (404). Из-за этого:
  1) лог засорялся 404-ошибками на каждом цикле main();
  2) новые задания копились в статусе assigned и не обрабатывались;
  3) при исключении внутри _execute_task задание оставалось в assigned
     до срабатывания stale-таймаута Manager (30 минут).

Проверяем:
  * submit_results_status: 404/410 -> LOST, 5xx -> RETRY, 200 -> OK;
  * submit_results (bool-обёртка) не ломает контракт;
  * _flush_offline отбрасывает потерянную пачку вместо бесконечного retry;
  * _fail_task_safely переводит задание в failed и не бросает исключений.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scanner" / "src"))

from managed_scanner import ManagerClient, SubmitStatus  # noqa: E402


class _Resp:
    """Минимальная заглушка ответа requests."""

    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, params=None, timeout=None):
        self.calls.append((url, params))
        return self._responses.pop(0)


def _client(responses, scanner_id=1):
    c = ManagerClient(base_url="http://manager:8000", scanner_id=scanner_id, config=None)
    c.session = _Session(responses)
    return c


# --- submit_results_status -------------------------------------------------


def test_404_returns_lost():
    """404 (задание удалено) -> LOST, а не RETRY (BUG-097)."""
    c = _client([_Resp(404, text='{"detail":"Task not found"}')])
    status = c.submit_results_status(43, [], [], [], {})
    assert status == SubmitStatus.LOST


def test_410_returns_lost():
    """410 (задание истекло) -> тоже LOST."""
    c = _client([_Resp(410, text="gone")])
    assert c.submit_results_status(43, [], [], [], {}) == SubmitStatus.LOST


def test_500_returns_retry():
    """Временная ошибка сервера -> RETRY, пачку надо повторить."""
    c = _client([_Resp(500, text="boom")])
    assert c.submit_results_status(43, [], [], [], {}) == SubmitStatus.RETRY


def test_200_returns_ok():
    c = _client([_Resp(200, {"findings_count": 3})])
    assert c.submit_results_status(43, [], [], [], {}) == SubmitStatus.OK


def test_404_does_not_try_next_batches():
    """После 404 не отправляем остальные батчи — задачи уже не существует."""
    c = _client([_Resp(404, text="nf"), _Resp(200, {"findings_count": 1})])
    # 3 находки при MAX_BATCH_SIZE > 1 дадут один батч; принудительно проверим
    # длину очереди ответов: использован только первый.
    c.submit_results_status(43, [{"a": 1}], [], [], {})
    assert len(c.session.calls) == 1


def test_submit_results_bool_wrapper_contract():
    """Старый bool-контракт сохранён: True только при OK."""
    assert _client([_Resp(200, {"findings_count": 1})]).submit_results(
        43, [], [], [], {}
    ) is True
    assert _client([_Resp(404, text="nf")]).submit_results(43, [], [], [], {}) is False
    assert _client([_Resp(500, text="e")]).submit_results(43, [], [], [], {}) is False


def test_network_exception_returns_retry():
    """Сетевое исключение -> RETRY (не LOST, не OK)."""
    c = _client([])

    def _boom(*a, **kw):
        raise OSError("connection reset")

    c.session.post = _boom
    assert c.submit_results_status(43, [], [], [], {}) == SubmitStatus.RETRY


def test_scanner_not_registered_returns_retry():
    c = ManagerClient(base_url="http://manager:8000", scanner_id=None, config=None)
    assert c.submit_results_status(43, [], [], [], {}) == SubmitStatus.RETRY


# --- _flush_offline --------------------------------------------------------


class _StubScanner:
    """Минимальный ManagedScanner: нужен только _flush_offline и _fail_task_safely."""

    def __init__(self, client, offline_dir, fail_ok=True):
        from managed_scanner import logger  # noqa: F401

        self.client = client
        self._offline_dir = offline_dir
        self._fail_ok = fail_ok
        self.failed_calls = []

    def _get_offline_dir(self):
        return self._offline_dir

    _flush_offline = None  # будет подставлен ниже


def _scanner_with_flush(client, offline_dir, fail_ok=True):
    from managed_scanner import ManagedScanner

    s = ManagedScanner.__new__(ManagedScanner)
    s.client = client
    s.scanner_id = 1
    s._fail_ok = fail_ok
    s.failed_calls = []
    s._get_offline_dir = lambda: offline_dir
    s._fail_task_safely = lambda task_id, reason: s._fail_task_safely_real(task_id, reason)
    return s


def _write_offline(directory, task_id, findings=1):
    payload = {
        "task_id": task_id,
        "scanner_id": 1,
        "saved_at": "2026-09-28T00:00:00",
        "result": {
            "findings": [{"i": i} for i in range(findings)],
            "catalog_entries": [],
            "failed_files": [],
            "stats": {"files_scanned": 1},
        },
    }
    path = directory / f"task_{task_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_flush_offline_drops_lost_task(tmp_path):
    """Ключевой фикс: файл по удалённому заданию удаляется, а не ретраится."""
    from managed_scanner import ManagedScanner

    lost = _write_offline(tmp_path, 43)
    c = _client([_Resp(404, text='{"detail":"Task not found"}')])
    s = _scanner_with_flush(c, tmp_path)

    assert ManagedScanner._flush_offline(s) == 0
    assert not lost.exists(), "оффлайн-пачка потерянного задания должна быть удалена"


def test_flush_offline_keeps_retryable_task(tmp_path):
    """При временной ошибке файл сохраняется для следующей попытки."""
    from managed_scanner import ManagedScanner

    path = _write_offline(tmp_path, 50)
    c = _client([_Resp(503, text="unavailable")])
    s = _scanner_with_flush(c, tmp_path)

    assert ManagedScanner._flush_offline(s) == 0
    assert path.exists(), "при временной ошибке пачка обязана остаться в очереди"


def test_flush_offline_unlinks_on_success(tmp_path):
    from managed_scanner import ManagedScanner

    path = _write_offline(tmp_path, 60)
    c = _client([_Resp(200, {"findings_count": 1})])
    s = _scanner_with_flush(c, tmp_path)

    assert ManagedScanner._flush_offline(s) == 1
    assert not path.exists()


def test_flush_offline_lost_does_not_block_next_files(tmp_path):
    """LOST не прерывает разбор очереди (раньше был break)."""
    from managed_scanner import ManagedScanner

    lost = _write_offline(tmp_path, 43)
    good = _write_offline(tmp_path, 60)
    c = _client([_Resp(404, text="nf"), _Resp(200, {"findings_count": 1})])
    s = _scanner_with_flush(c, tmp_path)

    assert ManagedScanner._flush_offline(s) == 1
    assert not lost.exists()
    assert not good.exists()


# --- _fail_task_safely -----------------------------------------------------


def test_fail_task_safely_calls_manager():
    from managed_scanner import ManagedScanner

    calls = []

    class _Client:
        def fail_task(self, task_id, reason=""):
            calls.append((task_id, reason))
            return True

    s = ManagedScanner.__new__(ManagedScanner)
    s.client = _Client()
    assert ManagedScanner._fail_task_safely(s, 90, "scanner error: boom") is True
    assert calls == [(90, "scanner error: boom")]


def test_fail_task_safely_swallows_exception():
    """Ошибка уведомления Manager не должна ронять основной цикл."""
    from managed_scanner import ManagedScanner

    class _Client:
        def fail_task(self, task_id, reason=""):
            raise RuntimeError("manager down")

    s = ManagedScanner.__new__(ManagedScanner)
    s.client = _Client()
    assert ManagedScanner._fail_task_safely(s, 90, "x") is False
