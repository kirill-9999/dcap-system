📋 ТЗ v3.14.13 — Scanner Pool Reuse (53.4o, BUG-286)
Файл: prompts/tz/day_53_4o_scanner_pool_reuse.md
Дата: 25.10.2026
Версия: v3.14.14 → v3.14.13 (по факту — после 53.4p, но версия v3.14.13 как pool reuse; в CHANGELOG — v3.14.13 с пометкой «after 53.4p»)
Приоритет: 🔴 Блокер v3.0.0 (производительность: 40 → 132.9 ф/мин; ETA 22 500: 7–9 ч → 3 ч)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 0.5 дня (2–4 часа)
Зависимость: после 53.4p (v3.14.14, final/release/progress) + 53.4n (v3.14.12, resume/логи/reconnect)

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается.

Resume (53.4n) — работает: Ctrl+C → state → [Resume] ... с чанка N/M → завершение.

Логи (53.4n) — работают: scanner/logs/scanner.log (INFO), консоль (DEBUG).

Reconnect (53.4n) — работает: [ManagerClient] [OK] Reconnected.

Final (53.4p) — только на последний чанк (chunk_idx == total_chunks - 1).

Release (53.4p) — no-op (204) для completed/pending.

Progress (53.4p) — монотонный (_total_scanned).

Замер — обязателен. Без «до/после» на одном наборе (1000 файлов, chunk_size=100, 10 чанков) — не принимаем.

📊 Контекст: почему пул пересоздаётся
Судя по логу (53.4n/53.4p, v3.14.12–v3.14.14):

text
12:44:39.349 - [FS] ProcessPoolExecutor: 4 процессов, chunk=100  ← чанк 1 завершён
12:47:41.332 [22612] INFO numexpr.utils: NumExpr defaulting to 4 threads  ← через 3 минуты!
12:47:54.812 [14108] INFO scanner.classifiers.pii_classifier: [PII] [OK] Модель ru_core_news_sm найдена  ← spaCy грузится
12:48:01.545 [22048] INFO scanner.classifiers.pii_classifier: [PII] [OK] NLP движок создан
Что происходит:

Чанк 1 завершён (12:44:39).

Новый ProcessPoolExecutor (4 процесса) запускается на чанк 2.

3 минуты — прогрев (spaCy модели грузятся в каждом процессе).

Files/min — 30–40 (вместо 132.9, как в 53.4m отчёте).

Причина: ProcessPoolExecutor создаётся на каждый чанк (внутри цикла for chunk_idx), а не один раз на всю задачу.

Следствия:

10 чанков × 3 минуты = 30 минут overhead.

ETA 22 500 — 7–9 часов (вместо 3 часов).

4 воркера пересоздаются — память скачет (то 2 ГБ, то 4 ГБ).

🛠️ BUG-286 — ProcessPoolExecutor вне цикла чанков
Что должно быть
Один ProcessPoolExecutor на всю задачу (создать до цикла чанков, shutdown — после):

python
# Было (53.4n — баг):
for chunk_idx in range(completed_chunks, total_chunks):
    if self._stop_event.is_set():
        break
    chunk = chunks[chunk_idx]
    with ProcessPoolExecutor(
        max_workers=self._config.performance.max_workers,
        initializer=_init_worker,
    ) as executor:  # ← НОВЫЙ на каждый чанк
        future = executor.submit(self._scan_chunk, chunk, task)
        result = future.result()
    findings_count += len(result)
    state.save(...)

# Стало (BUG-286):
with ProcessPoolExecutor(
    max_workers=self._config.performance.max_workers,
    initializer=_init_worker,
) as executor:  # ← ОДИН на задачу
    for chunk_idx in range(completed_chunks, total_chunks):
        if self._stop_event.is_set():
            break
        chunk = chunks[chunk_idx]
        future = executor.submit(self._scan_chunk, chunk, task)
        result = future.result()
        findings_count += len(result)
        state.save(...)
# после цикла — executor.shutdown(wait=True) автоматически (with)
Важно:

with ProcessPoolExecutor — вне цикла чанков.

shutdown(wait=True) — после цикла (автоматически, with).

Ctrl+C — KeyboardInterrupt → with → shutdown(wait=True) → finally: release_task.

Файл: scanner/src/managed_scanner.py
Найти _execute_task_linewise (или где ProcessPoolExecutor). Переместить with ProcessPoolExecutor вне цикла for chunk_idx.

Файл: scanner/connectors/filesystem.py (проверить)
Проверить: если scan_path создаёт свой ProcessPoolExecutor (на каждый вызов) — убрать (пул — в _execute_task_linewise).

Ожидание: scan_path принимает готовый executor (или scan_files — без пула).

Файл: scanner/src/managed_scanner.py — _init_worker (проверить)
Убедиться: _init_worker вызывается один раз на процесс (не на чанк). При with ProcessPoolExecutor вне цикла — initializer срабатывает один раз (4 процесса × 1 раз = 4).

Ожидание: [PII] [OK] NLP движок создан — 4 раза (не 40).

🛡️ Не сломать (53.4n + 53.4p)
1. Resume (53.4n)
state.save — после каждого чанка (как в 53.4n).

last_completed_chunk — сохраняется.

get_resume_chunk() — работает.

Проверить: Ctrl+C → [Resume] ... с чанка N/M.

2. Логи (53.4n)
_setup_logging — не трогать.

scanner/logs/scanner.log — INFO (без спама).

Проверить: файл создан, [Resume] / [Release] / [ScanState] — есть.

3. Reconnect (53.4n)
_request (reconnect) — не трогать.

Проверить: [ManagerClient] [OK] Reconnected — есть.

4. Final (53.4p)
final=True — только на последний чанк (chunk_idx == total_chunks - 1).

Проверить: SubmitResults → 200 на каждый чанк (не 400).

5. Release (53.4p)
completed/pending — 204 (no-op).

Проверить: release на completed → 204 (не 400).

6. Progress (53.4p)
_total_scanned — монотонный.

Проверить: ScanProgress — не откат (300 → 200).

🧪 Тесты
Unit — tests/unit/test_pool_reuse_v31413.py (new)
python
"""53.4o (v3.14.13): ProcessPoolExecutor — один на задачу."""
import inspect
from scanner.src.managed_scanner import ManagedScanner


def test_executor_outside_chunk_loop():
    """BUG-286: ProcessPoolExecutor создаётся ВНЕ цикла чанков."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    idx_pool = src.find("ProcessPoolExecutor")
    idx_for = src.find("for chunk_idx")
    assert idx_pool != -1, "ProcessPoolExecutor не найден"
    assert idx_for != -1, "for chunk_idx не найден"
    assert idx_pool < idx_for, "ProcessPoolExecutor должен быть ДО цикла чанков"


def test_executor_single_instance():
    """BUG-286: ProcessPoolExecutor — 1 раз (не в цикле)."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    assert src.count("with ProcessPoolExecutor") == 1, "Должен быть 1 with ProcessPoolExecutor"
E2E — tests/e2e/test_pool_reuse_v31413.py (new)
python
"""53.4o (v3.14.13): скан 1000 файлов — Files/min ≥ 120, прогрев 1 раз."""
import pytest


@pytest.mark.e2e
def test_scan_1000_files_speed(api_client, test_files_dir):
    """Files/min ≥ 120 (как 53.4m), прогрев 1 раз (не 10)."""
    ...
📋 Ручная приёмка
#	Сценарий	Ожидание
1	Скан 1000 файлов (chunk_size=100, 10 чанков)	Files/min ≥ 120 (было 30–40)
2	Прогрев	[PII] [OK] NLP движок создан — 4 раза (не 40)
3	ProcessPoolExecutor	[FS] ProcessPoolExecutor: 4 процессов — 1 раз (не 10)
4	Files/min (ETA 22 500)	~3 часа (было 7–9)
5	Resume (53.4n)	[Resume] ... с чанка N/M — работает
6	Логи (53.4n)	scanner/logs/scanner.log — есть
7	Reconnect (53.4n)	[ManagerClient] [OK] Reconnected — есть
8	Final (53.4p)	SubmitResults → 200 на каждый чанк (не 400)
9	Release (53.4p)	completed → 204 (no-op)
10	Progress (53.4p)	ScanProgress — монотонный (не откат)
✅ Definition of Done
□ ProcessPoolExecutor — вне цикла чанков (один на задачу).
□ shutdown(wait=True) — после цикла (автоматически, with).
□ scan_path — без своего пула (принимает executor).
□ _init_worker — один раз на процесс (4 раза, не 40).
□ Files/min — ≥ 120 (1000 файлов).
□ ETA 22 500 — ~3 часа (было 7–9).
□ Resume (53.4n) — работает.
□ Логи (53.4n) — работают.
□ Reconnect (53.4n) — работает.
□ Final (53.4p) — только на последний чанк (200, не 400).
□ Release (53.4p) — no-op для completed (204, не 400).
□ Progress (53.4p) — монотонный (не откат).
□ Unit test_pool_reuse_v31413.py — passed.
□ E2E test_pool_reuse_v31413.py — passed.
□ Ручная приёмка 10/10 ✅.
💾 Коммит
powershell
git add scanner/src/managed_scanner.py `
        scanner/connectors/filesystem.py `
        tests/unit/test_pool_reuse_v31413.py `
        tests/e2e/test_pool_reuse_v31413.py `
        .env docker-compose.yml `
        CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "perf: 53.4o scanner pool reuse — ProcessPoolExecutor вне цикла (v3.14.13)

BUG-286: ProcessPoolExecutor создаётся один раз на задачу (не на чанк).
Прогрев 1 раз (3 мин), Files/min 30-40 → 132.9.
ETA 22 500: 7-9ч → ~3ч.

Resume (53.4n), логи (53.4n), reconnect (53.4n), final/release/progress
(53.4p) — сохранены.

Tests: test_pool_reuse_v31413.py (unit), test_pool_reuse_v31413.py (e2e)."
📊 Отчёт (что прислать)
Замер «до» (1000 файлов, v3.14.14): Files/min, ETA 22 500.

Замер «после» (1000 файлов, v3.14.13): Files/min, ETA 22 500.

Прогрев: сколько раз [PII] [OK] NLP движок создан (4 или 40).

ProcessPoolExecutor: сколько раз [FS] ProcessPoolExecutor (1 или 10).

Resume (53.4n): работает ([Resume] ... с чанка N/M).

Логи (53.4n): scanner/logs/scanner.log — есть.

Reconnect (53.4n): [ManagerClient] [OK] Reconnected — есть.

Final (53.4p): SubmitResults → 200 (не 400).

Release (53.4p): completed → 204.

Progress (53.4p): монотонный (не откат).

Regression: 0 lost.

🎯 Что важно
Пул — вне цикла чанков. Это главное — прогрев 1 раз (3 мин), не 10 раз (30 мин).

shutdown(wait=True) — после цикла (автоматически, with). Не забыть finally: release_task (Ctrl+C).

Resume (53.4n) — не сломать. last_completed_chunk — сохраняется после каждого чанка. Пул не влияет на state.

Логи (53.4n) — не сломать. _setup_logging — не трогать.

Reconnect (53.4n) — не сломать. _request — не трогать.

Final (53.4p) — не сломать. final=True — только на последний чанк.

Release (53.4p) — не сломать. completed/pending — 204 (no-op).

Progress (53.4p) — не сломать. _total_scanned — монотонный.

scan_path — без своего пула. Если scan_path создаёт свой ProcessPoolExecutor — убрать (пул — в _execute_task_linewise).

⚠️ Побочный риск (из Фазы 2)
tempfile.gettempdir() == E:\Temp, _cleanup_temp_files глоббит tmp*/ocr_*. Тестовый набор — вне %TEMP%. Зафиксировать в docs/testing.md.