# День 49 — Фикс-спринт BUG-098 / BUG-099 / BUG-100 / BUG-101 (v3.13.26)

**Дата:** 29.09.2026
**ТЗ:** `TZ_FIX_SPRINT_BUG098-101.md` (Блок 5, WebUI — п.5 PATCH status, п.6 Bulk, п.8 False positives)
**Ветка:** `fix/scanner_deep`
**Версия:** v3.13.25 → **v3.13.26**

---

## 1. Итог

Все 4 бага закрыты, все правки — в одном файле `manager/src/api/findings.py`.
Закрыт открытый вопрос ТЗ про `DELETE findings` (5-я находка, найдена при фиксе).
Юнит-прогон: **264 → 301 passed** (+40 новых тестов при 22 требуемых в ТЗ).

| ID | Баг | Статус |
|----|-----|--------|
| BUG-101 🔴 | PATCH + bulk не писались в `audit_logs` | ✅ |
| BUG-101b 🔴 | DELETE findings не писался в `audit_logs` (открытый вопрос ТЗ) | ✅ |
| BUG-100 🟡 | PATCH `status=new` не очищал `reviewed_by`/`reviewed_at` | ✅ |
| BUG-099 🟡 | `/false-positives?offset=-1` / `?limit=-5` → 500 | ✅ |
| BUG-098 🟡 | `/false-positives` отдавал `file_path` = директория | ✅ |

---

## 2. BUG-101 🔴 — PATCH и bulk не писались в `audit_logs`

### Доказательство (до фикса, v3.13.25)

За 30 минут активности — 0 записей `finding_confirmed` / `finding_false_positive` /
`finding_updated`, только `auth_login` (3 шт.), хотя PATCH и bulk были вызваны 10+ раз.

| Эндпоинт | event_type | Пишется? |
|----------|-----------|----------|
| `POST /{id}/reveal` | `finding_reveal` | ✅ |
| `GET /{id}/fragment` | `fragment_accessed` | ✅ |
| `GET /findings/export` | `findings_exported` | ✅ |
| `POST /auth/login` | `auth_login` | ✅ |
| `PATCH /{id}` | — | 🐛 |
| `POST /bulk` | — | 🐛 |

### Причина

`update_finding` и `bulk_update` меняли статус и делали `db.commit()` — вызова
`AuditLog` не было. Решение ревью находки (подтвердить / отклонить / отправить в
архив) нигде не фиксировалось — пробел 152-ФЗ / GDPR / PCI DSS 10.2.

### Фикс

Хелпер `_log_finding_status_change()` с маппингом статуса на `event_type`
(решения ТЗ: bulk = **Вариант A**, reset = `finding_reset`):

```python
_STATUS_EVENT_MAP = {
    "confirmed":      "finding_confirmed",
    "false_positive": "finding_false_positive",
    "archived":       "finding_archived",
    "new":            "finding_reset",
}
```

- `update_finding` — вызов с `via="patch"`.
- `bulk_update` — **по одной записи на каждую находку** с `via="bulk"` (удобнее
  искать по `finding_id` в SIEM).
- Хелпер **не делает коммит** — записи копятся и пишутся одним коммитом вызывающего
  кода, иначе bulk дал бы N коммитов.
- В `metadata_json`: `action`, `finding_id`, `category`, `finding_type`,
  `old_status`, `new_status`, `comment`, `via`.
- `audit_logs.user` = реальный пользователь (`user.username`), не роль БД.

Три эндпоинта (`update_finding`, `bulk_update`, `delete_finding`) получили
`request: Request` — нужен `source_host` для записи аудита.

---

## 3. BUG-101b 🔴 — DELETE тоже не аудировался (открытый вопрос ТЗ)

**Вопрос ТЗ:** «что с DELETE findings? Тоже не пишется? Проверить в ходе фикса».
**Ответ:** не писался. `DELETE /api/findings/{id}` (только Admin) удалял находку
без следа в журнале.

Добавлена запись `finding_deleted` (`old_status`, `resource_id`, `via="delete"`).
Нюанс реализации: объект `AuditLog` строится **до** `db.delete(finding)` и уходит
в том же коммите — после коммита инстанс expire'ится, и `fragment_path` / `category`
уже не прочитать. Закрыт 3 тестами (`test_delete_writes_audit`,
`test_delete_audit_survives_row_removal`, `test_delete_404_writes_no_audit`).

---

## 4. BUG-100 🟡 — PATCH `status=new` не очищал поля ревью

### Доказательство (до фикса)

```
PATCH /findings/1521 {status: false_positive} -> reviewed_by=35, reviewed_at=18:57:17
PATCH /findings/1521 {status: new}            -> status=new, НО reviewed_by=35,
                                                    reviewed_at=18:58:05
```

Находка снова `new`, но выглядит одобренной прошлым ревьюером. `/false-positives`
сортирует по `reviewed_at`, WebUI показывает «кто и когда проверил» — данные
заведомо неверные.

### Фикс

Общая функция `_apply_status()` используется и PATCH, и bulk — поведение больше
не расходится:

```python
if status == "new":
    finding.reviewed_by = None
    finding.reviewed_at = None
else:
    finding.reviewed_by = user.id
    finding.reviewed_at = datetime.utcnow()
```

`comment` при сбросе = `body.comment` (решение ТЗ; если не передан — `None`).

---

## 5. BUG-099 🟡 — `/false-positives` → 500 на отрицательной пагинации

### Причина

В `list_false_positives` остались старые параметры — clamp из фикса BUG-084 был
применён к `list_findings`, но не сюда:

```python
limit: int = Query(100, le=1000),   # нет ge=1
offset: int = 0,                   # нет ge=0
```

Отрицательные значения доходили до `.offset(-1)` / `.limit(-5)`, PostgreSQL отвечал
ошибкой → HTTP 500.

### Фикс

`OptInt` + `_clamp_int` — ровно как в `list_findings`:

```python
limit_val  = _clamp_int(limit,  100, 1, 1000)
offset_val = _clamp_int(offset,   0, 0, 10_000_000)
```

### Проверка остальных эндпоинтов (требование ТЗ)

Просканирован весь `manager/src/api/`:

| Файл:строка | Параметры | Защита | Реакция на мусор |
|-------------|-----------|--------|------------------|
| `findings.py:302` (`/false-positives`) | `limit`, `offset` | **было: ничего** | 🐛 **500** → исправлено |
| `audit.py:294`, `catalog.py:15,199`, `permissions.py:187,347`, `resources.py:54`, `tasks.py:16`, `webui.py:432,472` | `limit`, `offset` | `ge`/`le` в `Query` | 422 (не 500) |
| `retention.py:21` (`ExportRequest.limit`) | `limit` | явная проверка `if limit < 1: raise HTTPException(400)` | 400 (не 500) |

**Других случаев 500 не осталось** — все эндпоинты либо валидируют границы, либо
проверяют вручную.

---

## 6. BUG-098 🟡 — `/false-positives` отдавал `file_path` = директория

### Доказательство (до фикса)

Один и тот же finding (id=1523):

```
GET /api/findings?task_id=41&status=false_positive
  -> file_path = C:\test\scanner_clean\pii\phones_clean.txt   ✅ (файл)
GET /api/findings/false-positives
  -> file_path = C:\test\scanner_clean                        🐛 (директория)
```

### Причина

```python
# было — приоритет у res_map, а res_map[r.id] = r.path (путь РЕСУРСА = директория)
"file_path": res_map.get(f.resource_id) or f.fragment_path,
```

В `_finding_to_response` (основной список) путь фрагмента приоритетнее:
`"file_path": finding.fragment_path`.

### Фикс

```python
"file_path": f.fragment_path or res_map.get(f.resource_id),
```

`res_map` остался как fallback для находок без `fragment_path`.

---

## 7. Тесты

| Файл | Тестов | Покрытие |
|------|--------|----------|
| `tests/unit/test_audit_status_change_v31326.py` | 18 | 4 статуса через PATCH, последовательность изменений, `metadata` (old/new/comment/finding_id), bulk по записи на находку, `skipped` для отсутствующих id, `via=patch` vs `bulk`, `user` = текущий пользователь, два разных пользователя, персистентность (отдельная сессия), аудит DELETE, отсутствие записей при 404 |
| `tests/unit/test_patch_reset_clears_review_v31326.py` | 8 | очистка `reviewed_by`, `reviewed_at`, `comment` из тела, сброс из `false_positive` и `confirmed`, регрессия «для confirmed/fp/archived ревью проставляется», bulk, ответ PATCH отдаёт `null` |
| `tests/unit/test_fp_pagination_v31326.py` | 8 | `offset=-1`, `limit=-5`, `limit=0`, `limit=99999`, пустые `limit=&offset=`, валидная пагинация, offset за концом, пустая БД + мусор |
| `tests/unit/test_fp_file_path_v31326.py` | 6 | путь файла вместо директории, согласованность с `/findings`, fallback на ресурс, совпадение с `_finding_to_response`, несколько строк |

**Итого +40 unit (264 → 301 passed).**

⚠️ **Важно:** `tests/unit/test_false_positives_v31325.py:190` закреплял **баговое**
поведение BUG-098 (`file_path == "C:/data/fp-demo"`, т.е. директория). Ассерт
обновлён на путь файла — иначе фикс ломал бы регрессионный тест предыдущего дня.

---

## 8. Проверки

### Юнит

```
python -m pytest tests/unit -q
301 passed in 69.90s
```

### E2E

Тестовый стенд (`docker-compose.test.yml`, БД пустая, реального сканера нет):

```
python -m pytest tests/e2e -q
38 passed, 9 skipped, 5 failed (334.05s)
```

5 провалов — экологические, не связаны с правками:
`test_full_scan_cycle` (задание `pending` — некому взять), `test_real_scanner_end_to_end`,
`test_scanner_heartbeat_keeps_active` (на тестовом стенде нет реального сканера —
он живёт на хосте против `:8000`), `test_proxy_forwards_total_count` и
`test_findings_filters_csv_and_empty` (`X-Total-Count == 0` — в свежей БД стенда
нет находок).

**Проверка на основном стенде** (те же образы 3.13.26, реальные данные + живой сканер):

```
$env:MANAGER_URL="http://127.0.0.1:8000"; $env:WEBUI_URL="http://127.0.0.1:8001"
python -m pytest <те 5 тестов> -q
5 passed in 87.25s
```

→ Провалы вызваны окружением, а не изменениями.

### Live — API (Manager :8000, v3.13.26)

```
BUG-099: ?offset=-1    -> 200 (2 записи)
         ?limit=-5     -> 200 (1 запись — clamp к lo=1, как в list_findings)
         ?limit=0      -> 200 (1 запись)
         ?limit=99999  -> 200
         ?limit=&offset= -> 200
         ?offset=999999  -> 200 (пусто)
BUG-098: file_path = 'C:\test\scanner_clean\pii\phones_clean.txt'  ✅ совпадает с /findings
BUG-100: PATCH new -> reviewed_by=None, reviewed_at=None, comment='live reset'  ✅
BUG-101: bulk confirmed -> updated=2, skipped=0
```

### Live — `audit_logs` (PostgreSQL)

> ⚠️ В SQL колонка `user` обязана быть в кавычках — иначе PostgreSQL возвращает
> `CURRENT_USER` (имя роли БД `dcap`), а не значение. Это уже ловили в BUG-087.

```sql
SELECT id, created_at, event_type, "user", source_host, metadata::text
FROM audit_logs WHERE event_type LIKE 'finding_%' AND created_at > NOW() - INTERVAL '15 minutes'
ORDER BY id;
```

```
 id  |       event_type       | user  | source_host | metadata
-----+------------------------+-------+-------------+-------------------------------------------------------------------------
 350 | finding_confirmed      | admin | 172.19.0.1  | via=patch, old_status=false_positive, new_status=confirmed, comment="live test", finding_id=1522
 351 | finding_false_positive | admin | 172.19.0.1  | via=patch, old_status=confirmed,  new_status=false_positive, finding_id=1522
 352 | finding_archived       | admin | 172.19.0.1  | via=patch, old_status=false_positive, new_status=archived,  finding_id=1522
 353 | finding_reset          | admin | 172.19.0.1  | via=patch, old_status=archived,  new_status=new, comment="live reset", finding_id=1522
 354 | finding_confirmed      | admin | 172.19.0.1  | via=bulk,  old_status=false_positive, new_status=confirmed, comment="live bulk", finding_id=1523
 355 | finding_confirmed      | admin | 172.19.0.1  | via=bulk,  old_status=new,          new_status=confirmed, comment="live bulk", finding_id=1522
(6 rows)
```

**Было 0 записей — стало 6** (4 от PATCH, 2 от bulk — по одной на находку).

---

## 9. Релиз

- Версия: **3.13.25 → 3.13.26** (`.env`, `.env.example`, `docker-compose.yml`).
- Образы пересобраны: `dcap/manager:3.13.26`, `dcap/webui:3.13.26`.
- `docker compose up -d` — весь стек (15 сервисов) на новых образах.
- `GET /api/health` → `{"status":"healthy","version":"3.13.26"}` на :8000 и :8001.

---

## 10. Изменённые файлы

| Файл | Действие |
|------|----------|
| `manager/src/api/findings.py` | хелпер `_log_finding_status_change()` + `_STATUS_EVENT_MAP` + `_apply_status()`; вызовы в PATCH/bulk/DELETE; `request: Request` в трёх эндпоинтах; `OptInt` + `_clamp_int` в `list_false_positives`; `file_path` = `fragment_path` |
| `tests/unit/test_audit_status_change_v31326.py` | новый, 18 тестов |
| `tests/unit/test_patch_reset_clears_review_v31326.py` | новый, 8 тестов |
| `tests/unit/test_fp_pagination_v31326.py` | новый, 8 тестов |
| `tests/unit/test_fp_file_path_v31326.py` | новый, 6 тестов |
| `tests/unit/test_false_positives_v31325.py` | ассерт `file_path` с директории на путь файла |
| `.env`, `.env.example`, `docker-compose.yml` | VERSION → 3.13.26 |
| `CHANGELOG.md`, `STATE.md`, `ROADMAP.md` | BUG-098…101 → ✅ |

---

## 11. Ответы на открытые вопросы ТЗ

1. **BUG-101 — bulk audit:** Вариант A (по записи на каждую находку) ✅, как рекомендовали.
2. **BUG-100 — comment при reset:** `body.comment` ✅, как рекомендовали.
3. **BUG-101 — DELETE findings:** да, не писался; исправлено (`finding_deleted`), закрыт 3 тестами.
4. **Event type для reset:** `finding_reset` ✅, как рекомендовали.

---

## 12. Инструкция для ручного теста

```powershell
# 0. Убедиться, что стенд на новой версии
Invoke-RestMethod http://127.0.0.1:8000/api/health
# -> version 3.13.26

# 1. Логин
$login = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }
$base = "http://127.0.0.1:8000/api/findings"

# 2. BUG-099: отрицательная пагинация больше не 500
Invoke-RestMethod "$base/false-positives?offset=-1" -Headers $h | Measure-Object | Select-Object Count
Invoke-RestMethod "$base/false-positives?limit=-5"  -Headers $h | Measure-Object | Select-Object Count

# 3. BUG-098: file_path = файл, а не директория
(Invoke-RestMethod "$base/false-positives" -Headers $h)[0].file_path
# ожидается C:\test\scanner_clean\pii\phones_clean.txt

# 4. BUG-100 + BUG-101: PATCH по всем 4 статусам
$id = (Invoke-RestMethod "$base/false-positives" -Headers $h)[0].id
"confirmed"      | ForEach-Object { Invoke-RestMethod -Method PATCH "$base/$id" -Headers $h -ContentType "application/json" -Body (@{status=$_} | ConvertTo-Json) | Out-Null }
"false_positive" | ForEach-Object { Invoke-RestMethod -Method PATCH "$base/$id" -Headers $h -ContentType "application/json" -Body (@{status=$_} | ConvertTo-Json) | Out-Null }
"archived"       | ForEach-Object { Invoke-RestMethod -Method PATCH "$base/$id" -Headers $h -ContentType "application/json" -Body (@{status=$_} | ConvertTo-Json) | Out-Null }

# сброс в new — reviewed_by/reviewed_at должны стать null
$r = Invoke-RestMethod -Method PATCH "$base/$id" -Headers $h -ContentType "application/json" -Body '{"status":"new"}'
$r.status; $r.reviewed_by; $r.reviewed_at   # -> new, пусто, пусто

# 5. BUG-101: bulk
Invoke-RestMethod -Method POST "$base/bulk" -Headers $h -ContentType "application/json" `
  -Body (@{finding_ids=@($id); status="confirmed"; comment="manual"} | ConvertTo-Json)

# 6. Аудит (PostgreSQL) — "user" обязательно в кавычках!
docker exec -i dcap-postgres psql -U dcap -d dcap -c `
  'SELECT id, created_at, event_type, "user", metadata::text FROM audit_logs WHERE event_type LIKE ''finding_%'' AND created_at > NOW() - INTERVAL ''5 minutes'' ORDER BY id;'

# ожидается 5 записей: finding_confirmed, finding_false_positive, finding_archived,
# finding_reset (via=patch) и finding_confirmed (via=bulk)
```

В WebUI: страница «Ложные срабатывания» — колонка «Файл» показывает путь к файлу,
а не к папке; кнопка сброса статуса очищает «Кто проверил / Когда».

---

## 13. Следующий шаг

Блок 5 (WebUI) → п.7 (Stats) → п.13 (count) → п.14 (WebUI) → п.15 (Регрессия),
затем п.2.4 (отчёты/архив).
