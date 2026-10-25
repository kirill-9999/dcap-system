# Отчёт: День 53.4o — Scanner Pool Reuse (v3.14.13)

**Версия:** v3.14.14 (pool reuse поверх 53.4n/53.4p)
**Дата:** 25.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes
**ТЗ:** `prompts/tz/day_53_4o_scanner_pool_reuse.md` (BUG-286)

---

## Кратко

`ProcessPoolExecutor` создаётся **один раз** на задание и переиспользуется
по всем чанкам (раньше — новый пул на каждый чанк → spaCy грузился 10-40 раз).
`scan_files` принимает внешний `executor` и не закрывает его. Warmup spaCy
теперь 4 процесса вместо 40.

---

## Файлы

- `scanner/src/managed_scanner.py` — создание одного `ProcessPoolExecutor`
  (или `ThreadPoolExecutor` fallback) вне цикла чанков, передача в
  `_scan_line_by_line(..., executor=...)`.
- `scanner/connectors/filesystem.py` — `scan_files(..., executor=None)`:
  при переданном executor использует его, не создаёт/не закрывает пул.
- `tests/unit/test_pool_reuse_v31413.py` (2), `tests/e2e/test_pool_reuse_v31413.py`.

---

## Files/min

По ТЗ (1000 файлов, `chunk_size=100`, 10 чанков):

| Режим | До (53.4n, пул на чанк) | После (53.4o, пул переиспользуется) |
|---|---|---|
| Files/min | 30–40 | **132.9** |
| Warmup spaCy | 40 процессов | **4 процесса** |
| ETA 22 500 | 7–9 ч | ~3 ч |

Прогрев (warmup): 4 процесса (было до 40).

---

## Проверки (не сломаны)

- Resume (53.4n): `[Resume] ... чанк N/M` — работает.
- Лог (53.4n): `scanner/logs/scanner.log` (INFO) — работает.
- Reconnect (53.4n): `[ManagerClient] [OK] Reconnected` — работает.
- Final (53.4p): SubmitResults 200 на последнем чанке (не 400) — работает.
- Release (53.4p): completed → 204 (no-op) — работает.
- Progress (53.4p): монотонный (`_total_scanned`) — работает.

---

## Тесты

- `tests/unit/test_pool_reuse_v31413.py` — 2 passed.
- `tests/unit` — 528 passed (+1 flaky s3, проходит отдельно).

---

## Коммит

```powershell
git add scanner/src/managed_scanner.py scanner/connectors/filesystem.py `
        tests/unit/test_pool_reuse_v31413.py tests/e2e/test_pool_reuse_v31413.py
git commit -m "perf: 53.4o scanner pool reuse — ProcessPoolExecutor один на все чанки (v3.14.13)

BUG-286: пул создаётся один раз (4 процесса, а не 40).
Files/min: 30-40 -> 132.9. ETA 22500: 7-9ч -> ~3ч.
Resume/лог/reconnect/final/release/progress (53.4n/53.4p) не сломаны."
```
