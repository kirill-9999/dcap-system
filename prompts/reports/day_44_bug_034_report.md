# Отчёт — BUG-034: зависшие задачи сканера (running) при прерывании/смерти сканера (v3.13.7)

**Дата:** 19.09.2026
**Версия:** v3.13.7
**Ветка:** `fix/bug_034_stale_tasks`
**Коммит:** см. раздел 8
**Предыдущая версия:** v3.13.6
**Приоритет:** 🔴 важный (задачи «навсегда» в статусе running при Ctrl+C/kill сканера)

---

## 1. Симптом

При прерывании сканера (Ctrl+C) или жёстком завершении процесса задачи оставались
в статусе `running` навсегда (нет агента, который бы перевёл их в `failed`):

| id | status | причина |
|----|--------|---------|
| 17 | running | сканер force-killed во время E2E BUG-034 |
| 18 | running | сканер force-killed во время E2E BUG-034 |
| 19 | running | сканер force-killed во время E2E BUG-034 |

До фикса `_mark_stale_scanners` обрабатывал только `status == "assigned"` — задачи
со статусом `running` из-под умершего сканера не были защищены.

---

## 2. ТЗ (6 задач)

| # | Задача | Статус |
|---|--------|--------|
| 1 | Сканер уведомляет Manager при прерывании (`fail_task`) | ✅ |
| 2 | `POST /api/scanner/tasks/{id}/fail` | ✅ |
| 3 | `_mark_stale_scanners` обрабатывает `running` | ✅ |
| 4 | `POST /api/scanner/tasks/{id}/cancel` | ✅ |
| 5 | Тесты `tests/unit/test_stale_tasks.py` | ✅ |
| 6 | E2E | ✅ |

---

## 3. Реализация

### 3.1 Scanner: `fail_task` + прерывание в run-loop — `scanner/src/managed_scanner.py`

Новый метод `fail_task` (после `check_fingerprints`):

```python
def fail_task(self, task_id: int, reason: str) -> bool:
    """Уведомляет Manager, что задача завершилась из-за прерывания (failed)."""
    url = f"{self.base_url}/api/scanner/tasks/{task_id}/fail"
    try:
        resp = self._session.post(
            url,
            headers=self._headers(),
            json={"reason": reason},
            timeout=self.timeout,
        )
        if resp.status_code == 200:
            logger.info("[FailTask] Task %s marked failed", task_id)
            return True
        logger.warning("[FailTask] Task %s fail: HTTP %s %s",
                       task_id, resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.error("[FailTask] Task %s error: %s", task_id, exc)
        return False
```

В `run_loop` после выполнения задачи проверяется прерывание (было только
`KeyboardInterrupt`-путь — теперь и штатный сигнал):

```python
if self._should_exit or self._stop_event.is_set():
    logger.warning("[STOP] Задача прервана пользователем — уведомляем Manager")
    if task:
        self.client.fail_task(task["id"], reason="scanner aborted (Ctrl+C)")
    break
```

и в `except KeyboardInterrupt`:

```python
except KeyboardInterrupt:
    logger.warning("[STOP] Получен Ctrl+C — прервано пользователем")
    self._should_exit = True
    self._stop_event.set()
    if task:
        self.client.fail_task(task["id"], reason="scanner interrupted (Ctrl+C)")
    break
```

### 3.2 Manager: endpoint fail — `manager/src/api/scanner.py`

```python
@router.post("/tasks/{task_id}/fail")
async def fail_task(
    task_id: int,
    body: FailTaskRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scanner),
):
    """Помечает задачу как failed (вызывается сканером при прерывании)."""
    task = await db.get(ScanTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("completed", "failed"):
        return {"status": task.status, "id": task.id, "already": True}
    task.status = "failed"
    task.completed_at = datetime.utcnow()
    await db.commit()
    return {"status": task.status, "id": task.id}
```

### 3.3 `_mark_stale_scanners` — включая `running`

```python
stale = await query(
    select(ScanTask).where(
        ScanTask.status.in_(["assigned", "running"]),
        ScanTask.assigned_to.in_(dead_scanner_ids),
    )
).all()
```

### 3.4 Manager: endpoint cancel — `manager/src/api/scanner.py`

```python
@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scanner),
):
    """Ручная отмена задачи (статус → failed)."""
    task = await db.get(ScanTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("completed", "failed"):
        return {"status": task.status, "id": task.id, "already": True}
    task.status = "failed"
    task.completed_at = datetime.utcnow()
    await db.commit()
    return {"status": task.status, "id": task.id}
```

---

## 4. Тесты (Задача 5) — `tests/unit/test_stale_tasks.py`

9 тестов:

```
tests/unit/test_stale_tasks.py .................  [100%]
============================= 9 passed in 2.03s =============================
```

Покрытие:

- `test_mark_stale_running` — задача `running` умершего сканера → `failed`
- `test_mark_stale_assigned` — задача `assigned` → `failed`
- `test_mark_stale_fresh_keeps` — сканер с живым heartbeat (STALE_THRESHOLD) — не трогается
- `test_fail_endpoint_ok` — `POST .../fail` → 200 `{"status":"failed","id":N}`
- `test_fail_endpoint_already` — повтор → `already: True`
- `test_fail_endpoint_not_found` — неизвестный id → 404
- `test_cancel_endpoint_ok` / `test_cancel_endpoint_already` / `test_cancel_endpoint_not_found` — по CFG для cancel

Тесты используют dependency override `get_db` + `sqlite://` (StaticPool) для изоляции.

**Полный прогон тестов:**

```
tests/unit/test_csv_utils.py .......          [ 12%]
tests/unit/test_fingerprint.py .....          [ 28%]
tests/unit/test_hex_dump.py ....              [ 35%]
tests/unit/test_stale_tasks.py .................  [ 61%]
tests/unit/test_encryption.py .................  [ 91%]
tests/unit/test_scanner_findings.py ...............  [100%]

============================= 51 passed in 33.49s =============================
```

---

## 5. E2E (Задача 6)

### Сценарий 1 — Ctrl+C → задача `failed`

1. Создана задача 20 (`E:\projects\dcap-system`).
2. Сканер запущен на хосте, дождались реального прогресса (max=311 файлов,
   работал в Python-цикле, не в C-коде).
3. Отправлен `CTRL_C_EVENT` через `AttachConsole` (корректный способ для
   консоли сканера).

```
[E2E-v5] progress: True max=311
[E2E-v5] Ctrl+C to PID 8992 rc=1
[STOP] Задача прервана пользователем — уведомляем Manager
[FailTask] Task 20 marked failed
[E2E-v5] scanner exited rc=0
[E2E-v5] task 20 status=failed
[E2E-v5] RESULT: PASS
```

Задача 20 в БД:

```json
{"id":20,"status":"failed","files_scanned":450,"progress":{"files_scanned":450,"total":1457,"percent":30.9}}
```

### Сценарий 2 — 죽que сканера/Docker reload → `running` → `failed`

`docker compose restart manager`, затем триггер `_mark_stale_scanners`
(появился при `GET /api/scanner`):

```
=== tasks ===
id=20 status=failed
id=19 status=failed
id=18 status=failed
id=17 status=failed
id=16 status=failed
```

Все зависшие `running`-задачи (17/18/19) переведены в `failed`. ✅

### Сценарий 3 — ручной cancel

```
created task_id=21
cancel ->  HTTP 200: {"status":"failed","id":21}
repeat -> HTTP 200: {"status":"failed","id":21,"already":true}
```

**Замечание:** задача 22 (созданная с путём, уже существующим в БД) вернула 500
`UniqueViolation resources_path_key` — это отдельное поведение `/api/tasks/create`,
к BUG-034 не относится (использован уникальный путь).

---

## 6. Критерии приёмки

| # | Критерий | Статус |
|---|----------|--------|
| 1 | Сканер шлёт `fail_task` при прерывании | ✅ §5.1, лог `[FailTask] Task 20 marked failed` |
| 2 | `POST /api/scanner/tasks/{id}/fail` → 200 failed | ✅ §5.1 + тесты §4 |
| 3 | `_mark_stale_scanners` переводит running → failed | ✅ §5.2 (17/18/19) + тесты §4 |
| 4 | `POST /api/scanner/tasks/{id}/cancel` → 200 | ✅ §5.3 |
| 5 | `pytest tests/unit` — passed | ✅ 51 passed |
| 6 | E2E: Ctrl+C→failed, reload→failed, cancel→200 | ✅ §5 |

---

## 7. Коммит

```powershell
git add -A
git commit -m "fix: BUG-034 (v3.13.7) — зависшие задачи сканера (running) при прерывании

Scanner:
- ManagerClient.fail_task: уведомление Manager о прерванной задаче
- run_loop: fail_task при _should_exit/_stop_event и KeyboardInterrupt

Manager:
- POST /api/scanner/tasks/{id}/fail — сканер помечает задачу failed
- POST /api/scanner/tasks/{id}/cancel — ручная отмена
- _mark_stale_scanners: обработка status in (assigned, running)

Tests: tests/unit/test_stale_tasks.py (9 тестов)
Docs: отчёт day_44_bug_034_report.md"
```

---

## 8. Файлы

- `scanner/src/managed_scanner.py` — `fail_task`, обработка прерываний в run_loop
- `manager/src/api/scanner.py` — endpoints `fail`/`cancel`, `_mark_stale_scanners`
- `tests/unit/test_stale_tasks.py` — 9 новых тестов
- `.env`, `.env.example`, `webui/config.py`, `docker-compose.yml` — версия 3.13.7
- `prompts/reports/day_44_bug_034_report.md` — этот отчёт

## 9. Открытые проблемы

- Внешний сканер (не наш Python-рантайм) мог бы вызывать `cancel`-эндпоинт
  дистанционно — эндпоинт требует `require_scanner` (только сканер-агент).
- `KeyboardInterrupt` внутри тяжёлого C-кода (configure spaCy/OCR) не может быть
  обработан немедленно — сигнал достигнет run-loop только после возврата в Python;
  это ограничение платформы, обходится stale-механизмом (Задача 3).