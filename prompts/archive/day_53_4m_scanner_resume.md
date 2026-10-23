📋 ТЗ v3.14.12 — Scanner Resume (53.4n)
Файл: prompts/tz/day_53_4n_scanner_resume.md
Дата: 22.10.2026
Версия: v3.14.11 → v3.14.12
Приоритет: 🔴 Блокер v3.0.0 (эксплуатация: длинные сканы невозможны без resume)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 0.5–1 день
Зависимость: после 53.4m (v3.14.11, multiprocessing) — resume строится поверх ProcessPoolExecutor.

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Все находки baseline присутствуют (fingerprint set ⊆ after). Контекст (metadata["locations"]) сохранён. Resume не должен дублировать находки и не должен терять уже найденные.

Замер — обязателен. Без E2E test_resume_v31412 (1000 файлов, chunk_size=100, 10 чанков) — не принимаем.

📊 Контекст: почему resume сложнее с multiprocessing
Было (ThreadPool, до 53.4m): last_processed_index в родительском процессе — resume с paths[last_processed_index+1:].

Стало (ProcessPool, после 53.4m): файлы разбиты на чанки (chunk_size=100), каждый чанк — в отдельном процессе. Resume должен знать:

Какие чанки завершены (last_completed_chunk).

Сколько файлов в чанке (chunk_size).

Сколько всего чанков (total_chunks = ceil(total_files / chunk_size)).

Иначе: если сохранить только last_processed_index=599, но чанки по 100, то resume с 600 может пропустить файлы 600–699 (незавершённый чанк 6). Или дублировать их (если чанк 6 частично обработан).

Решение: resume — с последнего завершённого чанка (last_completed_chunk + 1). Чанк, который не завершён (прерван) — пересканировать с начала чанка (повторная обработка ≤ 100 файлов — приемлемо, дубликаты схлопнутся по fingerprint в Manager).

🔴 BUG-280 — Scanner: остановка не продолжает задание
Severity: 🔴 (блокер эксплуатации)
Файлы:

scanner/src/state_manager.py (новый модуль).

scanner/src/managed_scanner.py.

scanner/connectors/filesystem.py.

scanner/connectors/s3_line_connector.py.

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

Важно: wait=True ждёт завершения текущих чанков. Если чанк долгий (OCR на PDF) — Ctrl+C ждёт до 30–60 сек. Это приемлемо.

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

Если state есть — продолжить с last_completed_chunk + 1 (пропустить завершённые чанки).

Если нет — начать с нуля (chunk 0).

После успешного завершения — удалить state (clear_state(task_id)).

Manager:

POST /api/scanner/tasks/{id}/release — уже есть в API. Проверить, что при release задача возвращается в pending, не в failed.

Manager должен выдавать ту же задачу (id #212) при GET /api/scanner/tasks/pending, пока она не завершена.

🛠️ Что нужно сделать
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
_execute_task_linewise (или _execute_task):

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

    # ... запуск ProcessPoolExecutor ...
    chunk_size = self._config.performance.chunk_size  # 100
    paths = sorted(self._discover_files(root))  # детерминированный порядок
    total_chunks = (len(paths) + chunk_size - 1) // chunk_size

    # разбить на чанки
    chunks = [paths[i * chunk_size:(i + 1) * chunk_size]
              for i in range(total_chunks)]

    completed_chunks = resume_chunk  # с какого начинать
    findings_count = resume["findings_count"] if resume else 0

    try:
        with ProcessPoolExecutor(
            max_workers=self._config.performance.max_workers,
            initializer=_init_worker,
        ) as executor:
            for chunk_idx in range(completed_chunks, total_chunks):
                if self._stop_event.is_set():
                    break  # выходим из цикла, shutdown будет ниже
                
                chunk = chunks[chunk_idx]
                future = executor.submit(self._scan_chunk, chunk, task)
                result = future.result()  # ждём завершения чанка
                findings_count += len(result)
                
                # save state после каждого завершённого чанка
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
        # executor.__exit__ → shutdown(wait=True) — уже вызван
    finally:
        if self._stop_event.is_set():
            # soft stop: state уже сохранён (после последнего чанка)
            # но если Ctrl+C пришёл посреди чанка — state не обновлён
            # (потеряем до chunk_size файлов — приемлемо)
            await self._release_task(task_id)
            return

    # успешное завершение:
    state.clear()
_release_task(task_id):

python
async def _release_task(self, task_id):
    try:
        await self.client.release_task(task_id)  # POST /api/scanner/tasks/{id}/release
        logger.info("[Release] Task %d released (pending, not failed)", task_id)
    except Exception as e:
        logger.warning("[Release] Failed to release task %d: %s", task_id, e)
Signal handler (Ctrl+C):

python
def _handle_sigint(self, signum, frame):
    logger.info("[Scan] SIGINT — setting stop_event")
    self._stop_event.set()
    # ProcessPoolExecutor.__exit__ (wait=True) — ждёт текущий чанк
    # После __exit__ — finally: release_task
3. scanner/connectors/filesystem.py
scan_path должен принимать start_chunk (или start_index):

python
def scan_path(self, root, *, start_chunk: int = 0, chunk_size: int = 100, ...):
    paths = sorted(self._discover_files(root))
    start_index = start_chunk * chunk_size
    for idx, path in enumerate(paths[start_index:], start=start_index):
        ...
Или — ProcessPoolExecutor.map с chunksize=chunk_size (сам разбивает). Resume — paths[start_index:] (где start_index = start_chunk * chunk_size).

4. scanner/connectors/s3_line_connector.py
Для S3: важно, что list_objects_v2 возвращает объекты в лексикографическом порядке (S3 не гарантирует, но на практике — да). Если порядок не гарантирован — хранить processed_keys (set) в state.

Рекомендация: processed_keys (set) в state (полный список ключей). Для 22 500 — ~22 500 строк, ~1 МБ. Приемлемо.

Или: start_key (последний обработанный ключ) — если порядок гарантирован.

Resume для S3: scan_path(start_key=...) или scan_path(processed_keys={...}).

🧪 Тесты
Unit — tests/unit/test_scan_state_v31412.py (new)
python
"""53.4n (v3.14.12): ScanState — save/load/clear, chunk-aware."""
from scanner.src.state_manager import ScanState


def test_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr("scanner.src.state_manager.STATE_DIR", tmp_path)
    s = ScanState(212)
    s.save(
        chunk_size=100, total_files=1000, total_chunks=10,
        last_completed_chunk=5, last_completed_index=599,
        findings_count=42,
    )
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
    assert s.get_resume_chunk() == 6  # 5 + 1
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
✅ Definition of Done
□ scanner/src/state_manager.py — ScanState (save/load/clear/get_resume_chunk, chunk-aware).
□ managed_scanner.py — graceful shutdown: executor.shutdown(wait=True) → state.save → release_task.
□ managed_scanner.py — при старте: load_state → resume_chunk = last_completed_chunk + 1.
□ managed_scanner.py — periodic save после каждого завершённого чанка.
□ filesystem.py — scan_path(start_chunk=K).
□ s3_line_connector.py — scan_path(start_key=...) или processed_keys.
□ State удаляется после успешного завершения.
□ Unit test_scan_state_v31412.py — passed.
□ E2E test_resume_v31412.py — passed.
□ Ручная приёмка 8/8 ✅.
□ docker inspect dcap-scanner (или версия) — обновлена.
💾 Коммит
powershell
git add scanner/src/state_manager.py `
        scanner/src/managed_scanner.py `
        scanner/connectors/filesystem.py `
        scanner/connectors/s3_line_connector.py `
        tests/unit/test_scan_state_v31412.py `
        tests/e2e/test_resume_v31412.py `
        .env docker-compose.yml `
        ARCHITECTURE.md CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "feat: 53.4n scanner resume — chunk-aware state + release (v3.14.12)

BUG-280: при Ctrl+C сканер сохраняет state (last_completed_chunk,
chunk_size, findings_count) в scanner/state/scan_<task_id>.json
и вызывает POST /api/scanner/tasks/{id}/release (pending, не failed).
При старте — load state, continue с last_completed_chunk + 1.
Graceful shutdown: executor.shutdown(wait=True) до state.save.

FilesystemConnector: scan_path(start_chunk=K).
S3LineConnector: scan_path(start_key=...) / processed_keys.
Periodic save после каждого завершённого чанка.
State удаляется после успешного завершения.

Функционал сохранён: все находки baseline, без дублей, без потерь.

Tests: test_scan_state_v31412.py (unit), test_resume_v31412.py (e2e)."
📊 Отчёт (что прислать)
Diff по 4 файлам (state_manager.py, managed_scanner.py, filesystem.py, s3_line_connector.py) — или описание.

Unit test_scan_state_v31412.py — passed.

E2E test_resume_v31412.py — passed.

Ручной сценарий:

Скриншот/лог: [Resume] Continuing task <id> from chunk 4/10.

ScanProgress после перезапуска — с ~400 (не с 1).

findings count = baseline (без дублей).

State-файл удалён после завершения.

Manager task status после остановки — pending (не failed).

docker inspect dcap-scanner (или версия).

🎯 Что важно
Graceful shutdown — до state.save. executor.shutdown(wait=True) → потом state.save. Если state.save до shutdown — потеряем результаты текущего чанка.

Periodic save — после каждого чанка. Не «каждые 100 файлов» (чанк и есть 100). Если чанк не завершён — state не обновлён (потеряем ≤ chunk_size файлов, но не всё).

Resume — с last_completed_chunk + 1. Незавершённый чанк — пересканировать с начала (дубликаты схлопнутся по fingerprint в Manager).

State удаляется после успеха. Иначе следующий запуск той же задачи — продолжит с середины, хотя должен с начала.

Для S3 — processed_keys (set) или start_key (если порядок гарантирован).

Release, не failed. При Ctrl+C — POST /api/scanner/tasks/{id}/release (вернуть в пул). Не _fail_task.

⚠️ Побочный риск (из Фазы 2)
tempfile.gettempdir() == E:\Temp, _cleanup_temp_files глоббит tmp*/ocr_*. Тестовый набор — вне %TEMP%. Зафиксировать в docs/testing.md.