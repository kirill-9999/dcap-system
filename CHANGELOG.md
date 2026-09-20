# CHANGELOG

## v3.13.10 (2026-09-20)

### BUG-048b — middleware пропускал machine-API без извлечения JWT
- **BUG-048b**: `_is_public` в `AuthMiddleware` преждевременно возвращал `True` для
  `/api/scanner/*`, middleware выходил из `dispatch` без извлечения JWT → `request.state.user`
  оставался пустым → защищённые `require_admin` scanner-эндпоинты (`DELETE /api/scanner/{id}`)
  возвращали 401 вместо 403/404 (manager/src/auth/middleware.py)
- Убрана ветка `/api/scanner*` из `_is_public` — запросы теперь идут через
  `_is_machine_endpoint`, где JWT извлекается и `request.state.user` устанавливается
- В machine-ветке `call_next` перенесён внутрь `try/finally` — сессия БД держится открытой,
  пока хендлер читает `user.roles` (иначе DetachedInstanceError → 500)
- Machine-API агентов (register/heartbeat/tasks/events) остаются публичными без JWT (by design)
- **Тесты**: `tests/unit/test_scanner_middleware_rbac.py` — 9 регрессионных тестов
  (viewer→403, admin→404, без JWT→401, garbage→401, heartbeat/register/список без JWT публичны,
  mTLS relaxed не блокирует JWT); полный `tests/unit` — 118 passed
- **Docs**: `docs/admin-guide/06-scanner.md` (раздел «Модель доступа к scanner-API»),
  `docs/admin-guide/05-security.md` (§5.1 «Machine-API и JWT»)

## v3.13.9 (2026-09-19)

### Fix-спринт (TZ_FIX_SPRINT.md) — Auth/RBAC + стабильность
- **BUG-039**: refresh-токен больше не валиден как access — `verify_token(token, expected_type)`
  проверяет `payload["type"]`; `/api/auth/refresh` требует `"refresh"` (manager/src/auth/jwt.py, router.py)
- **BUG-046**: RBAC на CRUD ресурсов: POST/DELETE `/api/resources`, PUT `/api/resources/{id}/config` —
  только `admin`; POST `/api/resources/{id}/scan` — `admin/scanner` (manager/src/api/resources.py)
- **BUG-047**: RBAC + транзакция на задачи: POST `/api/tasks/{id}/cancel` и DELETE `/api/tasks/{id}` —
  только `admin`, DELETE возвращает 409 для `assigned/running`, rollback при ошибке (tasks.py)
- **BUG-048**: DELETE `/api/scanner/{id}` — только `admin` (scanner.py)
- **BUG-049..054**: RBAC на WebUI-эндпоинты: DELETE `/api/scanners/{id}` — admin; ping — scanner;
  `/api/tasks/create` — scanner; `/api/resources/create` — admin; алерт-status и отчёты
  (preview/excel/pdf) — auditor (webui.py)
- **BUG-055**: DELETE `/api/audit/agents/{id}` — только admin; `/api/permissions` mode/sync — admin,
  update/generate алертов — auditor (audit.py, permissions.py)
- **BUG-037**: `group_mapping` в конфиге — множественное число (`DCAP_Admins/DCAP_Auditors/DCAP_Scanners`)
- **BUG-043**: каталог `/api/catalog/tree` — `children` теперь всегда `list` (листья не ломали WebUI),
  агрегация рекурсивная корректная (catalog.py)
- **BUG-045**: `/api/scanner/heartbeat` — 400 при кривом JSON/`scanner_id`/`task_id` вместо 500
- **BUG-057**: сканер fail-fast — без `FINDINGS_ENCRYPTION_KEY`/`FINDINGS_HMAC_KEY` не стартует;
  legacy только при `DCAP_ALLOW_LEGACY_SCANNER=true` (run_scanner.py, scanner/src/encryption.py)
- **BUG-058**: Manager fallback `line_text_encrypted` — если сканер не прислал шифрованную строку,
  Manager шифрует сам (scanner.py submit_results)
- **BUG-059**: POST `/api/tasks/create` — нормализация `resource_type` в lowercase + fallback поиска
  без type при IntegrityError (больше не 500); уникальность ресурсов (path,type) — модель + Alembic 004
  (webui.py, resources.py, models.py, migrations/004_resources_path_type_unique.py)
- **BUG-038**: TTL JWT из env (`JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`) + bind-mount
  `manager/config` в docker-compose
- **BUG-041**: jti/iat во всех токенах; blacklist jti при logout и ротации refresh (Redis, fail-open)
- **BUG-042**: HttpOnly-cookie `Secure`-флаг из `AUTH_COOKIE_SECURE` (default false для localhost)
- **BUG-044**: маска email маскирует и домен (`us***@ex***.com`) — manager + scanner encryption
- Тесты: `tests/unit/test_rbac_guard.py`, `test_jwt_type.py`, `test_catalog_tree.py`,
  `test_tasks_create.py` + обновлены `test_encryption.py`, `test_scanner_findings.py`
  (всего 109 unit-тестов, green)

## v3.13.1 (2026-09-13)

### Файловый PII-анализ + остановка по Ctrl+C (день 42.5+, по прямому ТЗ)
- `PiiClassifier.scan_text(text)` — ОДИН вызов Presidio на весь файл (вместо построчного
  `analyze(line)` на каждую прошедшую quick-check строку); номера строк находок
  вычисляются из offset (`_line_starts` + bisect), позиции — относительно строки
- `FilesystemConnector._scan_text`: классификаторы с `scan_text` обрабатываются один раз
  на файл, остальные (Credentials/Code) — построчно `scan_line` как раньше
- `FilesystemConnector.scan_path(..., stop_event)`: сканирование останавливается после
  текущих файлов (seq — break, parallel — воркеры возвращают [])
- `ManagedScanner._stop_event`: `stop()`/Ctrl+C устанавливает событие → задача прерывается,
  результаты НЕ отправляются в Manager (task остаётся assigned, не искажается)
- Итог: Presidio на файле 200 строк — в 1.64x быстрее при идентичных находках (1200=1200);
  seq/par паритет сохранён (30/30, speedup 3.32x); контроль: 20/200 (seq) и 23/200 (par) файлов

## v3.13.0 (2026-09-13)

### Сканер-оптимизация (день 42.5, по прямому ТЗ)
- file-level prefilter: `_file_pass_prefilter` в `FilesystemConnector` — файл пропускается
  целиком, если ни один классификатор не видит признаков (`file_prefilter` у Credentials/PII)
- precompile всех regex: `CredentialsClassifier._compile_all()` (`prefilter_regex`,
  `compiled_patterns`, `_entropy_patterns`), `PiiClassifier` `_quick_line_patterns` + `_quick_file_regex`;
  убран `re.compile` из горячих циклов `scan_line`/`classify`
- ThreadPoolExecutor в `scan_path` (ex.map, монотонный прогресс) —
  `ConnectorConfig.max_parallel_files` (default 1 = seq; конфиг 4)
- `_analyzer_lock` у PiiClassifier (Presidio AnalyzerEngine не потокобезопасен)
- Синтетика: seq vs parallel идентичны (30/30), speedup 3.81x;
  реальный каталог: 27–43 файл/мин (было <25)

## v3.12.0 (2026-09-12)

### Findings Refactor — Этап 4 (финал)
- BACKLOG-058: фрагменты изображений — `GET /api/findings/{id}/fragment` → PNG
  (вырезанный из `fragment_path` или crop по `bounding_box` через Pillow, кэширование)
- BACKLOG-059: hex-дамп бинарных фрагментов — `?format=hex` вокруг `byte_offset`
  (окно ±64 байта, `manager/src/core/hex_dump.py`)
- BACKLOG-060: экспорт CSV/JSON с маскированием + reveal (Auditor+),
  аудит `findings_exported`, CSV injection protection (`csv_utils.py`), BOM для Excel
- BACKLOG-067: `X-Total-Count` в `GET /api/findings`; пагинация с номерами страниц в WebUI
- WebUI: `<img>` для image_region, `<pre>` для byte_range (finding_detail.js),
  кнопка «Экспорт» с диалогом формата/reveal (findings.js), `api.getWithMeta`
- Тесты: `tests/e2e/test_finding_fragments.py`, `tests/e2e/test_findings_export.py`,
  `tests/unit/test_hex_dump.py`, `tests/unit/test_csv_utils.py`