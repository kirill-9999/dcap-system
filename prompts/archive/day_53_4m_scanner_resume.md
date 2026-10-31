📋 ТЗ v3.14.12 — Scanner Resume + Logging + Reconnect (53.4n)
Файл: prompts/tz/day_53_4n_scanner_resume.md
Дата: 23.10.2026
Версия: v3.14.11 → v3.14.12
Приоритет: 🔴 Блокер v3.0.0 (эксплуатация: resume, логирование, reconnect)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 1–1.5 дня
Зависимость: после 53.4m (v3.14.11, multiprocessing)

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Все находки baseline присутствуют (fingerprint set ⊆ after). Контекст (metadata["locations"]) сохранён. Resume не должен дублировать находки и не должен терять уже найденные.

Консольный вывод — сохраняется полностью. На консоли — все события (как сейчас). В лог-файл — значимые события и ошибки (не спам).

Замер — обязателен. Без E2E test_resume_v31412 (1000 файлов, chunk_size=100, 10 чанков) — не принимаем.

🎯 Задачи (3 шт.)
ID	Название	Severity
BUG-280	Scanner resume: остановка не продолжает задание	🔴
BUG-283	Файловый лог: консольного вывода недостаточно	🟡
BUG-284	Reconnect: нет сообщения об успешном переподключении к Manager	🟡
🔴 BUG-280 — Scanner Resume (основная)
Проблема
Сценарий:

Manager выдал задачу #212 (22 500 файлов).

Сканер начал скан (ProcessPoolExecutor, chunk_size=100, 225 чанков).

Обработано 5 чанков (500 файлов).

Ctrl+C (или сбой).

Сканер остановился. В логе: [FailTask] Task 212 marked failed + Task 212 прервана — post-processing пропущен (N находок не сериализованы).

При повторном запуске сканер не продолжает задачу #212. Manager выдаёт новую (или ту же, но сканер начинает с нуля).

Это блокер эксплуатации: скан на 22 500 файлов идёт 5–7 часов (после 53.4m). Если пользователь остановил сканер (перезагрузка, обновление, сбой), при повторном запуске задание должно продолжиться с места остановки.

Что должно быть
При остановке (Ctrl+C / stop_event):

Graceful shutdown ProcessPoolExecutor:

executor.shutdown(wait=True, cancel_futures=True) — дождаться текущих задач (или отменить, если cancel_futures=True).

После shutdown — state сохраняется (не до, иначе потеряем результаты текущего чанка).

Сохранить state в scanner/state/scan_<task_id>.json:

json
{
  "task_id": 212,
  "resource_id": 1,
  "source_type": "filesystem",
  "chunk_size": 100,
  "total_files": 22500,
  "total_chunks": 225,
  "last_completed_chunk": 5,
  "last_completed_index": 599,
  "findings_count": 313095,
  "started_at": "2026-10-21T08:11:45Z",
  "timestamp": "2026-10-22T07:43:35Z"
}
Отправить накопленные findings батчем в Manager (или сохранить в state, если отправить не успели — но лучше отправить до release).

Вызвать POST /api/scanner/tasks/{id}/release — вернуть задачу в пул без failed.

НЕ вызывать _fail_task.

При старте:

Проверить scanner/state/scan_<task_id>.json для текущей задачи (Manager выдаёт task_id — проверить state для этого id).

Если state есть — продолжить с last_completed_chunk + 1.

Если нет — начать с нуля (chunk 0).

После успешного завершения — удалить state (clear_state(task_id)).

Manager:

POST /api/scanner/tasks/{id}/release — уже есть в API. Проверить, что при release задача возвращается в pending, не в failed.

Manager должен выдавать ту же задачу (id #212) при GET /api/scanner/tasks/pending, пока она не завершена.

Что нужно сделать
1. scanner/src/state_manager.py (новый модуль)
python
"""53.4n (v3.14.12): ScanState — resume state для задач сканера (chunk-aware)."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).resolve().parents[2] / "state"  # scanner/state/


class ScanState:
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.file = STATE_DIR / f"scan_{task_id}.json"
        self._started_at: Optional[str] = None

    def save(self, *, chunk_size: int, total_files: int, total_chunks: int,
             last_completed_chunk: int, last_completed_index: int,
             findings_count: int, resource_id: int = None,
             source_type: str = "filesystem") -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if self._started_at is None:
            self._started_at = datetime.utcnow().isoformat() + "Z"
        data = {
            "task_id": self.task_id,
            "resource_id": resource_id,
            "source_type": source_type,
            "chunk_size": chunk_size,
            "total_files": total_files,
            "total_chunks": total_chunks,
            "last_completed_chunk": last_completed_chunk,
            "last_completed_index": last_completed_index,
            "findings_count": findings_count,
            "started_at": self._started_at,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("[ScanState] Saved: %s (chunk=%d/%d, findings=%d)",
                    self.file, last_completed_chunk, total_chunks, findings_count)

    def load(self) -> Optional[dict]:
        if not self.file.exists():
            return None
        with open(self.file, encoding="utf-8") as f:
            data = json.load(f)
        self._started_at = data.get("started_at")
        return data

    def clear(self) -> None:
        if self.file.exists():
            self.file.unlink()
            logger.info("[ScanState] Cleared: %s", self.file)

    def get_resume_chunk(self) -> int:
        """С какого чанка продолжить (last_completed_chunk + 1, или 0)."""
        data = self.load()
        if not data:
            return 0
        return data.get("last_completed_chunk", -1) + 1
2. scanner/src/managed_scanner.py
python
async def _execute_task_linewise(self, task):
    task_id = task["id"]
    state = ScanState(task_id)
    resume = state.load()
    resume_chunk = state.get_resume_chunk()  # 0 если нет state

    if resume:
        logger.info("[Resume] Continuing task %d from chunk %d/%d (last=%s)",
                    task_id, resume_chunk, resume["total_chunks"],
                    resume.get("last_completed_index"))

    chunk_size = self._config.performance.chunk_size  # 100
    paths = sorted(self._discover_files(root))
    total_chunks = (len(paths) + chunk_size - 1) // chunk_size
    chunks = [paths[i * chunk_size:(i + 1) * chunk_size]
              for i in range(total_chunks)]

    completed_chunks = resume_chunk
    findings_count = resume["findings_count"] if resume else 0

    try:
        with ProcessPoolExecutor(
            max_workers=self._config.performance.max_workers,
            initializer=_init_worker,
        ) as executor:
            for chunk_idx in range(completed_chunks, total_chunks):
                if self._stop_event.is_set():
                    break
                chunk = chunks[chunk_idx]
                future = executor.submit(self._scan_chunk, chunk, task)
                result = future.result()
                findings_count += len(result)
                state.save(
                    chunk_size=chunk_size,
                    total_files=len(paths),
                    total_chunks=total_chunks,
                    last_completed_chunk=chunk_idx,
                    last_completed_index=(chunk_idx + 1) * chunk_size - 1,
                    findings_count=findings_count,
                    resource_id=task.get("resource_id"),
                    source_type=task.get("source_type", "filesystem"),
                )
    except KeyboardInterrupt:
        logger.info("[Scan] Ctrl+C — graceful shutdown")
    finally:
        if self._stop_event.is_set():
            await self._release_task(task_id)
            return

    state.clear()

async def _release_task(self, task_id):
    try:
        await self.client.release_task(task_id)
        logger.info("[Release] Task %d released (pending, not failed)", task_id)
    except Exception as e:
        logger.warning("[Release] Failed to release task %d: %s", task_id, e)
3. scanner/connectors/filesystem.py
scan_path должен принимать start_chunk:

python
def scan_path(self, root, *, start_chunk: int = 0, chunk_size: int = 100, ...):
    paths = sorted(self._discover_files(root))
    start_index = start_chunk * chunk_size
    for idx, path in enumerate(paths[start_index:], start=start_index):
        ...
4. scanner/connectors/s3_line_connector.py
Для S3: processed_keys (set) в state (полный список ключей, ~22 500 строк ~1 МБ) или start_key (если порядок гарантирован).

Resume для S3: scan_path(start_key=...) или scan_path(processed_keys={...}).

🟡 BUG-283 — Файловый лог (не только консоль)
Проблема
Сейчас сканер пишет только в консоль (stdout). Файл scanner/logs/scanner.log не создаётся (проверено: Get-Item scanner\logs\scanner.log → «путь не существует»). Это проблема эксплуатации: при Ctrl+C / kill / перезагрузке консоль теряется (нет истории).

Что должно быть
Консоль — все события (как сейчас): [ScanProgress], [OCR] ..., [PII] ..., [FS] ..., [Register] ..., print(...) — всё.

Файл scanner/logs/scanner.log — значимые события и ошибки:

INFO: [ScanProgress], [Register], [GetTask], [Resume], [Release], [FS] ProcessPoolExecutor, [PII] [OK] NER-категории отключены, [ScanState] Saved/Cleared.

WARNING / ERROR: все.

Не пишутся в файл: [OCR] Found via 'where' (спам), [OCR_WORKER] ... (спам, если каждый файл), print(...) (только консоль).

Что нужно сделать
1. run_scanner.py — FileHandler + StreamHandler
python
import logging
import logging.handlers
from pathlib import Path

def _setup_logging(config):
    log_cfg = config.get("logging", {})
    log_file = log_cfg.get("file", "logs/scanner.log")
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)  # создаём logs/

    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    max_bytes = log_cfg.get("max_size_mb", 100) * 1024 * 1024
    backup_count = log_cfg.get("backup_count", 5)

    root = logging.getLogger()
    root.setLevel(level)

    # Console — все события (как сейчас)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)  # всё в консоль
    console.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    root.addHandler(console)

    # File — значимые события (INFO+), ротация
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)  # INFO+ в файл
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    root.addHandler(file_handler)

    logging.info("[Logging] Console=DEBUG, File=%s (level=%s, max=%dMB, backups=%d)",
                 log_path, log_cfg.get("level", "INFO"), log_cfg.get("max_size_mb", 100),
                 backup_count)
**В main() / run() — вызвать _setup_logging(config) до остальной инициализации.

2. print(...) → logger.debug(...)
Файл: scanner/classifiers/pii_classifier.py, scanner/classifiers/ocr_worker.py.

Было:

python
print(f"[OCR] Found via 'where': {path}")
print(f"[OCR_WORKER] Tesseract: {path}")
Стало:

python
logger.debug(f"[OCR] Found via 'where': {path}")
logger.debug(f"[OCR_WORKER] Tesseract: {path}")
Почему: logger.debug не пишется в файл (level=INFO), но пишется в консоль (level=DEBUG). Это ровно то, что нужно: консоль — всё, файл — значимое.

Важно: logging.getLogger(__name__) в каждом модуле (не root).

3. start_scanner.bat — перенаправление (опционально)
Если FileHandler не хотите — альтернатива:

bat
python run_scanner.py scanner\config\scanner_config.json > logs\scanner.log 2>&1
Но: это не ротация (файл растёт). FileHandler — лучше (ротация 100 МБ × 5).

Тест
python
# tests/unit/test_logging_v31412.py
def test_file_handler_created(tmp_path, monkeypatch):
    """BUG-283: FileHandler создаёт scanner.log."""
    monkeypatch.chdir(tmp_path)
    from run_scanner import _setup_logging
    _setup_logging({"logging": {"file": "logs/scanner.log", "level": "INFO"}})
    logging.getLogger("test").info("test message")
    assert (tmp_path / "logs" / "scanner.log").exists()


def test_debug_not_in_file(tmp_path, monkeypatch):
    """BUG-283: DEBUG — в консоль, но не в файл."""
    monkeypatch.chdir(tmp_path)
    from run_scanner import _setup_logging
    _setup_logging({"logging": {"file": "logs/scanner.log", "level": "INFO"}})
    logging.getLogger("test").debug("debug message")
    logging.getLogger("test").info("info message")
    content = (tmp_path / "logs" / "scanner.log").read_text(encoding="utf-8")
    assert "debug message" not in content
    assert "info message" in content
Ручная приёмка
#	Сценарий	Ожидание
1	Запустить сканер	scanner/logs/scanner.log создан
2	Консоль	Все события (как раньше)
3	Файл	Только INFO+ (не [OCR] Found via 'where')
4	Ротация	При 100 МБ — scanner.log.1, .2, … .5
5	Ctrl+C	Файл остаётся (история сохранена)
🟡 BUG-284 — Reconnect: сообщение об успешном переподключении
Проблема
Сейчас при обрыве связи с Manager сканер пытается переподключиться (retry, WARNING в лог), но не сообщает об успешном переподключении. Пользователь видит только WARNING-и (обрывы), но не знает, восстановилась ли связь.

Пример из логов:

text
2026-10-23 08:01:50,587 - WARNING - Retrying (Retry(total=4, ...)): /api/scanner/heartbeat
2026-10-23 08:07:12,152 - WARNING - Retrying (Retry(total=4, ...)): /api/scanner/heartbeat
2026-10-23 08:20:03,616 - INFO - [GetTask] Received task 219  ← связь восстановилась, но сообщения нет
Нужно: [ManagerClient] [OK] Reconnected (was offline Xs) — и в консоль, и в файл.

Что должно быть
При обрыве — WARNING (как сейчас) + сохранить last_offline_at = datetime.utcnow().

При успешном запросе (после обрыва) — INFO: [ManagerClient] [OK] Reconnected (was offline Xs) — и консоль, и файл.

Если last_offline_at не было (первый запрос) — не писать (нет «reconnect»).

Что нужно сделать
Файл: scanner/src/managed_scanner.py (или client.py, где ManagerClient).

python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ManagerClient:
    def __init__(self, ...):
        ...
        self._last_offline_at: Optional[datetime] = None
        self._is_offline = False

    def _request(self, method, path, **kwargs):
        try:
            response = self._session.request(method, url, **kwargs)
            # успешный запрос — reconnect?
            if self._is_offline:
                offline_sec = (datetime.utcnow() - self._last_offline_at).total_seconds()
                logger.info("[ManagerClient] [OK] Reconnected (was offline %ds)", offline_sec)
                self._is_offline = False
                self._last_offline_at = None
            return response
        except (ConnectionError, Timeout, ...) as e:
            if not self._is_offline:
                logger.warning("[ManagerClient] Connection lost: %s", e)
                self._last_offline_at = datetime.utcnow()
                self._is_offline = True
            raise
Важно:

logger.info — и в консоль, и в файл (INFO+).

Не дублировать: если уже offline — не писать WARNING на каждый retry (только первый раз). Или — писать [ManagerClient] Retrying (N/5)... на DEBUG (консоль, не файл).

Heartbeat — _request тоже проходит через ManagerClient (reconnect сработает).

Тест
python
# tests/unit/test_reconnect_v31412.py
def test_reconnect_logged(monkeypatch, caplog):
    """BUG-284: reconnect — INFO в лог и консоль."""
    from scanner.src.client import ManagerClient
    client = ManagerClient(...)
    # имитация обрыва
    client._is_offline = True
    client._last_offline_at = datetime.utcnow()
    # успешный запрос
    with caplog.at_level(logging.INFO):
        client._request("GET", "/api/scanner/heartbeat")
    assert any("[OK] Reconnected" in r.message for r in caplog.records)
Ручная приёмка
#	Сценарий	Ожидание
1	Остановить Manager	WARNING: Connection lost (1 раз)
2	Запустить Manager	INFO: [OK] Reconnected (was offline Xs) — консоль + файл
3	Повторный обрыв	WARNING снова (1 раз), затем INFO при reconnect
🧪 Тесты (сводно)
Unit — tests/unit/test_scan_state_v31412.py (new)
python
"""53.4n (v3.14.12): ScanState — save/load/clear, chunk-aware."""
from scanner.src.state_manager import ScanState


def test_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr("scanner.src.state_manager.STATE_DIR", tmp_path)
    s = ScanState(212)
    s.save(chunk_size=100, total_files=1000, total_chunks=10,
           last_completed_chunk=5, last_completed_index=599, findings_count=42)
    data = s.load()
    assert data["task_id"] == 212
    assert data["chunk_size"] == 100
    assert data["total_chunks"] == 10
    assert data["last_completed_chunk"] == 5
    assert data["last_completed_index"] == 599
    assert data["findings_count"] == 42


def test_clear(tmp_path, monkeypatch):
    monkeypatch.setattr("scanner.src.state_manager.STATE_DIR", tmp_path)
    s = ScanState(212)
    s.save(chunk_size=100, total_files=1000, total_chunks=10,
           last_completed_chunk=1, last_completed_index=199, findings_count=0)
    s.clear()
    assert s.load() is None


def test_load_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("scanner.src.state_manager.STATE_DIR", tmp_path)
    s = ScanState(999)
    assert s.load() is None
    assert s.get_resume_chunk() == 0


def test_get_resume_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr("scanner.src.state_manager.STATE_DIR", tmp_path)
    s = ScanState(212)
    s.save(chunk_size=100, total_files=1000, total_chunks=10,
           last_completed_chunk=5, last_completed_index=599, findings_count=0)
    assert s.get_resume_chunk() == 6
Unit — tests/unit/test_logging_v31412.py (new)
python
"""53.4n (v3.14.12): BUG-283 — FileHandler + StreamHandler."""
import logging
from pathlib import Path


def test_file_handler_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from run_scanner import _setup_logging
    _setup_logging({"logging": {"file": "logs/scanner.log", "level": "INFO"}})
    logging.getLogger("test").info("test message")
    assert (tmp_path / "logs" / "scanner.log").exists()


def test_debug_not_in_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from run_scanner import _setup_logging
    _setup_logging({"logging": {"file": "logs/scanner.log", "level": "INFO"}})
    logging.getLogger("test").debug("debug message")
    logging.getLogger("test").info("info message")
    content = (tmp_path / "logs" / "scanner.log").read_text(encoding="utf-8")
    assert "debug message" not in content
    assert "info message" in content
Unit — tests/unit/test_reconnect_v31412.py (new)
python
"""53.4n (v3.14.12): BUG-284 — reconnect."""
import logging
from datetime import datetime


def test_reconnect_logged(caplog):
    from scanner.src.client import ManagerClient
    client = ManagerClient("http://localhost:8000", ...)
    client._is_offline = True
    client._last_offline_at = datetime.utcnow()
    with caplog.at_level(logging.INFO):
        client._request("GET", "/api/scanner/heartbeat")
    assert any("[OK] Reconnected" in r.message for r in caplog.records)
E2E — tests/e2e/test_resume_v31412.py (new)
python
"""53.4n (v3.14.12): E2E — resume после остановки."""
import pytest
import time


@pytest.mark.e2e
def test_scan_resume_after_stop(api_client, test_files_dir):
    """Resume: остановка + перезапуск — продолжает с последнего чанка."""
    # 1. Создать resource (1000 файлов), запустить scan (chunk_size=100).
    # 2. Дождаться progress > 300 файлов (last_completed_chunk >= 3).
    # 3. Остановить сканер (Ctrl+C / stop_event).
    # 4. Проверить: state <task_id>.json, last_completed_chunk >= 3.
    # 5. Проверить: Manager task status = pending (не failed).
    # 6. Перезапустить сканер.
    # 7. Проверить: [Resume] Continuing task <id> from chunk 4/10 (не с 0).
    # 8. Дождаться завершения — findings count = baseline (без дублей).
    ...
📋 Ручная приёмка
#	Сценарий	Ожидание
1	Запустить скан 1000 файлов (chunk_size=100)	10 чанков, ScanProgress растёт
2	Через 5–10 сек — Ctrl+C	Graceful shutdown (процессы завершены)
3	Проверить state	scanner/state/scan_<task_id>.json: last_completed_chunk >= 3
4	Проверить Manager	GET /api/scanner/tasks/{id} → pending (не failed)
5	Перезапустить сканер	[Resume] Continuing task <id> from chunk 4/10
6	ScanProgress	Начинается с ~400 (не с 1)
7	Завершить скан	findings count = baseline (без дублей, без потерь)
8	State после завершения	scan_<task_id>.json удалён
9	Лог-файл	scanner/logs/scanner.log создан, есть [Resume], [Release], [ScanState]
10	Консоль	Все события (как раньше), включая [OCR] Found via 'where'
11	Лог-файл — нет спама	[OCR] Found via 'where' не в файле
12	Reconnect	Остановить Manager → WARNING Connection lost. Запустить → INFO [OK] Reconnected (was offline Xs) — консоль + файл
✅ Definition of Done
BUG-280 (resume):

□ scanner/src/state_manager.py — ScanState (save/load/clear/get_resume_chunk, chunk-aware).
□ managed_scanner.py — graceful shutdown: executor.shutdown(wait=True) → state.save → release_task.
□ managed_scanner.py — при старте: load_state → resume_chunk = last_completed_chunk + 1.
□ managed_scanner.py — periodic save после каждого завершённого чанка.
□ filesystem.py — scan_path(start_chunk=K).
□ s3_line_connector.py — scan_path(start_key=...) или processed_keys.
□ State удаляется после успешного завершения.
BUG-283 (логи):

□ run_scanner.py — _setup_logging(config) с FileHandler (RotatingFileHandler) + StreamHandler.
□ logs/ создаётся (mkdir(parents=True, exist_ok=True)).
□ print(...) → logger.debug(...) в pii_classifier.py / ocr_worker.py.
□ Консоль — все события (DEBUG). Файл — INFO+ (без спама).
□ Ротация: 100 МБ × 5 бэкапов.
BUG-284 (reconnect):

□ ManagerClient._request — отслеживание _is_offline / _last_offline_at.
□ При reconnect — logger.info("[ManagerClient] [OK] Reconnected (was offline Xs)") — консоль + файл.
Тесты:

□ Unit test_scan_state_v31412.py — passed.
□ Unit test_logging_v31412.py — passed.
□ Unit test_reconnect_v31412.py — passed.
□ E2E test_resume_v31412.py — passed.
□ Ручная приёмка 12/12 ✅.
□ docker inspect dcap-scanner (или версия) — обновлена.
💾 Коммит
powershell
git add scanner/src/state_manager.py `
        scanner/src/managed_scanner.py `
        scanner/src/client.py `
        scanner/connectors/filesystem.py `
        scanner/connectors/s3_line_connector.py `
        scanner/classifiers/pii_classifier.py `
        scanner/classifiers/ocr_worker.py `
        run_scanner.py `
        tests/unit/test_scan_state_v31412.py `
        tests/unit/test_logging_v31412.py `
        tests/unit/test_reconnect_v31412.py `
        tests/e2e/test_resume_v31412.py `
        .env docker-compose.yml `
        ARCHITECTURE.md CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "feat: 53.4n scanner resume + logging + reconnect (v3.14.12)

BUG-280: при Ctrl+C сканер сохраняет state (last_completed_chunk,
chunk_size, findings_count) в scanner/state/scan_<task_id>.json
и вызывает POST /api/scanner/tasks/{id}/release (pending, не failed).
При старте — load state, continue с last_completed_chunk + 1.
Graceful shutdown: executor.shutdown(wait=True) до state.save.

BUG-283: FileHandler (RotatingFileHandler) + StreamHandler.
Консоль — все события (DEBUG). Файл — INFO+ (без спама).
print(...) → logger.debug(...) для [OCR] / [OCR_WORKER].

BUG-284: ManagerClient отслеживает offline/reconnect.
INFO '[OK] Reconnected (was offline Xs)' — консоль + файл.

Функционал сохранён: все находки baseline, без дублей, без потерь.

Tests: test_scan_state_v31412.py (unit), test_logging_v31412.py (unit),
test_reconnect_v31412.py (unit), test_resume_v31412.py (e2e)."
📊 Отчёт (что прислать)
Diff по 6 файлам (state_manager.py, managed_scanner.py, client.py, filesystem.py, s3_line_connector.py, run_scanner.py) — или описание.

Unit test_scan_state_v31412.py, test_logging_v31412.py, test_reconnect_v31412.py — passed.

E2E test_resume_v31412.py — passed.

Ручной сценарий (resume):

Скриншот/лог: [Resume] Continuing task <id> from chunk 4/10.

ScanProgress после перезапуска — с ~400 (не с 1).

findings count = baseline (без дублей).

State-файл удалён после завершения.

Manager task status после остановки — pending (не failed).

Лог-файл: scanner/logs/scanner.log создан, есть [Resume], [ScanState], [Release], нет [OCR] Found via 'where'.

Reconnect: лог/скриншот [ManagerClient] [OK] Reconnected (was offline Xs).

docker inspect dcap-scanner (или версия).

🎯 Что важно
Graceful shutdown — до state.save. executor.shutdown(wait=True) → потом state.save. Если state.save до shutdown — потеряем результаты текущего чанка.

Periodic save — после каждого чанка. Не «каждые 100 файлов» (чанк и есть 100). Если чанк не завершён — state не обновлён (потеряем ≤ chunk_size файлов, но не всё).

Resume — с last_completed_chunk + 1. Незавершённый чанк — пересканировать с начала (дубликаты схлопнутся по fingerprint в Manager).

State удаляется после успеха. Иначе следующий запуск той же задачи — продолжит с середины, хотя должен с начала.

Логи: консоль = всё, файл = значимое. print → logger.debug (консоль — да, файл — нет). logger.info — в оба. Не терять консольный вывод (как сейчас).

Reconnect — INFO, не WARNING. WARNING — при обрыве (1 раз). INFO — при восстановлении (с длительностью offline).

Для S3 — processed_keys (set) или start_key (если порядок гарантирован).

⚠️ Побочный риск (из Фазы 2)
tempfile.gettempdir() == E:\Temp, _cleanup_temp_files глоббит tmp*/ocr_*. Тестовый набор — вне %TEMP%. Зафиксировать в docs/testing.md.