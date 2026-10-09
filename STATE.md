> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 05.10.2026
**Текущая версия:** v3.13.35
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) — все 4 части выполнены (v3.13.29–v3.13.32) + контракт bucket (v3.13.35). Тестовый стенд автоматизирован (v3.13.34): healthcheck, чистый запуск `run-tests.sh all`, версии образов 3.13.34. Далее — 53.3-fs-regress, затем 53.4a–53.4e (WebUI-редизайн Dovetail-style, до GitHub-пакета).

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.3-test-stand-fix (автоматический запуск E2E-стенда + версии) — выполнен |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_53_3_test_stand_fix_report.md` (v3.13.34) |
| Следующий шаг | 53.3-fs-regress (ручной регресс FS после 53.1b/53.2), затем 53.4a (WebUI-редизайн, этап 1) |
| Открытые вопросы к архитектору | 1) BUG-123 (сбор прав Windows) — Блок 6.5; 2) BUG-125 (MANAGER_URL); 3) BUG-130 (backoff); 4) BUG-135 (BOM в JSON); 5) TEST-NOTE-10.8 (2 legacy WebUI-теста требуют непустую БД) — отдельный день; 6) когда делаем документацию масштабирования — отдельным днём (53.4? v3.1.0?) |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | до v3.12.0 | *(см. предыдущие STATE)* |
| 42.1-42.4 | Админ-руководство | — | ✅ |
| 43-44 | Блок 1 + AD-контейнер | v3.13.3-8 | `day_43_*`, `day_44_*` |
| 45 (тест) | Мастер-сессия Блок 2 (Auth/RBAC) | v3.13.8 | `STATE_TEST_SESSION.md` |
| 45 (fix1) | Fix-спринт №1: Auth/RBAC | **v3.13.9** | `day_45_fix_sprint_report.md` |
| 46 (fix2) | Fix-спринт №2: middleware BUG-048b | **v3.13.10** | — |
| 46 (fix3) | Fix-спринт №2: ENV-ключи Findings | **v3.13.11** | `day_46_report.md` |
| 46 (fix3.5) | Fix-спринт №3: OCR, HTTP-retry, Luhn, dedup | **v3.13.12** | `day_46.5_fix_sprint_3_report.md` |
| 46.6-46.7 (fix4) | Fix-спринт №4: OCR-секция + Presidio ru+en | **v3.13.13** | `day_46.7_fix_sprint_4_report.md` |
| 46.8 (fix5) | Fix-спринт №5: url-over-email, OCR-markup, spaCy noise, credentials | **v3.13.14** | `day_46.8_fix_sprint_5_report.md` |
| 46.9 (fix6) | Fix-спринт №6: url-over-email (line_text), аббревиатуры, uk_nhs | **v3.13.15** | `day_46.9_fix_sprint_6_report.md` |
| 46.10 (fix7) | Fix-спринт №7: url = домен email (BUG-075) | **v3.13.16** | `day_46.10_fix_sprint_7_report.md` |
| 47 (test) | Мастер-сессия: Блок 3 (Scanner deep) — **ЗАКРЫТ** | — | ✅ |
| 47.2 (test) | Мастер-сессия: **Блок 8 (Мониторинг) — ЗАКРЫТ** | v3.13.16 | ✅ |
| 47.3 (bug077) | BUG-077: bounding_box=None для OCR + fallback | **v3.13.17** | `day_47.3_fix_bug077_report.md` |
| 47.4 (bug077 diag) | BUG-077 diag: Manager дефолтил bbox (H3) | **v3.13.18** | `day_47.4_bug077_diag_report.md` |
| 47.5 (BACKLOG-086) | Встроенные OCR-фрагменты в БД | **v3.13.19** | `day_47.5_backlog086_embed_fragments_report.md` |
| 47.6 (BUG-080/081) | Reliability сканера: heartbeat backoff + graceful shutdown | **v3.13.20** | `day_47.6_backlog080_081_scanner_reliability_report.md` |
| 47.7 (BUG-086) | Masking контекстов (_CONTEXT_PATTERNS) | **v3.13.21** | `day_47.7_fix_bug086_mask_context_report.md` |
| 48 (Блок 5, п.2.3) | Фильтры/пагинация/аудит/экспорт WebUI | **v3.13.22** | `day_48_block5_webui_filters_report.md` |
| 48.1 (BUG-094) | «BUG-087» аудит reveal: ложное срабатывание | **v3.13.23** | `day_48.1_bug087_audit_user_report.md` |
| 48.2 (BUG-095) | Аудит аутентификации и управления пользователями | **v3.13.24** | `day_48.2_bug095_auth_audit_report.md` |
| 48.3 (BUG-096/096b/097) | `/false-positives` 500, устаревшие E2E, зависшие задания | **v3.13.25** | `day_48.3_bug096_097_report.md` |
| 49 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, reset review, FP-пагинация, FP `file_path` | **v3.13.26** | `day_49_bug098_101_report.md` |
| 50 (BUG-102) | Retention + sweep падали на Mapper[Finding] ... 'User' | **v3.13.27** | `day_50_bug102_celery_mapper_report.md` |
| **51 (Блок 9)** | **Фикс-спринт Блок 9 (Безопасность)** — 10 BUG | **v3.13.28** | `block9_fix_sprint_v31328_report.md` |
| **52 (Блок 6)** | **Блок 6 (Агенты): Windows + Linux + S3 + MinIO** | **v3.13.28** | `block6_agents_full_report.md` |
| **53.1a (BACKLOG-097 ч.1)** | **Manager: `ScanTask.source_type` + S3/MinIO-ресурсы, миграция 006** | **v3.13.29** | `day_53_1a_report.md` |
| **53.1b (BACKLOG-097 ч.2)** | **Scanner: фабрика коннекторов + `_text_scanner.py` + boto3** | **v3.13.30** | `day_53_1b_report.md` |
| **53.2 (BACKLOG-097 ч.3)** | **Scanner: S3LineConnector (streaming, ENV-секреты, OCR/документы)** | **v3.13.31** | `day_53_2_report.md` |
| **53.3 (BACKLOG-097 ч.4)** | **E2E на MinIO + WebUI-форма S3 + docs** | **v3.13.32** | `day_53_3_report.md` |
| **53.3-fix-s3-bucket** | **`S3LineConnector`: bucket только из `scan_config`; BACKLOG-103 заведён** | **v3.13.35** | `day_53_3_fix_s3_bucket_report.md` |
| **53.3-test-stand-fix** | **Тестовый стенд: healthcheck, авто-очистка, версии 3.13.34** | **v3.13.34** | `day_53_3_test_stand_fix_report.md` |

---

## 🔴 Открытые проблемы

### 🔴 Критичные (v3.0.0 / v3.1.0)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| **BUG-117** | Manager не маскирует контексты сам (defense-in-depth) | 📋 v3.0.0 hotfix | 🔴 |
| **BUG-118** | Auth middleware держит 2 соединения → потолок 15 | 📋 v3.1.0 | 🔴 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM (UTF-8 BOM) | 📋 v3.1.0 | 🟡 |
| **BUG-123** | Windows-агент: сбор прав = 0 (2 бага) | 📋 Блок 6.5 | 🟡 |
| **BUG-130** | Linux-агент: retry без backoff при ошибке отправки прав | 📋 v3.1.0 | 🟡 |
| **BACKLOG-044** | `/metrics` публичный | 📋 v3.0.0 production | 🟡 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | Статус |
|----|----------|--------|
| BUG-121 | README Windows-агента: неверный SACL | 📋 v3.1.0 |
| BUG-122 | Linux-агент: unit-файл не portable | ✅ fixed v3.13.28 |
| BUG-124 | `docker-compose.s3.yml` конфликт по `container_name` | 📋 v3.1.0 |
| BUG-125 | Linux-агент: `MANAGER_URL` env игнорируется | 📋 v3.1.0 |
| BUG-126 | S3-агент: `verify_ssl` строковый, не bool | 📋 v3.1.0 |
| BUG-127 | Windows-агент: «Manager недоступен?» при отправке прав | 📋 вместе с BUG-123 |
| BUG-128 | Кириллица в логах (UTF-8 vs PowerShell 5.1) | 📋 док |
| BUG-129 | Windows-агент: шум от собственного чтения Security Log | 📋 v3.1.0 |
| BUG-131 | WSL → Manager: `localhost:8000` терялся | ✅ само-исправился |
| BUG-132 | S3-агент не переустанавливает соединение после перезагрузки Docker | 🟢 v3.1.0 |
| BUG-134 | `mc.exe` без alias → файл в локальную папку (не баг DCAP) | 🟢 док |
| **BUG-136** | `decode_text_bytes`: cp1251-ветка была недостижима | ✅ **fixed v3.13.31** |
| **BACKLOG-103** | `S3LineConnector`/`S3Connector`: fallback на config-секреты (политика TASK-018 — только ENV) | 📋 **v3.1.0** |
| BACKLOG-093 | **Редизайн WebUI (Dovetail-style, `DESIGN.md`)** | 📋 **v3.0.0, 53.4a–53.4e, до GitHub-пакета** |
| BACKLOG-094 | WebUI/Manager не пересобирается автоматически при `up -d` | 📋 v3.0.0 |
| BACKLOG-046 | Полный E2E-прогон на CI | 📋 v3.0.0 |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | 📋 v3.0.0 |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует с живым сканером | 📋 v3.0.0 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит основной стек | 📋 v3.0.0 |
| TEST-NOTE-10.1 | Alembic из PowerShell уходит в SQLite | 📋 док |
| TEST-NOTE-10.2 | Артефакты E2E-сканеров накапливаются (101+) | 📋 бэклог |
| TEST-NOTE-10.3 | Дубли секций в `scan_config` старых FS-ресурсов | 📋 бэклог |
| TEST-NOTE-10.4 | BUG-136 меняет поведение FS-пути (cp1251 теперь декодируется) | ⏳ 53.3-fs-regress |
| TEST-NOTE-10.5 | Smoke FS в 53.1b был слабый (1 файл) | ⏳ 53.3-fs-regress |
| TEST-NOTE-10.6 | `docker-compose.test.yml`: `manager_test` стартует раньше готовности PostgreSQL → нужен `restart` | ✅ **fixed v3.13.34** (healthcheck + `--wait`) |
| TEST-NOTE-10.7 | `postgres_test_data` — персистентный том: копит pending-задачи, E2E виснет (нужен `down -v`) | ✅ **fixed v3.13.34** (`run-tests.sh all`: `down -v` + `up --wait`) |
| TEST-NOTE-10.8 | 2 legacy-теста WebUI ждут непустую таблицу findings (`X-Total-Count != "0"`) | 📋 тесты (вне ТЗ 53.3-test-stand-fix) |

---

## 🎯 Ключевые решения

**S3-коннектор сканера (BACKLOG-097, v3.13.29–31):**
- Части 1–4 закрыты: Manager (`source_type`, S3-ресурсы, миграция 006), Scanner (фабрика + `_text_scanner.py` + boto3), `S3LineConnector` (streaming, ENV-секреты, OCR/документы), E2E + WebUI-форма + docs.
- `ScanTask.source_type` (`filesystem | s3 | minio`) — явный, а не угадывание по префиксу пути.
- `minio` трактуется как `s3`; различие только в `endpoint`.
- Уникальность ресурсов — по `(path, type)` (BUG-059).
- **Секреты S3 в `scan_config` не пишутся** — только ENV (`S3_ACCESS_KEY` / `S3_SECRET_KEY`), политика TASK-018.
- **`endpoint` — вариант B** (53.3, v3.13.32): query при создании ресурса → иначе `S3_DEFAULT_ENDPOINT` → иначе 400. Хардкод `host.docker.internal:9000` удалён.
- **Рекурсия S3 — всегда**, без опции отключения (защита от пропуска вложенных объектов).
- **BUG-136** (cp1251 strict-decoding) закрыт в 53.2; подтверждён на живых данных MinIO.
- Часть 4 закрыта (53.3, v3.13.32): `tests/e2e/test_s3_e2e.py`, форма S3/MinIO в WebUI (REST `POST /api/resources`), `.env.example`, `docs/admin-guide/06-scanner.md` §8.
- **Контракт bucket** (53.3-fix, v3.13.35): bucket — **только** из `scan_config.connector.s3.bucket`; `path` (`s3://bucket/prefix/`) даёт лишь суффикс префикса, bucket из path игнорируется. Сравнение `netloc != bucket` и ложный WARNING удалены (53.3-fix), fallback на config-секреты вынесен в BACKLOG-103 (v3.1.0).

**WebUI-редизайн (BACKLOG-093, v3.0.0, 53.4a–53.4e):**
- **Стиль — Dovetail** (`DESIGN.md`): тёмный command-center, Inter + JetBrains Mono, `#6798ff` единственный акцент, 8px радиусы, zero-shadow, grid-wireframe.
- **Dark-only** (`theme.js` удаляется, light — в бэклог).
- **Font Awesome остаётся**, цвета/размеры под палитру; переход на stroke-SVG — в бэклог.
- **Chart.js — монохром + `#6798ff`** (без семантических цветов).
- **Grid-wireframe везде** (`body::before` в `base.html`).
- **Шрифты — локально** в `webui/static/vendor/fonts/` (CDN запрещён; кодер скачивает через `curl`).
- **CSS — новые файлы** (`tokens.css`, `components.css`, `grid-wireframe.css`); `main.css` остаётся для страничной специфики.
- **5 под-дней:** 53.4a (токены + base + компоненты), 53.4b (login/dashboard/resources/findings), 53.4c (finding_detail/catalog/audit/scanners/access), 53.4d (roles/users/settings/footer/графики), 53.4e (полировка + скриншоты в `docs/ui-screenshots/` + `docs/DESIGN.md`).
- **Условие GitHub-пакета:** 53.4a–53.4e закрыты, старая тема не осталась нигде.

**Агенты (Блок 6, v3.13.28):**
- **Windows-агент:** служба `DCAPAuditAgent` (Automatic), Security Log через `wevtutil`.
- **Linux-агент:** WSL 2 (Ubuntu 22.04), systemd-user, `watchdog`.
- **S3-агент:** MinIO (нативный), seed-логи, BUG-120 fixed.
- **BUG-122 fixed:** systemd-unit portable.

**Безопасность (Блок 9, v3.13.28):**
- mTLS strict → `CERT_REQUIRED` (BUG-108).
- CRL enforce на 2 уровнях: TLS + middleware (BUG-107).
- Volume PKI: `./certs:/app/certs:ro` (BUG-105).
- Machine-endpoints: mTLS до `_is_public` (BUG-106).
- MetricsMiddleware — outermost + нормализация endpoint (BUG-103).
- Reveal при ошибке → 409 + аудит (BUG-110).
- Rotate keys: пересчёт fingerprint + dedup (BUG-116).
- SQLAlchemy pinned `==2.0.54` (регресс).

---

## 📁 Последние использованные файлы

### День 53.3-test-stand-fix — автоматический стенд (v3.13.34)
- `docker-compose.test.yml` — healthcheck `manager_test` (`/api/health`) и `webui_test` (`/health`), `webui_test` ждёт `service_healthy`
- `scripts/run-tests.sh` — режимы `stand` и `all` (`down -v` + `up -d --wait`), fallback для Compose без `--wait`
- `docker-compose.yml` / `docker-compose.s3.yml` — теги образов и in-container `VERSION` на `${VERSION:-3.13.34}`
- `docs/testing.md` — автоматический запуск, требования к сканеру (ключи `FINDINGS_*`), известные ограничения

### День 53.3-fix — bucket только из scan_config (v3.13.35)
- `scanner/connectors/s3_line_connector.py` — убрано сравнение `parsed.netloc != self._bucket` и ложный WARNING; docstring `scan_path`.
- `tests/unit/test_s3_line_connector_v31331.py` — +3 теста (bucket из config, нет bucket-WARNING, fallback prefix).
- `docs/admin-guide/06-scanner.md` §8.1 — контракт bucket/prefix.
- `ROADMAP.md` — BACKLOG-103 (v3.1.0).

### День 53.3 — E2E на MinIO + форма S3/MinIO в WebUI (v3.13.32)
- `tests/e2e/test_s3_e2e.py` — NEW, полный живой цикл S3 (маркеры `e2e`/`requires_manager`/`requires_minio`).
- `manager/src/api/resources.py` — вариант B: query → `S3_DEFAULT_ENDPOINT` → 400.
- `webui/templates/resources.html` — типы `filesystem`/`s3`/`minio`, блок `#s3-fields`, REST `POST /api/resources`.
- `tests/unit/test_s3_resource_v31329.py` — 22 теста (endpoint/env/400).
- `pyproject.toml` — маркер `requires_minio`.
- `.env.example` — секция `SCANNER: S3/MinIO`.
- `docs/admin-guide/06-scanner.md` — §8 «S3/MinIO-сканирование», ENV-таблица, troubleshooting.

### День 53.2 — S3LineConnector (v3.13.31)
- `scanner/connectors/s3_line_connector.py` — NEW, построчный S3/MinIO-коннектор.
- `scanner/connectors/_text_scanner.py` — BUG-136 fix (`decode_text_bytes`).
- `scanner/connectors/factory.py` — регистрация `s3` / `minio`.
- `scanner/src/managed_scanner.py` — `_current_source_type`, `_current_scan_config`, `_parent_of_path`.
- `scanner/connectors/s3_connector.py` — ENV-секреты.
- `tests/unit/test_s3_line_connector_v31331.py` — 16 тестов.
- `tests/unit/test_decode_text_cp1251_v31331.py` — 5 тестов.
- `tests/unit/test_factory_v31330.py` — обновлён.

### День 53.1b — Scanner ядро (v3.13.30)
- `scanner/connectors/_text_scanner.py` — NEW, 5 функций.
- `scanner/connectors/factory.py` — NEW, реестр коннекторов.
- `scanner/connectors/filesystem.py` — рефакторинг.
- `scanner/src/config_loader.py` — `S3ConnectorConfig` + `ConnectorConfig.s3`.
- `scanner/src/managed_scanner.py` — `source_type` из payload.
- `scanner/requirements.txt` — `boto3`.

### День 53.1a — Manager (v3.13.29)
- `manager/src/db/migrations/versions/006_add_source_type.py` — NEW.
- `manager/src/db/models.py` — `ScanTask.source_type`.
- `manager/src/api/resources.py` — S3/MinIO-ресурсы.
- `manager/src/api/scanner.py` — `source_type` в payload.
- `tests/unit/test_s3_resource_v31329.py` — 19 тестов.

### Тесты
- `tests/unit/` — **430 passed** (с 53.3-fix).
- `tests/e2e/` — **53 passed, 7 skipped** (стенд `docker-compose.test.yml`, чистая БД, живой MinIO + Scanner).

---

## 📌 Рекомендации архитектору

1. **Следующий день — 53.3-fs-regress** (после закрытия 53.3): ручной прогон FS-пути по чек-листу из `STATE_TEST_SESSION.md` (12 пунктов). Особое внимание — cp1251-файлы (BUG-136).
2. **Затем — 53.4a–53.4e** (WebUI-редизайн Dovetail-style). ТЗ на 53.4a готовится к моменту получения отчёта по 53.3.
3. **BUG-135** (BOM в JSON S3-агента) — фикс в v3.1.0.
4. **BUG-123** (сбор прав Windows) — Блок 6.5 (52.2).
5. **Linux-агент — дотест** (метрики `:9102` из WSL, сквозной поток после restart, BUG-130) — 52.1.
6. **Rate-limit** — увеличить до 10000 для тестов через `.env` (TEST-NOTE-6.10).

---

**Актуально на:** 04.10.2026
**Версия:** v3.13.35
**Следующий шаг:** 53.3-fs-regress → 53.4a (WebUI-редизайн, этап 1) → 53.4b–53.4e → 55 (GitHub-пакет)