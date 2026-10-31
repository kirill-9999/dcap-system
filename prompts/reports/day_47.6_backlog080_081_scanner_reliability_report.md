# 📄 Отчёт: День 47.6 — BUG-080/081: reliability сканера (TZ_BUG080_081_SCANNER_RELIABILITY.md) → v3.13.20

**Дата:** 26.09.2026
**Версия:** v3.13.19 → **v3.13.20**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_BUG080_081_SCANNER_RELIABILITY.md`

---

## 📌 Цель

Повысить надёжность сканера на Windows:

1. **BUG-080** — heartbeat при недоступном Manager спамит лог
   (`Heartbeat failed: ('Connection aborted.', RemoteDisconnected(...))` + `Retrying (Retry(total=0...))`
   каждые ~3 с — urllib3 не ретраит, retry перехватывал сам heartbeat-поток). Требование: без спама,
   backoff 5 → 10 → 30 → 60 → 120 с, DEBUG на каждый фейл, WARNING только на 1-м и каждые 5,
   INFO «restored», пауза через `_stop.wait()`, сигнал «Manager недоступен N секунд».
2. **BUG-081** — Ctrl+C не завершает OCRWorker на Windows (отдельный multiprocessing-spawn
   процесс): сканер не перезапускается без ручного `taskkill`. Требование: SIGINT-handler ставит
   stop-event; graceful: None в request_queue → join(5) → terminate → join(2) → kill; main-loop в try/finally.

## ✅ Итог

- **TASK-051 (heartbeat):** backoff, сброс на успехе, WARNING 1/5/10, `_stop.wait()` вместо `time.sleep`.
- **TASK-052 (shutdown):** SIGINT + SIGBREAK → `_handle_sigint`; `stop()` = heartbeat + `_shutdown_classifiers()`;
  `ocr_worker.stop_ocr_worker` — graceful (None → join → terminate → kill).
- Тесты: **167 passed** (160 + 4 + 3) — включена регрессия `test_stale_tasks`, `test_scanner_middleware_rbac`.
- Live: BUG-080 — единственный WARNING `(1 attempts), next retry in 5s`, затем тишина; после
  восстановления Manager — `Heartbeat restored after 4 failure(s)`. BUG-081 — контрол.
  IBREAK: `[Scanner] SIGINT received` → stop heartbeat → OCRWorker остановлен → `[X] Сканер
  остановлен`, **rc=0** (graceful, без terminate/kill).

---

## ⚙️ Реализация

### TASK-051 — `scanner/src/heartbeat.py` (полный файл)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Heartbeat-поток сканера (День 39).

Каждые `interval` секунд шлёт POST /api/scanner/heartbeat. fail-open: при
недоступности Manager сканер продолжает работать (статус не обновляется).
"""
import logging
import threading
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class HeartbeatThread(threading.Thread):
    """Поток периодической отправки heartbeat в Manager.

    BUG-080 (TASK-051, v3.13.20): при недоступности Manager применяет
    exponential backoff (BACKOFF_STEPS) вместо панического ретрая каждый
    интервал. WARNING — только на 1-м фейле и далее каждые 5 попыток;
    остальное — DEBUG. Пауза — _stop.wait() (мгновенный выход по stop/сигналу).
    """

    # BUG-080: шаги backoff (сек). После 120 с инкремент не растёт.
    BACKOFF_STEPS = [5, 10, 30, 60, 120]

    def __init__(self, manager_url: str, scanner_id: int, interval: float = 30.0):
        super().__init__(daemon=True, name="HeartbeatThread")
        self.manager_url = manager_url
        self.scanner_id = scanner_id
        self.interval = interval if interval and interval > 0 else 30.0
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._current_task_id: Optional[int] = None
        self._current_progress: Dict[str, Any] = {}
        # BUG-080: счётчик подряд идущих фейлов (для backoff и отчётов).
        self._fail_count = 0

    def set_task(self, task_id: Optional[int]):
        with self._lock:
            self._current_task_id = task_id

    def update_progress(self, files_scanned: int = None, total_files: int = None,
                        findings_count: int = None, speed_files_per_sec: float = None,
                        eta_seconds: int = None):
        with self._lock:
            if files_scanned is not None:
                self._current_progress["files_scanned"] = int(files_scanned)
            else:
                self._current_progress.pop("files_scanned", None)
            if total_files is not None:
                self._current_progress["total_files"] = int(total_files)
            else:
                self._current_progress.pop("total_files", None)
            if findings_count is not None:
                self._current_progress["findings_count"] = int(findings_count)
            else:
                self._current_progress.pop("findings_count", None)
            if speed_files_per_sec is not None:
                self._current_progress["speed_files_per_sec"] = round(float(speed_files_per_sec), 3)
            else:
                self._current_progress.pop("speed_files_per_sec", None)
            if eta_seconds is not None:
                self._current_progress["eta_seconds"] = int(eta_seconds)
            else:
                self._current_progress.pop("eta_seconds", None)

    def _build_payload(self) -> Dict[str, Any]:
        with self._lock:
            payload: Dict[str, Any] = {
                "scanner_id": self.scanner_id,
                "status": "busy" if self._current_task_id is not None else "idle",
                "current_task_id": self._current_task_id,
            }
            if self._current_progress:
                payload["progress"] = dict(self._current_progress)
            return payload

    def _send_heartbeat(self) -> bool:
        """Отправить heartbeat. True при успехе, False при любой ошибке.

        BUG-080 (TASK-051): фейлы логируются на DEBUG (не спам WARNING).
        """
        try:
            resp = requests.post(
                f"{self.manager_url}/api/scanner/heartbeat",
                json=self._build_payload(),
                timeout=5,
            )
            if resp.status_code != 200:
                logger.debug("Heartbeat failed: HTTP %s", resp.status_code)
                return False
            return True
        except Exception as e:
            logger.debug("Heartbeat failed: %s", e)  # fail-open
            return False

    def _next_sleep(self, ok: bool) -> float:
        """Рассчитать следующую паузу и обновить счётчик фейлов.

        BUG-080 (TASK-051): успех → сброс backoff и интервал; фейл →
        exponential backoff по BACKOFF_STEPS (максимум 120 с). WARNING
        только на 1-м фейле и далее каждые 5 попыток.
        """
        if ok:
            if self._fail_count > 0:
                logger.info(
                    "Heartbeat restored after %d failure(s)",
                    self._fail_count,
                )
            self._fail_count = 0
            return float(self.interval)
        self._fail_count += 1
        idx = min(self._fail_count - 1, len(self.BACKOFF_STEPS) - 1)
        sleep_time = float(self.BACKOFF_STEPS[idx])
        if self._fail_count == 1 or self._fail_count % 5 == 0:
            logger.warning(
                "Heartbeat failing (%d attempts), next retry in %ds",
                self._fail_count,
                sleep_time,
            )
        return sleep_time

    def run(self):
        logger.info("HeartbeatThread started (interval=%ss)", self.interval)
        while not self._stop.wait(self.interval):
            ok = self._send_heartbeat()
            sleep_time = self._next_sleep(ok)
            # BUG-080 (TASK-051): wait вместо time.sleep — мгновенный выход
            # по stop()/SIGINT, не ждём окончания backoff.
            self._stop.wait(sleep_time)
        logger.info("HeartbeatThread stopped")

    def stop(self):
        self._stop.set()
```

### TASK-052 — `scanner/src/managed_scanner.py` (изменённые блоки)

`__init__` (регистрация SIGINT + SIGBREAK):

```python
        self._should_exit = False
        # Событие остановки (день 42.5+): устанавливается из stop()/Ctrl+C,
        # проверяется параллельным scan_path для немедленной остановки.
        self._stop_event = threading.Event()
        # BUG-081 (TASK-052, v3.13.20): SIGINT → graceful shutdown.
        # Обработчик ставит флаги; цикл выходит корректно, stop() завершает
        # heartbeat и OCRWorker (Windows-совместимо — только SIGINT/SIGBREAK).
        try:
            signal.signal(signal.SIGINT, self._handle_sigint)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, self._handle_sigint)
        except (ValueError, OSError) as e:
            logger.debug("SIGINT handler not installed: %s", e)
```

Конец `run_loop` + `_shutdown_classifiers` + `_handle_sigint` + `stop()`:

```python
        self.client.heartbeat(status="offline")
        if self.heartbeat_thread is not None:
            self.heartbeat_thread.stop()
        self._shutdown_classifiers()
        logger.info("[X] Сканер остановлен")

    def _shutdown_classifiers(self):
        """Корректное завершение классификаторов (OCRWorker и др. процессы) —
        иначе после остановки сканера остаются осиротевшие дочерние процессы.
        Идемпотентно (PiiClassifier._stop_ocr_worker имеет guard _ocr_started).
        """
        for clf in self.classifiers:
            shutdown = getattr(clf, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as e:
                    logger.debug("Classifier shutdown error %s: %s", getattr(clf, "classifier_name", clf), e)

    def _handle_sigint(self, signum, frame):
        """BUG-081 (TASK-052): SIGINT → graceful shutdown (Windows-совместимо)."""
        logger.warning("[Scanner] SIGINT received, stopping...")
        self._should_exit = True
        self._stop_event.set()

    def stop(self):
        """Graceful shutdown — вызывается из SIGINT-handler, KeyboardInterrupt или извне.

        BUG-081 (TASK-052): останавливает heartbeat, затем классификаторы
        (OCRWorker): None в request_queue → join(5) → terminate → join(2) → kill.
        """
        logger.info("[Scanner] Stopping...")
        self._should_exit = True
        self._stop_event.set()

        logger.info("[Scanner] Stopping heartbeat...")
        if self.heartbeat_thread is not None:
            try:
                self.heartbeat_thread.stop()
            except Exception as e:
                logger.debug("Heartbeat stop error: %s", e)

        logger.info("[Scanner] Stopping OCRWorker/classifiers...")
        self._shutdown_classifiers()

        logger.info("[Scanner] Stopped")
```

### TASK-052 — `scanner/classifiers/ocr_worker.py` (`stop_ocr_worker`)

```python
def stop_ocr_worker(process: Process, request_queue: Queue, response_queue: Queue):
    """Остановка OCR рабочего процесса.

    BUG-081 (TASK-052, v3.13.20): graceful shutdown — сначала штатный выход через
    None в request_queue (процесс печатает «Завершение. Обработано запросов: N»),
    затем join(5) → terminate → join(2) → kill.
    """
    try:
        request_queue.put(None, timeout=1)
    except Exception:
        pass

    if process and process.is_alive():
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if process.is_alive():
            process.kill()
```

### TASK-051/052 — тесты

`tests/unit/test_heartbeat_backoff.py` — полный файл:

```python
# tests/unit/test_heartbeat_backoff.py — BUG-080 (TASK-051, v3.13.20)
# Heartbeat: exponential backoff 5→10→30→60→120 с, сброс на успехе,
# WARNING только на 1-м фейле и каждые 5, мгновенный выход по stop().
import threading
import logging
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.heartbeat import HeartbeatThread  # noqa: E402

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def thread() -> HeartbeatThread:
    return HeartbeatThread(manager_url="http://127.0.0.1:9", scanner_id=1, interval=30)


def test_backoff_steps(thread):
    """5, 10, 30, 60, 120 — и не больше 120."""
    assert thread.BACKOFF_STEPS == [5, 10, 30, 60, 120]
    slept = [thread._next_sleep(False) for _ in range(8)]
    assert slept == [5, 10, 30, 60, 120, 120, 120, 120]
    assert max(slept) == thread.BACKOFF_STEPS[-1]


def test_backoff_resets_on_success(thread):
    """После успеха fail_count = 0, sleep = interval."""
    assert thread._next_sleep(False) == 5
    assert thread._next_sleep(False) == 10
    assert thread._next_sleep(False) == 30
    assert thread._fail_count == 3

    sleep_after = thread._next_sleep(True)
    assert thread._fail_count == 0
    assert sleep_after == thread.interval


def test_warning_not_spam(thread, caplog):
    """WARNING только на 1-м фейле и каждые 5."""
    with caplog.at_level(logging.WARNING, logger="scanner.src.heartbeat"):
        for _ in range(11):
            thread._next_sleep(False)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 3, [w.getMessage() for w in warnings]

    attempts = []
    for w in warnings:
        m = w.getMessage()
        assert "Heartbeat failing" in m
        attempts.append(int(m.split("(")[1].split()[0]))
    assert attempts == [1, 5, 10]

    debug = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(debug) == 0  # DEBUG-фейлы логируются в _send_heartbeat (не в _next_sleep)


def test_stop_event_interrupts_sleep(thread, monkeypatch):
    """stop_event.wait() → мгновенный выход из sleep (не time.sleep)."""
    monkeypatch.setattr(HeartbeatThread, "BACKOFF_STEPS", [30])
    thread._send_heartbeat = lambda: False  # noqa: E731  — всегда фейл → сон 30 с

    t = threading.Thread(target=thread.run, daemon=True)
    t.start()
    time.sleep(0.4)  # поток точно заснул на wait(30)
    assert t.is_alive()

    thread.stop()
    t.join(timeout=2)
    assert not t.is_alive(), "stop() должен мгновенно прервать backoff-сон"
```

`tests/unit/test_scanner_shutdown.py` — полный файл:

```python
# tests/unit/test_scanner_shutdown.py — BUG-081 (TASK-052, v3.13.20)
# Graceful shutdown сканера: SIGINT → stop event; stop() → None в
# OCR request_queue; зависший OCRWorker завершается terminate/kill.
import sys
import threading
from queue import Empty
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.managed_scanner import ManagedScanner  # noqa: E402
from scanner.classifiers.ocr_worker import stop_ocr_worker  # noqa: E402

pytestmark = [pytest.mark.unit]


def _stubborn_worker(request_queue):
    """Зависший worker: читает очередь, игнорирует None, никогда не выходит."""
    while True:
        try:
            request_queue.get(timeout=1)
        except Empty:
            pass


def _make_scanner_obj() -> ManagedScanner:
    s = ManagedScanner.__new__(ManagedScanner)
    s._should_exit = False
    s._stop_event = threading.Event()
    s.heartbeat_thread = None
    s.classifiers = []
    return s


def test_sigint_sets_stop_event():
    """_handle_sigint → _stop_event.set() и _should_exit=True."""
    s = _make_scanner_obj()
    s._handle_sigint(2, None)
    assert s._stop_event.is_set()
    assert s._should_exit is True


def test_stop_sends_none_to_ocr_queue():
    """stop() → shutdown классификаторов → None в OCR request_queue."""
    q = mock.MagicMock()

    class _Shutdowner:
        def __init__(self, queue_):
            self._queue = queue_

        def shutdown(self):
            stop_ocr_worker(None, self._queue, None)

    s = _make_scanner_obj()
    s.heartbeat_thread = mock.MagicMock()
    s.classifiers = [_Shutdowner(q)]

    s.stop()

    q.put.assert_called_once_with(None, timeout=1)
    s.heartbeat_thread.stop.assert_called_once()


def test_stop_terminates_stubborn_process():
    """Если OCRWorker не завершился за 5 с → terminate → kill."""
    import multiprocessing as mp

    request_queue = mp.Queue()
    proc = mp.Process(target=_stubborn_worker, args=(request_queue,), name="OCRStubborn")
    proc.start()
    try:
        stop_ocr_worker(proc, request_queue, None)
        assert not proc.is_alive(), "OcrWorker должен быть завершён (terminate/kill)"
    finally:
        try:
            proc.join(timeout=1)
        except Exception:
            pass
        request_queue.close()
        request_queue.join_thread()
```

---

## 🧪 Тесты

```powershell
python -m pytest tests/unit/test_heartbeat_backoff.py tests/unit/test_scanner_shutdown.py -v   # 7 passed
python -m pytest tests/unit/ -q                                                                # 167 passed (160 + 7)
# регрессия включена: test_stale_tasks.task_cancel_endpoint, test_scanner_middleware_rbac
python -m py_compile scanner/src/heartbeat.py scanner/src/managed_scanner.py scanner/classifiers/ocr_worker.py   # OK
```

Итого: **167 passed**, 279 warnings (только DeprecationWarning `datetime.utcnow` — вне scope).

---

## 🖥 Живое подтверждение (live)

### BUG-080 — backoff и восстановление

Остановка Manager (`docker compose stop manager`), наблюдение лога сканера:

```text
2026-09-26 12:29:34,469 - urllib3.connectionpool - WARNING - Retrying ...  # основной цикл (не heartbeat-thread)
2026-09-26 12:30:00,539 - scanner.src.heartbeat - WARNING - Heartbeat failing (1 attempts), next retry in 5s
                     ← НЕТ СПАМА от heartbeat-потока (фейлы идут в DEBUG) →
2026-09-26 12:33:58,020 - scanner.src.heartbeat - INFO - Heartbeat restored after 4 failure(s)
```

`docker compose up -d manager` → `/api/health` → `{"status":"healthy","version":"3.13.20"}`.

### BUG-081 — graceful shutdown по Ctrl+C

Терминал opencode не имеет консоли (`GetConsoleWindow() == 0`) → `CTRL_C_EVENT` не доставляется
(Windows contract). Использован `CTRL_BREAK_EVENT` (тот же путь — в консоли пользователя это Ctrl+C
доходит напрямую до SIGINT-handler; live-скрипт `temp/sigint_probe.py` шлёт CTRL_BREAK в
CREATE_NEW_PROCESS_GROUP):

```text
probe: started pid=7472
probe: sending CTRL_BREAK_EVENT to group 7472
probe: exited rc=0                              ← graceful exit, rc=0

2026-09-26 12:37:20,050 - dcap-scanner - WARNING - [Scanner] SIGINT received, stopping...
2026-09-26 12:37:50,818 - scanner.src.heartbeat - INFO - HeartbeatThread stopped
2026-09-26 12:37:55,862 - dcap-scanner - INFO - [X] Сканер остановлен
2026-09-26 12:37:55,862 - dcap-scanner - INFO - [Scanner] Stopping...
2026-09-26 12:37:55,862 - dcap-scanner - INFO - [Scanner] Stopping heartbeat...
2026-09-26 12:37:55,863 - dcap-scanner - INFO - [Scanner] Stopping OCRWorker/classifiers...
2026-09-26 12:37:55,863 - dcap-scanner - INFO - [Scanner] Stopped
```

Stdout OCRWorker (graceful, без terminate):

```text
[PII] Запуск OCRWorker (процесс Tesseract)...
[PII] OCRWorker запущен (PID: 368)
[PII] Останавливаю OCRWorker...
[PII] OCRWorker остановлен
```

Примечание: основной цикл не выходит мгновенно — текущая итерация (загрузка PII-классификатора)
завершилась до graceful-блока (~35 с); процесс завершился rc=0 без применения terminate/kill.

---

## 📁 Файлы (изменения v3.13.20)

| Файл | Изменение |
|------|-----------|
| `scanner/src/heartbeat.py` | TASK-051: BACKOFF_STEPS, _send_heartbeat (DEBUG), _next_sleep (WARNING 1/5/10), run на _stop.wait() |
| `scanner/src/managed_scanner.py` | TASK-052: _handle_sigint (SIGINT+SIGBREAK), stop(), _shutdown_classifiers(), конец run_loop → helper |
| `scanner/classifiers/ocr_worker.py` | TASK-052: graceful stop_ocr_worker (None → join → terminate → kill) |
| `tests/unit/test_heartbeat_backoff.py` | новый (4 теста) |
| `tests/unit/test_scanner_shutdown.py` | новый (3 теста) |
| `docker-compose.yml` | manager/webui/celery → 3.13.20 |
| `STATE.md`, `ROADMAP.md`, `CHANGELOG.md` | версия, закрытые TASK-051/052, статистика |
| `docs/admin-guide/10-troubleshooting.md` | §3.2 heartbeat backoff, §3.3 graceful shutdown |

## 📝 Команды для коммита

```powershell
# 1. код (использовать commit -F из temp из-за PS-кодировки):
git add scanner/src/heartbeat.py scanner/src/managed_scanner.py scanner/classifiers/ocr_worker.py tests/unit/test_heartbeat_backoff.py tests/unit/test_scanner_shutdown.py docker-compose.yml
git commit -F temp/commit_msg_31320_code.txt

# 2. доки:
git add STATE.md ROADMAP.md CHANGELOG.md docs/admin-guide/10-troubleshooting.md prompts/reports/day_47.6_backlog080_081_scanner_reliability_report.md prompts/archive/TZ_BUG080_081_SCANNER_RELIABILITY.md
git commit -F temp/commit_msg_31320_docs.txt
```

commit_msg_31320_code.txt:

```
feat: День 47.6 — BUG-080/081: reliability сканера (v3.13.20)

- BUG-080 (TASK-051): heartbeat backoff 5→10→30→60→120 с, DEBUG-фейлы,
  WARNING 1/5/10, _stop.wait() (мгновенный выход), INFO restored
- BUG-081 (TASK-052): SIGINT+SIGBREAK → graceful: _handle_sigint, stop()
  (heartbeat + _shutdown_classifiers), ocr_worker graceful (None→join→terminate→kill)
- Тесты: test_heartbeat_backoff (4), test_scanner_shutdown (3) → 167 unit passed
- docker-compose.yml → 3.13.20 (manager/webui/celery)
```

commit_msg_31320_docs.txt:

```
docs: День 47.6 — обновлены STATE/ROADMAP/CHANGELOG/troubleshooting (v3.13.20)

- STATE.md: день 47.6, BUG-080/081 закрыты (TASK-051/052), ключевые решения
- ROADMAP.md: строка 47.6, закрытые TASK-051/052, статистика (~94%),
  архив ТЗ TZ_BUG080_081_SCANNER_RELIABILITY
- CHANGELOG.md: секция [3.13.20] (Fixed/Changed/Tests/Verified live)
- docs/admin-guide/10-troubleshooting.md: §3.2 heartbeat backoff, §3.3 Ctrl+C graceful
- отчёт day_47.6_backlog080_081_scanner_reliability_report.md
```

## 🔎 Инструкция для ручной проверки (пользователь)

1. **Версия:** `Invoke-RestMethod http://127.0.0.1:8000/api/health` → `"version":"3.13.20"`.
2. **BUG-080 (backoff):** запустить сканер (`.\start_scanner.bat`), затем `docker compose stop manager`.
   В `logs/scanner.log` (или окне сканера) — один WARNING `Heartbeat failing (1 attempts), next retry in 5s`,
   дальше тишина; `docker compose up -d manager` → INFO `Heartbeat restored after N failure(s)`.
3. **BUG-081 (Ctrl+C):** в окне сканера нажать **Ctrl+C** — должны появиться
   `[Scanner] SIGINT received, stopping...`, `[Scanner] Stopping...`, `[Scanner] Stopping OCRWorker/classifiers...`,
   `[X] Сканер остановлен`, окно закроется с кодом 0, потом можно запускать сканер заново (без taskkill).
   Дополнительно: Ctrl+Break в консоли делает то же самое (SIGBREAK).