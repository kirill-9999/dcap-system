📄 ТЗ: Scanner — надёжность перезапуска и heartbeat
Файл: TZ_BUG080_081_SCANNER_RELIABILITY.md
Версия: v3.13.19 → v3.13.20
Оценка: ~2 ч
Дата: 26.09.2026
Контекст: обнаружено при пересборке Manager во время BACKLOG-086 (26.09.2026, 11:53)

🎯 Цель
Устранить две проблемы надёжности сканера:

BUG-080 — heartbeat retry без backoff при недоступном Manager (спамит лог, лишний CPU).

BUG-081 — Ctrl+C не завершает OCRWorker на Windows (multiprocessing spawn), из-за чего сканер невозможно корректно перезапустить.

📌 Доказательная база
BUG-080 (лог сканера, 11:53:11):

text
2026-09-26 11:53:11,405 - scanner.src.heartbeat - WARNING - Heartbeat failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
2026-09-26 11:53:14,886 - urllib3.connectionpool - WARNING - Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'RemoteDisconnected(...)': /api/scanner/heartbeat
Повторы без backoff (каждые ~3 с).

Retry(total=0) — urllib3 не повторяет.

Нет сообщения «Manager недоступен N секунд».

Лог спамится.

Контекст: Manager пересобирался (docker compose build manager → up -d) — был недоступен 30–60 с. За это время сканер засыпал лог.

BUG-081 (из вывода процесса):

text
PID 21972 — python -X utf8 run_scanner.py scanner\config\scanner_config.json
PID 17756 — "E:\Dev\Anaconda3\python.exe" "-X" "utf8" "-c" "from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=21972, pipe_handle=852)" "--multiprocessing-fork"
OCRWorker — отдельный процесс через multiprocessing (spawn).

Ctrl+C в консоли не пробрасывается в дочерний процесс (особенность Windows + spawn).

Основной поток ждёт join → процесс висит.

Симптом: «Ctrl+C не останавливает сканер, приходится убивать через Task Manager».

🔧 Задача
TASK-051 (BUG-080) — Heartbeat с exponential backoff
Файл: scanner/src/heartbeat.py

Требование:

При ошибке heartbeat — exponential backoff: 5, 10, 30, 60, 120 с (максимум 120 с).

При успехе — сброс backoff.

После N фейлов (например, 5) — один WARNING: «Manager недоступен N секунд», а не спам каждые 3 с.

Логировать DEBUG каждый фейл, WARNING — только на границах backoff.

Скелет:

python
import time

class HeartbeatThread(threading.Thread):
    BACKOFF_STEPS = [5, 10, 30, 60, 120]

    def __init__(self, ..., interval: int = 30):
        ...
        self._fail_count = 0

    def _send_heartbeat(self) -> bool:
        try:
            resp = requests.post(...)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")  # DEBUG
            return False

    def run(self):
        while not self._stop_event.is_set():
            ok = self._send_heartbeat()
            if ok:
                if self._fail_count > 0:
                    logger.info(f"Heartbeat restored after {self._fail_count} failures")
                self._fail_count = 0
                sleep_time = self._interval
            else:
                self._fail_count += 1
                idx = min(self._fail_count - 1, len(self.BACKOFF_STEPS) - 1)
                sleep_time = self.BACKOFF_STEPS[idx]
                if self._fail_count == 1 or self._fail_count % 5 == 0:
                    logger.warning(
                        f"Heartbeat failing ({self._fail_count} attempts), "
                        f"next retry in {sleep_time}s"
                    )
            self._stop_event.wait(sleep_time)
Замечание: использовать self._stop_event.wait(sleep_time) вместо time.sleep() — чтобы Ctrl+C / stop-флаг работал мгновенно.

TASK-052 (BUG-081) — Graceful shutdown OCRWorker на Windows
Файл: scanner/src/managed_scanner.py (запуск и остановка OCRWorker), scanner/classifiers/ocr_worker.py

Требование:

Обработчик SIGINT в основном потоке сканера: при получении — установить флаг _stopped, послать None в request_queue, дождаться process.join(timeout=5), при необходимости process.terminate() → process.kill().

signal.signal(signal.SIGINT, handler) — Windows-совместимо (использовать signal.signal без SIGTERM).

Логировать шаги завершения.

Скелет:

python
import signal

class ManagedScanner:
    def __init__(self, ...):
        ...
        self._stop_event = threading.Event()
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum, frame):
        logger.info("[Scanner] SIGINT received, stopping...")
        self._stop_event.set()

    def stop(self):
        """Graceful shutdown — вызывается из SIGINT или извне."""
        logger.info("[Scanner] Stopping heartbeat...")
        self._heartbeat_thread.stop()

        logger.info("[Scanner] Stopping OCRWorker...")
        if self._ocr_process and self._ocr_process.is_alive():
            try:
                self._ocr_request_queue.put_nowait(None)
            except Exception:
                pass
            self._ocr_process.join(timeout=5)
            if self._ocr_process.is_alive():
                logger.warning("[Scanner] OCRWorker didn't stop, terminating")
                self._ocr_process.terminate()
                self._ocr_process.join(timeout=2)
            if self._ocr_process.is_alive():
                logger.warning("[Scanner] OCRWorker didn't terminate, killing")
                self._ocr_process.kill()

        logger.info("[Scanner] Stopped")
Дополнительно: обернуть основной цикл сканера в try/finally:

python
try:
    self._main_loop()
finally:
    self.stop()
Проверка: в ocr_worker.py уже есть signal.signal(signal.SIGINT, signal.SIG_IGN) — оставить (родитель управляет shutdown через очередь).

🧪 Тесты
Unit — heartbeat backoff
Файл: tests/unit/test_heartbeat_backoff.py

python
class TestHeartbeatBackoff:
    def test_backoff_steps(self):
        """5, 10, 30, 60, 120 — и не больше 120."""
        pass

    def test_backoff_resets_on_success(self):
        """После успеха fail_count = 0, sleep = interval."""
        pass

    def test_warning_not_spam(self):
        """WARNING только на 1-м фейле и каждые 5."""
        pass

    def test_stop_event_interrupts_sleep(self):
        """stop_event.wait() → мгновенный выход из sleep."""
        pass
Ожидание: 4 passed.

Unit — graceful shutdown
Файл: tests/unit/test_scanner_shutdown.py

python
class TestScannerShutdown:
    def test_sigint_sets_stop_event(self):
        """_handle_sigint → _stop_event.set()."""
        pass

    def test_stop_sends_none_to_ocr_queue(self):
        """stop() → None в request_queue."""
        pass

    def test_stop_terminates_stubborn_process(self):
        """Если OCRWorker не завершился за 5 с → terminate."""
        pass
Ожидание: 3 passed.

📊 Live-проверка
BUG-080 — backoff
Запустить сканер.

Остановить Manager: docker compose stop manager.

Наблюдать лог сканера 2–3 минуты.

Ожидание:

text
WARNING - Heartbeat failing (1 attempts), next retry in 5s
WARNING - Heartbeat failing (5 attempts), next retry in 30s
WARNING - Heartbeat failing (10 attempts), next retry in 120s
Вместо спама каждые 3 с.

Вернуть Manager: docker compose start manager.

Ожидание:

text
INFO - Heartbeat restored after N failures
BUG-081 — Ctrl+C
Запустить сканер.

Нажать Ctrl+C.

Ожидание:

text
[Scanner] SIGINT received, stopping...
[Scanner] Stopping heartbeat...
[Scanner] Stopping OCRWorker...
[OCR_WORKER] Завершение. Обработано запросов: N
[Scanner] Stopped
Процесс завершается без Task Manager.

Проверить, что процесс исчез:

powershell
Get-CimInstance Win32_Process -Filter "name like 'python%'" |
  Where-Object { $_.CommandLine -match "run_scanner|OCRWorker" }
Ожидание: пусто.

📝 Сводка правок
#	Файл	Действие	Задача
1	scanner/src/heartbeat.py	Exponential backoff + stop_event.wait()	TASK-051
2	scanner/src/managed_scanner.py	SIGINT handler + graceful shutdown	TASK-052
3	scanner/classifiers/ocr_worker.py	(опционально) проверка SIG_IGN	TASK-052
4	tests/unit/test_heartbeat_backoff.py	4 теста	TASK-051
5	tests/unit/test_scanner_shutdown.py	3 теста	TASK-052
6	docker-compose.yml	VERSION → 3.13.20 (только manager/webui)	релиз
7	STATE.md, ROADMAP.md, CHANGELOG.md, docs/admin-guide/10-troubleshooting.md	BUG-080/081 → ✅	док
✅ Критерии закрытия ТЗ
□ py_compile изменённых .py — OK
□ pytest tests/unit/test_heartbeat_backoff.py -v — 4 passed
□ pytest tests/unit/test_scanner_shutdown.py -v — 3 passed
□ pytest tests/unit/ -q — 167 passed (160 + 7)
□ Live BUG-080: heartbeat backoff 5→10→30→60→120, без спама
□ Live BUG-080: восстановление после возврата Manager
□ Live BUG-081: Ctrl+C завершает сканер без Task Manager
□ Manager /api/health → 3.13.20
□ Обновлены STATE.md, ROADMAP.md, CHANGELOG.md, docs/admin-guide/10-troubleshooting.md
📌 Примечания
TASK-051/TASK-052 — независимы. Можно делать параллельно или по отдельности.

Риск: изменение heartbeat.py и managed_scanner.py может задеть существующие тесты test_stale_tasks, test_scanner_middleware_rbac. Проверить регрессию.

Не путать с BUG-076 (dcap_scanner_current_task не сбрасывается) — это отдельный баг, v3.1.0.

Автор ТЗ: архитектор
Дата: 26.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.20, BUG-080/081 → ✅