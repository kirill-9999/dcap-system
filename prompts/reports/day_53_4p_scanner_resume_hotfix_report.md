# Отчёт: День 53.4p — Scanner Resume Hotfix (v3.14.14)

**Версия:** v3.14.13 → **v3.14.14**
**Дата:** 25.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes
**ТЗ:** `prompts/tz/day_53_4p_scanner_resume_hotfix.md` (BUG-287, BUG-288, BUG-289)

---

## Кратко

Исправлены три дефекта, выявленные при реальном запуске resume (22 500 файлов):

- **BUG-287**: `final=True` отправлялся на каждом чанке → Manager завершал
  задание после первого чанка (400 на следующих: «Task status is completed»).
  Теперь `final=is_last` (только `chunk_idx == total_chunks - 1`).
- **BUG-288**: `release` на `completed` возвращал 400 → scanner не мог
  корректно завершить цикл. Теперь `completed`/`pending` → no-op (204),
  `failed` → 409, `assigned`/`running` → release (204).
- **BUG-289**: `ScanProgress` откатывался (300 → 200). Теперь монотонный
  прогресс через `_total_scanned` accumulator и `meta["scanned"]`.

---

## Изменённые файлы

- `scanner/src/managed_scanner.py` — `ManagerClient.release_task` (200/204),
  `_scan_line_by_line` (meta["scanned"], max), `_execute_task_linewise`
  (`_total_scanned`), `_on_chunk` (state.save files_scanned).
- `manager/src/api/scanner.py` — `release_task` no-op для completed/pending,
  409 для failed/прочих.
- `tests/unit/test_resume_hotfix_v31414.py`, `tests/e2e/test_resume_hotfix_v31414.py`.
- `CHANGELOG.md`, `STATE.md`, `docs/admin-guide/06-scanner.md`.

---

## Тесты

- `tests/unit/test_resume_hotfix_v31414.py` — 3 passed.
- `tests/unit/test_scan_state_v31412.py` — 6 passed.
- `tests/unit/test_bug097_offline_flush.py` — 14 passed.
- `tests/unit` — 519 passed.

---

## Ручной сценарий

1. Каталог 1000 файлов, `chunk_size=100`.
2. Обработать ≥2 чанка → Ctrl+C.
3. Manager task status = `pending` (не `completed`, не `failed`).
4. Перезапуск сканера → `[Resume] ... чанк 3/10`, завершение → `completed`,
   findings = baseline.
5. `ScanProgress` монотонно возрастает (без откатов).
6. `final` — только на последнем чанке (SubmitResults 200, не 400).
7. `release` на `completed` → 204 (no-op), не 400.

---

## Коммит

```powershell
git add -A
git commit -m "fix: День 53.4p — resume hotfix (final last chunk, release no-op, monotonic progress) (v3.14.14)"
```
