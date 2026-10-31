# Отчёт: День 47.5 — BACKLOG-086: встраивание OCR-фрагментов в БД (TZ_BACKLOG_086_EMBED_FRAGMENTS.md) — v3.13.19

**Дата:** 26.09.2026
**Версия:** v3.13.18 → **v3.13.19**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_BACKLOG_086_EMBED_FRAGMENTS.md`

---

## Цель

Встраивать OCR-фрагменты (весь PNG) в БД при создании finding — Manager/WebUI/аудит получают
неизменяемое доказательство, даже если исходный файл удалён или Manager не видит хостовый путь
(контекст BUG-077). **Ключевое преимущество: «Файл удалили — доказательство осталось».**

Зафиксированные решения архитектора: БД (не S3); дубли фрагментов (дедуп → BACKLOG-087, v3.1.0);
`/fragment` → только Auditor+; `MAX_FRAGMENT_EMBED_SIZE` по умолчанию 2 МБ; OCR при bbox=None —
весь PNG; text_line **не** встраиваем; byte_range → v3.1.0; батчинг POST'ов — TASK-050 в рамках ТЗ.

## Реализация

### TASK-045 — модель `Finding` (`manager/src/db/models.py`)

```python
# BACKLOG-086 (TASK-045, v3.13.19): встроенный фрагмент (доказательная база).
# Только для image_region. text_line — данные в line_text_encrypted.
# byte_range — отложено до v3.1.0.
fragment_data = Column(LargeBinary, nullable=True)      # base64-decoded bytes
fragment_mime = Column(String(50), nullable=True)       # image/png, image/jpeg
fragment_hash = Column(String(64), nullable=True)       # SHA-256 (целостность)
fragment_size = Column(Integer, nullable=True)          # bytes
fragment_embedded_at = Column(DateTime, nullable=True)  # когда встроен
```

### TASK-046/050 — сканер (`scanner/src/managed_scanner.py`)

Модульные константы (env-override):

```python
MAX_FRAGMENT_EMBED_SIZE = int(os.environ.get("MAX_FRAGMENT_EMBED_SIZE", 2 * 1024 * 1024))
MAX_BATCH_SIZE_BYTES = int(os.environ.get("MAX_BATCH_SIZE_BYTES", 20 * 1024 * 1024))
_MAX_BATCH_COUNT = 500
_IMAGE_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
               "gif": "image/gif", "bmp": "image/bmp", "tif": "image/tiff",
               "tiff": "image/tiff", "webp": "image/webp"}
```

`_embed_fragment(finding)` — только `image_region` + файл существует + размер ≤ лимита:
`{"fragment_base64", "fragment_mime", "fragment_hash" (SHA-256), "fragment_size"}`; иначе `{}`.
Интеграция в `_serialize_finding` через `**_embed_fragment(finding)`.
`_split_by_size(findings, max_bytes)` разбивает список на батчи; `submit_results` отправляет
по батчам (TASK-050). Хэш и mime — из фактических данных файла (не хардкод).

### TASK-047 — Manager: сохранить фрагмент (`manager/src/api/scanner.py`)

```python
fragment_b64 = finding_data.get("fragment_base64")
fragment_data = None
if fragment_b64:
    try:
        fragment_data = base64.b64decode(fragment_b64)
    except Exception as e:
        logger.warning(f"Failed to decode fragment: {e}")

finding = Finding(
    ...
    bounding_box=finding_data.get("bounding_box"),          # TASK-044 (BUG-077)
    fragment_data=fragment_data,
    fragment_mime=finding_data.get("fragment_mime"),
    fragment_hash=finding_data.get("fragment_hash"),
    fragment_size=len(fragment_data) if fragment_data else None,
    fragment_embedded_at=datetime.utcnow() if fragment_data else None,
)
```

### TASK-048 — `/fragment` + `/fragment/hash` (`manager/src/api/findings.py`)

- `GET /api/findings/{id}/fragment` — теперь `Depends(require_auditor)` (RBAC Viewer+ → **Auditor+**, BUG-079).
  `_get_image_fragment`: **embedded-first** — при `fragment_data` → 200 `fragment_mime`,
  `X-Fragment-Mode: embedded`, `X-Fragment-Hash`, `Content-Disposition=attachment`; затем
  full-image (image_region без bbox, файл есть на хосте Manager); затем crop-ветки; иначе 404.
- `GET /api/findings/{id}/fragment/hash` (Auditor+) — `{finding_id, hash, size, mime, embedded_at}`;
  404, если фрагмент не встроен.
- Аудит: `AuditLog(event_type="fragment_accessed", metadata_json={"action","finding_id","mode"})`
  для обоих эндпоинтов (`_log_fragment_access`).
- `_is_auditor` остался (используется в `get_finding`, L293).

### TASK-049 — миграция

`manager/src/db/migrations/versions/005_add_fragment_columns.py` (revision `005_add_fragment_columns`,
down `004_resources_path_type_unique`), идемпотентная через `inspect`. Применена к live PostgreSQL:
`alembic upgrade head` → head = 005; колонки подтверждены (`fragment_data bytea`).

## Тесты

Новые файлы:
- `tests/unit/test_fragment_embed_v31319.py` — 8 тестов Manager (сохранение из payload, text_line не
  встраивается, embedded-ответ, fallback full-image, 404, RBAC viewer 403/auditor 200, `/fragment/hash`,
  аудит).
- `tests/unit/test_scanner_fragment_embed.py` — 6 тестов Scanner (малый PNG встраивается, лимит 2 МБ,
  text_line {}, hash=SHA-256 данных, кастомный лимит env через monkeypatch, `_split_by_size`).
- Фикс `tests/unit/test_ocr_bbox_v31317.py`: `_make_entity` теперь содержит `fragment_data/fragment_mime/
  fragment_hash = None` (иначе AttributeError при новых колонках).
- `tests/e2e/test_fragment_e2e.py` — E2E: сканирование → embedded → удаление исходника → 200 (с
  восстановлением файла в finally).

Прогоны:
- `pytest tests/unit/` → **160 passed** (146 + 14; ТЗ ожидал 159 — +1 за 6-й scanner-тест батчинга).
- `pytest tests/e2e/test_fragment_e2e.py -v` (с `$env:MANAGER_URL="http://127.0.0.1:8000"`) → **1 passed**.
  (По умолчанию conftest использует :18000 → SKIP; окружение задаёт `MANAGER_URL`.)

## Release v3.13.19

- `docker-compose.yml`: `dcap/manager` (×3: manager/celery_worker/celery_beat) и `dcap/webui` →
  3.13.19; env-блок Manager: `MAX_FRAGMENT_EMBED_SIZE: ${...:-2097152}`, `MAX_BATCH_SIZE_BYTES: ${...:-20971520}`
  (pass-through, пересборка не обязательна). `compose config` валиден.
- `.env.example`: добавлены обе переменные (ASCII-append).
- Сборка + деплой: `$env:VERSION="3.13.19"; docker compose build manager webui celery_worker celery_beat`,
  `up -d` → `/api/health` → `{"status":"healthy","version":"3.13.19"}`.
- Сканер перезапущен на хосте (`start_scanner.bat`, ключи из `secrets\`), PID 22940; active/heartbeat OK.

## Live-подтверждение (task 39)

```
DELETE FROM findings WHERE task_id IN (36, 37, 38);   -- 29 удалено
task 39: status=completed, findings_count=29, files_scanned=7, files_failed=0

SELECT id, category, fragment_type, detector, fragment_size, fragment_mime, ... FROM findings
WHERE task_id = 39 AND fragment_type = 'image_region';
  id  | category | fragment_type | detector | fragment_size | fragment_mime | has_hash | has_embedded_at | data_bytes
 1444 | email    | image_region  | ocr      | 8255          | image/png      | t        | t               | 8255
 1445 | phone    | image_region  | ocr      | 8255          | image/png      | t        | t               | 8255

SELECT COUNT(*) FROM findings WHERE task_id = 39 AND fragment_type = 'text_line' AND fragment_data IS NOT NULL;
  0
```

API (аудитор):
- `GET /api/findings/1444/fragment` → 200, `Content-Type: image/png`, `Content-Length: 8255`,
  `X-Fragment-Mode: embedded`, `X-Fragment-Hash: 9ecadc2f9059b07916a78a4a58d0de1e9cd62c9724287d5eb9f4bf708e928701`.
- `GET /api/findings/1444/fragment/hash` → `{finding_id, hash, size: 8255, mime, embedded_at}`.
- RBAC: той же эндпоинт под токеном `viewer` → **403**.
- **Ключевой тест**: `Remove-Item C:\test\scanner_clean\images\screenshot_clean.png` (копия сохранена в
  `temp\screenshot_clean_backup.png`) → `GET /fragment` по-прежнему **200**, `X-Fragment-Mode: embedded`,
  `Content-Length: 8255`. ✅ «Файл удалили — доказательство осталось». Исходник восстановлен.
- `audit_logs`: записи `fragment_accessed` (mode embedded/hash, user auditor, finding_id 1444/1445).

## Критерии закрытия ТЗ

- [x] py_compile всех изменённых .py — OK
- [x] Alembic-миграция применена (live PG: head 005, колонки проверены)
- [x] `pytest tests/unit/test_fragment_embed_v31319.py -v` — **8 passed**
- [x] `pytest tests/unit/test_scanner_fragment_embed.py -v` — **6 passed**
- [x] `pytest tests/unit/ -q` — **160 passed**
- [x] `pytest tests/e2e/test_fragment_e2e.py -v` — **1 passed**
- [x] Manager `/api/health` → 3.13.19
- [x] Task 39: fragment_data сохранён для OCR-findings (2 шт)
- [x] text_line: fragment_data = NULL
- [x] GET /fragment (auditor) → embedded + X-Fragment-Hash
- [x] GET /fragment (viewer) → 403 (RBAC ужесточён, BUG-079)
- [x] GET /fragment/hash → SHA-256, size, mime, embedded_at
- [x] После удаления исходного PNG — GET /fragment по-прежнему 200
- [x] audit_logs: action=fragment_accessed
- [x] Батчинг POST'ов работает (TASK-050, `_split_by_size` + лимит 500)
- [x] Доки: STATE.md, ROADMAP.md, ARCHITECTURE.md, CHANGELOG.md, STATE_TEST_SESSION.md,
  docs/admin-guide/05-security.md (+10-troubleshooting.md, §3.1)

> Примечание: пункт ТЗ «docs/admin-guide/09-retention.md» — файла в репо нет (админ-гайд содержит
> 04, 05, 06, 10). Retetion-аспект отражён в 05-security.md («Неизменяемые доказательства»):
> фрагмент удаляется вместе с finding.

## Отложено (v3.1.0)

- BACKLOG-085 — полный OCR-пайплайн с bbox (tesseract tsv)
- BACKLOG-087 — дедупликация встроенных фрагментов
- BACKLOG-088 — шифрование fragment_data (AES-256-GCM, как match_text_encrypted)

## Команда для коммита

```powershell
git add manager/src/db/models.py manager/src/db/migrations/versions/005_add_fragment_columns.py manager/src/api/scanner.py manager/src/api/findings.py scanner/src/managed_scanner.py tests/unit/test_fragment_embed_v31319.py tests/unit/test_scanner_fragment_embed.py tests/unit/test_ocr_bbox_v31317.py tests/e2e/test_fragment_e2e.py docker-compose.yml .env.example
git commit -F temp/commit_msg_31319_code.txt
# (сообщение многострочное — через файл во избежание проблем с фигурными скобками в PowerShell)
```

Затем доки:

```powershell
git add STATE.md ROADMAP.md ARCHITECTURE.md CHANGELOG.md prompts/reports/day_47.5_backlog086_embed_fragments_report.md prompts/tz/TZ_BACKLOG_086_EMBED_FRAGMENTS.md
git commit -F temp/commit_msg_31319_docs.txt
```

## Инструкция по запуску / ручное тестирование

```powershell
# 1. БД (миграция для новых БД)
alembic upgrade head

# 2. Сканер (на хосте, с ключами)
.\start_scanner.bat        # или: python run_scanner.py scanner\config\scanner_config.json

# 3. Стек
$env:VERSION="3.13.19"; docker compose up -d manager webui celery_worker celery_beat
Invoke-RestMethod http://127.0.0.1:8000/api/health   # → version 3.13.19

# 4. Сканирование (web login admin/admin123 → New scan → C:\test\scanner_clean)

# 5. Проверка доказательства
# auditor/auditor123:
#   GET /api/findings/{id}/fragment      → 200, X-Fragment-Mode: embedded, X-Fragment-Hash
#   GET /api/findings/{id}/fragment/hash → JSON с hash/size/mime
#   Дальше удалите исходный PNG на диске и повторите GET /fragment → всё ещё 200 (из БД)
# viewer/viewer123 → 403
```

## Док-правки

- `docs/admin-guide/05-security.md` — раздел «4.1 Неизменяемые доказательства (фрагменты, с v3.13.19)».
- `docs/admin-guide/10-troubleshooting.md` — §3.1 «Фрагмент недоступен, хотя файл был просканирован».
- `ARCHITECTURE.md` — колонки fragment_* в модели, типы фрагментов, `/fragment` Auditor+ + `/fragment/hash`,
  событие ИБ `fragment_accessed`.
- `ROADMAP.md` / `STATE.md` / `CHANGELOG.md` / `STATE_TEST_SESSION.md` — v3.13.19, BACKLOG-086 ✅.

## Статус

**BACKLOG-086 → ✅ подтверждён в live (task 39, embedded после удаления исходника).**
BUG-079 → исправлено (TASK-048: /fragment только Auditor+).
Следующий шаг: **Блок 5 (WebUI)** — п.2.3 (фильтры).