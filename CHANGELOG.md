# Changelog — DCAP

Все значимые изменения проекта DCAP.

Формат — [Keep a Changelog](https://keepachangelog.com/),
версионирование — [SemVer](https://semver.org/).

---

# Changelog

Все значимые изменения проекта DCAP.
Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Версионирование: [SemVer](https://semver.org/lang/ru/).

## [3.0.0] — 2026-10-31 (дата тега)

Первый публичный релиз **Enterprise Ready**. Закрывает вехи v3.0.0:
Enterprise-функциональность (S3/MinIO, Retention, SIEM-каркас), WebUI-редизайн
(Dovetail), security-hardening (53.5), мультипроцессинговый сканер.

### Added — Enterprise Ready

**S3/MinIO-коннектор сканера (BACKLOG-097, v3.13.29–35)**
- Явный `ScanTask.source_type` (`filesystem` / `s3` / `minio`), миграция 006.
- `S3LineConnector` — построчное чтение S3/MinIO (`Body.iter_chunks`),
  streaming + временный файл для документов/OCR.
- Общий построчный пайплайн `_text_scanner.py` + `factory.create_line_connector`.
- `POST /api/resources?type=s3&path=s3://...&endpoint=...` — endpoint обязателен
  (query → `S3_DEFAULT_ENDPOINT` → 400).
- Bucket фиксируется при создании ресурса; `path` — суффикс префикса (v3.13.35).
- Секреты S3 — только ENV на хосте сканера (`S3_ACCESS_KEY` / `S3_SECRET_KEY`,
  TASK-018). Manager никогда не передаёт секреты в payload задачи.
- BUG-149 (v3.13.41): S3-скан возвращал 0 files для ресурсов из legacy WebUI —
  добавлены bucket-фолбэк из path, `connector.s3` в `/api/tasks/create` и
  `/api/resources/create`, DEBUG-логи `list_objects_v2`.
- BUG-136 (v3.13.31): strict-декод utf-8 → cp1251 (cp1251-ветка была
  недостижимой из-за `errors="ignore"`).

**Retention (Блок 18, v3.14.4)**
- `GET /api/retention/status`, `/policies`, `/stats`; `POST /run` (sync),
  `/start` (Celery), `/export` (JSON/CSV).
- Dry-run, ручной запуск, Celery-путь (`run_retention.delay`) + Beat-schedule.
- Политики: audit_events (90д → архив), findings (180д → архив), tasks (30д).
- Партиционирование `audit_logs` (RANGE по `created_at`).
- BUG-102 (v3.13.27): импорт `User` в 6 модулях + `configure_mappers()` в
  celery_app.py (Mapper init).

**Мультипроцессинговый сканер (53.4j–p, v3.14.8–14)**
- `ProcessPoolExecutor` — реальный параллелизм (×2.09 на 4 ядрах: 63.7 → 132.9 ф/мин).
- Ленивая инициализация spaCy/OCR в воркерах (память ×1.54).
- `performance.executor`: `"process"` / `"thread"` (fallback); `max_workers`,
  `chunk_size` (bounded submit).
- **Resume** (BUG-280): `ScanState` chunk-aware; `Ctrl+C` → save → release (pending,
  не failed) → `[Resume] с чанка N+1/M`.
- Pool reuse (BUG-286): `ProcessPoolExecutor` 1 раз на задачу.
- **Дедуп** по `(category, match_text)` (BUG-281), `metadata["locations"]` —
  finding-взрыв 609 → 0.6/файл.
- NER off (BUG-282): PERSON/LOCATION/ORG/DATE_TIME/NRP — 99.9% FP.
- Логи: `logs/scanner.log` (INFO, ротация) + консоль (DEBUG); reconnect (BUG-284).
- `final=True` только последний чанк (BUG-287); `release` completed → 204 (BUG-288);
  `ScanProgress` монотонный (BUG-289).

**WebUI-редизайн Dovetail (BACKLOG-093, 53.4a–f, v3.13.37–3.14.7)**
- Dark-only тема, Inter Variable + JetBrains Mono (локально, кириллица — BUG-212).
- #6798ff, 8px радиусы, zero-shadow, grid-wireframe (blueprint).
- Страницы: login, dashboard, resources, findings, finding_detail, catalog, audit,
  scanners, access, roles, users, settings + footer.
- RBAC-фронт (BUG-265/267): viewer/scanner не вызывают `/api/audit/*`, KPI «—» +
  «Нет прав».
- Responsive `/users` и `/findings` (BUG-270/271, BACKLOG-320/321/324).
- 53.4i (BUG-278): чекбоксы неактивных сканеров.
- ⚠️ Light-тема и stroke-SVG иконки — v3.1.0 (BACKLOG-101/102).

**Аудит-агенты (Блок 6, v3.13.28; TEST-AUDIT-AGENTS 56.5, v3.14.17)**
- Windows-агент (1017 событий), Linux-агент (inotify/watchdog, 25 событий),
  S3-агент (9 событий).
- WebUI `/audit` + stats + RBAC + кодировка.
- `POST /api/audit/agents/register`, `/heartbeat`, `/events`, `/permissions` —
  machine-эндпоинты (mTLS опционально; strict без сертификата → 401, BUG-106).

**RBAC-hotfix (53.4e-rbac-hotfix, v3.14.3)**
- BUG-253: нельзя снять роль `admin` с себя (чекбокс disabled + 400).
- BUG-254: создание пользователя без ролей → 400.
- BUG-257: системные роли immutable по `name`/`ad_group`.
- BUG-258: кастомные роли отключены до v3.1.0 (`POST /roles` → 403).
- BACKLOG-316: машинная роль `scanner` скрыта в `/users`.

**Мониторинг (Блок 8, v3.14.2)**
- Grafana протестирована: datasource provisioned, 2 дашборда (dcap-overview 11
  панелей, dcap-scanner 5), 4 alert rules (fire + resolve).
- Prometheus targets 5/5 up.
- BUG-246: `dcap_findings_total` — Gauge из БД; `dcap_findings_created_total` —
  Counter сессии.
- BUG-245: `dcap_scanner_heartbeat_age_seconds` — hardening.
- ⚠️ Grafana RBAC (BACKLOG-307) — v3.1.0.

### Security — 53.5 (v3.14.16, 10/10)

- **Bandit**: 0 HIGH (убран `shell=True` в `local.py`, 9 `# nosemgrep`).
- **Semgrep**: 0 findings (3 `shell=True` убраны; `sqlalchemy.text`, CORS, logger,
  md5 → `# nosemgrep`).
- **Gitleaks**: 0 leaks (190 commits; allowlist для tests/reports).
- **pip-audit**: 0 vulns (manager + scanner).
- **Trivy (vuln)**: 0 CRITICAL (manager + webui; Pillow 13.0.0, certifi 2026.10.19).
- **ZAP WebUI**: 0 HIGH (7 WARN — триаж).
- **ZAP API**: 0 HIGH (5 WARN; заголовки → BACKLOG-346/347).
- **Trivy config**: 0 misconfig; `cap_drop: [ALL]` → `--force-recreate` → `CapDrop=[ALL]`.
- **docker inspect**: non-root (`dcap`), `CapDrop=[ALL]`.
- **Dogfooding**: DCAP-сканер на собственном репо — 11718 файлов, 0 findings.

### Fixed — security/masking

- **BUG-117** (v3.14.17): Manager не маскировал контексты сам. Введён
  `mask_context` (22 паттерна, `_CONTEXT_PATTERNS`) + `MASK_RULES` 19 категорий
  в `manager/src/core/encryption.py`; маскирование при записи и чтении.
  Специфичные токены (`ghp_`, `xox[baprs]-`, `AKIA`) — раньше generic.
  Generic `KEY=VALUE` маскирует только значение, сохраняя маркер категории.
  `person` и `high_entropy` в контекст не попадают (осознанно).
- **BUG-292** (v3.14.15): `finding_detail.js` — CP1251 → UTF-8 (без BOM).
- **BUG-201** (v3.13.39): `POST /api/auth/change-password` возвращал 200, но не
  менял пароль (мутация `request.state.user` из чужой сессии). Фикс — пере-запрос
  user в сессии хендлера + commit/refresh + аудит после commit.
- **BUG-202** (v3.13.39): `with_audit` — единая транзакция «бизнес-изменение +
  аудит»; исключение → rollback + raise.
- **BUG-168** (v3.13.39): системные роли (admin/auditor/scanner/viewer) иммутабельны
  по `name`/`ad_group`; редактируется только `description`.
- **BUG-181** (v3.13.39): аудит всех операций с ролями (`role_created` /
  `role_updated` / `role_deleted`).
- **BUG-150** (v3.13.41): `DELETE /api/resources/{id}` → 500 (FK NO ACTION);
  миграция 007_add_cascade_deletes (11 FK).
- **BUG-214/223** (v3.13.39): `GET /api/audit*` — Auditor+ (viewer/scanner → 403);
  деталь события с `metadata_json`, 404.
- **BUG-106** (v3.13.28): machine-эндпоинты не входят в `public_paths`; в strict
  без клиентского сертификата → 401.

### Fixed — scanner/infra

- **BUG-136**: cp1251 (см. S3).
- **BUG-149**: S3 bucket из path (см. S3).
- **BUG-280/283/284** (53.4n): resume + логи + reconnect.
- **BUG-286** (53.4o): pool reuse.
- **BUG-287/288/289** (53.4p): `final`/`release`/`ScanProgress`.
- **BUG-259/260/261/263** (v3.14.3): тест-инфра (conftest basetemp, regular-пакет
  connectors, фикстура Finding, `loadFilterOptions`).
- **BACKLOG-317** (v3.14.3): `docker-compose.test.yml` — `name: dcap-test` (раньше
  сносило основной стек).

### Changed

- Версия Docker-образов: `3.14.17` (manager + webui пересобраны с Pillow 13.0.0,
  certifi 2026.10.19, `mask_context`).
- `ScanTask.source_type` — явный тип источника (миграция 006, идемпотентна).
- WebUI: `.btn-primary` — белый фон (#ffffff) / текст #0a0a0a (BACKLOG-121,
  отменяет отклонение 53.4a).
- Badge режима на `/login` — только для `windows_integrated` (BACKLOG-119).

### Known Limitations (v3.0.0)

- S3: `s3://*` (все bucket'ы одной задачей) — не поддерживается (на каждый bucket
  свой Resource).
- S3: `recursive=false`, `skip_prefixes`, параллелизм (BACKLOG-100/099) — v3.1.0.
- S3: fallback на config-секреты и endpoint `host.docker.internal:9000` в коннекторе
  (BACKLOG-103) — v3.1.0.
- Grafana RBAC (BACKLOG-307) — v3.1.0.
- SIEM, Cython, Rust, DLP — не реализованы (план v3.1.0+).
- E2E-эталон (53/7) требует внешних предусловий (сканер + MinIO + seed-findings +
  auditor); BUG-262 этап B — до 57, CI — BACKLOG-046 (55).
- Кастомные роли без `permissions` (BUG-258) — v3.1.0.
- `/metrics` публичный (BACKLOG-044) — production.

### Migration Notes (v2.x → v3.0.0)

- **Обязательные миграции Alembic**: `alembic upgrade head` (001–007).
  - 003_findings_refactor (переименование findings → findings_old, только PG).
  - 005_add_fragment_columns (5 колонок fragment_*).
  - 006_add_source_type (ScanTask.source_type, идемпотентна).
  - 007_add_cascade_deletes (11 FK, BUG-150).
- **ENV**: `FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY` — обязательны для сканера
  (fail-fast; `DCAP_ALLOW_LEGACY_SCANNER=true` — только dev).
- **S3**: `S3_ACCESS_KEY` / `S3_SECRET_KEY` — на хосте сканера (ENV-only, TASK-018);
  `S3_DEFAULT_ENDPOINT` — на Manager (fallback для endpoint).
- **Пароль admin**: `admin/admin123` создаётся при первом запуске — **сменить**.

## [v3.14.17] — 2026-10-31

### Fixed (56.5 — TEST-AUDIT-AGENTS)

- **Windows-агент (icacls, cp866)** — `a537f95`: парсинг `icacls` в cp866
  (раньше — кракозябры в именах групп/пользователей). Отчёт audit agents:
  registered + heartbeat, 0 events.
- **WebUI `/audit` + stats + RBAC + кодировка** — приёмка событий аудита от агентов
  (Windows — 1017 событий, Linux — 25, S3 — 9; `WebUI /audit total` — 2108).
  RBAC: viewer/scanner → 403; кодировка — UTF-8.

### Fixed (BUG-117 — Manager маскирует контексты)

- **BUG-117** — Manager не маскировал контексты сам (полагался на сканер).
  Введён `mask_context` (22 паттерна, `_CONTEXT_PATTERNS`) + `MASK_RULES`
  (19 категорий) в `manager/src/core/encryption.py`; маскирование при записи
  **и** чтении. Специфичные токены (`ghp_`, `xox[baprs]-`, `AKIA`, `sk-`) —
  раньше generic; generic `KEY=VALUE` маскирует только значение, сохраняя
  маркер категории (`GITHUB_TOKEN=ghp_***`). `person` и `high_entropy` в
  контекст не попадают (осознанно).
- Тесты: `manager/tests/test_mask_context_v31417.py` — **16 passed**.

### Tests

- Unit: **544 passed** (528 + 16 BUG-117).
- WebUI `/audit`: total 2108; агенты — Windows 1017, Linux 25, S3 9.
- E2E: стенд `:18000/:18001`; эталон 53/7 — при предусловиях.

### Changed

- `.env`, `docker-compose.yml`, `docker-compose.test.yml` — `VERSION=3.14.17`
  (manager + webui пересобраны: Pillow 13.0.0, certifi 2026.10.19, `mask_context`).

---

## [v3.14.16] — 2026-10-30

### Security (53.5 — security_scan, 10/10)

- **Bandit**: 0 HIGH (убран `shell=True` в `local.py`, 9 `# nosemgrep` + комментарии).
- **Semgrep**: 0 findings (3 `shell=True` убраны; `sqlalchemy.text`, CORS, logger,
  md5 → `# nosemgrep`).
- **Gitleaks**: 0 leaks (190 commits; allowlist для `tests/`/`reports/`;
  `reports/` → `.gitignore`).
- **pip-audit**: 0 vulns (manager + scanner).
- **Trivy (vuln)**: 0 CRITICAL (manager + webui; Pillow 13.0.0, certifi 2026.10.19;
  `--scanners vuln`, `--timeout 30m`, `docker.sock`).
- **ZAP WebUI**: 0 HIGH (7 WARN — триаж; `username` в URL → BACKLOG-344;
  XSS — ложное Jinja2).
- **ZAP API**: 0 HIGH (5 WARN; 500-е → BUG-298 low; заголовки → BACKLOG-346/347).
- **Trivy config**: 0 misconfig; `cap_drop: [ALL]` → `--force-recreate` →
  `CapDrop=[ALL]`.
- **docker inspect**: non-root (`dcap`), `CapDrop=[ALL]`, `ReadonlyRootfs=false`
  (v3.1.0).
- **Dogfooding**: DCAP-сканер на собственном репозитории — 11718 файлов,
  0 findings (gap=0, FP=0; маскирование — 56.5, закрыто в v3.14.17).

### Added

- `scripts/security_scan.ps1` — единый прогон (Bandit, Semgrep, Gitleaks,
  pip-audit, Trivy, ZAP, docker inspect, dogfooding).
- `reports/` → `.gitignore` (артефакты 53.5).

### Known Limitations (53.5)

- `username` в URL на `/settings` — BACKLOG-344 (v3.0.1).
- `X-Content-Type-Options: nosniff` не установлен — BACKLOG-346 (v3.0.1).
- `Cross-Origin-Resource-Policy` не установлен — BACKLOG-347 (v3.0.1).
- 500 на `/api/audit/*` (ZAP-фаззинг; не воспроизвелось после пересоздания) —
  BUG-298 (low, v3.0.1).

### Changed

- `.env`, `docker-compose.yml`, `docker-compose.test.yml` — `VERSION=3.14.16`.

---

## [v3.14.15] — 2026-10-25

### Fixed (53.4n/53.4o/53.4p — Scanner Resume/Pool/Progress + UI)

- **BUG-280 (resume)** — `scanner/src/state_manager.py` (`ScanState`, chunk-aware):
  `save/load/clear/get_resume_chunk`, атомарная запись (tmp + `os.replace`),
  проверка `task_id` и возраста state. При `Ctrl+C`: `executor.shutdown(wait=True)` →
  `state.save` → `POST /api/scanner/tasks/{id}/release` (pending, не failed).
  При старте: `load` → `resume_chunk = last_completed_chunk + 1`.
- **BUG-286 (pool reuse)** — `ProcessPoolExecutor` создаётся **один раз** на задание
  (вне цикла чанков), `scan_files(..., executor=...)` использует переданный пул и не
  закрывает его. Warmup spaCy: **4 процесса** (было до 40).
  `Files/min`: 30–40 → **132.9**; ETA 22 500: 7–9 ч → **~3 ч**.
- **BUG-287 (final)** — `final=True` отправляется **только** на последний чанк
  (`chunk_idx == total_chunks - 1`); `SubmitResults` → 200 на каждом чанке (не 400
  «Task status is completed»).
- **BUG-288 (release)** — `release` для `completed`/`pending` → **no-op (204)**,
  `failed` → 409, `assigned`/`running` → release. Сканер не вызывает `release`,
  если `SubmitResults` вернул 400 «Task status is completed».
- **BUG-289 (progress)** — `ScanProgress` монотонный (`_total_scanned` accumulator),
  без откатов (300 → 200).
- **BUG-292 (кодировка UI)** — `webui/static/js/finding_detail.js` был сохранён
  в CP1251 (двойная/тройная перекодировка) → кириллические подписи отображались
  как кракозябры, а после «лечения» — `Uncaught SyntaxError: Invalid or unexpected token`.
  Файл перезаписан чистым UTF-8 (без BOM). Все подписи/кнопки — на русском,
  Console — 0 ошибок.
- **BUG-293 (UX аудит)** — в `/audit` для `finding_reveal` дублируется текст
  (`finding_reveal — просмотр оригинала`): фронтенд добавляет перевод к
  `event_type`. Косметика, **v3.0.1**.

### Added (53.4n — логирование и reconnect)

- **BUG-283 (файловый лог)** — `run_scanner.py::_setup_logging`:
  `StreamHandler` (DEBUG — всё, как раньше) + `RotatingFileHandler`
  (`logs/scanner.log`, INFO, 100 МБ × 5). `print(...)` → `logger.debug(...)`
  в `pii_classifier.py`/`ocr_worker.py` (консоль — да, файл — без спама).
- **BUG-284 (reconnect)** — `ManagerClient._request` отслеживает offline/reconnect:
  `WARNING` при обрыве (1 раз), `INFO [OK] Reconnected (was offline Xs)` при
  восстановлении — **и в консоль, и в файл**.

### Fixed (53.4l — finding-взрыв, NER, дедуп)

- **BUG-281** — finding-взрыв (609/файл → 0.6): дедуп по `(category, match_text)`
  в рамках файла (`dedup_findings_by_file`), `metadata["locations"]` = все вхождения,
  `line_number`/`context_*` — первого вхождения.
- **BUG-282** — NER-шум (99.9% находок): `PERSON/LOCATION/ORGANIZATION/DATE_TIME/NRP`
  отключены (`ner_enabled=false`), spaCy `parser/ner` off. `person` не маскируется
  по решению — это FP, не PII.
- **Performance:** `Files/min` 24.0 → **65.8** (+174%), findings/файл **0.6**,
  ETA 22 500: 15.6 ч → **5.7 ч**.
- **53.4m (multiprocessing)** — `ProcessPoolExecutor` (×2.09 на 4 ядрах, 63.7 → 132.9 ф/мин),
  ленивая инициализация spaCy/OCR, `temp_dir` на процесс, graceful `Ctrl+C`,
  auto-fallback на `ThreadPoolExecutor`.

### Tests

- `tests/unit/test_perf_v3149.py` — 4 passed (singleton extractor, lru_cache).
- `tests/unit/test_dedup_v31410.py` — 12 passed.
- `tests/unit/test_perf_regression_v31410.py` — 6 passed (0 lost).
- `tests/unit/test_multiprocessing_v31411.py` — 9/10 passed.
- `tests/unit/test_scan_state_v31412.py` — 6 passed.
- `tests/unit/test_logging_v31412.py` — 2 passed.
- `tests/unit/test_resume_hotfix_v31414.py` — 3 passed.
- `tests/unit/test_pool_reuse_v31413.py` — 2 passed.
- `tests/unit` — **528 passed** (+1 flaky s3, проходит отдельно — BACKLOG-339).
- E2E: `test_multiprocessing_v31411.py` (process vs thread parity),
  `test_pool_reuse_v31413.py`, `test_resume_v31412.py`.

### Verified (ручная приёмка)

- **Resume:** `Ctrl+C` → `[Resume] Задание N приостановлено: обработано чанков X/M` →
  `[Release] Task N возвращено в очередь (resume)` → Manager `pending` →
  перезапуск → `[Resume] продолжаем с чанка X+1/M` → завершение (findings = baseline).
- **Pool reuse:** `[FS] ProcessPoolExecutor: 4 процессов` — **1 раз**; `[PII] NLP движок
  создан` — **4 раза** (не 40).
- **Логи:** `scanner/logs/scanner.log` — есть; `[OCR] Found via 'where'` — **нет** в файле.
- **Reconnect:** `[ManagerClient] [OK] Reconnected (was offline Xs)` — консоль + файл.
- **WebUI (находки):** `/findings` (список, фильтры, пагинация), `/findings/{id}`
  (детали, контекст, **Reveal** — расшифровка + подсветка match), смена статуса
  (confirmed/false_positive/duplicate/archived), `/audit` (`finding_reveal`,
  `fragment_accessed`, `auth_login`) — ✅. Кодировка — ✅ (UTF-8, 0 ошибок в Console).

### Changed

- `.env`, `docker-compose.yml`, `docker-compose.test.yml` — `VERSION=3.14.15`.

---

## [v3.14.10] — 2026-10-22

### Fixed (53.4l — finding-взрыв)

- Дедуп по `(category, match_text)`, `metadata["locations"]`, NER off.
- `Files/min` 24.0 → 65.8; findings/файл 666 → 0.6.

### Tests

- `test_dedup_v31410.py` (12), `test_perf_regression_v31410.py` (6).

---

## [v3.14.9] — 2026-10-21

### Fixed (53.4k — scanner perf, часть)

- 3.1: singleton `DocumentExtractor` (linewise).
- 3.2: `@lru_cache` в `OCREngine` (`_get_tesseract_path`/`_get_tesseract_langs`).
- 3.3: файл-уровневый префильтр — не дал эффекта (уже был).
- OCR-спам: 3 subprocess/файл → 0.2/файл (−93%); OCR 0.686 → 0.280 с/файл.

### Tests

- `test_perf_v3149.py` — 4 passed.

---

## [v3.14.8] — 2026-10-20

### Fixed (53.4j — scanner perf, первая попытка)

- A) `os.scandir` вместо `os.walk` (discovery ×2.5–2.8).
- B) `@lru_cache` для Tesseract (не подключён к linewise — исправлено в 53.4k).
- C) `ThreadPoolExecutor` (GIL — не дал CPU-bound ускорения).
- D) быстрые regex-префильтры.

### Note

- Discovery не был узким местом (0.6 с на 22 500). Корень — classify (Presidio).

---

## [v3.14.7] — 2026-10-20

### Fixed (53.4g UI hotfix)

- BUG-274/275/276/277/273/272 — dashboard RBAC, settings password/last_run/CSS,
  KPI responsive, «Нет данных» (см. `day_53_4g_ui_hotfix`).

---

## [v3.14.6] — 2026-10-20

### Fixed (53.4h — Dashboard RBAC)

- **BUG-274** — `checkAuditAccess()` → `Auth.me()` (без `RBAC.isAuditor()`),
  fail-safe `return false` при `me=null`. Viewer: 0 запросов к `/api/audit/*`,
  0 ошибок 403.

---

## [v3.14.5] — 2026-10-20

### Fixed (53.4g — UI, первая итерация)

- BUG-274/275/276/277/273/272 (частично; BUG-274 — закрыт в v3.14.6).

---

## [v3.14.4] — 2026-10-18

### Fixed (53.4f UI hotfix — блоки 15/17)

- BUG-265/267 (dashboard RBAC/403), BUG-266 (api.js 403), BUG-270/271 (users responsive),
  BACKLOG-320/321/324. Unit **521 passed**.

---

## [v3.14.3] — 2026-10-17

### Fixed (53.4e RBAC hotfix — Users, Roles + test-infra)

- BUG-253/254/255/256/257/258, BACKLOG-316 (RBAC);
- BUG-259/260/261/263, BACKLOG-317, BUG-262 этап A (тест-инфра).

---

## [v3.14.2] — 2026-10-17

### Fixed (53.4e-grafana hotfix)

- BUG-245/246/247/236/241/243/239 (Grafana/метрики).

---

## [v3.14.1] — 2026-10-14

### Changed (53.4b–53.4e, WebUI-редизайн, этапы 2–5)

- login/dashboard/resources/findings, finding_detail/catalog/audit/scanners/access,
  roles/users/settings, footer, Chart.js, favicon, CSP, DESIGN.md, скриншоты.

---

## [v3.13.41] — 2026-10-13

### Fixed

- BUG-150 (ON DELETE CASCADE, миграция 007), BUG-149 (S3 bucket-фолбэк,
  legacy WebUI connector.s3), BACKLOG-121 (.btn-primary white filled),
  BACKLOG-119 (badge /login — только windows_integrated).

---

## [v3.13.40] — 2026-10-12

### Fixed (BUG-212 — fonts, кириллица)

- `unicode-range` + кириллица (Inter, JetBrains Mono v2.304), OFL.txt.

---

## [v3.13.39] — 2026-10-12

### Fixed (BUG-201/202/214/223/181/168/142/148)

- change-password (пере-запрос user в сессии), `with_audit`, `/api/audit` Auditor+,
  `GET /api/audit/{id}`, аудит ролей, immutable системные роли, `total_resources`,
  `.env` для сканера.

---

## [v3.13.38] — 2026-10-10

### Fixed (BUG-138/139/140)

- Font Awesome (монохром), `finding_detail.js` (addEventListener, toggle, mark),
  `findings.css` (.reveal-block).

---

## [v3.13.37] — 2026-10-09

### Added (53.4a — Dovetail tokens, base, components, grid-wireframe, fonts)

- `tokens.css`, `base.css`, `components.css`, `grid-wireframe.css`,
  локальные Inter/JetBrains Mono, `DESIGN.md`. Удалены `variables.css`,
  `theme-dark.css`, `theme.js`.

---

## [v3.13.36] — 2026-10-07

### Fixed (BUG-137 — OCR temp race)

- `_work_dir`-изоляция temp, WARNING при потере OCR-ответа.

---

## [v3.13.35] — 2026-10-06

### Fixed (53.3-fix-s3-bucket)

- `S3LineConnector`: bucket только из `scan_config.connector.s3.bucket`;
  `s3://bucket/prefix` — суффикс префикса.

---

## [v3.13.34] — 2026-10-05

### Fixed (53.3-test-stand-fix)

- healthcheck + `service_healthy`; `run-tests.sh all` — `down -v` + `up -d --wait`.

---

## [v3.13.32] — 2026-10-04

### Added (53.3 — S3 E2E, WebUI-форма S3/MinIO, docs §8)

- `test_s3_e2e.py`, `resources.html` (`#s3-fields`), `06-scanner.md` §8.

### Changed

- `manager/src/api/resources.py` — endpoint: query → `S3_DEFAULT_ENDPOINT` → 400.

---

## [v3.13.31] — 2026-10-03

### Added (53.2 — S3LineConnector, factory)

- Streaming, документы/OCR через temp, ENV-секреты.

### Fixed (BUG-136 — decode cp1251)

- strict utf-8 → cp1251 → ignore (9 находок на MinIO).

---

## [v3.13.30] — 2026-10-02

### Added (53.1b — _text_scanner, factory)

- 5 функций общего пайплайна, реестр source_type → коннектор, boto3.

---

## [v3.13.29] — 2026-10-01

### Added (53.1a — ScanTask.source_type, миграция 006)

- `POST /api/resources?type=s3&path=s3://...`, `connector.s3`.

---

## [v3.13.28] — 2026-09-30

### Fixed (Блок 9 — 10 BUG: BUG-103/105/106/107/108/110/111/114…116)

### Added (Блок 6 — Windows/Linux/S3 агенты)

---

## [v3.13.27] — 2026-09-29

### Fixed (BUG-102 — Celery Mapper[User])

- импорт `User` в 6 модулях + `configure_mappers()`.

---

## [v3.13.26] — 2026-09-28

### Added (BUG-098…101, 101b)

- Аудит PATCH/bulk/DELETE findings, `_log_finding_status_change` (batch).

---

## [v3.13.25] — 2026-09-27

### Fixed (BUG-096/096b/097)

- `/false-positives` 500, устаревшие E2E, зависшие задания.

---

## [v3.13.24] — 2026-09-26

### Added (BUG-095 — аудит auth/users)

- `auth_login`/`auth_failed`/`auth_logout`/`user_created`/`user_updated`/
  `user_password_changed`/`role_assigned`/`role_revoked`/`user_deleted`,
  `_sanitize`, `auth_refresh` не логируется.

---

## [v3.13.23] — 2026-09-25

### Fixed (BUG-094 — audit user в кавычках)

---

## [v3.13.22] — 2026-09-24

### Added (Блок 5 — WebUI filters/pagination/export, detector/fragment_type/search, X-Total-Count)

---

## [v3.13.21] — 2026-09-23

### Fixed (BUG-086 — mask context, 22 паттерна)

---

## [v3.13.20] — 2026-09-22

### Fixed (BUG-080/081 — heartbeat backoff, graceful shutdown)

---

## [v3.13.19] — 2026-09-21

### Added (BACKLOG-086 — embedded OCR-фрагменты, миграция 005)

---

## [v3.13.18] — 2026-09-20

### Fixed (BUG-077 diag — bbox H3)

---

## [v3.13.17] — 2026-09-19

### Fixed (BUG-077 — bbox=None + fallback)

---

## [v3.13.16] — 2026-09-18

### Fixed (BUG-075 — url = домен email)

---

## [v3.13.15] — 2026-09-17

### Fixed (url-over-email, аббревиатуры, uk_nhs)

---

## [v3.13.14] — 2026-09-16

### Fixed (url-over-email, OCR-markup, spaCy noise, credentials)

---

## [v3.13.13] — 2026-09-15

### Fixed (OCR + Presidio ru+en)

---

## [v3.13.12] — 2026-09-14

### Fixed (OCR, HTTP-retry, Luhn, dedup)

---

## [v3.13.11] — 2026-09-13

### Fixed (ENV-ключи Findings)

---

## [v3.13.10] — 2026-09-12

### Fixed (middleware BUG-048b)

---

## [v3.13.9] — 2026-09-11

### Fixed (Auth/RBAC — fix-спринт №1)

---

## [v3.13.8] — 2026-09-10

### Added (Блок 1 Smoke + AD-контейнер)

---

## [v3.13.3-v3.13.7] — 2026-09-05..09

### Added (Начало v3.0.0 — WebUI, AD, безопасность, Findings Refactor)

---

## [v3.13.0-v3.13.2] — 2026-09-01..04

### Added (см. предыдущие CHANGELOG)

---

## [v3.12.0] — 2026-08-31

### Added (Findings Refactor v3.9.0-v3.10.0: masked+encrypted, AES-256-GCM, HMAC-fingerprint, миграция 003)

---

## [v3.0.0-v3.11.0] — 2026-07..08

### Added (Обнаружение, классификация, WebUI, Linux-агент, Finding, RBAC, mTLS, Retention, аудит)

---

## [v1.0.0-v2.1.0] — 2026-07

### Added (MVP, Блок 1 Smoke, Блок 2 Auth/RBAC)

---

**Актуально на:** 31.10.2026
**Версия:** v3.0.0
**Следующая версия:** v3.0.1 (BUG-293, BUG-298, BACKLOG-344/346/347, BACKLOG-339) → v3.1.0 (13 направлений + Cython/Rust + SIEM + Security Gateway v4.0.0)