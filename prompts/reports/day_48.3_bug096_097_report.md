# 📋 Отчёт День 48.3 — BUG-096 / BUG-096b / BUG-097 (v3.13.25)

**Дата:** 28.09.2026
**ТЗ:** `prompts/tz/TZ_FIX_BUG096_097.md`
**Версия:** v3.13.24 → **v3.13.25**
**Ветка:** `fix/scanner_deep`
**Статус:** ✅ выполнено

---

## 1. Кратко

| Задача | Что было | Статус |
|--------|----------|--------|
| TASK-064 (BUG-096) | 500 на `GET /api/findings/false-positives`: `_m.User` — `User` живёт в `manager.src.auth.models`, а не в `db.models` | ✅ исправлено, live 200 |
| TASK-065 (BUG-096b) | 2 E2E-теста падали: устаревшие поля, разрыв keep-alive, таймаут теста, ручное забирание задания | ✅ 5/5 проходят за 26 с |
| TASK-066 (BUG-097) | Задания навечно висели в `assigned`, в логах вечный 404 на `/tasks/{id}/results` | ✅ диагноз + фикс первопричины |

**Тесты:** 264 unit passed (было 242), 50 E2E passed / 2 skipped (было 47 passed / **3 failed** / 2 skipped).

---

## 2. TASK-064 — BUG-096: 500 на `/api/findings/false-positives`

**Причина.** В `manager/src/api/findings.py` использовалась несуществующая ссылка
`_m.User`. ORM-модель `User` объявлена в `manager/src/auth/models.py` (связь с ролями
через `user_roles`), а `manager/src/db/models.py` её не содержит → любой запрос к
эндпоинту падал с `AttributeError: module 'manager.src.db.models' has no attribute 'User'`
и превращался в HTTP 500.

**Фикс** (`manager/src/api/findings.py`): импорт `User` из `manager.src.auth.models`,
`Resource` — из `manager.src.db.models`; `_m.User` заменено на `User`.

**Тесты** — `tests/unit/test_false_positives_v31325.py` (8 тестов, все проходят):
- 5 функциональных для `/false-positives` (список, фильтры, статистика, права, сброс);
- 3 регрессионных **статических** (ast/tokenize): при возврате `_m.User` в код
  тесты падают с точным `AttributeError` — баг нельзя reintroduce молча.

Проверено: тест действительно ловит исходный баг (намеренный возврат `_m.User` → падение).

**Live:** `GET /api/findings/false-positives` → **200** с данными (было 500).

---

## 3. TASK-065 — BUG-096b: упавшие E2E-тесты

Найдено и исправлено **6** причин, из-за которых E2E валился:

| # | Причина | Где | Исправление |
|---|---------|-----|-------------|
| 1 | Тесты ждали `finding_type in {pii, credentials}` / `category` — схема изменилась в v3.13.22 | `tests/e2e/test_full_scan_cycle.py` | проверка `finding_type in {pii, credentials, code}` + гранулярный `category` |
| 2 | `RemoteDisconnected` при опросе статуса каждые 5 с против uvicorn `timeout_keep_alive=5` — подтверждено эмпирически (1 разрыв на 12 запросов) | `tests/fixtures/manager.py` | `_get_with_retry()`: 3 попытки, пауза, закрытие соединения |
| 3 | Тест убивался глобальным `timeout = 300` (`pyproject.toml`) ровно в момент ожидания задания | `tests/e2e/test_scanner_findings.py` | ожидание 240 с + `@pytest.mark.timeout(600)` |
| 4 | Без активного сканера тест не skip-ался, а упирался в таймаут | там же | precheck: нет активного сканера → `pytest.skip` |
| 5 | **Тест сам крал задание**: его `GET /tasks/pending` переводил задачу в `assigned`, реальный сканер (берёт только `pending`) её уже не видел | там же | задание не забирается вручную, `task_id` берётся из ответа `create_task`, сканер берёт сам |
| 6 | Ассерт на `f["fingerprint"]` — API его не отдаёт: `_finding_to_dict` собирает явный whitelist, `fingerprint` — внутренний ключ дедупликации (наружу только через `POST /api/findings/check-fingerprints`) | там же | ассерт заменён на реальный контракт: `status`, `severity`, `finding_type`, `category`, `has_encrypted` |

**Дополнительно:** `_release_stale_tasks()` — перед прогоном очередь очищается от
зависших заданий, иначе новое задание встаёт в конец и ждёт 30-минутный stale-таймаут
Manager на каждом накопленном.

**Результат:** `test_scanner_findings.py` + `test_full_scan_cycle.py` → **5 passed за 26.6 с**
(было 2 failed, таймаут 240 с каждый).

---

## 4. TASK-066 — BUG-097: зависшие задания и вечный 404

### 4.1 Диагностика (по шагам из ТЗ)

**A. Осиротевшие процессы сканеров?** — 1 процесс (`run_scanner.py`, PID 28680, старт 26.09 14:53)
+ OCR-воркер. Осиротевших процессов нет → гипотеза A отклонена.

**B/C. Задания и логи:**
```sql
SELECT id, status, scanner_id, files_scanned, assigned_at FROM scan_tasks
WHERE status IN ('assigned','running');
-- 80, 85, 90 — assigned, files_scanned=0, неделю/сутки без прогресса
```
История: задания 65/67/74 завершались ровно через **30 минут** — точное совпадение
с `TASK_TIMEOUT_MINUTES = 30`.

Логи Manager показали бесконечный цикл одного сканера:
```
POST /api/scanner/heartbeat                     → 200
POST /api/scanner/tasks/43/results?batch=1&total=1 → 404   (задачи 43 больше нет в БД)
GET  /api/scanner/tasks/pending?scanner_id=1    → 200
```

**CPU сканера и OCR-воркера: 0.0 s приращения за 6 с** — сканер не работал, хотя
выглядел живым (свежий heartbeat, статус `active`).

**D. Логи сканера:** `logs/scanner.log` из конфига **не создаётся** (пишется в stderr),
поэтому 10-часовое зависание не логировалось — гипотеза D подтвердилась частично.

**E. Оффлайн-буфер:**
```
scanner/data/offline/task_43.json   6619 байт   27.09 11:41
```

### 4.2 Полная цепочка причин

1. E2E создавал задание на `tmp_path`, который pytest удалял после теста.
2. Сканер брал задание, падал на несуществующем каталоге, **исключение гасилось**
   внешним `except Exception` в `main()` → задание оставалось в `assigned`
   до срабатывания stale-таймаута Manager (30 минут), а каждое новое задание
   вставало в очередь за зависшими.
3. Офлайн-пачка `task_43.json` по удалённой задаче ретраилась **бесконечно**
   (`submit_results` возвращал только `bool`, 404 был неотличим от временной ошибки),
   засоряя лог на каждом цикле.
4. Новые задания Manager продолжал назначать «живому» сканеру — они копились в `assigned`.

### 4.3 Фиксы

**`scanner/src/managed_scanner.py`:**
- новый `SubmitStatus`: `OK` / `RETRY` / `LOST`;
- `submit_results_status()` — 404/410 → `LOST`, 5xx/сеть → `RETRY`, 200 → `OK`;
  старый `submit_results()` сохранён как bool-обёртка (контракт не сломан);
- `_flush_offline()` — `LOST` → пачка отбрасывается, файл удаляется, разбор очереди
  продолжается (раньше `break` глушил и остальные файлы);
- главный цикл — исключение в `_execute_task()` переводит задание в `failed`
  через `_fail_task_safely()` сразу, причина логируется `logger.exception` (со стеком);
- `LOST` при отправке результатов не создаёт оффлайн-пачку (иначе цикл 404 повторился бы).

**`manager/src/api/scanner.py`:** 404 на `/tasks/{task_id}/results` теперь логируется
с `task_id`, `scanner_id`/CN клиента и `batch`/`total` вместо безликой строки в общем логе.

### 4.4 Проверка

**Unit:** `tests/unit/test_bug097_offline_flush.py` — 14 тестов (все проходят):
404/410 → LOST, 5xx → RETRY, 200 → OK, исключение сети → RETRY,
bool-обёртка не сломана, после 404 не идут остальные батчи, `LOST`/`RETRY`/OK
в `_flush_offline` (в т.ч. что `LOST` не блокирует следующие файлы),
`_fail_task_safely` (успех и проглатывание исключения).

**Live (до/после):**
```
[SubmitResults] task 43 not found in Manager (HTTP 404, scanner_id=1) — results dropped
[Offline] Задание 43 удалено в Manager — оффлайн-пачка отброшена
```
Буфер `scanner/data/offline/` — **пуст**. Задания 80/85/90 завершились
**за ~1 с** каждое (4 файла, 4 находки) вместо 30 минут ожидания.

**Лог Manager:**
```
[Scanner] Results for unknown task 999999 (scanner=None) — task not found
(deleted or expired), results rejected. batch=1/1
```

---

## 5. Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `manager/src/api/findings.py` | BUG-096: `User` из `auth.models` вместо `_m.User` |
| `manager/src/api/scanner.py` | BUG-097: контекстное логирование 404 (`task_id`, scanner, `batch`/`total`) |
| `scanner/src/managed_scanner.py` | BUG-097: `SubmitStatus`, `submit_results_status()`, отбрасывание потерянных пачек, `_fail_task_safely()` |
| `tests/unit/test_false_positives_v31325.py` | **новый** — 8 тестов BUG-096 |
| `tests/unit/test_bug097_offline_flush.py` | **новый** — 14 тестов BUG-097 |
| `tests/fixtures/manager.py` | `_get_with_retry()` против разрыва keep-alive |
| `tests/e2e/test_full_scan_cycle.py` | `finding_type` / `category` |
| `tests/e2e/test_scanner_findings.py` | precheck, таймауты, освобождение зависших заданий, отказ от ручного забирания, контракт findings |
| `.env` (gitignore), `.env.example`, `docker-compose.yml` | версия 3.13.25 |

---

## 6. Тесты

**Unit:** `264 passed` (242 → +8 BUG-096, +14 BUG-097), 71 с.

**E2E:** `50 passed, 2 skipped` за 141 с (было `47 passed, 3 failed, 2 skipped`).
Прогон выполнялся с временным `docker-compose.override.yml`
(`AUTH_LOGIN_MAX_ATTEMPTS=500`, штатный лимит 5/мин не выдерживает 50 логинов);
override **удалён**, Manager перезапущен на дефолте.

**Среда:** Manager v3.13.25 (healthy), WebUI healthy, сканер перезапущен с новым кодом,
heartbeat сканера свежий.

---

## 7. Побочные находки (не в скоуп ТЗ)

1. **Логи сканера пишутся в stderr, а не в `logging.file`** (`logs/scanner.log` не создаётся)
   — это и было гипотезой D; сильно затрудняет диагностику. Заведено в открытые вопросы STATE.
2. **BUG-061 подтвердился:** при рестарте контейнера Manager heartbeat сканера отбивается
   `RemoteDisconnected`; urllib3-retry вытягивает, но восстановлениеHTTP — отдельная задача.
3. `TASK_TIMEOUT_MINUTES = 30` — очень большой интервал: при падении сканера очередь
   встаёт на полчаса. Стоит обсудить снижение (отдельная задача).
4. Ассерт на `fingerprint` в E2E вскрыл, что `fingerprint` не отдаётся наружу ни одним
   read-эндпоинтом, хотя есть `POST /findings/check-fingerprints`. Если UI должен
   показывать fingerprint — нужна отдельная задача на API.

---

## 8. Команда для коммита

```bash
git add -A
git commit -m "fix: День 48.3 — BUG-096/096b/097: /false-positives, зависшие задания, оффлайн-пачки (v3.13.25)

fix(BUG-096): 500 на GET /api/findings/false-positives — _m.User заменён на User
из manager.src.auth.models (в db.models модели User нет)
fix(BUG-097): задания больше не висят assigned 30 минут и не копятся в очереди:
  - scanner: SubmitStatus (OK/RETRY/LOST) + submit_results_status(); 404/410 -> LOST
  - scanner: оффлайн-пачка по удалённой задаче отбрасывается вместо бесконечного 404
  - scanner: исключение в _execute_task переводит задание в failed сразу (fail_task)
    и логируется со стеком, вместо ожидания stale-таймаута 30 минут
  - manager: 404 на /tasks/{id}/results логируется с task_id/scanner/batch
test(BUG-096b): E2E — finding_type/category, retry keep-alive (RemoteDisconnected),
  precheck сканера, timeout(600) против глобальных 300 с, освобождение зависших
  заданий, отказ от ручного забирания задания, контракт findings без fingerprint
test: 264 unit (было 242), 50 E2E passed / 2 skipped (было 47/3 failed)
chore: версия 3.13.25, docs (STATE/ROADMAP/CHANGELOG/troubleshooting), отчёт, архив ТЗ"
```
