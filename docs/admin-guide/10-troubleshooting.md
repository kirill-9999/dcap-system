# 10. Troubleshooting

> **Руководство администратора DCAP.**
> Раздел «Поиск и устранение неисправностей»: частые проблемы и решения.

**Обновлено:** 26.09.2026
**Версия:** v3.13.18

---

## 📖 Содержание

1. [Общие принципы](#1-общие-принципы)
2. [Код сканера не влияет на новые findings](#2-код-сканера-не-влияет-на-новые-findings)
3. [OCR-findings сохраняются с bounding_box = {0,0,0,0}](#3-ocr-findings-сохраняются-с-bounding_box--000)
4. [Manager/WebUI отвечают старой версией](#4-managerwebui-отвечают-старой-версией)
5. [Контейнеры зависают при пересоздании](#5-контейнеры-зависают-при-пересоздании)

---

## 1. Общие принципы

- **Сканер работает на хосте** (не в Docker) — его код не пересобирается контейнером.
  Перезапуск сканера — Ctrl+C в окне `start_scanner.bat` → запуск снова.
- **Manager/WebUI в Docker** — после правки их кода нужны `docker compose build` + `up -d`.
- Проверка актуальной версии — `GET /api/health` (ожидаем `"version": "x.y.z"`).
- Проверка процесса сканера:
  ```powershell
  Get-CimInstance Win32_Process -Filter "name like 'python%'" | Select ProcessId, CommandLine
  ```
  Ожидание для рабочего сканера: `python -X utf8 run_scanner.py scanner\config\scanner_config.json`
  (запуск из корня репо; на PID смотришь атрибут `CommandLine`).

---

## 2. Код сканера не влияет на новые findings

**Симптом:** поправил `scanner/**/*.py`, перезапустил сканер, но результаты не изменились.

**Причины и решения (по убыванию вероятности):**

1. **Сканер не перезапущен.** Решение: Ctrl+C в окне `start_scanner.bat` →
   `.\start_scanner.bat`. Проверить: `[OK] Manager: healthy, version X.X.X`.
2. **Stale `__pycache__`** (устаревший байткод). Решение:
   ```powershell
   Get-ChildItem E:\projects\dcap-system\scanner -Recurse -Directory -Filter __pycache__ |
     Remove-Item -Recurse -Force
   .\start_scanner.bat
   ```
   Быстрая проверка свежести: `.pyc` должен быть новее `.py`:
   ```powershell
   Get-ChildItem scanner\connectors\__pycache__ -Filter "filesystem*.pyc" |
     Select Name, LastWriteTime
   Get-Item scanner\connectors\filesystem.py | Select LastWriteTime
   ```
3. **Дедупликация по fingerprint.** Если пути/строки не менялись, повторный скан
   того же ресурса не создаёт новые записи (для существующих `new`-findings обновляется
   `last_seen_at`). Для контрольного прогона очистить тестовые findings:
   ```powershell
   docker exec dcap-postgres psql -U dcap -d dcap -c "DELETE FROM findings WHERE task_id = <id>;"
   ```

---

## 3. OCR-findings сохраняются с bounding_box = {0,0,0,0}

**Симптом (BUG-077, исправлен в v3.13.18):** у `image_region`-findings в БД
`bounding_box = {"x":0,"y":0,"width":0,"height":0}`, хотя в `filesystem.py` стоит `None`.

**Причина:** сканер шлёт `bounding_box: null` (координаты OCR не вычисляются — Tesseract
вызывается без tsv). Но Manager при сохранении имел fallback:
```python
bounding_box=finding_data.get("bounding_box") or (
    {"x": 0, "y": 0, "width": 0, "height": 0} if fragment_type == "image_region" else None
)
```
`None or default` → в БД уходил `{0,0,0,0}`.

**Решение (v3.13.18):** fallback убран — `bounding_box=finding_data.get("bounding_box")`.
Теперь для OCR хранится честный `NULL`, а endpoint `/api/findings/{id}/fragment` для
`image_region` без bbox возвращает весь PNG с заголовком `X-Fragment-Mode: full-image`.
Полный OCR-пайплайн с реальным bbox — **BACKLOG-085 (v3.1.0)**.

---

## 3.1 Фрагмент недоступен, хотя файл был просканирован

**Симптом:** `/api/findings/{id}/fragment` → 404, либо viewer впервые видит находку и получает 403.

**Причины:**

- **RBAC (с v3.13.19):** `/fragment` и `/fragment/hash` — только **Auditor/Admin** (BUG-079).
  Viewer получает 403 by design.
- **Фрагмент не встроен:** третий вариант — файл удалён/Manager не видит путь (Docker),
  а `fragment_data` в БД отсутствует (например, файл на момент сканирования был > 2 МБ
  — лимит `MAX_FRAGMENT_EMBED_SIZE`, default 2097152). Проверить:
  ```sql
  SELECT id, fragment_type, fragment_size, fragment_mime, fragment_embedded_at
  FROM findings WHERE id = <id>;
  ```
  Если `fragment_size IS NULL` — фрагмент не встраивался.

**Решение:** при сканировании в БД сохраняется PNG (`X-Fragment-Mode: embedded`). Для
увеличения покрытия поднимите `MAX_FRAGMENT_EMBED_SIZE` (env + docker-compose, пересборка
не нужна — переменная pass-through). Дедуп фрагментов и их шифрование — BACKLOG-087/088 (v3.1.0).

---

## 3.2 Сканер: лог завален heartbeat-сообщениями при недоступном Manager

**Симптом:** при остановленном/недоступном Manager (BUG-080, до v3.13.20) в логе сканера каждые
несколько секунд: `Heartbeat failed: ...` + `Retrying...`, лишняя нагрузка на CPU/диск.

**Решение (исправлено в v3.13.20):** heartbeat больше не спамит:
- фейлы пишутся на **DEBUG**, WARNING — только на 1-й попытке и далее каждые 5;
- backoff 5 → 10 → 30 → 60 → 120 с (`scanner/src/heartbeat.py`, `BACKOFF_STEPS`);
- при восстановлении Manager — INFO `Heartbeat restored after N failure(s)`.

Наблюдение с v3.13.20:
```text
2026-09-26 12:30:00,539 - scanner.src.heartbeat - WARNING - Heartbeat failing (1 attempts), next retry in 5s
2026-09-26 12:33:58,020 - scanner.src.heartbeat - INFO - Heartbeat restored after 4 failure(s)
```
Для диагностики можно поднять уровень до DEBUG (logging.level в `scanner_config.json`).

---

## 3.3 Сканер не завершается по Ctrl+C (остаётся OCRWorker)

**Симптом:** после Ctrl+C процесс сканера висит, OCRWorker остаётся «осиротевшим»;
перезапуск сканера невозможен до ручного `taskkill` (BUG-081, до v3.13.20).

**Решение (исправлено в v3.13.20):** Ctrl+C (и Ctrl+Break/SIGBREAK) → graceful shutdown:
`[Scanner] SIGINT received` → останавливается heartbeat → классификаторам уходит
None в request_queue → OCRWorker завершает обработку штатно (`[PII] OCRWorker остановлен`,
`[X] Сканер остановлен`), процесс выходит с кодом 0.

Если после обновления всё ещё виден зависший OCRWorker:
```powershell
Get-CimInstance Win32_Process -Filter "name like 'python%'" | Where-Object { $_.CommandLine -match 'spawn_main|ocr_worker' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

---

## 3.4 В контекстах находок видны сырые credentials (+1-телефоны)

**Симптом:** через API (`GET /api/findings/{id}`, поля `context_before`/`context_after`)
видны сырые секреты: `GITHUB_TOKEN=ghp_…`, `BASIC_AUTH=Basic base64`, `SLACK_TOKEN=xoxb-…`,
`us: +1 415 …` (BAG-086, критический блокер v3.0.0 — утекали находки категорий
slack_token/basic_auth/database_url/phone и др.).

**Решение (исправлено в v3.13.21):** `mask_context` в `scanner/src/encryption.py`
переписан на конвейер `_CONTEXT_PATTERNS` (21 паттерн на все категории `MASK_RULES`;
специфичные токены раньше generic; generic `KEY=VALUE` маскирует только значение).
**Важно:** старые findings (сканированные до v3.13.21) сохраняют старые контексты —
нужен перескан ресурса. Признак устаревших данных — низкий `task_id` в findings.

Проверка себя:
```sql
-- В БД (dev-SQLite manager/dcap.db; prod — PostgreSQL)
SELECT id, category FROM findings
WHERE context_before_masked ~ 'ghp_[a-zA-Z0-9]{20,}|Basic [A-Za-z0-9+/=]{10,}|xox[baprs]-[a-zA-Z0-9-]{10,}|\+1[\s\-\.]?\(?\d{3}\)?';
```
Ожидание: 0 строк у findings **последнего скана**; старые строки — пересканировать
(задание → DELETE старых findings или экспорт/архивация).

---

## 4. Manager/WebUI отвечают старой версией

**Симптом:** `GET /api/health` показывает старую версию после правок.

**Решение:**
```powershell
$env:VERSION="X.Y.Z"          # обязательно задать, иначе компоузер возьмёт default из .env/yml
docker compose build manager webui
docker compose up -d manager webui
# celery при необходимости:
docker compose build celery_worker celery_beat
docker compose up -d celery_worker celery_beat
Invoke-RestMethod http://127.0.0.1:8000/api/health   # → "version":"X.Y.Z"
```
⚠️ Если не задать `VERSION`, может собран `<имя>:<старый default>` и контейнер
останется на прежнем образе.

---

## 5. Контейнеры зависают при пересоздании

**Симптом:** `docker compose up -d` пишет `cannot stop container ... did not receive an exit event`.

**Решение:** принудительно остановить и удалить зависший контейнер, затем повторить:
```powershell
docker stop $(docker ps -aqf "name=celery_worker")
docker rm $(docker ps -aqf "name=celery_worker")
docker compose up -d
```

---

**Актуально на:** 26.09.2026