📋 ТЗ v3.14.14 — Scanner Resume Hotfix (53.4p)
Файл: prompts/tz/day_53_4p_scanner_resume_hotfix.md
Дата: 25.10.2026
Версия: v3.14.13 → v3.14.14
Приоритет: 🔴 Блокер v3.0.0 (53.4n resume не работает — задача теряется)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 0.5 дня (2–4 часа)
Зависимость: после 53.4n (v3.14.12, resume) + 53.4o (v3.14.13, pool reuse)

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Resume (53.4n) должен работать: задача не теряется, продолжается с последнего чанка. Pool reuse (53.4o) сохраняется. Логи (53.4n) сохраняются. Reconnect (53.4n) сохраняется.

Замер — обязателен. Без E2E: остановка → resume → завершение (без потери задачи) — не принимаем.

🔴 Контекст: что сломалось в 53.4n
Судя по логу (25.10.2026, 12:48):

text
12:48:47 - [ScanProgress] 300/22500 (1.3%) | скорость 40.6 ф/мин
12:48:52 - [ScanProgress] 200/22500 (0.9%) | скорость 26.7 ф/мин   ← ОТКАТ (300→200)
12:48:53 - ERROR - [SubmitResults] batch 1/1 failed: 400
12:48:53 - ERROR - response: {"detail":"Task status is completed, expected assigned/running"}
12:48:53 - ERROR - Чанк 2/225 не отправлен — задание будет продолжено с этого чанка
12:48:53 - WARNING - [Release] Failed: 400 {"detail":"Task is not assigned (status: completed)"}
12:48:53 - WARNING - [Resume] Не удалось вернуть задание 223 в очередь — Manager вернёт его по таймауту
12:48:54 - DEBUG - [Heartbeat] OK: idle
12:48:55 - DEBUG - [GetTask] No pending tasks   ← задача ПОТЕРЯНА
Три бага:

#	Баг	Последствие
BUG-287	final передаётся на чанк 1 (не на последний) → Manager закрывает задачу (completed) → чанк 2 — 400	Задача теряется
BUG-288	release для completed — 400 (не no-op) → сканер сдаётся	Задача не возвращается в очередь
BUG-289	ScanProgress откатывается (300 → 200)	Оператор дезинформирован
🛠️ BUG-287 — final только на последний чанк
Проблема
final=True в SubmitResults передаётся на чанк 1 (или на каждый чанк). Manager видит final=True → закрывает задачу (completed) → не принимает чанк 2 (400: Task status is completed).

Что нужно сделать
Файл: scanner/src/managed_scanner.py (или где SubmitResults).

Было (вероятно):

python
# final=True на каждый чанк (или на чанк 0)
final = True  # ← ошибка
# или:
final = (chunk_idx == 0)  # ← ошибка
Стало:

python
# final=True ТОЛЬКО на последний чанк
final = (chunk_idx == total_chunks - 1)
Если final не используется (Manager сам закроет по completed == total) — убрать final из SubmitResults (Manager не должен закрывать по final, а только по completed всех чанков).

Проверить: SubmitResults — один вызов на чанк, final — только на последний.

🛠️ BUG-288 — release для completed — no-op (204), не 400
Проблема
POST /api/scanner/tasks/{id}/release для задачи в completed → 400: Task is not assigned (status: completed). Сканер сдаётся (не может вернуть в очередь).

Что нужно сделать
Файл: manager/src/api/scanner.py (release_task).

Было (вероятно):

python
if task.status not in ("assigned", "running"):
    raise HTTPException(400, f"Task is not assigned (status: {task.status})")
Стало:

python
if task.status == "completed":
    # Задача уже завершена — release не нужен, но и не ошибка
    logger.info("[Release] Task %d already completed — no-op", task_id)
    return {"status": "noop", "reason": "already_completed"}

if task.status not in ("assigned", "running"):
    raise HTTPException(409, f"Task is not assigned (status: {task.status})")
Важно:

completed → 204 (или 200 {"status": "noop"}) — не ошибка.

pending → 204 (уже в очереди).

failed → 409 (нельзя release failed — но не 400).

assigned / running → 204 (release).

Или — сканер не должен вызывать release, если SubmitResults вернул 400: Task status is completed (задача уже завершена — release не нужен).

Рекомендация: оба фикса:

Manager: release для completed — no-op (204).

Сканер: если SubmitResults → 400: completed — не вызывать release (задача уже закрыта).

🛠️ BUG-289 — ScanProgress монотонный (не откат)
Проблема
ScanProgress откатывается (300 → 200). Причина — progress сбрасывается при повторном чанке (или при пересчёте). Счётчик не монотонный.

Что нужно сделать
Файл: scanner/src/managed_scanner.py (или где set_progress).

Было (вероятно):

python
# progress = files_scanned (текущий чанк)
self._set_progress(files_scanned=chunk_processed)  # ← сбрасывается
Стало:

python
# progress = накопительный (не сбрасывается)
self._total_scanned += chunk_processed
self._set_progress(files_scanned=self._total_scanned)
Или:

python
# progress = max(текущий, предыдущий) — монотонный
self._set_progress(files_scanned=max(self._total_scanned, chunk_processed))
Важно:

progress.files_scanned — накопительный (с учётом resume: resume_index + chunk_processed).

Не сбрасывается при переходе между чанками.

Монотонный (только растёт).

🧪 Тесты
Unit — tests/unit/test_resume_hotfix_v31414.py (new)
python
"""53.4p (v3.14.14): BUG-287, BUG-288, BUG-289."""
import inspect
from scanner.src.managed_scanner import ManagedScanner


def test_final_only_last_chunk():
    """BUG-287: final=True только на последний чанк."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    # final = (chunk_idx == total_chunks - 1)
    assert "total_chunks - 1" in src or "total_chunks-1" in src
    # Не должно быть final=True на каждый чанк
    assert "final = True" not in src


def test_progress_monotonic():
    """BUG-289: ScanProgress монотонный (накопительный)."""
    src = inspect.getsource(ManagedScanner._execute_task_linewise)
    # total_scanned += chunk_processed
    assert "_total_scanned" in src or "total_scanned" in src


def test_release_completed_noop():
    """BUG-288: release для completed — no-op (не 400)."""
    from manager.src.api.scanner import release_task
    src = inspect.getsource(release_task)
    # completed → return noop (не raise 400)
    assert "completed" in src
    assert "noop" in src or "204" in src or "return" in src
E2E — tests/e2e/test_resume_hotfix_v31414.py (new)
python
"""53.4p (v3.14.14): E2E — resume без потери задачи."""
import pytest


@pytest.mark.e2e
def test_resume_does_not_lose_task(api_client, test_files_dir):
    """Resume: остановка → resume → завершение (без потери задачи)."""
    # 1. Создать resource (1000 файлов), запустить scan (chunk_size=100).
    # 2. Дождаться ≥2 чанков.
    # 3. Ctrl+C.
    # 4. Проверить: Manager task status = pending (не failed, не completed).
    # 5. Перезапустить сканер.
    # 6. Проверить: [Resume] ... с чанка 3/10.
    # 7. Дождаться завершения — findings count = baseline, task status = completed.
    ...


@pytest.mark.e2e
def test_progress_monotonic(api_client, test_files_dir):
    """ScanProgress монотонный (не откат)."""
    # 1. Запустить скан, собрать progress.files_scanned (каждые 2 сек).
    # 2. Проверить: каждое следующее ≥ предыдущего.
    ...
📋 Ручная приёмка
#	Сценарий	Ожидание
1	Скан 1000 файлов (chunk_size=100)	ScanProgress растёт (не откат)
2	Через 2 чанка — Ctrl+C	Manager task = pending (не completed, не failed)
3	Перезапустить сканер	[Resume] ... с чанка 3/10
4	ScanProgress	Начинается с ~200 (не с 1)
5	Дождаться завершения	Manager task = completed, findings = baseline (без дублей)
6	final	Только на последний чанк (SubmitResults → 200, не 400)
7	release для completed	204 (no-op), не 400
8	Pool reuse (53.4o)	ProcessPoolExecutor: 4 процессов — 1 раз (не 10)
9	Логи (53.4n)	scanner/logs/scanner.log — есть
10	Reconnect (53.4n)	[ManagerClient] [OK] Reconnected — есть
✅ Definition of Done
□ BUG-287: final=True — только на последний чанк (chunk_idx == total_chunks - 1).
□ BUG-288: Manager release для completed — no-op (204), не 400.
□ BUG-288: Сканер не вызывает release, если SubmitResults → 400: completed.
□ BUG-289: ScanProgress — монотонный (накопительный, не откат).
□ Pool reuse (53.4o) — сохраняется (1 пул на задачу).
□ Resume (53.4n) — работает (задача не теряется).
□ Логи (53.4n) — работают.
□ Reconnect (53.4n) — работает.
□ Unit test_resume_hotfix_v31414.py — passed.
□ E2E test_resume_hotfix_v31414.py — passed.
□ Ручная приёмка 10/10 ✅.
💾 Коммит
powershell
git add scanner/src/managed_scanner.py `
        manager/src/api/scanner.py `
        tests/unit/test_resume_hotfix_v31414.py `
        tests/e2e/test_resume_hotfix_v31414.py `
        .env docker-compose.yml `
        CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "fix: 53.4p scanner resume hotfix — final, release, progress (v3.14.14)

BUG-287: final=True только на последний чанк (не на чанк 1).
BUG-288: release для completed — no-op (204), не 400.
         Сканер не вызывает release, если SubmitResults → 400: completed.
BUG-289: ScanProgress монотонный (накопительный, не откат).

Resume (53.4n), pool reuse (53.4o), логи (53.4n), reconnect (53.4n) — сохранены.

Tests: test_resume_hotfix_v31414.py (unit), test_resume_hotfix_v31414.py (e2e)."
📊 Отчёт (что прислать)
Diff по 2 файлам (managed_scanner.py, manager/scanner.py) — или описание.

Unit test_resume_hotfix_v31414.py — passed.

E2E test_resume_hotfix_v31414.py — passed.

Ручной сценарий:

Ctrl+C → Manager task = pending (не completed).

Перезапуск → [Resume] ... с чанка 3/10.

ScanProgress — монотонный (не откат).

Завершение → Manager task = completed, findings = baseline.

final: SubmitResults → 200 на каждый чанк (не 400).

release для completed: 204 (no-op).

Pool reuse (53.4o): ProcessPoolExecutor — 1 раз.

Логи (53.4n): scanner/logs/scanner.log — есть.

Reconnect (53.4n): [ManagerClient] [OK] Reconnected — есть.

🎯 Что важно
final — только на последний чанк. Иначе Manager закрывает задачу раньше времени → чанк 2 — 400.

release для completed — no-op (204). Не 400. Сканер не должен ломаться.

Сканер не вызывает release, если 400: completed. Задача уже закрыта — release не нужен.

ScanProgress — монотонный. Накопительный (_total_scanned += chunk_processed), не сбрасывается.

Pool reuse (53.4o) — не сломать. Пул — вне цикла чанков.

Resume (53.4n) — не сломать. last_completed_chunk — сохраняется.

Логи (53.4n) — не сломать. _setup_logging — не трогать.

Reconnect (53.4n) — не сломать. _request — не трогать.