# 📓 CHANGELOG.md — История версий DCAP

> Формат — по мотивам [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
> Версионирование — SemVer.

---

## [Unreleased] — v3.0.0 (release)

**Осталось:** Блок 5 (WebUI, п.2.4), Блок 6.5 (сбор прав Windows, BUG-123/127), дотест Linux-агента (метрики с хоста, сквозной поток после restart WSL, BUG-130), BACKLOG-097 части 2–3 (53.1b/53.2/53.3 — Scanner S3), Блок 11, GitHub-пакет.
(Блок 7 — Retention — закрыт в v3.13.27. Фикс-спринт Блок 9 — закрыт в v3.13.28. Блок 6 — закрыт в v3.13.28 на 5 из 6 под-блоков. BACKLOG-097 часть 1 (Manager) — закрыта в v3.13.29.)

---

## [3.13.29] — 2026-10-03 — День 53.1a: `source_type` для S3-ресурсов (BACKLOG-097, часть 1: Manager)

### Added

- 📁 `manager/src/db/migrations/versions/006_add_source_type.py` — колонка
  `scan_tasks.source_type VARCHAR(20) NOT NULL DEFAULT 'filesystem'` + индекс
  `ix_scan_tasks_source_type`. Идемпотентная (inspect-guard, как 002/005): на
  свежих БД колонка создаётся из `Base.metadata`, `add_column` пропускается.
- 📁 `manager/src/db/models.py` — `ScanTask.source_type`
  (`String(20), default="filesystem", nullable=False, index=True`) сразу после
  `source_path`.
- `POST /api/resources` — создание **S3/MinIO-ресурсов**: query-параметры
  `type` (`s3` | `minio`), `endpoint`, `secure`, `use_path_style`, `region`;
  `path` вида `s3://bucket[/prefix]`. В `scan_config` добавляется секция
  `connector.s3` (`endpoint` / `bucket` / `prefix` / `secure` /
  `use_path_style` / `region`). Дефолтный endpoint — `S3_DEFAULT_ENDPOINT`
  или `host.docker.internal:9000` (MinIO Блока 6).
- `GET /api/scanner/tasks/pending` — в payload задачи появился **`source_type`**
  (fallback-цепочка `task.source_type → resource.type → 'filesystem'`),
  чтобы сканер выбирал коннектор явно, а не угадывал по префиксу `s3://`.

### Fixed

- 📁 `manager/src/api/resources.py` — **регрессия BUG-059:** уникальность
  ресурса проверялась только по `path`, хотя миграция
  `004_resources_path_type_unique` разрешает одинаковый `path` с разным
  `type`. Теперь проверяется пара `(path, type)`.
- Валидация типа ресурса: whitelist `filesystem` / `s3` / `minio`, всё
  остальное → `400`. Раньше произвольный `type` молча попадал в БД.
- Валидация S3-пути: схема должна быть `s3://` / `minio://`, `bucket`
  (netloc) — непустой, иначе `400`.

### Changed

- `POST /api/resources/{id}/scan` — в `ScanTask` прописывается
  `source_type` из `Resource.type` (в `lowercase`).
- Секреты S3 в `scan_config` **не пишутся** — только ENV на хосте сканера
  (`S3_ACCESS_KEY` / `S3_SECRET_KEY`), единая политика TASK-018.

### Тесты

- 📁 `tests/unit/test_s3_resource_v31329.py` — **19 unit-тестов**: создание
  filesystem/s3/minio-ресурсов, дефолты и кастомный endpoint, endpoint из ENV,
  валидация пути, уникальность `(path, type)`, `source_type` в задаче,
  `source_type` в payload пендинга (включая нормализацию регистра и
  приоритет `task.source_type` над `resource.type`).
- `tests/unit` — **378 passed** (было 359 + 19 новых), регрессий нет.
- Миграция 006 проверена на SQLite **и** PostgreSQL: `upgrade head`,
  `downgrade → upgrade` (round-trip), повторный `upgrade head` (идемпотентность).

### Not fixed (требует отдельного ТЗ)

- Сканер по-прежнему игнорирует `source_type` и создаёт `FilesystemConnector`
  жёстко — это **53.1b** (фабрика коннекторов, `_text_scanner.py`, boto3).
- WebUI-форма добавления S3-ресурса отсутствует (только API/Swagger) — **53.3**.

---

## [3.13.28] — 2026-10-03 — Фикс-спринт Блок 9: 10 багов безопасности (BUG-103/105/106/107/108/110/111/114/115/116)

### Fixed

- **BUG-115 🟡 medium — `/api/findings/count` без явного `require_auth`** — 📁 `manager/src/api/findings.py`
  Эндпоинт не декларировал `Depends(require_auth)`, полагаясь только на
  `AuthMiddleware`, закрывающий `/api/*`. Анонимный доступ фактически
  блокировался middleware (проверено на v3.13.27: 401 c
  `WWW-Authenticate: Negotiate`), поэтому это **эшелонированная защита**, а не
  открытая утечка: при любом ослаблении/пробросе middleware (например, через
  WebUI-прокси) маршрут оставался без собственной проверки.
  **Решение:** `Depends(require_auth)` на маршрут.

- **BUG-110 🔴 critical — reveal падал в 500 при недоступном ключе расшифровки** — 📁 `manager/src/api/findings.py`
  Ошибка `decrypt()` пробрасывалась наружу. **Решение:** отлов `ValueError`,
  ответ `409 Conflict` (не 500) + аудит-событие `finding_reveal_failed`.
  Успешный reveal остался `200`.

- **BUG-114 🟠 high — экспорт находок не аудировался** — 📁 `manager/src/api/findings.py`
  Событие создавалось, но без `source_host`, из-за чего источник выгрузки
  установить было невозможно; `file_path` писался одним значением вместо списка.
  **Решение:** `request` в сигнатуре, `source_host` из клиента, агрегация
  `file_path` (до 10 путей, остальные сворачиваются в `...`).

- **BUG-111 🟠 high — ошибка расшифровки роняла список находок** — 📁 `manager/src/api/findings.py`
  `_resolve_text()` не перехватывал исключение: одна «битая» находка валила
  весь `GET /api/findings`. **Решение:** `except Exception` → masked-заглушка,
  листинг остаётся доступным.

- **BUG-107 🟠 high — CRL не проверялся по TLS** — 📁 `manager/src/core/security.py`, `manager/src/auth/middleware.py`
  Сертификаты не сверялись со списком отзыва. **Решение:** `VERIFY_CRL_CHECK_LEAF`,
  проверка DER через `getpeercert(binary_form=True)` → `is_revoked()` в
  `_check_mtls()`, конвертация DER↔PEM (`_to_pem`).

- **BUG-108 🟠 high — `run_manager.py` игнорировал `CertificateManager`** — 📁 `run_manager.py`
  Собственный `ssl.SSLContext` без проверки CRL и без единой точки конфигурации.
  **Решение:** единый `get_server_ssl_context()`; strict → `CERT_REQUIRED`,
  relaxed → `CERT_OPTIONAL`; `${VAR:-default}` через `_resolve_env`.

- **BUG-106 🟡 medium — machine-эндпоинты не проходили mTLS-проверку** — 📁 `manager/src/auth/middleware.py`
  `_is_public()` помечал `/api/scanner*`, `/api/audit/agents/*`,
  `/api/audit/events` публичными, и `_check_mtls()` не вызывался в `dispatch()`.
  **Решение:** machine-prefixes исключены из public, `_check_mtls()` вызывается
  явно, CN клиента попадает в `request.state.client_cert_cn`.

- **BUG-105 🟡 medium — контейнер Manager монтировал неверный каталог PKI** — 📁 `docker-compose.yml`
  Было `./manager/certs:/app/certs`, при генерации `scripts/generate_certs.py`
  кладёт сертификаты в `./certs`. При `mtls_enabled=true` Manager не находил PKI.
  **Решение:** `./certs:/app/certs:ro`.

- **BUG-103 🟡 medium — метрики не видели 401 и раздували cardinality** — 📁 `manager/src/metrics.py`, `manager/src/main.py`
  `MetricsMiddleware` стоял **внутри** `AuthMiddleware`, поэтому отказы
  авторизации не попадали в `dcap_http_requests_total`; кроме того, метка
  `endpoint` бралась из сырого пути, и каждый `/api/findings/{id}` создавал
  новую серию. **Решение:** middleware зарегистрирован последним (outermost);
  нормализация через шаблон маршрута с regex-fallback (`{id}`, `{uuid}`, `{hash}`).

- **BUG-116 🟡 medium — повторный прогон reencrypt ломал дедупликацию** — 📁 `scripts/reencrypt_findings.py`, `webui/templates/findings.html`, `webui/static/js/findings.js`
  После ротации `hmac_key` все fingerprint'ы пересчитывались, но дубликаты
  не помечались, а UI не знал о статусе `duplicate`. **Решение:** пересчёт FP
  новым ключом с использованием `Resource.path`, флаги `--dedup` /
  `--delete-duplicates`, статус `duplicate` + фильтр и badge в WebUI.

### Added
- 📁 `tests/unit/test_security_block9_v31328.py` — 42 unit-теста на все 10 багов.
- 📁 `tests/e2e/test_security_block9_e2e_v31328.py` — 5 E2E-тестов против живого Manager.

### Fixed (вне scope Блока 9, найдено при прогоне E2E)
- **Регресс зависимости — свежая сборка падала на `ModuleNotFoundError: No module named 'psycopg'`** — 📁 `manager/src/db/session.py`, `manager/src/db/migrations/env.py`
  `requirements.txt` не закрепляет SQLAlchemy; в свежей сборке подтянулся
  SQLAlchemy 2.1.3, где голая схема `postgresql://` по умолчанию тянет
  отсутствующий psycopg v3 (проект ставит `psycopg2-binary`). Рабочий образ
  содержал SQLAlchemy 2.0.54 и поэтому маскировал проблему.
  **Решение:** `_normalize_url()` — явная схема `postgresql+psycopg2://`;
  используется в `session.py` и в Alembic `env.py`. Явные драйверы
  (`+psycopg`, `+pg8000`) не трогаются.

### Тесты
- `tests/unit`: **359 passed** (было 317 + 42 новых), регрессий нет.
- `tests/e2e`: **46 passed, 12 skipped** против живого Manager на `:18000`.
- `manager/tests`: 44 passed, 1 пре-существующее падение (`test_retention.py::test_archiver_findings`,
  `Finding.file_path` → `fragment_path`, не связано со спринтом).

### Fixed — Блок 6 (Агенты)

**BUG-120 🔴 critical — S3-агент лез в AWS S3 вместо MinIO** — 📁 `.env`, `docker-compose.yml`, `docker-compose.s3.yml`
S3-агент не отправлял события (`events_sent: 0` за 3 недели). Причина:
в `.env` задан `S3_ENDPOINT=https://s3.amazonaws.com` и пустые credentials.
**Решение:** `S3_ENDPOINT=http://host.docker.internal:9000`, MinIO развёрнут нативно.
Live: 16 событий в `audit_logs` (`event_source='s3_agent'`).

**BUG-122 🟡 medium — systemd-unit Linux-агента не portable** — 📁 `audit-agent-linux/service/*`
Unit-файл содержал `User=kirill` и `/home/kirill/dcap-system/...` — на любом другом хосте не работал.
**Решение:** плейсхолдеры `__DCAP_USER__` / `__DCAP_HOME__` / `__DCAP_PYTHON__` + `install.sh` подставляет.

### Added — Блок 6 (Агенты)

- **Windows-агент как служба** (`DCAPAuditAgent`, Automatic) — читает Security Log, отправляет 4663/4656/4660.
- **Linux-агент в WSL 2** — systemd-user (`~/.config/systemd/user/dcap-audit-agent.service`), использует `watchdog`.
- **MinIO нативный** (`E:\Dev\MinIO\bin\minio.exe`) — бакет `dcap-audit-logs`, seed-логи.
- **Setup-скрипты:** `scripts/minio-seed/access-logs/*.json`, `*.csv`.
- **Audit Policy + SACL на Windows** — `auditpol` + `FileSystemAuditRule` через `S-1-1-0`.
- **Ubuntu 22.04 в WSL 2** — установлен, systemd включён через `/etc/wsl.conf`.

### Known issues (v3.1.0)

- **BUG-123** — Windows-агент: сбор прав = 0 (2 бага: распаковка ACE, `win32security.*` → `win32file.*`).
- **BUG-135** — S3-агент: `json.loads` падает на BOM.
- **BUG-125** — Linux-агент: `MANAGER_URL` env игнорируется.
- **BUG-130** — Linux-агент: retry без backoff.
- **BUG-131** — WSL → Manager: `localhost:8000` терялся при зависании Docker (само-исправился).
- **BUG-132** — S3-агент не переустанавливает соединение после перезагрузки Docker.

---

## [3.13.27] — 2026-09-30 — День 50, BUG-102: Retention и sweep_scheduled_scans падали на Mapper[Finding] ... 'User'

### Fixed
- **BUG-102 🔴 critical — Retention и `sweep_scheduled_scans` не работали вообще** — 📁 `manager/src/workers/tasks.py` (+ `celery_app.py`, `retention/*`, `services/access_service.py`)
  Тот же класс бага, что BUG-096, но в другом модуле: `Finding.reviewer` объявлен
  строкой — `relationship("User", ...)`, а сам `User` определён в
  `manager/src/auth/models.py`. Celery-воркер этот модуль не импортировал, поэтому
  первое же обращение к `Finding` роняло инициализацию mapper'ов **всего** registry:

  ```
  When initializing mapper Mapper[Finding(findings)],
  expression 'User' failed to locate a name ('User')
  ```

  Ошибка каскадная: после первого сбоя `Mapper[Finding]` все последующие попытки
  падали с «One or more mappers failed to initialize». `run_retention` при этом
  **формально отчитывался об успехе** — все 5 шагов (архивация audit, архивация
  findings, очистка архивных таблиц, очистка tasks, экспорт) возвращали
  `{"archived": 0, "error": "When initializing mapper ..."}`, то есть цикл не делал
  ничего. `sweep_scheduled_scans` возвращал `{"error": "When initializing mapper ..."}`
  и не запускал запланированные сканирования.
  **Решение:** явный импорт `User` в точку входа воркера до первого обращения к
  моделям (Вариант A ТЗ) + fail-fast `configure_mappers()` в `celery_app.py`
  (Вариант B, страховка). Вариант C (`db/__init__.py`) отклонён: `auth.models`
  импортирует `Base` из `db.models`, при первом импорте `auth.models` возникает
  частичный цикл.
  **Проверено «заодно»:** тот же дефект был в `retention/archiver.py`,
  `retention/cleaner.py`, `retention/exporter.py` и `services/access_service.py` —
  они работали только потому, что в API-процессе раньше них импортировался
  `auth.models`; в воркере и при standalone-запуске гарантии не было.
  Live: `POST /api/retention/run?dry_run=true` → все 5 шагов без `error`;
  `POST /api/retention/start` (Celery) → задача выполнена за 0.15 с без
  mapper-ошибки; `sweep_scheduled_scans` → `{'dispatched': []}`, ошибки нет.

### Added
- **TASK-073 — тесты BUG-102** — 📁 `tests/unit/test_celery_mapper_v31327.py` (13), `tests/e2e/test_retention_e2e.py` (1)
  Ключевой приём: регрессионные проверки выполняются в **чистом подпроцессе**,
  который импортирует ровно то, что импортирует Celery-воркер. Проверка в том же
  процессе pytest не годится — `User` нужен в registry глобально и появляется там
  при первом же импорте любого API-модуля, поэтому баг маскировался бы и тест
  проходил бы на сломанном коде. На коде без фикса падают 12 из 13 тестов с
  настоящим сообщением `failed to locate a name ('User')`.
  Функциональный сценарий (`run_retention` + `sweep_scheduled_scans` на временной
  SQLite) готовит схему в родительском процессе и открывает её из подпроцесса —
  так `Base.metadata.create_all` не требует импортировать `auth.models`, и падение
  остаётся именно mapper-ошибкой, а не `NoReferencedTableError`.
- **TEST-NOTE-7.1…7.5** — зафиксированы в `ROADMAP.md` (`findings_archive` —
  legacy-таблица вне ARCHITECTURE.md; `last_run`/`last_result` retention живут
  только в памяти; `findings.ttl_days=180` без архивации; dry_run через API
  работает и без Celery; Flower не видит worker'ов).

### Changed
- Версия 3.13.26 → **3.13.27**: `.env`, `.env.example`, `docker-compose.yml`
  (включая устаревшие fallback `${VERSION:-3.13.12}`, из-за которых образы
  собирались со старой версией при отсутствии `.env`).
- Полный прогон: **317 unit passed** (было 304, +13), **47 E2E passed / 6 skipped**
  (было 46/6, +1).

---

## [3.13.26] — 2026-09-29 — День 49, BUG-098 / BUG-099 / BUG-100 / BUG-101: аудит ревью, сброс ревью-полей, пагинация и путь FP

### Fixed
- **BUG-101 🔴 — PATCH + bulk не писались в `audit_logs`** — 📁 `manager/src/api/findings.py`
  Смена статуса находки нигде не аудировалась: за 30 минутlive-активности в журнале
  оказалось 0 записей `finding_confirmed` / `finding_false_positive` / `finding_updated`
  (только `auth_login`), хотя PATCH и bulk вызывались 10+ раз. Сравнение подтвердило,
  что аудит в модуле работает (`finding_reveal`, `fragment_accessed`, `findings_exported`).
  **Исправление:** хелпер `_log_finding_status_change()` с маппингом статуса на `event_type`
  (`confirmed` → `finding_confirmed`, `false_positive` → `finding_false_positive`,
  `archived` → `finding_archived`, `new` → `finding_reset`), вызов в `update_finding`
  (`via='patch'`) и в `bulk_update` (`via='bulk'`, **по записи на каждую находку** —
  Вариант A из ТЗ, удобнее искать по `finding_id` в SIEM). Записи копятся без коммита и
  пишутся одним коммитом вызывающего кода — bulk не делает N commit'ов.
  В `metadata_json`: `action`, `finding_id`, `category`, `finding_type`, `old_status`,
  `new_status`, `comment`, `via`. В `audit_logs.user` — реальный пользователь.
  Live: 4 записи от PATCH (включая `finding_reset`) + 2 от bulk за одну операцию.
- **BUG-101 (открытый вопрос ТЗ) — DELETE findings тоже не аудировался** — 📁 `manager/src/api/findings.py`
  Проверено в ходе фикса: `DELETE /api/findings/{id}` (только Admin) удалял находку без
  следа в журнале. Добавлена запись `finding_deleted` (`old_status`, `resource_id`,
  `via='delete'`), которая создаётся **до** `db.delete()` и уходит в том же коммите —
  после коммита инстанс expire'ится и `fragment_path`/`category` уже не прочитать.
- **BUG-100 🟡 — PATCH `status=new` не очищал поля ревью** — 📁 `manager/src/api/findings.py`
  Сброс ревью оставлял `reviewed_by` / `reviewed_at` от предыдущего ревьюера, и находка
  со статусом `new` выглядела одобренной (а `/false-positives` сортирует по `reviewed_at`).
  **Исправление:** общая функция `_apply_status()` — при `status='new'` поля ревью
  очищаются в `None`, `comment` берётся из тела запроса (решение ТЗ). Тот же путь
  использует `bulk_update`, поэтому поведение PATCH и bulk больше не расходится.
- **BUG-099 🟡 — `/false-positives?offset=-1` / `?limit=-5` → 500** — 📁 `manager/src/api/findings.py`
  В `list_false_positives` остались старые `limit: int = Query(100, le=1000)` /
  `offset: int = 0` без нижних границ — отрицательные значения доходили до
  `.offset(-1)` / `.limit(-5)`, и PostgreSQL отвечал ошибкой → HTTP 500.
  **Исправление:** `OptInt` + `_clamp_int()` как в `list_findings`.
  Проверен весь `manager/src/api/`: остальные эндпоинты защищены валидацией
  `ge/le` (422 вместо 500), `retention.py` — явной проверкой (400). Реальных
  случаев 500 не осталось.
- **BUG-098 🟡 — `/false-positives` отдавал `file_path` = директория** — 📁 `manager/src/api/findings.py`
  `file_path` брался из `res_map` (путь **ресурса** = сканируемая папка) раньше
  `fragment_path` (путь **файла**), поэтому один и тот же finding давал разные пути
  в `/false-positives` и в `/findings?status=false_positive`. **Исправление:**
  `fragment_path` в приоритете, `res_map` — только fallback для находок без фрагмента.
  Live: `C:\test\scanner_clean\pii\phones_clean.txt` (ожидаемое из ТЗ значение).

### Added
- Тесты (40 новых, юнит-прогон 264 → 301):
  - `tests/unit/test_audit_status_change_v31326.py` — 18 (все 4 статуса через PATCH,
    bulk по записи на находку, `metadata` old/new, `via=patch|bulk`, реальный `user`,
    аудит удаления, отсутствие записей при 404);
  - `tests/unit/test_patch_reset_clears_review_v31326.py` — 8 (очистка `reviewed_by` /
    `reviewed_at`, `comment` из тела, сброс из `false_positive` и `confirmed`,
    регрессия «для confirmed/false_positive/archived ревью проставляется»);
  - `tests/unit/test_fp_pagination_v31326.py` — 8 (`offset=-1`, `limit=-5`, `limit=0`,
    `limit=99999`, пустые параметры, валидная пагинация, offset за концом);
  - `tests/unit/test_fp_file_path_v31326.py` — 6 (путь файла, не директория;
    согласованность с `/findings`; fallback на путь ресурса; несколько строк).

### Changed
- `update_finding`, `bulk_update` и `delete_finding` принимают `request: Request` —
  нужен `source_host` для записи аудита.
- `tests/unit/test_false_positives_v31325.py` — ассерт `file_path` обновлён: ранее тест
  закреплял **баговое** значение (директорию ресурса), теперь — путь файла.

---

## [3.13.25] — 2026-09-28 — День 48.3, BUG-096 / BUG-096b / BUG-097: /false-positives, зависшие задания и осиротевшие пачки

### Fixed
- **BUG-096 — 500 на `/api/findings/false-positives`** (TASK-064): в `manager/src/api/findings.py`
  использовалась несуществующая ссылка `_m.User`. `User` — это модель `manager/src/auth/models.py`,
  а не `manager/src/db/models.py`, поэтому любой запрос к эндпоинту падал с
  `AttributeError: module 'manager.src.db.models' has no attribute 'User'` (HTTP 500).
  Исправлено: импорт `User` из `manager.src.auth.models`, `Resource` — из `manager.src.db.models`.
  Live: `GET /api/findings/false-positives` → 200.
- **BUG-097 — задания навечно застревали в статусе `assigned`, в логах 404 на `/tasks/{id}/results`** (TASK-066).
  Полная цепочка причин (установлена на живой системе):
  1. E2E создавал задание на `tmp_path`, который pytest удалял после теста; сканер
     падал на несуществующем пути, а исключение глушилось внешним `except Exception`
     в `main()` — задание оставалось в `assigned` до `TASK_TIMEOUT_MINUTES` (30 минут)
     в Manager, и каждое новое задание вставало в очередь за зависшими;
  2. офлайн-пачка `scanner/data/offline/task_43.json` по удалённой задаче
     ретраилась **бесконечно** — 404 на каждом цикле `main()`.
  Исправлено в `scanner/src/managed_scanner.py`:
  - новый `SubmitStatus` (`OK` / `RETRY` / `LOST`) и `submit_results_status()`:
    404/410 → `LOST`; прежний `submit_results()` сохранён как bool-обёртка;
  - `_flush_offline()` отбрасывает пачку потерянного задания (файл удаляется)
    вместо бесконечного retry; `LOST` не прерывает разбор очереди;
  - главный цикл: исключение в `_execute_task()` больше не оставляет задание
    в `assigned` — задание сразу переводится в `failed` через
    `_fail_task_safely()`, причина логируется со стеком (`logger.exception`).
  В `manager/src/api/scanner.py` 404 на `/tasks/{task_id}/results` теперь
  логируется с `task_id`, `scanner_id`/CN клиента и `batch`/`total` (было
  без контекста в generic-логе).
- **BUG-096b — падавшие E2E-тесты** (TASK-065):
  - `test_full_scan_cycle`: `finding_type` (`pii`/`credentials`/`code`) и
    гранулярный `category` вместо устаревших полей;
  - `tests/fixtures/manager.py`: `_get_with_retry()` — обход разрыва
    keep-alive соединения (`RemoteDisconnected` при опросе каждые 5 с против
    uvicorn `timeout_keep_alive=5`), 3 попытки с паузой и закрытием соединения;
  - `test_scanner_findings`: precheck активного сканера (иначе skip вместо
    таймаута 300 с), ожидание задания 240 с + `@pytest.mark.timeout(600)`
    (глобальный `timeout = 300` в `pyproject.toml` убивал тест ровно в момент
    ожидания), освобождение зависших заданий перед прогоном, задание больше не
    забирается вручную через `/tasks/pending` (это переводило его в `assigned`,
    и реальный сканер его уже не видел — полный цикл проходит за ~15 с),
    ассерт на `fingerprint` заменён на реальный контракт `/api/findings`.

### Tests
- 264 unit passed (было 242: +8 BUG-096, +14 BUG-097).
- 50 E2E passed, 2 skipped (было 47 passed, 3 failed, 2 skipped).

---

## [3.13.24] — 2026-09-27 — День 48.2, BUG-095: аудит входов и управления пользователями

### Added
- **Аудит аутентификации (TASK-061)** — `manager/src/auth/audit.py` (новый модуль):
  - `log_auth_event()` — единая запись в `audit_logs`, **fail-open** (сбой аудита не ломает
    аутентификацию: `logger.warning` + `rollback`, эндпоинт продолжает работать);
  - `_sanitize()` — рекурсивное вырезание из `metadata` ключей с паролями/токенами/секретами
    (`password`, `*_token`, `*_secret`, `*_hash`, `*_salt`, `*_credential`);
  - `classify_login_failure()` — `user_not_found` / `user_inactive` / `invalid_credentials`;
  - `role_diff()` — дифф ролей для `role_assigned` / `role_revoked`.
- Новые `event_type` в `audit_logs` (`event_source=api`, `file_path` = точный URL, `source_host` = IP):
  - `auth_login` (`auth_source`, `auth_method`, `auth_mode`, `roles`),
  - `auth_failed` (`reason`, `attempted_username`) — **без пароля и хеша**,
  - `auth_logout` (`jti`, не сам токен).
- **Аудит управления пользователями (TASK-062)** — `user_created`, `user_updated`
  (в т.ч. `status_changed` при блокировке/разблокировке), `user_deleted`,
  `user_password_changed` (self-service и сброс админом: `by_admin`, `self_service`),
  `role_assigned` / `role_revoked` (по диффу ролей, в т.ч. из `PUT /users/{id}`).

### Changed
- `manager/src/auth/router.py`: `login`, `logout`, `change-password`, `users` (create/update/delete),
  `users/{id}/status`, `users/{id}/roles` — добавлен `request: Request` и запись аудита;
  `update_user` теперь пишет `changes` только по реально изменённым полям, PII-поля
  (`email`, `full_name`) — как `"changed"` без значений.
- `update_user`: `is_active` пишется в `changes` только при фактическом изменении.

### Security
- Пароли, хеши, токены и JWT-секреты **не могут** попасть в `metadata` (проверено unit-тестами
  и live-запросом: `SELECT COUNT(*) ... LIKE '%пароль%'` → 0).
- Причина неудачи входа видна только в аудите; HTTP-ответ остаётся «Invalid credentials»
  (нет перечисления существующих учёток).
- `auth_refresh` намеренно не логируется (refresh каждые 15 мин → шум) — решение из ТЗ.

### Tests
- `tests/unit/test_auth_audit_v31324.py` — **15 тестов** (6 аутентификация, 7 управление
  пользователями/паролями/ролями, 2 безопасность метаданных) → 15 passed.
- `tests/e2e/test_auth_audit_e2e.py` — **2 теста** (полный флоу: создание → роли →
  блокировка → неудачный вход → удаление → logout; несуществующий пользователь) → 2 passed.
- Полный unit-набор: **242 passed** (было 227).
- Полный E2E: 47 passed, 3 failed, 2 skipped — все 3 падения **предсуществующие и вне ТЗ**
  (см. ниже).

### Live-проверка
Все 9 `event_type` пишутся в PostgreSQL; `auth_login` (admin 72, auditor 4), `auth_failed`
(admin 3 + тестовые), `auth_logout` (9), `user_created` (8), `user_updated` (7),
`user_deleted` (7), `user_password_changed` (`by_admin: true`), `role_assigned` (7).

### Known issues (найдено при полном E2E, вне ТЗ — не правил)
- **BUG-096**: `GET /api/findings/false-positives` → **500**
  (`manager/src/api/findings.py:324` — `_m.User`, а `User` в `manager.src.auth.models`).
- **BUG-096b**: устаревшие E2E-тесты `test_full_scan_cycle`, `test_real_scanner_end_to_end` —
  ждут `finding_type in {pii, credentials}` после рефакторинга v3.13.22 (теперь granular
  `category`: email/person/phone/aws_key).
- `docker-compose.override.yml` для прогона E2E (лимит логина 5/мин) удалён после проверки.

---

## [3.13.23] — 2026-09-27 — День 48.1, TASK-060: «аудит reveal пишет dcap» — ложное срабатывание

### Changed
- **BUG-087 (ТЗ) / BUG-094 (факт) — 🔴 баг НЕ подтверждён, код приложения корректен.**
  Диагностика ТЗ строилась на запросе `SELECT id, created_at, user FROM audit_logs`:
  в PostgreSQL `user` — зарезервированное слово (синоним `CURRENT_USER`), поэтому
  возвращалось **имя роли БД** `dcap`, а не значение колонки. Реальный `INSERT`
  содержит корректного пользователя (`'auditor'`). Гипотезы H1–H7 не подтвердились:
  нет SQLAlchemy-listener'ов, DEFAULT/TRIGGER/RULE, подмены в middleware/dependencies,
  второго писателя `AuditLog` или hardcoded `"dcap"`. **Правки кода не требуются.**
- Проверены остальные писатели аудита: `findings_exported` (admin 11 / auditor 4) и
  `fragment_accessed` (admin 11 / auditor 9) — реальные пользователи, проблемы нет.

### Added
- `tests/unit/test_audit_reveal_user_v31323.py` — 7 тестов: `audit_logs.user` ==
  `revealed_by` для reveal/export/fragment, `!= "dcap"`, admin ≠ auditor, имя колонки
  `user` и отсутствие Python-side `default` (регрессия на переименование).
- `tests/e2e/test_audit_reveal_user_e2e.py` — 3 теста: live-reveal → `/api/audit`
  отдаёт `user == "auditor"`, стабильность при повторах, прямая SQL-проверка
  `SELECT "user", user` (колонка ≠ `CURRENT_USER`).

### Documentation
- `docs/admin-guide/10-troubleshooting.md` — раздел 6 «Ложный "баг": `audit_logs.user`
  показывает `dcap`»: правильный SQL с кавычками, подтверждение INSERT'а, приём
  для других зарезервированных имён колонок (`order`, `group`, `default`).
- `prompts/reports/day_48.1_bug087_audit_user_report.md` — отчёт с разбором H1–H7,
  live-доказательствами и обратной связью архитектору.

### Tests
- 7 unit + 3 E2E (новые); полный unit-набор: **227 passed** (было 220).
- Контейнеры manager/webui/celery пересобраны на `3.13.23` (healthy).

### Known gaps (не в ТЗ)
- `auth_login`, `user_created`, `change_password` **не пишутся** в `audit_logs`
  (кандидат в бэклог: BUG-095).
- ⚠️ Коллизия ID: BUG-087 уже занят Днём 48 (TASK-054, прокси-заголовки WebUI);
  данный случай зафиксирован как **BUG-094**.

---

## [3.13.22] — 2026-09-27 — День 48, Блок 5 (WebUI) п.2.3: фильтры, пагинация, аудит, экспорт

### Fixed
- **BUG-087** (TASK-054, `webui/api/routes.py`): прокси WebUI пробрасывал только `content-type`
  и терял все остальные заголовки Manager — из-за этого не работала пагинация (`X-Total-Count`
  был 667 в Manager и отсутствовал в WebUI), не доходили `X-Fragment-Mode`/`X-Fragment-Hash`/
  `X-Bounding-Box` и `Content-Disposition` (имя файла экспорта). Добавлены `HOP_BY_HOP`
  и `forwarded_headers()`: копируются все заголовки ответа, кроме hop-by-hop
  (`connection`, `transfer-encoding`, `content-length`, `content-encoding`, `keep-alive`,
  `upgrade`, `proxy-*`, `te`, `trailer`) и `set-cookie` (JWT WebUI передаёт Bearer-заголовком,
  cookie Manager'а через прокси не доходят — иначе ломалась бы авторизация).
- **BUG-088** (TASK-055, `webui/static/js/finding_detail.js`): фрагмент (`/fragment?format=png`)
  грузился через `<img src>` — браузер не отправляет `Authorization: Bearer` (JWT в localStorage,
  cookie не пробрасываются) → 401, изображение не показывалось. Теперь `fetch` + `Blob` + objectURL
  с заголовками авторизации; в UI выводятся `X-Fragment-Mode` и сокращённый `X-Fragment-Hash`
  (hex-дамп — через безопасный textContent); при 401 выполняется переход на `/login`.
- **BUG-089** (TASK-056, `manager/src/api/webui.py`): `/api/access/resources` и
  `/api/access/resources/{id}/entries` отдавали **500** на PostgreSQL — `AccessEntry.is_active == 1`
  сравнивал Boolean-колонку с целым (`operator does not exist: boolean = integer`). Заменено на
  `== True` (2 места).
- **BUG-090** (TASK-057, `manager/src/api/findings.py`): фильтр «Категория» в WebUI принимает
  список через запятую (`phone, email...`), но backend сравнивал строкой целиком → всегда 0 находок.
  Теперь `_parse_categories` + `_apply_category_filter`: legacy-категории (`pii`, `credentials`,
  `code`) фильтруются по `finding_type`, остальные — по `category`, объединение через ИЛИ
  (`or_`), а не И. Дополнительно: пустые числовые параметры (`?task_id=&limit=&offset=&resource_id=`)
  больше не дают 422, добавлены фильтры `detector`, `fragment_type`, `search`
  (путь к файлу + маскированные значения), `order_by=id`; те же правила в `/count` и `/export`.
- **BUG-091** (TASK-058, `manager/src/api/audit.py`, `webui/templates/audit.html`): `event_source`
  принимался в `/api/audit`, но не передавался в SQL-фильтр — «Источник» в UI игнорировался
  (`api` и `scanner` возвращали одинаковые 47 событий). Добавлен фильтр по `event_source`;
  статические списки «Источник/Тип» (windows_agent/linux_agent, read/write/delete) заменены на
  реальные значения из `/api/audit/stats` (`by_source`, `by_type`).
- **BUG-093** (TASK-059, `webui/static/js/findings.js`): экспорт findings вызывался
  `window.location.href = '/api/findings/export'` — переход браузера без `Authorization`
  → 401 (у пользователя скачивался JSON с ошибкой). Теперь `fetch` + `Blob` + `<a download>`
  с именем файла из `Content-Disposition`, обработка 401 → редирект на `/login`.

### Changed
- `manager/src/api/findings.py`: `OptInt = Annotated[Optional[int], BeforeValidator(_blank_to_none), Query()]`
  + `_clamp_int()`. **FastAPI 0.137 gotcha:** `BeforeValidator` в `Annotated` теряется, если
  `Query(...)` указан в default (`create_model_field` берёт annotation из `field_info`), поэтому
  `Query()` вынесен внутрь `Annotated`, а дефолт — через `=`. Числовые `le`/`ge` несовместимы
  с `Optional[int]` (TypeError на `None`), поэтому границы limit/offset задаёт `_clamp_int`.
  `has_fragment` учитывает `fragment_data` (BACKLOG-086), а не только `fragment_path`.
- `webui/templates/findings.html`: фильтры перестроены в две строки — поиск, «Категория (через запятую)»,
  «Детектор», «Фрагмент», «Задание», статус/тип/severity + кнопки «Применить» и «Сброс».
- `webui/static/js/findings.js`: `collectFilters()` + новый `resetFilters()`, поиск по Enter,
  показ общего количества находок в заголовке списка.
- `webui/templates/audit.html`: `loadFilterOptions()`/`fillSelect()`; `d.total ?? events.length`
  (раньше `d.total || events.length` скрывал 0).
- `docker-compose.yml` — manager/webui/celery → 3.13.22.

### Tests
- `tests/unit/test_webui_block5_v31322.py` (33): прокси-заголовки (4), фильтры findings (18 —
  CSV-категории, legacy-микс, detector, fragment_type, search, order_by, пустые параметры, count,
  export, has_fragment), `/api/access/*` без 500 (3), `/api/audit` event_source (5).
- Итого **220 passed** (187 + 33) — регрессий нет.
- `tests/e2e/test_webui_block5_v31322.py` (8) против живого стека: X-Total-Count через прокси,
  CSV-категории и пустые параметры, новые фильтры, export 200/401, fragment 200/401,
  `/api/access/resources`, `event_source`, рендер `/findings` и `/audit`.
  В E2E один логин на модуль — `/api/auth/login` ограничен 5 попытками в минуту.

### Verified (live)
- `docker compose build manager webui` + `up -d` → `/api/health` = `3.13.22`.
- BUG-087: Manager `X-Total-Count: 667` → WebUI `X-Total-Count: 667`; fragment через WebUI
  200 `image/png` 8255 B, `X-Fragment-Mode: embedded`, `X-Fragment-Hash: 9ecadc2f…`,
  без токена — 401.
- BUG-090: `category=phone` → 11, `category=phone,email` → 623, `?task_id=`/`?limit=`/`?offset=` → 200
  (total 667), `/count?category=phone,email` → `{"count":623}`, `detector`/`fragment_type`/`search`/`order_by=id` → 200.
- BUG-089: `/api/access/resources` → 200 (7 ресурсов), `/entries` → 200.
- BUG-091: `/api/audit` без фильтра — 48 событий, `event_source=api` — 44, `event_type=finding_reveal` — 25.
- BUG-093: export CSV 200 (99 907 B, `Content-Disposition: attachment; filename="findings_20260927_002857.csv"`),
  JSON 200, `?task_id=&resource_id=&limit=` → 200, без токена — 401.

---

## [3.13.21] — 2026-09-26 — BUG-086: masking контекстов (критический блокер v3.0.0)

### Fixed
- **BUG-086** (TASK-053, `scanner/src/encryption.py`): `mask_context` маскировал только 6 паттернов
  из 19 в `MASK_RULES` — в `context_before_masked`/`context_after_masked` утекали сырые
  credentials/US-phone (Finding 1439: `GITHUB_TOKEN=ghp_…`, `BASIC_AUTH=Basic …`;
  Finding 1461: `us: +1 415 555 0199`). Viewer+ видел секреты через API.
  Новая реализация — конвейер `_CONTEXT_PATTERNS`: список `(regex, category)` на ВСЕ категории
  (21 паттерн: ghp_/github_pat_→github_token, xoxb→slack_token, AKIA→aws_key, sk-/sk_live_→api_key,
  discord→discord_token, JWT eyJ…, PEM→ssh_key, Basic→basic_auth, scheme://→database_url,
  generic password/api_key/token в KEY=VALUE — маскируется только значение (2 capture-группы),
  email, +7/+1/международные телефоны, паспорт/СНИЛС/ИНН/кредитные карты).
  Специфичные категории — раньше generic. `person` и `high_entropy` в контексте НЕ маскируются
  (high_entropy — до v3.1.0).

### Changed
- `scanner/src/encryption.py` — `mask_context` полностью переписан (стали специфичными,
  generic-паттерны KEY=VALUE маскируют только значение).
- `docker-compose.yml` — manager/webui/celery → 3.13.21.

### Tests
- `tests/unit/test_mask_context_v31321.py` (20): github/slack/aws/api_key/basic_auth/database_url/
  jwt/password/generic token (9), телефоны RU/US/US-скобки (3), регрессии PII
  email/inn/passport/credit_card/person-not-masked (5), edge empty/no_secrets/multiple (3).
- Итого **187 passed** (167 + 20), в т.ч. регрессия `test_encryption`, `test_finding_fragments`.
- `tests/e2e/test_mask_context_e2e.py` (1): контексты последнего скана не содержат сырых
  credentials/US-phone (проверка через API Manager, viewer-роль).

### Verified (live)
- БД: findings task 39 → удалены; новый task (id 41) → 29 findings; SQL-проверка
  `context_before_masked ~ ghp_…|Basic …|xoxb-…|+1…|AKIA…|sk-…` → **0 совпадений**.
- API (viewer/viewer123): findings 1496/1500/1503/1521/1522 — `raw_in_contexts=False`:
  `GITHUB_TOKEN=ghp_*****`, `BASIC_AUTH=Basic ***`, `DATABASE_URL=postgresql://***@cleandb.local…`,
  `us: 14***199`.
- `/api/health` → `{"status":"healthy","version":"3.13.21"}`.

---

## [3.13.20] — 2026-09-26 — BUG-080/081: reliability сканера (heartbeat backoff + graceful shutdown)

### Fixed
- **BUG-080** (TASK-051, `scanner/src/heartbeat.py`): heartbeat при недоступном Manager больше
  не спамит лог. Backoff 5→10→30→60→120 с (`BACKOFF_STEPS`), фейлы — на DEBUG,
  WARNING только на 1-й попытке и далее каждые 5, INFO «Heartbeat restored after N failure(s)».
  Пауза — `_stop.wait()` вместо `time.sleep()`: stop()/SIGINT мгновенно прерывает ожидание.
- **BUG-081** (TASK-052): Ctrl+C больше не оставляет осиротевший OCRWorker на Windows.
  `ManagedScanner._handle_sigint` (SIGINT + SIGBREAK) ставит флаги остановки;
  `stop()` = остановка heartbeat + `_shutdown_classifiers()`; `ocr_worker.stop_ocr_worker` —
  graceful: None в request_queue → join(5) → terminate → join(2) → kill.

### Changed
- `scanner/classifiers/ocr_worker.py` — порядок завершения процесса (было terminate → join).
- `docker-compose.yml` — manager/webui/celery → 3.13.20.

### Tests
- `tests/unit/test_heartbeat_backoff.py` (4): backoff_steps, resets_on_success,
  warning_not_spam (WARNING на 1/5/10), stop_event_interrupts_sleep (мгновенный выход).
- `tests/unit/test_scanner_shutdown.py` (3): sigint_sets_stop_event, stop_sends_none_to_ocr_queue,
  stop_terminates_stubborn_process (real mp.Process, terminate/kill).
- Итого **167 passed** (160 + 7), в т.ч. регрессия `test_stale_tasks`, `test_scanner_middleware_rbac`.

### Verified (live)
- BUG-080: docker stop manager → единственный `Heartbeat failing (1 attempts), next retry in 5s`,
  тишина далее; docker start → `Heartbeat restored after 4 failure(s)`.
- BUG-081: CTRL+C (эмуляция CTRL_BREAK в группе) → `[Scanner] SIGINT received`,
  graceful reенте: HeartbeatThread stopped → OCRWorker остановлен → `[X] Сканер остановлен`, rc=0.

---

## [3.13.19] — 2026-09-26 — BACKLOG-086: встроенные OCR-фрагменты («Файл удалили — доказательство осталось»)

### Added
- **BACKLOG-086** (TASK-045): модель `Finding` + 5 колонок — `fragment_data` (LargeBinary),
  `fragment_mime`, `fragment_hash` (SHA-256), `fragment_size`, `fragment_embedded_at`.
- **TASK-049**: миграция `005_add_fragment_columns` (идемпотентная, inspect); применена к live PG.
- **TASK-046/050** (`scanner/src/managed_scanner.py`): `_embed_fragment` — для `image_region`
  с существующим файлом и размером ≤ `MAX_FRAGMENT_EMBED_SIZE` (env, default 2 МБ) встраивает
  весь PNG (base64 + SHA-256 + mime); `_split_by_size` — батчинг результатов по
  `MAX_BATCH_SIZE_BYTES` (env, default 20 МБ, до 500 finding'ов), применён в `submit_results`.
  `text_line`/`byte_range` не встраиваются (текст — в `line_text_encrypted`; byte_range — v3.1.0).
- **TASK-047** (`manager/src/api/scanner.py`): декодирование `fragment_base64` → `fragment_data`
  + метаданные при создании Finding.
- **TASK-048** (`manager/src/api/findings.py`):
  - `/api/findings/{id}/fragment` — **embedded-first**: при `fragment_data` отдаёт PNG из БД
    с `X-Fragment-Mode: embedded` + `X-Fragment-Hash`; без данных — падение на full-image (по пути);
    RBAC ужесточён Viewer+ → **Auditor+** (BUG-079);
  - новый `GET /api/findings/{id}/fragment/hash` (Auditor+) — метаданные `{finding_id, hash, size, mime, embedded_at}`;
  - аудит доступа: `AuditLog(event_type="fragment_accessed", metadata={"action","finding_id","mode"})`.
- `docker-compose.yml` — manager/webui/celery → 3.13.19; env `MAX_FRAGMENT_EMBED_SIZE` /
  `MAX_BATCH_SIZE_BYTES` (pass-through, дефолты 2097152 / 20971520).
- `.env.example` — переменные фрагментов.

### Tests
- `tests/unit/test_fragment_embed_v31319.py` (8) — Manager: сохранение fragment из payload,
  text_line не встраивается, embedded-ответ с hash, fallback full-image, 404, RBAC (viewer 403),
  `/fragment/hash`, аудит `fragment_accessed`.
- `tests/unit/test_scanner_fragment_embed.py` (6) — Scanner: встраивание малого PNG, лимит 2 МБ,
  text_line {}, hash = SHA-256 данных, кастомный лимит (env), `_split_by_size`.
- `tests/unit/test_ocr_bbox_v31317.py` — фикс `_make_entity` (SimpleNamespace: `fragment_* = None`).
- `pytest tests/unit/` — **160 passed** (146 + 14).
- `tests/e2e/test_fragment_e2e.py` — **passed live**: удаление исходного PNG → `/fragment` всё ещё 200 embedded.

### Confirmed live (task 39)
- `C:\test\scanner_clean` → 29 findings, 7 файлов, 0 failed.
- `image_region` (ids 1444/1445): `fragment_size=8255`, `fragment_mime=image/png`, `fragment_data=8255 B`,
  hash `SHA-256` совпадает с `X-Fragment-Hash` ответа; текст-findings — fragment_* = NULL.
- Исходник `screenshot_clean.png` удалён с диска → `GET /api/findings/1444/fragment` (auditor) → 200,
  `Content-Length: 8255` — фрагмент из БД; viewer → 403; `/fragment/hash` → корректный JSON;
  audit_logs: `fragment_accessed` (mode embedded/hash).

### Docs
- `ARCHITECTURE.md` — модель + фрагменты/API (`/fragment` Auditor+, `/fragment/hash`, аудит),
  событие ИБ `fragment_accessed`.
- `docs/admin-guide/05-security.md` — раздел «Неизменяемые доказательства».
- `ROADMAP.md`, `STATE.md` — v3.13.19; отложено: BACKLOG-087 (дедуп фрагментов), BACKLOG-088 (шифрование).

---

## [3.13.18] — 2026-09-26 — BUG-077 diag (причина H3: Manager дефолтил bbox) + live-подтверждение

### Fixed
- **BUG-077 (live-диагностика, TASK-044)**: фикс TASK-041 не отражался в БД — после task 36
  `bounding_box` по-прежнему `{0,0,0,0}`. Исключены гипотезы H1/H2/H4/H5/H6/H7 (pyc свежий,
  единственный filesystem.py, процесс сканера = `run_scanner.py`, `"x": 0` в сканере нет).
  **Причина — H3**: сканер шлёт `bounding_box: null` (managed_scanner.py:673), но Manager
  при сохранении применял `finding_data.get("bounding_box") or ({"x":0,...} if image_region)`:
  `None or default` → в БД уходил `{0,0,0,0}`.
  - `manager/src/api/scanner.py` — убран дефолт, теперь `bounding_box=finding_data.get("bounding_box")`
    (честный `NULL` для OCR до BACKLOG-085, v3.1.0).

### Changed
- `docker-compose.yml` — manager/webui/celery → 3.13.18.

### Tests
- `tests/unit/test_ocr_bbox_v31317.py` — +`TestFragmentFallback` (2 теста):
  image_region + bbox=None → 200 + весь PNG + `X-Fragment-Mode: full-image`;
  файл отсутствует → 404.
- `pytest tests/unit/` — 146 passed (144 + 2).

### Confirmed live (task 38)
- SQL: `bounding_box = NULL` для обоих `image_region` (ids 1415/1416), 29 findings,
  разбивка = task 35 (15 категорий, без регрессий).
- API: `bounding_box` пусто, `has_fragment = True`, `file_path` → PNG.

### Docs
- `docs/admin-guide/10-troubleshooting.md` — создан (раздел «Код сканера не влияет»,
  bbox={0,0,0,0}, устаревшая версия, зависшие контейнеры).

---

## [3.13.17] — 2026-09-25 — BUG-077 (bbox=None для OCR + fallback full-image)

### Fixed
- **BUG-077** (TASK-041): OCR-finding'и получали захардкоженный `bounding_box = {x:0, y:0, width:0, height:0}`. Координаты не вычисляются (Tesseract вызывается без tsv) — теперь честно `None`, чтобы API/WebUI не пытались вырезать несуществующий регион.
  - `scanner/connectors/filesystem.py` — OCR-блок `scan_file`.
- **BUG-077** (TASK-042): endpoint `/api/findings/{id}/fragment` для `image_region` без bbox возвращает **весь PNG** с заголовком `X-Fragment-Mode: full-image` (Вариант 1). Файл недоступен → 404.

### Changed
- `docker-compose.yml` — VERSION агентов синхронизирован: `s3_agent`, `audit_agent_linux` 3.13.12 → 3.13.16 (TASK-043); manager/webui → 3.13.17.

### Tests
- `tests/unit/test_ocr_bbox_v31317.py` — 2 теста (OCR bbox=None, text finds bbox=None).
- `pytest tests/unit/` — 144 passed.

### Notes
- Полный OCR-пайплайн с реальным bbox (tesseract tsv) — **BACKLOG-085 (v3.1.0)**.
- BUG-078 не создавался: `has_fragment` в API считается по `fragment_path`, а не по bbox — кнопка фрагмента у OCR уже активна (fragment = сам PNG).

---

## [3.13.16] — 2026-09-22 — Fix-спринт №7 (BUG-075)

### Fixed
- **BUG-075**: Presidio URL recognizer ловил доменную часть email-адреса как отдельный url (`company.example` для `carol.new@company.example`). В таких строках нет `://`, поэтому фильтр ТЗ №6 не срабатывал.
  - `_filter_url_over_email_finding` расширен: собирает все email-значения (match_text email-findings + email-паттерны из line_text, case-insensitive), отбрасывает url, чей match_text целиком входит в email.
  - Покрыт дубль url в одной строке (разные start_pos/end_pos).

### Changed
- `docker-compose.yml`, `.env.example` — VERSION 3.13.16.

### Tests
- `tests/unit/test_pii_filters_v31316.py` — 7 тестов (domain of email url removed, multiple urls same line, real url kept, email without url kept, + регрессия).
- `pytest tests/unit/` — 142 passed.

---

## [3.13.15] — 2026-09-22 — Fix-спринт №6 (BUG-071…074)

### Fixed
- **BUG-071**: url-over-email не фильтровался — Presidio обрезает url по `@`, спаны url/email не пересекались.
- **BUG-072**: `organization = "INN"` (аббревиатура) — spaCy en-проход.
- **BUG-073**: `uk_nhs` на US-телефоне `+1 415 555 0199`.
- **BUG-074**: email из URL-логина `postgresql://user:pass@host/db`.

### Changed
- `_filter_url_over_email_finding` — работа по `line_text` (не по спанам): если строка содержит `://` И email-признак — отбрасываются все url/email этой строки.
- `_filter_spacy_noise` + `_filter_spacy_noise_classification` — добавлено условие: `len(val) <= 5 and val.isupper() and val.isascii() and val.isalpha()` (INN/SSN/DOB/URL/API).
- Новая `_filter_uk_nhs_with_phone` — отбрасывает `uk_nhs`, если в строке уже есть `phone`.

### Tests
- `tests/unit/test_pii_filters_v31315.py` — 7 тестов.
- `pytest tests/unit/` — 135 passed.

---

## [3.13.14] — 2026-09-21 — Fix-спринт №5 (BUG-065, 066b, 067d, 069/070)

### Fixed
- **BUG-066b**: `scan_text`/`scan_line` не фильтровали url-over-email (модель `Finding`, поля `start_pos/end_pos`).
- **BUG-067d**: OCR-изображения не помечались `fragment_type=image_region`, `detector=ocr`, `bounding_box`.
- **BUG-069**: ложные `date_time` из en-прохода Presidio.
- **BUG-070**: ложные `person`/`organization` из en-прохода Presidio.
- **BUG-065**: credentials-паттерны (`database_url`, `github_token`, `slack_token`, `basic_auth`).

### Changed
- `_filter_url_over_email_finding` — добавлен для модели `Finding`.
- `filesystem.py` — для `_IMAGE_EXTENSIONS` findings помечаются `image_region`/`ocr`/`bounding_box`.
- `_filter_spacy_noise` — добавлен для `scan_text`/`scan_line`.
- `credentials_classifier` — 5 фиксов (signature prefixes, placeholder patterns, BASIC_AUTH, SLACK_TOKEN, `_is_placeholder` для URL).

### Tests
- Smoke-тесты credentials — 4 кейса зелёные.

---

## [3.13.13] — 2026-09-21 — Fix-спринт №4 (BUG-067c, 063)

### Fixed
- **BUG-067c**: `ocr_enabled` брался из неверной секции конфига.
- **BUG-063**: `credit_card` не детектировался — Presidio `ru`-проход не находил US-сущности.

### Changed
- `ocr_enabled` — из `classifiers.pii` (TASK-029).
- Двухпроходный Presidio `ru`+`en` (TASK-030).

---

## [3.13.12] — 2026-09-21 — Fix-спринт №3 (BUG-061, 063, 067)

### Fixed
- **BUG-061**: сканер не восстанавливал HTTP после падения Manager.
- **BUG-063** (Luhn): credit_card без валидной Luhn-суммы.
- **BUG-067** (OCR): OCR не работал.
- **BUG-066** (url): SQL-очистка 607 url.

### Added
- HTTP retry в `ManagerClient` (total=5, backoff=0.5).
- `_is_valid_luhn` в `pii_classifier`.

---

## [3.13.11] — 2026-09-21 — Fix-спринт №2 (ENV-ключи)

### Changed
- Docker Secrets убраны для Findings (TASK-018).
- Ключи Findings — только через ENV: `FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY`, `FINDINGS_KEY_ID`.
- `scripts/reencrypt_findings.py` — ротация ключей (TASK-016).
- Scanner fail-fast без ключей (TASK-017).
- Документация обновлена (TASK-019).

### Tests
- `tests/unit/test_reencrypt.py`, `tests/unit/test_encryption.py`.
- `tests/e2e/test_key_rotation.py` — offline.

---

## [3.13.10] — 2026-09-21 — Fix-спринт №2 (BUG-048b)

### Fixed
- **BUG-048b**: middleware пропускал JWT для machine-API (scanner endpoints).

---

## [3.13.9] — 2026-09-21 — Fix-спринт №1 (Auth/RBAC, 15 багов)

### Fixed
- **BUG-037**: `_defaults.group_mapping` — ед.ч. vs мн.ч.
- **BUG-038**: TTL JWT не в env.
- **BUG-039**: refresh как access.
- **BUG-041**: reuse старого refresh.
- **BUG-042**: `secure=False` hardcoded.
- **BUG-043**: `/api/catalog/tree` → 500.
- **BUG-044**: `context_before` не маскировал домен.
- **BUG-045**: `/api/scanner/*` → 500.
- **BUG-046**: DELETE resources без RBAC.
- **BUG-047**: DELETE tasks без auth.
- **BUG-048**: DELETE scanner без auth + 500.
- **BUG-049…055**: 7 unprotected write-эндпоинтов.
- **BUG-057**: Scanner legacy mode by default.
- **BUG-058**: Manager fallback `line_text_encrypted`.
- **BUG-059**: `POST /api/tasks/create` 500.

### Changed
- `verify_token(token, expected_type)` — access ≠ refresh.
- RBAC системно — `Depends(require_role(...))` во все write-эндпоинты.
- Cookie `Secure` — env `AUTH_COOKIE_SECURE`.
- `jti` + `iat` + Redis blacklist.

---

## [3.13.8] — 2026-09-20 — AD-упаковка

### Added
- `docker-compose.ad.yml.example` — samba-ad-dc profile `ad`.
- `scripts/init_ad_test_data.py`.

---

## [3.13.7] — 2026-09-19 — BUG-034 (зависшие задачи)

### Fixed
- **BUG-034**: зависшие задачи сканера.

---

## [3.13.3-3.13.6] — 2026-09-19 — Блок 1 (Smoke + Findings)

### Fixed
- **BUG-034/035/027/022**.
- **BUG-022.9**: приоритизация категорий при дедупликации.

### Changed
- Deploy/Config/WebUI.

---

## [3.12.0] — 2026-09-18 — Findings: фрагменты и экспорт

### Added
- **BACKLOG-058**: фрагменты изображений (bounding box).
- **BACKLOG-059**: бинарные — hex-дамп.
- **BACKLOG-060**: экспорт с маскированием.
- **BACKLOG-067**: `X-Total-Count` в `/api/findings`.

---

## [3.11.0] — 2026-09-17 — WebUI Findings + MD5→SHA-256

### Added
- **BACKLOG-056**: WebUI — находки + каталог (строки).
- **BACKLOG-057**: WebUI — reveal + FP.
- **BACKLOG-061**: WebUI v3.8 — legacy Findings (деградация).

### Fixed
- **BACKLOG-066**: MD5 → SHA-256 в `_legacy_fingerprint`.

---

## [3.10.0] — 2026-09-16 — Scanner: построчное сканирование + FP

### Added
- **BACKLOG-053**: сканер — построчное сканирование.
- **BACKLOG-054**: fingerprint + дедупликация.
- **BACKLOG-055**: FP-фильтр перед отправкой.

---

## [3.9.0] — 2026-09-15 — Findings Refactor

### Added
- **BACKLOG-050**: модель Findings (строка/фрагмент).
- **BACKLOG-051**: шифрование находок (AES-256-GCM).
- **BACKLOG-052**: API находок + reveal + аудит.

---

## [3.7.0] — 2026-09-12 — Мониторинг + Heartbeat

### Added
- **BACKLOG-021**: расширенный мониторинг.
- **BACKLOG-037**: heartbeat-thread для сканера.
- **BACKLOG-038**: прогресс-пинг в heartbeat.
- **BACKLOG-041**: Prometheus/Grafana мониторинг.
- **BACKLOG-042**: Alertmanager + алерты.

---

## [3.6.0] — 2026-09-10 — Контейнеризация

### Added
- **BACKLOG-027**: контейнеризация и деплой.

---

## [3.4.0] — 2026-09-08 — Secret Scanner

### Added
- **BACKLOG-034**: Secret Scanner интеграция.

---

## [3.0.0] — 2026-09-01 — Enterprise Ready (начало)

### Added
- **BACKLOG-010**: S3/MinIO аудит-агент.
- **BACKLOG-013**: безопасность (mTLS, секреты).
- **BACKLOG-014**: масштабирование (PG, Redis, Celery).
- **BACKLOG-015**: WebUI редизайн.
- **BACKLOG-016**: гибридная аутентификация.
- **BACKLOG-026**: стандартизация структуры.
- **BACKLOG-029**: AD интеграция + RBAC.
- **BACKLOG-030**: архивация данных.

---

## [1.0.0-2.1.0] — до 2026-09-01

- Обнаружение, классификация, WebUI, Linux-агент.

---

**Актуально на:** 22.09.2026
**Текущая версия:** v3.13.16
**Следующая цель:** v3.0.0 (release)