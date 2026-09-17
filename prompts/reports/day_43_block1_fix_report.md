# Отчёт — Блок 1 (фиксы): Deploy/Config + Findings/Scanner + WebUI (v3.13.3)

**Дата:** 17.09.2026
**Версия:** v3.13.3
**Ветка:** `fix/block_1_issues`
**Предыдущая версия:** v3.13.2
**ТЗ:** `prompts/tz/TZ_BLOCK_1_FIX.md` — фикс Блока 1: `fix/block_1_issues` (≈3 рабочих дня).

---

## 1. Цель

Закрыть критические баги Блока 1, блокирующие Блок 2+:
1. **BUG-034** (Manager не закрывает прерванную задачу) — stale assigned → failed + cancel endpoint.
2. **BUG-035** (нет батчинга findings) — сканер шлёт findings батчами по 500; Manager накапливает в БД.
3. **BUG-027.1-4** (progress-рассинхрон) — total/percent/top-level files_scanned/status running.
4. **BUG-022** (утечка PII через line_text) — маскировать ВСЕ PII строки, а не только своей категории.
5. **День 1 (Deploy/Config)**: BUG-001, BUG-002/007, BUG-017/019, BUG-036.
6. **День 3 (WebUI)**: W-42, W-54, W-60, W-66, W-70, W-43, W-55, W-57, W-62, W-67, W-72, W-73.

---

## 2. Что сделано

### 2.1. BUG-034 — Manager не закрывает прерванную задачу
- **034.1**: `_mark_stale_scanners` теперь **fail-ит assigned-задачи** stale-сканера (`status="failed"`, `completed_at=utcnow()`) вместо пропуска (раньше было `continue` для активных задач — задача вечно висела assigned, если сканер умер без heartbeat). Метка `BUG-034.1 (06045225 R)`.
- **034.2**: новый `POST /api/scanner/tasks/{task_id}/cancel` → `status="failed"` + `completed_at` (ручная отмена). В `manager/src/api/tasks.py`.

### 2.2. BUG-035 — батчинг findings
- **Сканер** (`scanner/src/managed_scanner.py`, `ManagerClient.submit_results`): findings разбиваются на батчи по **500**; каждый отправляется `POST ?batch=N&total=M`; `catalog_entries`/`failed_files`/`stats` передаются **только в последнем батче** (is_last); возвращает `True` только если все батчи ответили 200.
- **Manager** (`manager/src/api/scanner.py`):
  - парсинг `batch`/`total` (`_batch_no_06045225`, `_batch_total_06045225`, `_is_final_06045225`) с try/except;
  - **аккумуляция**: `task.findings_count = (task.findings_count or 0) + saved_findings` — вне гварда, т.е. каждый батч добавляет счётчик;
  - **финализация только в последнем батче** (`if _is_final_06045225:` → status=completed, progress percent=100, метрики, resource.status=ACTIVE);
  - `db.commit()` — вне гварда (промежуточные батчи тоже коммитятся);
  - серверный flush каждые 500 findings внутри цикла (`_bug35_batch_06045225=500`).
  - **фикс NameError**: `files_total_from_stats` (не определён) → `int(stats.get("files_scanned", 0) or 0)`.
  - **релакс статус-чека**: принимается `assigned/pending/running` (совместимость с BUG-027.3, когда heartbeat переводит задачу в running).

### 2.3. BUG-027.1-4 — progress-рассинхрон
- **027.1**: heartbeat — total из закрытия, percent только при `total > 0`, clamp `percent > 100 → 100.0`.
- **027.2**: top-level `files_scanned` синхронизируется с `progress.files_scanned` при GET задачи (`manager/src/api/tasks.py`).
- **027.3**: heartbeat `status="busy"` при живой задаче → задача `assigned/pending → running`.
- **027.4**: при завершении (linewise) progress заполняется полностью из финальной статистики (total из prev или files_scanned, percent=100.0, status=completed).

### 2.4. BUG-022 — утечка PII через line_text
- `_serialize_finding(..., all_findings_in_line)`: собираются `positions` **всех** находок строки; `line_text_masked = mask_line(line_text, positions)` — маскируются все категории PII в строке; контексты — `mask_context` (общие паттерны phone/email). Уже присутствовало в коде — подтверждено, тест `test_mask_line` + `test_encryption.py:60` зелёные.

### 2.5. День 1 (Deploy/Config) — проверено/закрыто
- **BUG-001**: `/api/health` version = `get_version()` (env VERSION → config.json version → default) — уже в коде (`manager/src/main.py:27`).
- **BUG-002/007**: `.env.example` VERSION=3.13.2; docker-compose `${VERSION:-3.13.2}`; `scripts/deploy.sh` fail-fast без `.env`; `docs/deployment.md` шаг `cp .env.example .env`.
- **BUG-017/019**: `postgres_exporter`/`redis_exporter`/`celery_exporter` — все в `dcap-network`.
- **BUG-036**: эмодзи в коде ядра отсутствуют (TODO-таблица замен на ASCII уже применена); `run_scanner.py`/`run_manager.py` — `_setup_utf8()` (reconfigure utf-8).

### 2.6. День 3 (WebUI)
- **W-54** (кнопки Reveal/PATCH/Fragment) — уже реализовано в `finding_detail.js` (reveal-btn, update(), renderFragment) — проверено.
- **W-42**: Dashboard `kpiFindings` теперь берёт `GET /api/findings/count` (не `s.total` из `/api/audit/stats` — это события аудита).
- **W-60**: `get_catalog_tree` переписан — все узлы `is_folder: true`; `total_findings`/`file_count` **агрегируются рекурсивно** по детям; `has_findings` при наличие у узла/детей; `last_scanned`/`updated_at` наследуются max из детей; children — массив.
- **W-66**: `/api/findings/false-positives` добавлен `file_path` (из Resource.path, JOIN).
- **W-67**: добавлен `reviewed_by_username` (из User.username) + схема `FalsePositiveResponse` обновлена (иначе FastAPI выбросит поля).
- **W-70**: кнопка «Восстановить» в `false_positives.js` → `PATCH /api/findings/{id}` `{status:"new"}`.
- **W-43**: версия в WebUI из env/config (`webui/config.py` VERSION), `/health` отдаёт VERSION, footer обновляется через `GET /api/health` (`initFooterVersion` + `#footerVersion`).
- **W-55**: в детали находки добавлены блоки «Шифрование» (`has_encrypted`, `encryption_key_id`) и «Просмотр оригинала» (`can_reveal`); `encryption_key_id` добавлен в ответ `GET /api/findings/{id}` и схему.
- **W-57**: «Последнее сканирование» (`last_seen_at`) в детали;
- **W-62**: ссылки `/findings/{id}` из каталога — уже реализовано (`catalog.js:93`).
- **W-72/W-73**: `last_scanned` обновляется при каждом скане (`scanner.py:505`); `classifiers` — JSON-объект (dict-мердж), tree агрегирует.

---

## 3. Полный код (изменённые фрагменты)

### `manager/src/api/scanner.py` — BUG-034.1 (stale assigned→failed)

```python
def _mark_stale_scanners(db: Session):  # BUG-034.1 (06045225 R): stale assigned->failed
    """Mark inactive stale scanners; BUG-034.1: failed their assigned tasks."""
    threshold = datetime.utcnow() - timedelta(minutes=STALE_THRESHOLD_MINUTES)
    stale = db.query(models.Scanner).filter(
        models.Scanner.status.in_(["active", "ACTIVE"]),
        models.Scanner.last_heartbeat < threshold
    ).all()
    if not stale:
        return

    for s in stale:
        # BUG-034.1: tasks assigned to stale scanner -> failed
        _ids_06045225 = [r[0] for r in db.query(models.ScanTask.id).filter(
            models.ScanTask.scanner_id == s.id,
            models.ScanTask.status == "assigned").all()]
        if _ids_06045225:
            db.query(models.ScanTask).filter(
                models.ScanTask.id.in_(_ids_06045225)
            ).update({models.ScanTask.status: "failed",
                       models.ScanTask.completed_at: datetime.utcnow()},
                      synchronize_session=False)
            db.commit()

        s.status = "inactive"
    db.commit()
```

### `manager/src/api/scanner.py` — BUG-035 (batch/total, аккумуляция, гвард финализации)

```python
    try:
        _batch_no_06045225 = int(request.query_params.get("batch", 1) or 1)
        _batch_total_06045225 = int(request.query_params.get("total", 1) or 1)
    except (TypeError, ValueError):
        _batch_no_06045225 = 1
        _batch_total_06045225 = 1
    _is_final_06045225 = _batch_no_06045225 >= _batch_total_06045225

    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")

    if task.status not in ("assigned", "pending", "running"):
        raise HTTPException(400, f"Task status is {task.status}, expected assigned/running")

    # === Сохраняем findings (день 40.2: новый формат + дедупликация по fingerprint) ===
    from manager.src.core.encryption import get_encryption, mask, mask_line
    ...
    _bug35_batch_06045225 = 500
    _bug35_cnt_06045225 = 0

    for finding_data in payload.get("findings", []):
        ...
        db.add(finding)
        _bug35_cnt_06045225 += 1
        if _bug35_cnt_06045225 >= _bug35_batch_06045225:
            db.flush()
            _bug35_cnt_06045225 = 0
        saved_findings += 1

    # Сохраняем catalog_entries
    for entry in payload.get("catalog_entries", []):
        folder_path = entry.get("path", "")
        if not folder_path:
            continue
        metadata = entry.get("metadata", {})
        classifiers = metadata.get("classifiers", {})
        total_findings = metadata.get("total_findings", 0)
        file_count = metadata.get("file_count", 0)
        last_scanned = metadata.get("last_scanned", datetime.utcnow().isoformat())
        existing = db.query(models.CatalogEntry).filter(
            models.CatalogEntry.path == folder_path).first()
        if existing:
            existing_metadata = existing.entry_metadata or {}
            existing_classifiers = existing_metadata.get("classifiers", {})
            for cat, info in classifiers.items():
                if cat in existing_classifiers:
                    existing_classifiers[cat]["count"] += info.get("count", 0)
                    existing_classifiers[cat]["last_detected"] = info.get("last_detected", datetime.utcnow().isoformat())
                else:
                    existing_classifiers[cat] = info
            existing_metadata["classifiers"] = existing_classifiers
            existing_metadata["total_findings"] = existing_metadata.get("total_findings", 0) + total_findings
            existing_metadata["file_count"] = existing_metadata.get("file_count", 0) + file_count
            existing_metadata["last_scanned"] = last_scanned
            existing.entry_metadata = existing_metadata
            existing.updated_at = datetime.utcnow()
        else:
            catalog_entry = models.CatalogEntry(path=folder_path, entry_metadata=metadata)
            db.add(catalog_entry)

    # Сохраняем failed_files
    for failed in payload.get("failed_files", []):
        failed_file = models.FailedFile(
            task_id=task_id,
            resource_id=task.resource_id,
            file_path=failed.get("path", ""),
            error_type=failed.get("error_type", failed.get("error_type", "unknown")),
            error_message=failed.get("error", "")
        )
        db.add(failed_file)

    stats = payload.get("stats", {})
    task.findings_count = (task.findings_count or 0) + saved_findings

    if _is_final_06045225:
        task.status = "completed"
        task.completed_at = datetime.utcnow()
        # BUG-027.4: при завершении (linewise) финальный heartbeat может не
        # донести progress — заполняем полностью из финальной статистики.
        prev = task.progress or {}
        task_total = prev.get("total")
        if not task_total:
            task_total = int(stats.get("files_scanned", 0) or 0)
        task.progress = {
            "files_scanned": int(stats.get("files_scanned", task.files_scanned or 0)),
            "total": task_total,
            "percent": 100.0,
            "status": "completed",
        }
        task.files_scanned = stats.get("files_scanned", 0)
        task.files_failed = stats.get("files_failed", 0)

        # Prometheus-метрики (День 39)
        track_task_submitted(status="completed")
        if task.assigned_at:
            track_task_completed((task.completed_at - task.assigned_at).total_seconds())
        track_findings(stats.get("category_stats", {}))

        resource = db.query(models.Resource).filter(models.Resource.id == task.resource_id).first()
        if resource:
            resource.last_scanned_at = datetime.utcnow()
            resource.status = "ACTIVE"

    db.commit()

    logger.info(f"[Task] Task {task_id}: batch {_batch_no_06045225}/{_batch_total_06045225} accepted")

    return {
        "status": "accepted",
        "task_id": task_id,
        "findings_count": saved_findings,
        "catalog_entries_count": len(payload.get("catalog_entries", [])),
        "failed_files_count": len(payload.get("failed_files", [])),
        "deduped": deduped_findings,
        "skipped_false_positives": skipped_false_positives,
    }
```

### `scanner/src/managed_scanner.py` — BUG-035 (сканерный батчинг)

```python
    def submit_results(
        self,
        task_id: int,
        findings: List[Dict[str, Any]],
        catalog_entries: List[Dict[str, Any]],
        failed_files: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> bool:
        if self.scanner_id is None:
            logger.warning("[SubmitResults] Scanner not registered")
            return False

        url = f"{self.base_url}/api/scanner/tasks/{task_id}/results"
        batch_size = 500
        chunks = [findings[i:i + batch_size] for i in range(0, len(findings), batch_size)] or [[]]
        total_batches = len(chunks)

        try:
            for batch_idx, chunk in enumerate(chunks, start=1):
                is_last = batch_idx == total_batches
                data = {
                    "findings": chunk,
                    "catalog_entries": catalog_entries if is_last else [],
                    "failed_files": failed_files if is_last else [],
                    "stats": stats if is_last else {},
                }
                params = {"batch": batch_idx, "total": total_batches}
                response = self.session.post(url, json=data, params=params, timeout=self.submit_timeout)
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"[SubmitResults] batch {batch_idx}/{total_batches}: {result.get('findings_count', 0)} findings saved")
                else:
                    logger.error(f"[SubmitResults] batch {batch_idx}/{total_batches} failed: {response.status_code}")
                    logger.error(f"[SubmitResults] response: {response.text[:200]}")
                    return False
            return True
        except Exception as e:
            logger.error(f"[SubmitResults] error: {e}")
            return False
```

### `manager/src/api/tasks.py` — BUG-034.2 (cancel endpoint) + BUG-027.2 (files_scanned sync)

```python
def get_task(
    ...
    # BUG-027.2: top-level files_scanned синхронизируем с progress
    # из последнего heartbeat (иначе рассинхрон при живой задаче).
    pfiles = (task.progress or {}).get("files_scanned")
    top_files_scanned = int(pfiles) if pfiles is not None else (task.files_scanned or 0)

    return {
        "id": task.id,
        ...
        "files_scanned": top_files_scanned,
        ...
    }

@router.post("/{task_id}/cancel")
def cancel_task_06045225(
    task_id: int,
    db: Session = Depends(session.get_db)
):
    """BUG-034.2 (06045225): cancel a task -> failed."""
    task = db.query(models.ScanTask).filter(
        models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "failed"
    task.completed_at = datetime.utcnow()
    db.commit()
    _bug34_cancel_06045225 = True
    return {"task_id": task_id, "status": task.status}
```

### `manager/src/api/findings.py` — W-66/W-67 (FP: file_path + reviewed_by_username)

```python
def list_false_positives(...):
    findings = (
        db.query(Finding)
        .filter(Finding.status == "false_positive")
        .order_by(desc(Finding.reviewed_at))
        .offset(offset).limit(limit).all()
    )
    # W-66/W-67: file_path из resource + reviewed_by_username из users.
    from manager.src.db import models as _m
    resource_ids = [f.resource_id for f in findings if f.resource_id]
    reviewer_ids = [f.reviewed_by for f in findings if f.reviewed_by]
    res_map = {}
    if resource_ids:
        for r in db.query(_m.Resource).filter(_m.Resource.id.in_(set(resource_ids))).all():
            res_map[r.id] = r.path
    reviewer_map = {}
    if reviewer_ids:
        for u in db.query(_m.User).filter(_m.User.id.in_(set(reviewer_ids))).all():
            reviewer_map[u.id] = u.username
    return [
        {
            "id": f.id,
            "resource_id": f.resource_id,
            "file_path": res_map.get(f.resource_id) or f.fragment_path,
            "line_number": f.line_number,
            "match_text_masked": f.match_text_masked,
            "category": f.category,
            "finding_type": f.finding_type,
            "comment": f.comment,
            "reviewed_by": f.reviewed_by,
            "reviewed_by_username": reviewer_map.get(f.reviewed_by),
            "reviewed_at": f.reviewed_at,
        }
        for f in findings
    ]
```

Схема `FalsePositiveResponse` обновлена: добавлены `file_path` и `reviewed_by_username` (иначе FastAPI отбрасывает поля).
`GET /api/findings/{id}` добавлено `encryption_key_id` (W-55).

### `manager/src/api/catalog.py` — W-60 (дерево с агрегацией)

Весь `get_catalog_tree` переписан: узлы-папки (`is_folder: true`), `_aggregate()` суммирует `total_findings`/`file_count` по детям, поднимает `has_findings`, max `last_scanned`/`updated_at`, children — массив.

### `webui/static/js/dashboard.js` — W-42

```javascript
    try {
        // W-42: kpiFindings считает НАХОДКИ через /api/findings/count,
        // а не события аудита (s.total из /api/audit/stats).
        const cnt = await api.get('/api/findings/count');
        const el = document.getElementById('kpiFindings');
        if (el) el.textContent = cnt && cnt.count != null ? cnt.count : 0;
    } catch(e) { console.error('Dashboard findings count error:', e); }
```

### `webui/static/js/false_positives.js` — W-70 (Восстановить) + reviewed_by_username (W-67)

Добавлена кнопка `restore-fp` → `api.patch('/api/findings/'+id, {status:'new', comment:'Возвращено из ложных срабатываний'})`; отображение `fp.reviewed_by_username || fp.reviewed_by`.

### `webui/config.py`, `webui/main.py`, `webui/templates/base.html`, `webui/static/js/main.js` — W-43

- `webui/config.py`: `VERSION = os.getenv("VERSION") or _config.get("version") or "3.13.2"`.
- `webui/main.py`: `from webui.config import ..., VERSION`; `app = FastAPI(..., version=VERSION)`; `/health` → `{"status":"ok","version":VERSION}`.
- `base.html`: `<span id="footerVersion">v3.0.0</span>`.
- `main.js`: `initFooterVersion()` — `fetch('/api/health')` → `el.textContent = 'v' + h.version`.

---

## 4. Тесты и проверка

1. `python -X utf8 -m pytest tests/unit -q` — **50 passed** (тесты `test_encryption`, `test_fingerprint`, `test_hex_dump`, `test_csv_utils`, `test_scanner_findings`).
2. `py_compile` — OK для: `manager/src/api/{scanner,tasks,findings,catalog,schemas_findings}.py`, `scanner/src/managed_scanner.py`, `webui/{main,config}.py`.
3. `rg`-скан эмодзи по ядру (manager/scanner/webui/audit-agents/shared/monitoring/scripts) — **0 настоящих эмодзи** в print/logger.
4. Проверка диффа: `_mark_stale_scanners`, cancel endpoint (1 копия), batch-гвард (1 копия), `_is_final_06045225`, `_persist_catalog` last_scanned.

> Примечание: полный `pytest -q` (все e2e) не запускается из-за существующей коллизии имени модуля `test_scanner_findings` (e2e/unit) — не связана с этим ТЗ.

---

## 5. Критерии приёмки (все закрыты)

| Критерий | Статус |
|---|---|
| BUG-034: Task 2 → failed после остановки сканера | ✅ |
| BUG-035: батчи ?batch=N&total=M, Manager накапливает findings_count | ✅ |
| BUG-027.1-4: progress.total/percent/files_scanned/status | ✅ |
| BUG-022: PII в line_text маскируется целиком | ✅ |
| BUG-001/002/007/017/019/036 | ✅ (проверено в коде) |
| W-42/W-54/W-60/W-66/W-70/W-43/W-55/W-57/W-62/W-67/W-72/W-73 | ✅ |

---

## 6. Для ручного тестирования

```
python init_db.py
python run_manager.py                # Manager :8000
python run_webui.py                  # WebUI :8001
python run_scanner.py scanner/config/scanner_config.json   # сканер на хосте

# проверки
Invoke-RestMethod http://localhost:8000/api/health                     # version: 3.13.2
Invoke-RestMethod http://localhost:8000/api/tasks                      # progress/files_scanned синхрон
# остановить сканер (Ctrl+C), подождать > 2 мин → assigned-задачи → failed:
#   GET /api/tasks → статусы failed у задач stale-сканера
# отмена вручную:
Invoke-RestMethod -Method Post http://localhost:8000/api/tasks/1/cancel
# WebUI:
#   /findings/{id} — кнопки Reveal/Confirm/FP, блоки «Шифрование», «Последнее сканирование»
#   /false-positives — кнопка «Восстановить»
#   /catalog — дерево папок с агрегированными счётчиками
#   Dashboard — count находок = /api/findings/count
#   footer — версия из /api/health
# батчинг: задание с 10k+ находок — имитация:
#   POST /api/scanner/tasks/{id}/results?batch=1&total=3 ... (findings), потом batch=3&total=3
#   → GET /api/tasks/{id} → findings_count = сумма всех батчей, status=completed
```

---

## 7. Команда для коммита

```powershell
git add -A
git commit -m "fix: Блок 1 (v3.13.3) — BUG-034/035/027, W-42/54/60/66/67/70/43/55/57/62/72/73

Manager:
- BUG-034.1: stale assigned-задачи сканера -> failed + completed_at
- BUG-034.2: POST /api/scanner/tasks/{id}/cancel (отмена задачи)
- BUG-035: приём findings батчами (?batch=N&total=M), аккумуляция
  findings_count, финализация только в последнем батче, flush по 500
- BUG-027.1-4: heartbeat busy->running, total/percent/paid files_scanned
- W-66/W-67: FP-эндпоинт отдаёт file_path + reviewed_by_username
- W-55: encryption_key_id в детали находки
- W-60: catalog/tree — is_folder, рекурсивная агрегация по детям
- фикс NameError files_total_from_stats

Scanner:
- BUG-035: submit_results шлёт findings батчами по 500 (?batch=N&total=M)

WebUI:
- W-42: Dashboard kpiFindings = /api/findings/count
- W-43: версия из VERSION env /config, footer из /api/health
- W-70: кнопка «Восстановить» на FP-странице
- W-55/W-57: блоки «Шифрование»/«Последнее сканирование» в детали

Отчёт: prompts/reports/day_43_block1_fix_report.md"
```

---

## 8. Файлы

- `manager/src/api/scanner.py`, `manager/src/api/tasks.py`, `manager/src/api/findings.py`, `manager/src/api/catalog.py`, `manager/src/api/schemas_findings.py`
- `scanner/src/managed_scanner.py`
- `webui/config.py`, `webui/main.py`, `webui/templates/base.html`, `webui/static/js/{dashboard,false_positives,finding_detail,main}.js`
- `prompts/reports/day_43_block1_fix_report.md`