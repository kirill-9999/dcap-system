# День 53.3-fix-s3-bucket — `S3LineConnector`: bucket только из `scan_config` — отчёт

**Версия:** v3.13.35
**Дата:** 04.10.2026
**ТЗ:** `prompts/tz/TZ_53.3-fix-s3-bucket.md` → `prompts/archive/TZ_53.3-fix-s3-bucket.md`
**Контекст:** follow-up к BACKLOG-097 (замечание аудита 53.2), выполнен до 53.3-fs-regress

---

## 1. Что сделано

### TASK-134 — `scanner/connectors/s3_line_connector.py`

В `scan_path` удалены сравнение `parsed.netloc != self._bucket` и WARNING
`"[S3Line] Bucket в path (%s) != bucket в config (%s) — использую path"`.

Причина: bucket из `path` **никогда не использовался** — `list_objects_v2` всегда
получал `self._bucket` из `scan_config.connector.s3.bucket`. Предупреждение печаталось
вхолостую, а формулировка «использую path» создавала ощущение, что bucket может прийти
из пути.

Контракт зафиксирован комментарием:

```python
# Bucket — всегда из scan_config.connector.s3.bucket (см. 53.1a):
# Manager кладёт bucket в payload задачи, а path (s3://bucket/prefix)
# используется только как suffix для префикса. Если в path указан
# другой bucket — он игнорируется намеренно (контракт ресурса —
# bucket фиксирован на момент создания).
source_prefix = self._prefix
if path:
    parsed = urlparse(path)
    if parsed.scheme in ("s3", "minio"):
        source_prefix = (parsed.path or "").lstrip("/")
    else:
        source_prefix = (path or "").lstrip("/")
```

Дополнительно (в том же духе, не против ТЗ): приведён в соответствие docstring `scan_path`
— раньше он обещал «используется bucket/prefix из него», что противоречило коду.

`logger` не удалён — он используется в 7 других местах файла.

### TASK-135 — `docs/admin-guide/06-scanner.md` §8.1

После строки про формат пути добавлено:

```markdown
- **Bucket — из `scan_config.connector.s3.bucket`** (Manager кладёт в payload
  задачи при создании ресурса). Путь `s3://bucket/prefix/` в задании
  используется **только как суффикс префикса** (`prefix/`); bucket в path
  игнорируется — контракт ресурса фиксирует bucket на момент создания.
```

### TASK-136 — `ROADMAP.md`, версия v3.13.35

- План по дням: добавлена строка `53.3-fix-s3-bucket` → ✅ v3.13.35 (TASK-134…136).
- **BACKLOG-103** — «Убрать fallback на config-секреты в `S3LineConnector`/`S3Connector`
  (политика TASK-018 — только ENV)» → 🟡 в бэклог v3.1.0 (+ дубль в бэклоге v3.0.0,
  как BACKLOG-099/100).
- `CHANGELOG.md` — запись `[3.13.35]`.
- `STATE.md` — версия v3.13.35, строка дня, раздел файлов, контракт bucket в
  «Ключевых решениях», BACKLOG-103 в открытых проблемах.

### Тесты (критерий 2 — не было, добавлены)

`tests/unit/test_s3_line_connector_v31331.py` — +3 теста:

| Тест | Что проверяет |
|------|---------------|
| `test_bucket_in_path_is_ignored_and_config_wins` | `s3://other-bucket/logs` → `list_objects_v2(Bucket="test-bucket", Prefix="logs")` |
| `test_bucket_in_path_mismatch_emits_no_warning` | при расхождении bucket в path нет ни одного WARNING со словом «ucket» |
| `test_path_without_prefix_falls_back_to_config_prefix` | `s3://any-bucket/` → `Prefix="cfg/prefix"` (fallback внутри `_discover_keys`) |

В файл добавлен `import logging` (для `caplog.at_level`).

---

## 2. Критерии приёмки

| # | Критерий | Результат |
|---|----------|-----------|
| 1 | `scan_path` не сравнивает `parsed.netloc` с `self._bucket` | ✅ grep: `parsed.netloc != self._bucket` не найден, `"использую path"` не найден |
| 2 | Bucket всегда `self._bucket`, path даёт только prefix | ✅ 3 новых unit-теста |
| 3 | Существующие 16 тестов `test_s3_line_connector_v31331.py` не сломались | ✅ 19 passed (16 старых + 3 новых) |
| 4 | `06-scanner.md` §8.1 уточнён | ✅ grep: «только как суффикс префикса» |
| 5 | BACKLOG-103 в ROADMAP.md v3.1.0 | ✅ grep: 3 упоминания (план, бэклог v3.0.0, бэклог v3.1.0) |
| 6 | Unit-набор зелёный (427+) | ✅ **430 passed**, 1030 warnings, 91.40 с |

---

## 3. Что НЕ сделано (вне scope по ТЗ)

- Сам fallback на config-секреты (`self._access_key = env_access or self.config.get("access_key")`,
  `scanner/connectors/s3_line_connector.py:93-94`, и аналог в `s3_connector.py:61-66`)
  **не тронут** — это BACKLOG-103 (v3.1.0), как и предписано ТЗ.
- E2E не перезапускался: изменение чисто контрактное (сравнение + лог), путь данных
  (`Bucket`/`Prefix` в `list_objects_v2`) не изменился — unit-покрытие достаточно.
- `docs/DESIGN.md`, WebUI-редизайн, `docker-compose.test.yml` — не входили в ТЗ.

---

## 4. Известные смежные замечания

- `scanner/connectors/s3_connector.py:61-66` (старый, не построчный коннектор) содержит
  ту же проблему с ложным WARNING и fallback на config-секреты — закрывается вместе
  с BACKLOG-103.
- `docs/admin-guide/06-scanner.md` §8.1 утверждает, что «Рекурсия — всегда» и опции
  `recursive=false` для S3 нет — это соответствует коду (`_discover_keys` обходит всё
  поддерево prefix).

---

## 5. Файлы

Изменены: `scanner/connectors/s3_line_connector.py`, `tests/unit/test_s3_line_connector_v31331.py`,
`docs/admin-guide/06-scanner.md`, `ROADMAP.md`, `CHANGELOG.md`, `STATE.md`.
Добавлен: `prompts/reports/day_53_3_fix_s3_bucket_report.md`.
Перемещено: `prompts/tz/TZ_53.3-fix-s3-bucket.md` → `prompts/archive/TZ_53.3-fix-s3-bucket.md`.
