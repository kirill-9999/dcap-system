# Changelog — DCAP

Все значимые изменения проекта DCAP.

Формат — [Keep a Changelog](https://keepachangelog.com/),
версионирование — [SemVer](https://semver.org/).

---

---

## [v3.14.3] — 2026-10-17

### Fixed (53.4e RBAC hotfix — блоки 12–13: Users, Roles)

- **BUG-253** — нельзя снять роль `admin` с себя (лок-аут): чекбокс `admin`
  disabled при редактировании собственной учётки, backend
  `PUT /api/auth/users/{self}` без `admin` → 400.
- **BUG-257** — системные роли (`admin`/`auditor`/`scanner`/`viewer`)
  иммутабельны по `name` и `ad_group` (backend 400 + поля disabled в `/roles`);
  правится только `description`.
- **BUG-258** — кастомные роли без `permissions` отключены до v3.1.0:
  `POST /api/auth/roles` → 403, кнопка «Создать роль» disabled.
- **BUG-254** — валидация «хотя бы одна роль»: `POST /api/auth/users` без
  ролей → 400; frontend-проверка в модалке.
- **BACKLOG-316** — машинная роль `scanner` скрыта из `/users` (в `/roles`
  остаётся — нужна сканеру).
- **BUG-255** — кнопка «Войти» приведена к Dovetail (8px радиус, padding
  10×16, font-weight 500).
- **BUG-256** — при 403 WebUI показывает toast «Недостаточно прав» и
  редиректит на главную (раньше редирект был молчаливым).

### Added

- `tests/unit/test_auth_rbac_v3143.py` — 6 тестов: `POST /roles` → 403;
  `PUT /roles/{system}` (name) → 400, (description) → 200; `POST /users` без
  ролей → 400; `PUT /users/{self}` без `admin` → 400, с `admin` → 200.
- `tests/e2e/test_rbac_v3143.py` — 4 E2E-проверки WebUI (scanner скрыт,
  admin disabled, валидация роли, кнопка «Создать роль» disabled).

### Changed

- `tests/unit/test_roles_crud_audit_v31339.py` — 3 теста адаптированы под
  BUG-258 (создание ролей отключено): кастомные роли наполняются в БД
  напрямую, `role_created` через API недостижим.

### Fixed (53.4f test-infra)

- **BUG-259** — `test_ad_permissions.py` падал в combined-прогоне
  (`ModuleNotFoundError: connectors.permissions`): `manager/src/connectors/`
  был namespace-portion, а `scanner/connectors/` — regular-пакет, из-за чего
  `import connectors` перехватывал scanner. Добавлен `manager/src/connectors/__init__.py`;
  тест чистит `sys.modules['connectors*']` и ставит `manager/src` первым.
- **BUG-260** — на Windows `PermissionError: [WinError 5]` на
  `pytest-current`: корневой `conftest.py` переносит `basetemp` в
  `.pytest-tmp/` (git-ignored).
- **BUG-261** — `test_archiver_findings` падал (`TypeError`) на устаревшей
  схеме `Finding` (после v3.9.0): фикстура приведена к актуальным полям
  (`finding_type`, `fragment_type`, `fingerprint`, `encryption_key_id`,
  `first_seen_at`).
- **BUG-263** — `test_webui_pages_with_filters` ожидал `loadFilterOptions` в
  серверном HTML; функция определена в `webui/static/js/audit.js` (UI корректен).
  Тест проверяет подключение `/static/js/audit.js` в HTML + наличие функции в JS.
- **BACKLOG-317** — `docker-compose.test.yml` использовал общее имя проекта с
  основным стеком (`down -v --remove-orphans` сносил контейнеры `dcap-*`).
  Добавлен `name: dcap-test`.
- **BUG-262 (этап A)** — документация E2E-стенда (`docs/testing.md`):
  внешние предусловия (сканер `:9101`, MinIO `:9000`, seed-findings, `auditor`)
  и счётчики `48 passed, 12 skipped, 5 failed` (эталон `53/7` — при предусловиях).
  Этап B (seed + маркеры) — до 55; CI — BACKLOG-046.

### Changed (53.4f test-infra)

- Unit-команда: `pytest tests/unit manager/tests -q` → **517 passed**
  (корневой `conftest.py`, без `--basetemp`).
- `docker-compose.test.yml` — `name: dcap-test` (отдельный project name,
  не пересекается с основным `dcap-system`).

---

## [v3.14.2] — 2026-10-17

### Fixed (53.4e-grafana hotfix, диагностика Grafana/метрик)

- **BUG-245** — `dcap_scanner_heartbeat_age_seconds`/`dcap_scanner_active`
  больше не могут отдавать серию `scanner_id=""`. `_refresh_scanner_gauges()`
  изолирует обработку каждой строки, пропускает сканеры без id, логирует на
  уровне `warning` (был `debug` — ошибки не были видны в проде).
- **BUG-246** — `dcap_findings_total` переведён из Counter в **Gauge** и
  отражает реальное количество findings в БД по типам (pii, credentials, …),
  обновляется при каждом scrape (`_refresh_findings_gauges`). Сессионный
  счётчик переименован в `dcap_findings_created_total`.
- **BUG-247** — вводящая в заблуждение авто-метрика `dcap_findings_created`
  (timestamp `_created`) больше не генерируется, т.к. `dcap_findings_total`
  перестал быть Counter.
- **BUG-236** — в `monitoring/alertmanager/alertmanager.yml` закомментирован
  webhook на несуществующий `/api/alerts/webhook` (401 из-за AuthMiddleware).
- **BUG-241** — панель «HTTP error rate (5xx)» в `dcap-overview.json`:
  добавлен `or vector(0)` (показывает 0 вместо «No data»).
- **BUG-243** — job `s3-agent` закомментирован в `prometheus.yml` (target DOWN,
  т.к. S3-агент запускается только с `--profile agents`).
- **BUG-239** — удалены 2 пустые панели из `dcap-scanner.json`
  (per-file duration p50/p95, OCR latency — метрики не отдаются сканером).

### Added

- `manager/tests/test_metrics_v3142.py` — 6 тестов: `scanner_id="1"`,
  `+Inf` при отсутствии heartbeat, отсутствие `scanner_id=""`, findings
  из БД (pii/credentials), типы метрик, счётчик за сессию.

---

## [v3.14.1] — 2026-10-14

### Changed (53.4b–53.4e, WebUI-редизайн, этапы 2–5)

WebUI переведён на тёмную тему Dovetail (single accent `#6798ff`, 8px радиусы,
grid-wireframe, zero-shadow). Все 14 страниц переработаны.

- **53.4b** — login, dashboard, resources, findings: RBAC-гейты, datetime.js
  (UTC→локальное), фильтры, пагинация; `resources.js` (форма Filesystem/MinIO).
- **53.4c** — finding_detail, catalog, audit, scanners, access: пагинация,
  role-фильтр аудита, группировка типов событий, модалка metadata, массовое
  удаление неактивных сканеров (BACKLOG-155), `resources.js` (BUG-147).
- **53.4d** — роли/пользователи/настройки, футер, палитра графиков:
  - `/roles`: RU-бейджи системная/пользовательская, `ad_group`, описания
    системных ролей, confirm/тосты с именем (BUG-171/146/152/167/180,
    BACKLOG-149/150/151).
  - `/users`: статусы/тип учётки RU, `created_at`/`last_login`, привязка AD
    (`domain_user`), пароль + подтверждение, self-защита, сброс пароля,
    русские ошибки (BUG-160/164/165, BACKLOG-131/132/135/136/137/143/144/145).
  - Backend: `Role.to_dict` считает только активных (BUG-170);
    `UserCreate.password` default `""`, `domain_user` в `UserCreate`/`UserUpdate`
    (BUG-156/BACKLOG-134).
  - `/settings`: режим аутентификации только для чтения + предупреждение о
    lockout (BUG-187), счётчики данных через `/api/retention/stats` (BUG-199),
    пояснения архивации/экспорта/dry-run (BUG-189/190/191), пароль в `<form>`
    с требованиями и подтверждением (BUG-194/195/196), кнопка смены пароля в
    шапке (BUG-197), тосты Dovetail (BUG-198).
  - Footer: время помечено как местное, версия динамическая (BUG-185).
  - Графика: монохромная палитра Chart.js + акцент #6798ff.
  - Единый Dovetail-тост (BACKLOG-153).
- **53.4e (полировка)**:
  - **BUG-104** — favicon: `webui/static/favicon/` (svg/ico/png) + link-теги,
    маршрут `/favicon.ico`.
  - **BUG-126** — CSP и security-заголовки (`webui/main.py`); inline
    `<script>` вынесены в файлы (`audit.js`, `access.js`, `scanners.js`,
    `login.js`, `settings.js`, init в `dashboard.js`, `FINDING_ID` через
    data-атрибут в `finding_detail.js`).
  - **BACKLOG-138** — унификация модалок (единый порядок кнопок, отступы).
  - `DESIGN.md` → `docs/DESIGN.md` (git mv).
  - `docs/ui-screenshots/` — скриншоты страниц × 3 разрешения.
  - E2E-очистка: `e2e_*` пользователи, `test_event*` аудит, неактивные сканеры
    (BUG-166/183, TEST-NOTE-10.2).

---

## [v3.13.41] — 2026-10-13

### Fixed (53.4a-доп5, hotfix backend + sync)

- **BUG-150** — `DELETE /api/resources/{id}` → 500 (9+ FK с `NO ACTION`).
  Alembic-миграция `manager/src/db/migrations/versions/007_add_cascade_deletes.py`:
  **ON DELETE CASCADE** для FK на `resources.id` и `scan_tasks.id` —
  findings, scan_tasks, catalog_entries, access_entries, access_alerts,
  permission_changes, failed_files, schedules. `audit_logs` (партиционированная),
  `findings_old` (legacy) и `findings.reviewed_by` не тронуты.
  `delete_resource` → **204** (None); для SQLite (dev) связанные записи
  удаляются вручную. Миграция применена на PostgreSQL. Тест
  `tests/unit/test_delete_resource_v31341.py` (3 passed).
- **BUG-149** — S3-скан возвращал 0 files. Причина: ресурсы s3/minio,
  созданные через legacy WebUI (`/api/tasks/create`, `/api/resources/create`),
  не получали `scan_config.connector.s3` → `S3LineConnector` падал
  («bucket обязателен») → fallback на filesystem → 0 files. Фикс:
  - `S3LineConnector.__init__` больше не требует bucket (WARNING вместо ValueError);
  - `scan_path()` — bucket-фолбэк из `path` (config приоритетнее), `self._bucket`
    запоминается для чтения; `_discover_keys(prefix, bucket)` —
    DEBUG-логи key-count и страны; таймаут `list_objects_v2` теперь
    re-raise (раньше молча → 0 ключей);
  - webui-эндпоинты строят `connector.s3` (endpoint: `S3_DEFAULT_ENDPOINT`
    → `host.docker.internal:9000`, bucket/prefix из path);
  - `source_type` теперь сохраняется на `ScanTask`.
  Тесты: `tests/unit/test_s3_line_connector_v31331.py` (+3) и
  `tests/e2e/test_s3_scan_v31341.py` (S3-скан MinIO → > 0 files, ≥ 9 находок).

### Changed

- **BACKLOG-121** — `.btn-primary` → **white filled** `#ffffff`
  (текст `#0a0a0a`, hover `#a7a7a7`, disabled `#7c7c7c`) в
  `webui/static/css/components.css` — возврат к DESIGN.md (отклонение 53.4a отменено).
- **BACKLOG-119** — badge режима на `/login` показывается **только для
  `windows_integrated`**; для `local`/`hybrid` скрыт (режим `hybrid` остаётся
  в коде до v3.1.0). `webui/templates/login.html`.

### Docs

- **ARCHITECTURE.md** — синхронизирован с кодом (чек-лист 10 пунктов):
  BUG-150/149/148, .btn-primary white, badge /login, подраздел
  «WebUI: хранение токена» (`dcap_access_token`), BUG-176;
  структура tests/unit (460), миграции 001…007; VERSION 3.13.41.
- `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md` — обновлены на v3.13.41.

### Tests

- Unit: **460 passed** (455 эталон + BUG-150 ×3 + S3 bucket-фолбэк ×3 − S3 legacy test).
- E2E: `tests/e2e/test_s3_scan_v31341.py` (NEW, DoD-критерий ≥ 9 находок);
  эталонный прогон 53/7 — на стенде :18000/:18001.
- ⚠️ Docker-демон завис (окружение) на момент отчёта — живая проверка
  DELETE 204 / S3-скана на контейнере запланирована после перезапуска Docker Desktop.

### Files (53.4a-доп5)

- `manager/src/db/migrations/versions/007_add_cascade_deletes.py` — NEW.
- `scanner/connectors/s3_line_connector.py` — bucket-фолбэк, логи, re-raise.
- `manager/src/api/webui.py` — `_apply_s3_connector` в /api/tasks/create, /api/resources/create; source_type.
- `webui/static/css/components.css`, `webui/templates/login.html`.
- `tests/unit/test_delete_resource_v31341.py`, `tests/unit/test_s3_line_connector_v31331.py`,
  `tests/e2e/test_s3_scan_v31341.py`.
- `ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md`.
- `.env`, `.env.example`, `docker-compose*.yml` — `VERSION=3.13.41`.

---

## [v3.13.40] — 2026-10-12

### Fixed (53.4a-доп4, fonts, BUG-212)

- **BUG-212** — Inter / JetBrains Mono не применялись к кириллице.
  `unicode-range` в `inter.css` / `jetbrains-mono.css` расширен:
  Latin (U+0000-00FF …) + **Cyrillic base** (U+0400-045F, U+0490-0491, U+04B0-04B1, U+0301, U+2116)
  + **Cyrillic Extended** (U+0460-052F, U+1C80-1C88, U+20B4, U+2DE0-2DFF, U+A640-A69F)
  + Latin Extended Additional (U+1E00-1EFF). Теперь браузер запрашивает оба woff2 для русского текста.
- **`jetbrains-mono.woff2` заменён** — прежний был latin-only подмножеством Fontsource (229 глифов, кириллицы 0).
  Взят официальный **JetBrains Mono v2.304 variable** (`JetBrainsMono[wght].ttf` → woff2, fontTools):
  1363 глифа, базовая кириллица 92/96, ось `wght` 100-800 (соответствует `@font-face: font-weight: 100 800`, `woff2-variations`).
  `inter.woff2` не менялся (полный variable, кириллица 96 базовых + 155 extended).
- Добавлен `webui/static/vendor/fonts/OFL.txt` — лицензия SIL OFL 1.1 (JetBrains Mono).

### Tests (53.4a-доп4)

- Проверка через HTTP (то, что видит браузер): `inter.css` / `jetbrains-mono.css` — 200, `unicode-range` содержит U+0400-045F;
  `inter.woff2` (352 240 б) / `jetbrains-mono.woff2` (113 484 б) — 200.
- Glyph-чек cmap (fontTools): Inter — П/р/и/в/е/т/Ж/У/К/я все на месте; JetBrains Mono — 10/10.
- Эмуляция `unicode-range`-матчинга браузера: кириллическая выборка полностью попадает в диапазоны обоих файлов.
- CSS-цепочка: `main.css → base.css → @import inter.css/jetbrains-mono.css`; `tokens.css` — `--font-inter: 'Inter', …`, `--font-jetbrains-mono: 'JetBrains Mono', …`, `--font-mono: var(--font-jetbrains-mono)`.
- Регресс страниц WebUI — **14/14 вернули 200** (`/`, `/login`, `/catalog`, `/findings`, `/findings/{id}`, `/false-positives`, `/resources`, `/audit`, `/access`, `/scanners`, `/users`, `/roles`, `/settings`, `/health`).

### Files (53.4a-доп4)

- `webui/static/vendor/fonts/inter.css` — unicode-range + кириллица.
- `webui/static/vendor/fonts/jetbrains-mono.css` — unicode-range + кириллица.
- `webui/static/vendor/fonts/jetbrains-mono.woff2` — заменён на официальный JetBrains Mono v2.304 variable (кириллица).
- `webui/static/vendor/fonts/OFL.txt` — NEW (SIL OFL 1.1).
- `.env`, `.env.example`, `docker-compose*.yml` — `VERSION=3.13.40`.

### Docs (53.4a-доп4)

- `ARCHITECTURE.md` — файл в переработке архитектора; готовый патч раздела «Шрифты» — в отчёте
  `prompts/reports/day_53_4a_add4_fonts_report.md`.

---

## [v3.13.39] — 2026-10-12

### Fixed (53.4a-доп3, hotfix backend-critical)

- **BUG-201** — `POST /api/auth/change-password` возвращал 200, но пароль в БД не менялся:
  мутация объекта `request.state.user` из middleware не доходила до сессии хендлера
  (`db.commit()` пустой). В `change_password` пользователь пере-запрашивается
  в сессии хендлера, commit +refresh, аудит `user_password_changed` пишется после commit.
- **BUG-202** — аудит писался до `db.commit()`: при откате транзакции запись оставалась,
  а изменения — нет. Введён единый контекст-менеджер `with_audit(db, event_type, **kwargs)`
  (`manager/src/api/audit_helper.py`): yield → `_log_audit` → commit; исключение → rollback + raise.
  Переведены: `api/resources.py` (created/updated/deleted), `api/findings.py` (update PATCH),
  `auth/router.py` (role_created/updated/deleted, change_password).
- **BUG-214** — `GET /api/audit` и `/api/audit/stats` были доступны viewer/scanner.
  Добавлено `dependencies=[Depends(require_auditor)]`.
- **BUG-223** — `GET /api/audit/{id}` — отсутствовал (metadata_json недоступен).
  Добавлен эндпоинт с `AuditLogDetail` (включает metadata), 404 при отсутствии.
- **BUG-181** — нет аудита ролей. `POST/PUT/DELETE /api/auth/roles` теперь пишут
  `role_created`/`role_updated`/`role_deleted`.
- **BUG-168** — системные роли (`admin/auditor/scanner/viewer`) можно было переименовывать
  и менять AD-группу → RBAC ломался. Запрещено (400), `description` — редактируется.
- **BUG-142** — `/api/audit/stats` не возвращал `total_resources` (Dashboard KPI «Ресурсов» = 0).
  Добавлен `count(Resource.id)`.
- **BUG-148** — сканер не читал `.env`: `load_dotenv()` добавлен в `run_scanner.py`,
  блок загрузки `.env` — в `start_scanner.bat`.

### Tests (53.4a-доп3)

- NEW: `tests/unit/test_audit_rollback_v31339.py` (4), `test_auth_password_v31339.py` (4),
  `test_audit_rbac_v31339.py` (8), `test_roles_crud_audit_v31339.py` (7).
- `pytest tests/unit` — **455 passed** (DoD ≥433).
- `pytest tests/e2e` (изолированный стенд `:18000`, нативный сканер) — **53 passed / 7 skipped**.

### Data (53.4a-доп3)

- Удалены ложные `user_password_changed` из `audit_logs` в PostgreSQL (5 записей:
  id 250, 1886–1889; осталось 0). Cleanup-скрипт — `E:\Temp\opencode\cleanup_pw_audit.py` (вне репо).

### Files (53.4a-доп3)

- `manager/src/api/audit_helper.py` — NEW: `_log_audit` (без commit) + `with_audit`.
- `manager/src/api/schemas_audit.py` — NEW: `AuditLogDetail` (c metadata).
- `manager/src/api/audit.py`, `manager/src/api/findings.py`, `manager/src/api/resources.py`,
  `manager/src/auth/router.py`, `manager/src/auth/schemas.py` — обновлены.
- `run_scanner.py`, `scripts/start_scanner.bat` — BUG-148.
- `tests/unit/test_{audit_rollback,auth_password,audit_rbac,roles_crud_audit}_v31339.py` — NEW.

---

## [v3.13.38] — 2026-10-10

### Fixed (53.4a-доп)

- **BUG-139** — WebUI: иконки Font Awesome были цветные (эмодзи вместо монохромных).
  Добавлены `fa-solid-900.woff2`, `fa-regular-400.woff2`, `fa-brands-400.woff2` в `webui/static/vendor/webfonts/`.
- **BUG-138** — `finding_detail.js`: `onerror` с HTML в атрибуте давал `SyntaxError`
  в Console. Заменено на `addEventListener('error')`.
- **BUG-140** — `finding_detail.js`: reveal для `image_region` был лишним; перезапись
  `#fragment`; спам аудита; дубль `line`/`match`; `bg-light` вместо `.reveal-block`.
  Исправлено: toggle + кэш (`cachedReveal`), подсветка match внутри line (`<mark>`),
  скрытие кнопки reveal для `image_region`.

### Files (53.4a-доп)

- `webui/static/vendor/webfonts/` — NEW: FA 6.4.0.
- `webui/static/js/finding_detail.js` — обновлён.
- `webui/static/css/findings.css` — `.reveal-block` + `mark`.
- `.env` / `.env.example` / compose — `VERSION=3.13.38`.

---

## [v3.13.37] — 2026-10-09

### Added (53.4a, BACKLOG-093, этап 1/5)

- **Dovetail-токены** — `webui/static/css/tokens.css` (dark-only, + legacy-алиасы).
- **Base** — `webui/static/css/base.css`.
- **Components** — `webui/static/css/components.css` (override Bootstrap).
- **Grid-wireframe** — `webui/static/css/grid-wireframe.css` (blueprint-сетка `body::before`).
- **Локальные шрифты** — `webui/static/vendor/fonts/`:
  - `inter.woff2` (352 KB, Inter Variable).
  - `jetbrains-mono.woff2` (40 KB).
  - `inter.css`, `jetbrains-mono.css` (с `@font-face`).
- **`DESIGN.md`** — коммит `34e3383` (референс Dovetail; в v3.14.1 перенесён в `docs/DESIGN.md`).

### Changed (53.4a)

- `webui/templates/base.html`, `webui/templates/login.html` — `data-theme="dark"`, новые `<link>`, без `theme.js`.
- `webui/static/css/main.css` — обновлённые `@import`, без дублей глобальных правил и `.btn*`.

### Removed (53.4a)

- `webui/static/css/variables.css` — перенесено в `tokens.css`.
- `webui/static/css/theme-dark.css` — dark-only, не нужен.
- `webui/static/js/theme.js` — переключатель темы удалён.

### Известные проблемы (53.4a)

- ⚠️ `unicode-range` в `inter.css` / `jetbrains-mono.css` — **latin-only** (BUG-212).
- ⚠️ Chart.js палитра — не под Dovetail (BACKLOG-154).
- ⚠️ Grid-wireframe тонкий (~3% контраста).

---

## [v3.13.36] — 2026-10-07

### Fixed (BUG-137, hotfix)

- **BUG-137** — OCR: тихая потеря находок PNG при параллельной обработке (гонка temp-файлов).
  Исправлено: `_work_dir`-изоляция temp (`uuid`-подпапка на движок).
  Добавлен WARNING при потере OCR-ответа.
- Тест: `tests/unit/test_ocr_worker_race_v31336.py` — 3 прошли.

### Files

- `scanner/utils/ocr_engine.py` — `_work_dir`-изоляция.
- `scanner/classifiers/pii_classifier.py` — WARNING при потере OCR.
- `scanner/connectors/_text_scanner.py` — WARNING при пустом документ-OCR.

---

## [v3.13.35] — 2026-10-06

### Fixed (53.3-fix-s3-bucket)

- **`S3LineConnector`** — bucket только из `scan_config.connector.s3.bucket`.
  Убрано сравнение `parsed.netloc != self._bucket` и ложный WARNING.
  `s3://bucket/prefix` — суффикс префикса; bucket фиксируется при создании ресурса.
- **BACKLOG-103** — заведён (fallback на config-секреты → v3.1.0).

### Files

- `scanner/connectors/s3_line_connector.py`.
- `tests/unit/test_s3_line_connector_v31331.py` — +3 теста.
- `docs/admin-guide/06-scanner.md` §8.1 — контракт bucket/prefix.

---

## [v3.13.34] — 2026-10-05

### Fixed (53.3-test-stand-fix)

- **TEST-NOTE-10.6** — `manager_test` / `webui_test` стартовали раньше готовности PostgreSQL.
  Исправлено: healthcheck + `depends_on: service_healthy`.
- **TEST-NOTE-10.7** — `postgres_test_data` копил pending-задачи.
  Исправлено: `scripts/run-tests.sh` — режим `all` делает `down -v` + `up -d --wait`.

### Files

- `docker-compose.test.yml` — healthcheck + `service_healthy`.
- `scripts/run-tests.sh` — режимы `stand` / `all`.
- `docker-compose.yml` / `docker-compose.s3.yml` — теги образов `${VERSION:-3.13.34}`.
- `docs/testing.md` — автоматический запуск.

---

## [v3.13.32] — 2026-10-04

### Added (53.3, BACKLOG-097 ч.4)

- **E2E на MinIO** — `tests/e2e/test_s3_e2e.py`.
- **WebUI-форма S3/MinIO** — `webui/templates/resources.html` (типы `filesystem` / `s3` / `minio`, блок `#s3-fields`).
- **`docs/admin-guide/06-scanner.md` §8** — «S3/MinIO-сканирование».

### Changed (53.3)

- **`manager/src/api/resources.py`** — вариант B endpoint: query → `S3_DEFAULT_ENDPOINT` → 400.
  Хардкод `host.docker.internal:9000` удалён.

### Files

- `tests/e2e/test_s3_e2e.py` — NEW, полный живой цикл S3.
- `tests/unit/test_s3_resource_v31329.py` — 22 теста.
- `.env.example` — секция `SCANNER: S3/MinIO`.

---

## [v3.13.31] — 2026-10-03

### Added (53.2, BACKLOG-097 ч.3)

- **`S3LineConnector`** — построчный S3/MinIO-коннектор (`scanner/connectors/s3_line_connector.py`):
  - Streaming через `Body.iter_chunks`.
  - Документы / OCR — через временный файл + `DocumentExtractor`.
  - Секреты — только ENV (`S3_ACCESS_KEY` / `S3_SECRET_KEY`).
  - Интерфейс как у `FilesystemConnector`.

### Fixed (BUG-136)

- **BUG-136** — `decode_text_bytes` не доходил до cp1251-ветки из-за `errors="ignore"` в первой итерации.
  Исправлено: strict-декод: `utf-8` → `cp1251` → `fallback utf-8 errors="ignore"`.
  Подтверждено на живых данных MinIO (9 находок).

### Files

- `scanner/connectors/s3_line_connector.py` — NEW.
- `scanner/connectors/_text_scanner.py` — BUG-136 fix.
- `scanner/connectors/factory.py` — регистрация `s3` / `minio`.
- `scanner/src/managed_scanner.py` — `_current_source_type`, `_current_scan_config`, `_parent_of_path`.
- `tests/unit/test_s3_line_connector_v31331.py` — 16 тестов.
- `tests/unit/test_decode_text_cp1251_v31331.py` — 5 тестов.

---

## [v3.13.30] — 2026-10-02

### Added (53.1b, BACKLOG-097 ч.2)

- **`scanner/connectors/_text_scanner.py`** — NEW, 5 функций общего построчного пайплайна:
  `is_supported_file`, `decode_text_bytes`, `file_pass_prefilter`, `scan_text`, `extract_document_text`.
- **`scanner/connectors/factory.py`** — NEW, реестр `source_type` → коннектор.
- **`boto3`** — добавлен в `scanner/requirements.txt`.
- **`S3ConnectorConfig`** — в `scanner/src/config_loader.py`.

### Changed (53.1b)

- **`scanner/connectors/filesystem.py`** — рефакторинг на `_text_scanner`.

---

## [v3.13.29] — 2026-10-01

### Added (53.1a, BACKLOG-097 ч.1)

- **`ScanTask.source_type`** — `filesystem` / `s3` / `minio` (миграция 006).
- **S3/MinIO-ресурсы** — `manager/src/api/resources.py`:
  - `POST /api/resources?type=s3&path=s3://bucket/prefix[&endpoint=...]`.
  - `scan_config.connector.s3 = {endpoint, bucket, prefix, secure, use_path_style, region}`.
- **Миграция 006** — `manager/src/db/migrations/versions/006_add_source_type.py` (идемпотентна).

### Changed (53.1a)

- **`POST /api/resources/{id}/scan`** — проставляет `source_type = (resource.type or "filesystem").lower()`.
- **`manager/src/api/scanner.py`** — `source_type` в payload задачи.

### Files

- `tests/unit/test_s3_resource_v31329.py` — 19 тестов.

---

## [v3.13.28] — 2026-09-30

### Fixed (Блок 9, Безопасность — 10 BUG)

- **BUG-103** — MetricsMiddleware — outermost, нормализация endpoint.
- **BUG-105** — Volume PKI: `./certs:/app/certs:ro`.
- **BUG-106** — Machine-endpoints: mTLS до `_is_public`.
- **BUG-107** — CRL enforce на 2 уровнях: TLS + middleware.
- **BUG-108** — mTLS strict → `CERT_REQUIRED`.
- **BUG-110** — Reveal при ошибке → 409 + аудит.
- **BUG-111/114…116** — (см. `block9_fix_sprint_v31328_report.md`).

### Added (Блок 6, Агенты)

- **Windows-агент** — служба `DCAPAuditAgent` (Automatic), Security Log через `wevtutil`.
- **Linux-агент** — WSL 2 (Ubuntu 22.04), systemd-user, `watchdog`.
- **S3-агент** — MinIO (нативный), seed-логи.
- **BUG-122** — systemd-unit portable.

### Files

- `block9_fix_sprint_v31328_report.md`.
- `block6_agents_full_report.md`.

---

## [v3.13.27] — 2026-09-29

### Fixed (BUG-102)

- **BUG-102** — Retention + sweep падали на `Mapper[Finding] ... 'User' failed to locate a name`.
  Фикс: импорт `User` из `auth.models` в 6 модулях + `configure_mappers()` в `celery_app.py`.

### Files

- `day_50_bug102_celery_mapper_report.md`.

---

## [v3.13.26] — 2026-09-28

### Added (BUG-098…101, 101b)

- **BUG-098** — `PATCH /findings/{id}` — аудит.
- **BUG-099** — `POST /findings/bulk` — аудит (по одной записи на finding).
- **BUG-100** — Сброс review-полей при `new` (`_apply_status`).
- **BUG-101/101b** — `DELETE /findings/{id}` — аудит; FP `file_path`.
- Единая точка аудита `_log_finding_status_change` (без commit — batch).

### Files

- `day_49_bug098_101_report.md`.

---

## [v3.13.25] — 2026-09-27

### Fixed (BUG-096/096b/097)

- **BUG-096** — `/false-positives` 500.
- **BUG-096b** — устаревшие E2E.
- **BUG-097** — зависшие задания.

### Files

- `day_48.3_bug096_097_report.md`.

---

## [v3.13.24] — 2026-09-26

### Added (BUG-095)

- **BUG-095** — Аудит аутентификации и управления пользователями:
  - `auth_login`, `auth_failed`, `auth_logout`.
  - `user_created`, `user_updated`, `user_password_changed`.
  - `role_assigned`, `role_revoked`, `user_deleted`.
  - `auth_refresh` — не логируется.
  - `_sanitize` — рекурсивно вырезает secrets.

### Files

- `day_48.2_bug095_auth_audit_report.md`.

---

## [v3.13.23] — 2026-09-25

### Fixed (BUG-094)

- **BUG-094** — Аудит reveal: ложное срабатывание. `user` в SQL — в кавычках.

### Files

- `day_48.1_bug087_audit_user_report.md`.

---

## [v3.13.22] — 2026-09-24

### Added (Блок 5, п.2.3 — WebUI)

- Фильтры, пагинация, аудит, экспорт findings.
- `detector`, `fragment_type`, `search` — в `GET /api/findings`.
- `X-Total-Count` — заголовок.

### Files

- `day_48_block5_webui_filters_report.md`.

---

## [v3.13.21] — 2026-09-23

### Fixed (BUG-086)

- **BUG-086** — Masking контекстов: `_CONTEXT_PATTERNS` — 22 паттерна (17 категорий).
  Специфичные токены раньше generic.

### Files

- `day_47.7_fix_bug086_mask_context_report.md`.

---

## [v3.13.20] — 2026-09-22

### Fixed (BUG-080/081)

- **BUG-080** — Heartbeat backoff: `[5, 10, 30, 60, 120]`.
- **BUG-081** — Graceful shutdown сканера.

### Files

- `day_47.6_backlog080_081_scanner_reliability_report.md`.

---

## [v3.13.19] — 2026-09-21

### Added (BACKLOG-086)

- **Встроенные OCR-фрагменты в БД**:
  - `fragment_data` (LargeBinary), `fragment_mime`, `fragment_hash`, `fragment_size`, `fragment_embedded_at`.
  - Миграция `005_add_fragment_columns.py`.
  - Base64-encoded PNG в payload от сканера.

### Files

- `day_47.5_backlog086_embed_fragments_report.md`.

---

## [v3.13.18] — 2026-09-20

### Fixed (BUG-077 diag)

- **BUG-077** — Manager дефолтил `bbox` (H3).

### Files

- `day_47.4_bug077_diag_report.md`.

---

## [v3.13.17] — 2026-09-19

### Fixed (BUG-077)

- **BUG-077** — `bounding_box=None` для OCR + fallback.

### Files

- `day_47.3_fix_bug077_report.md`.

---

## [v3.13.16] — 2026-09-18

### Fixed (Fix-спринт №7, BUG-075)

- **BUG-075** — url = домен email.

### Files

- `day_46.10_fix_sprint_7_report.md`.

---

## [v3.13.15] — 2026-09-17

### Fixed (Fix-спринт №6)

- url-over-email (line_text), аббревиатуры, uk_nhs.

### Files

- `day_46.9_fix_sprint_6_report.md`.

---

## [v3.13.14] — 2026-09-16

### Fixed (Fix-спринт №5)

- url-over-email, OCR-markup, spaCy noise, credentials.

### Files

- `day_46.8_fix_sprint_5_report.md`.

---

## [v3.13.13] — 2026-09-15

### Fixed (Fix-спринт №4)

- OCR-секция + Presidio ru+en.

### Files

- `day_46.7_fix_sprint_4_report.md`.

---

## [v3.13.12] — 2026-09-14

### Fixed (Fix-спринт №3)

- OCR, HTTP-retry, Luhn, dedup.

### Files

- `day_46.5_fix_sprint_3_report.md`.

---

## [v3.13.11] — 2026-09-13

### Fixed (Fix-спринт №2)

- ENV-ключи Findings.

### Files

- `day_46_report.md`.

---

## [v3.13.10] — 2026-09-12

### Fixed (Fix-спринт №2)

- middleware BUG-048b.

---

## [v3.13.9] — 2026-09-11

### Fixed (Fix-спринт №1)

- Auth/RBAC.

### Files

- `day_45_fix_sprint_report.md`.

---

## [v3.13.8] — 2026-09-10

### Added

- Блок 1 (Smoke) + AD-контейнер.

### Files

- `day_43_*`, `day_44_*`.

---

## [v3.13.3-v3.13.7] — 2026-09-05..09

### Added

- Начало v3.0.0 (WebUI, AD, безопасность, Findings Refactor).

---

## [v3.13.0-v3.13.2] — 2026-09-01..04

### Added

- См. предыдущие CHANGELOG.

---

## [v3.12.0] — 2026-08-31

### Added

- Findings Refactor (v3.9.0-v3.10.0):
  - Гибрид: masked + encrypted.
  - AES-256-GCM.
  - HMAC-SHA256 fingerprint (вместо SHA256).
  - Миграция `003_findings_refactor.py`.

---

## [v3.0.0-v3.11.0] — 2026-06..08

### Added

- Обнаружение, классификация, WebUI, Linux-агент.
- Модель Finding (строка/фрагмент).
- RBAC.
- mTLS.
- Retention.
- Аудит (частично).

---

## [v1.0.0-v2.1.0] — 2025-2026

### Added

- MVP: сканирование, классификация, WebUI.
- Блок 1 (Smoke), Блок 2 (Auth/RBAC).

---

**Актуально на:** 12.10.2026
**Версия:** v3.13.38
**Следующая версия:** v3.13.39 (53.4a-доп3 — hotfix) → v3.13.40 (53.4a-доп4 — fonts) → v3.14.0 (53.4b)
📄 C — README_MASTER_SESSION.md
markdown
# 📊 DCAP v3.13.38 — Master Session Report

**Дата:** 12.10.2026
**Версия:** v3.13.38
**Тип:** Мастер-сессия ручного тестирования (WebUI 1–17 + RBAC)
**Длительность:** ~10 часов
**Источник:** `STATE_TEST_SESSION.md`

---

## 🎯 Итог одним абзацем

Пройдены **все 17 блоков** WebUI + **RBAC-прогон** (4 роли × ~10 страниц).
**Backend — работает (96%)**; **Frontend — требует редизайна** (Responsive, RBAC, локализация).
Найдено **~100 багов** и **~40 улучшений**. Собран **пакет из 4 ТЗ**:
hotfix (backend-critical) + hotfix (fonts) + 53.4b + 53.4c/d/e.

---

## 📊 Статистика

| Показатель | Значение |
|-----------|----------|
| Пройдено блоков | 17 + RBAC |
| Найдено BUG | **~100** (BUG-141…236) |
| Найдено BACKLOG | **~40** (BACKLOG-131…155) |
| Закрыто по ходу | 3 (BUG-138/139/140 — 53.4a-доп) |
| Critical (hotfix) | 12 |
| Unit-тестов | **433 passed** |
| E2E-тестов | **53 passed, 7 skipped** |
| ТЗ собрано | 4 |

---

## 🚨 Топ-12 критичных (блокеры v3.0.0)

| # | ID | Проблема | Область |
|---|-----|----------|---------|
| 1 | **BUG-201** | Смена пароля: 200 OK, пароль не меняется | Backend / security |
| 2 | **BUG-202** | Audit-log пишется при провале транзакции | Backend / compliance |
| 3 | **BUG-214** | `/api/audit` доступен viewer/scanner | Backend / RBAC |
| 4 | **BUG-223** | `GET /api/audit/{id}` — 404 (metadata недоступна) | Backend / compliance |
| 5 | **BUG-181** | Нет аудита ролей | Backend / compliance |
| 6 | **BUG-168** | Системные роли редактируются (RBAC риск) | Backend / RBAC |
| 7 | **BUG-212** | Шрифты — fallback (unicode-range latin-only) | Frontend / design |
| 8 | **BUG-148** | Scanner не читает `.env` (S3-секреты) | Scanner |
| 9 | **BUG-142** | Dashboard KPI «Ресурсов» = 0 | Frontend |
| 10 | **BUG-232** | Модалки ломаются на mobile | Frontend / responsive |
| 11 | **BUG-233** | Гамбургер не работает | Frontend / responsive |
| 12 | **BUG-213** | Frontend RBAC не работает | Frontend / RBAC |

---

## 📋 Разбивка по блокам

### Блок 12 — Users
**BUG:** 156, 157, 158, 159, 160, 161, 162, 164, 165, 166.
**BACKLOG:** 131, 132, 134, 135, 136, 137, 141, 142, 143, 144, 145, 131.
**Критично:** форма создания/редактирования сломана.

### Блок 13 — Roles
**BUG:** 167, 168, 170, 171, 172, 173, 174, 176, 177, 178, 179, 180, 181.
**BACKLOG:** 146, 148, 149, 150, 151, 152.
**Критично:** системные роли редактируются; нет аудита; нет permissions.

### Блок 14 — Settings
**BUG:** 187, 188, 189, 190, 191, 192, 194, 195, 196, 197, 198, 199, 200, 201.
**BACKLOG:** 153.
**Критично:** смена пароля не работает; смена auth_mode → лок-аут.

### Блок 15 — Console
**BUG:** 104, 142, 203, 204, 205, 206, 207, 210, 211.
**BACKLOG:** 104, 154, 155.
**Оценка:** ✅ (в основном warnings).

### Блок 16 — Network
**BUG:** 212.
**Оценка:** ✅ (favicon + шрифты).

### Блок 17 — Responsive
**BUG:** 228, 229, 230, 231, 232, 233, 234.
**Оценка:** 🔴 ~30% (только KPI).

### Блок B — RBAC
**BUG:** 213, 214, 215, 216, 217, 218, 219, 220, 222, 223, 224, 225, 227.
**Оценка:** 🔴 Frontend RBAC сломан.

### Блок C — SIEM
**BUG:** 235.
**Оценка:** ✅ 404 (ожидаемо, BACKLOG-072).

---

## 📁 Пакет ТЗ

| № | Файл | Содержание | Приоритет | Длительность |
|---|------|-----------|-----------|--------------|
| 1 | `prompts/tz/day_53_4a_add3_hotfix.md` | BUG-201/202/214/223/181/168/142/148 | 🔴🔴 | 3–5 дней |
| 2 | `prompts/tz/day_53_4a_add4_fonts.md` | BUG-212 | 🔴 | 0.5 дня |
| 3 | `prompts/tz/day_53_4b_webui_pages_1.md` | 53.4b: login/dashboard/findings + RBAC + Responsive | 🔴 | 3–5 дней |
| 4 | `prompts/tz/day_53_4cde_webui_pages_2_5.md` | 53.4c/d/e | 🟡 | 10–15 дней |

**Общая оценка:** ~4 недели до полного закрытия.

---

## ✅ Что **работает** (важно зафиксировать)

- ✅ **Backend** — 96% (тесты зелёные).
- ✅ **Reveal** — работает, аудит пишется (BUG-095).
- ✅ **Маскирование** — email: `us***@ex***.com` (BUG-044).
- ✅ **`user_roles` M:N** — работает.
- ✅ **Backend self-protection** — `Cannot delete yourself` / `Cannot disable yourself`.
- ✅ **KPI-карточки** — адаптивны.
- ✅ **Chart.js** — работает (не адаптивен).
- ✅ **Dovetail-тема** — цвета, сетка, 8px, иконки.

---

## ❌ Что **сломано**

### Backend (критично)
- Смена пароля — **не работает**.
- Аудит — **пишется при откате**.
- `/api/audit` — **открыт** для viewer/scanner.
- `GET /api/audit/{id}` — **не существует**.
- Аудит ролей — **отсутствует**.
- Системные роли — **редактируются**.

### Frontend
- RBAC — **не работает** (sidebar, router, кнопки).
- Responsive — **30%** (sidebar, гамбургер, модалки, таблицы, Chart.js).
- Шрифты — **fallback** (unicode-range).
- Локализация — **частичная**.
- Ошибки — `[object Object]`, английский, alert-danger.
- Формы — **сломаны** (`/users`, `/roles`).

### Scanner
- `.env` — **не читается**.

---

## 🔮 Что дальше

### Немедленно
1. **53.4a-доп3** (hotfix backend-critical) — **отправить разработчику**.
2. **53.4a-доп4** (fonts) — **быстро**, **параллельно**.

### Краткосрочно
3. **53.4b** (WebUI этап 2: login/dashboard/findings + RBAC + Responsive).
4. **53.4c/d/e** (остальные страницы + полировка + документация).

### После 53.4e
5. **55** — GitHub-пакет.
6. **56** — BUG-117 hotfix (Manager-маскирование).
7. **57** — **релиз v3.0.0**.

### v3.1.0+
- Formal Grammars (CFG/AST).
- Rust Scanner.
- DLP/ICAP.
- SIEM.

---

## 📚 Связанные документы

- **`STATE.md`** — текущее состояние (v3.13.38).
- **`ROADMAP.md`** — план v3.0.0/v3.1.0/v3.2.0/v4.0.0.
- **`ARCHITECTURE.md`** — архитектура, API, модели.
- **`CHANGELOG.md`** — история версий.
- **`STATE_TEST_SESSION.md`** — протокол тестирования.
- **`DESIGN.md`** — Dovetail-референс (в v3.14.1 перенесён в `docs/DESIGN.md`).
- **`prompts/tz/*.md`** — 4 ТЗ.

---

## 🎓 Уроки мастер-сессии

1. **Backend защищает — frontend нет.** Классическая проблема SPA: RBAC на backend ✅, но **UI не фильтрует** разделы/кнопки → UX-провал + security-риск (info leak).
2. **`[object Object]`** — симптом **неразобранных ошибок FastAPI 422**. Один `formatApiError()` — **закроет 10+ BUG**.
3. **`unicode-range`** — **невидимый** баг. **Все** видят fallback, но **никто не замечает**, потому что **система выглядит нормально**. Тест с `Arial vs InterTest` — **эталонная диагностика**.
4. **Аудит без `commit`** — **тихая** ошибка. **Хуже**, чем отсутствие аудита: логи **говорят**, что действие **было** — а его **не было**.
5. **Гамбургер — не работает.** Классика: **кнопка есть**, **обработчик отсутствует**.
6. **Responsive — это не "мелочь".** ~30% багов — **на mobile**. В Dovetail (dark-only) — **обязательно**.
7. **53.4a был объявлен «закрытым», но шрифты не работали.** **Урок:** «файлы подключены» ≠ «шрифты применяются».
8. **E2E-артефакты накапливаются.** 106 сканеров + `e2e_*` users + `test_event*` в audit. Нужна **очистка** в 53.4e.

---

**Конец `README_MASTER_SESSION.md`**
**Дата:** 12.10.2026
**Версия:** v3.13.38
**Следующий шаг:** 53.4a-доп3 (hotfix)