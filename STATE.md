> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 10.10.2026
**Текущая версия:** v3.13.38
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) закрыт полностью (v3.13.29–v3.13.32 + v3.13.35). Тестовый стенд автоматизирован (v3.13.34). BUG-137 закрыт (v3.13.36). **WebUI-редизайн, этап 1 (53.4a) закрыт (v3.13.37):** тёмная тема Dovetail (токены + base + компоненты + grid-wireframe), локальные Inter + JetBrains Mono, `theme.js` удалён. **Фиксы 53.4a-доп (v3.13.38) закрыты:** BUG-139 (webfonts FA — иконки монохромные), BUG-138 (finding_detail — пустая Console), BUG-140 (reveal: toggle + кэш, без дублей в аудите, `.reveal-block` вместо `bg-light`). Далее — 53.4b–53.4e (редизайн страниц), затем GitHub-пакет.

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.4a-доп (WebUI-фиксы BUG-138/139/140: webfonts + finding_detail) — выполнен |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_53_4a_add_webui_fixes_report.md` (v3.13.38) |
| Следующий шаг | 53.4b (WebUI-редизайн, этап 2: login, dashboard, resources, findings) |
| Открытые вопросы к архитектору | 1) `unicode-range` в `inter.css` / `jetbrains-mono.css` — кириллица (v3.1.0); 2) `DESIGN.md` — временно в корне, перенести в `docs/` в 53.4e; 3) Chart.js-палитра — 53.4d; 4) BUG-123 (сбор прав Windows) — Блок 6.5; 5) BUG-125/130/135 — v3.1.0; 6) TEST-NOTE-10.8 (2 legacy WebUI-теста) — отдельный день |

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
| **53.3-test-stand-fix** | **Тестовый стенд: healthcheck, авто-очистка, версии 3.13.34** | **v3.13.34** | `day_53_3_test_stand_fix_report.md` |
| **53.3-fix-s3-bucket** | **`S3LineConnector`: bucket только из `scan_config`; BACKLOG-103 заведён** | **v3.13.35** | `day_53_3_fix_s3_bucket_report.md` |
| **53.3-fs-regress-ocr-diag (BUG-137)** | **Гонка temp-файлов `OCREngine`; фикс + WARNING при потере + тест** | **v3.13.36 (hotfix)** | `bug_137_ocr_race_report.md` |
| **53.3-fs-regress** | **Ручной регресс FS после 53.1b/53.2 (cp1251, PII, OCR)** | **(эталон v3.13.34)** | ✅ 07.10.2026 |
| **B (ручной FS-регресс после BUG-137)** | **12/12 пунктов чек-листа** | **v3.13.36** | ✅ 09.10.2026 |
| **53.4a (BACKLOG-093, этап 1/5)** | **WebUI-редизайн Dovetail: токены + base + компоненты + grid-wireframe; шрифты; `theme.js` удалён** | **v3.13.37** | `day_53_4a_report.md` |
| **53.4a-доп (BACKLOG-093)** | **WebUI-фиксы: BUG-139 (webfonts FA 6.4.0), BUG-138 (Console/finding_detail), BUG-140 (reveal toggle + кэш, `.reveal-block`)** | **v3.13.38** | `day_53_4a_add_webui_fixes_report.md` |

---

## 🔴 Открытые проблемы

### 🔴 Критичные (v3.0.0 / v3.1.0)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| **BUG-117** | Manager не маскирует контексты сам (defense-in-depth) | 📋 v3.0.0 hotfix (день 56) | 🔴 |
| **BUG-118** | Auth middleware держит 2 соединения → потолок 15 | 📋 v3.1.0 | 🔴 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM (UTF-8 BOM) | 📋 v3.1.0 | 🟡 |
| **BUG-123** | Windows-агент: сбор прав = 0 (2 бага) | 📋 Блок 6.5 (52.2) | 🟡 |
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
| **BUG-137** | **OCR: тихая потеря находок PNG при параллели (гонка temp)** | ✅ **fixed v3.13.36** |
| **BUG-138** | **finding_detail.js: onerror с HTML в атрибуте → SyntaxError в Console** | ✅ **fixed v3.13.38** |
| **BUG-139** | **webfonts/ пуст → иконки sidebar как цветные emoji** | ✅ **fixed v3.13.38** |
| **BUG-140** | **reveal: лишний для image_region, перезапись #fragment, спам аудита, дубль line/match, bg-light** | ✅ **fixed v3.13.38** |
| **BACKLOG-103** | `S3LineConnector`/`S3Connector`: fallback на config-секреты (политика TASK-018 — только ENV) | 📋 **v3.1.0** |
| BACKLOG-093 | **Редизайн WebUI (Dovetail-style, `DESIGN.md`)** | 🔄 **53.4a ✅ (v3.13.37), 53.4a-доп ✅ (v3.13.38), 53.4b–53.4e 📋** |
| BACKLOG-094 | WebUI/Manager не пересобирается автоматически при `up -d` | 📋 v3.0.0 |
| BACKLOG-046 | Полный E2E-прогон на CI | 📋 v3.0.0 |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | 📋 v3.0.0 |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует с живым сканером | 📋 v3.0.0 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит основной стек | 📋 v3.0.0 |
| TEST-NOTE-10.1 | Alembic из PowerShell уходит в SQLite | 📋 док |
| TEST-NOTE-10.2 | Артефакты E2E-сканеров накапливаются (101+) | 📋 бэклог |
| TEST-NOTE-10.3 | Дубли секций в `scan_config` старых FS-ресурсов | 📋 бэклог |
| TEST-NOTE-10.4 | BUG-136 меняет поведение FS-пути (cp1251 теперь декодируется) | ✅ закрыто в B (12/12) |
| TEST-NOTE-10.5 | Smoke FS в 53.1b был слабый (1 файл) | ✅ закрыто в 53.3-fs-regress |
| TEST-NOTE-10.6 | `docker-compose.test.yml`: `manager_test` стартует раньше готовности PostgreSQL | ✅ **fixed v3.13.34** (healthcheck + `--wait`) |
| TEST-NOTE-10.7 | `postgres_test_data` — персистентный том копит pending-задачи | ✅ **fixed v3.13.34** (`run-tests.sh all`) |
| TEST-NOTE-10.8 | 2 legacy-теста WebUI ждут непустую таблицу findings | 📋 отдельный день |
| TEST-NOTE-10.15 | ~40 % FP Presidio (url, organization, us_driver_license, nrp, person="Дата") — качество детекции | 📋 отдельный день |
| **ТЗ BACKLOG-093** | **`unicode-range` в `inter.css` / `jetbrains-mono.css` — кириллица** | 📋 v3.1.0 |
| **ТЗ BACKLOG-093** | **Chart.js-палитра под Dovetail** | 📋 53.4d |
| **ТЗ BACKLOG-093** | **`DESIGN.md` — временно в корне; перенести в `docs/`** | 📋 53.4e |

---

## 🎯 Ключевые решения

**S3-коннектор сканера (BACKLOG-097, v3.13.29–35):**
- Части 1–4 закрыты + контракт bucket (53.3-fix, v3.13.35).
- `ScanTask.source_type` (`filesystem | s3 | minio`) — явный.
- `minio` трактуется как `s3`; различие только в `endpoint`.
- Уникальность ресурсов — по `(path, type)` (BUG-059).
- **Секреты S3 в `scan_config` не пишутся** — только ENV (`S3_ACCESS_KEY` / `S3_SECRET_KEY`), политика TASK-018.
- **`endpoint` — вариант B** (53.3, v3.13.32): query → `S3_DEFAULT_ENDPOINT` → 400.
- **Рекурсия S3 — всегда**, без опции отключения.
- **BUG-136** (cp1251 strict-decoding) закрыт в 53.2.
- **Контракт bucket** (53.3-fix, v3.13.35): bucket — **только** из `scan_config.connector.s3.bucket`; `path` (`s3://bucket/prefix/`) даёт только суффикс префикса.
- Fallback на config-секреты → BACKLOG-103 (v3.1.0).

**WebUI-редизайн (BACKLOG-093, v3.0.0, 53.4a–53.4e):**
- **Стиль — Dovetail** (`DESIGN.md`): тёмный command-center, Inter + JetBrains Mono, `#6798ff` — единственный акцент, 8px радиусы, zero-shadow, grid-wireframe.
- **Dark-only** (`theme.js` удалён, light — BACKLOG-102).
- **Font Awesome остаётся** (переход на stroke-SVG — BACKLOG-101).
- **Chart.js — монохром + `#6798ff`** (53.4d).
- **Grid-wireframe везде** (`body::before` в `base.html`).
- **Шрифты — локально** в `webui/static/vendor/fonts/` (CDN запрещён).
- **CSS — новые файлы** (`tokens.css`, `base.css`, `components.css`, `grid-wireframe.css`); `main.css` — только `.app/.main-content/.page-content/.text-*` + медиа-запросы.
- **`components/*.css`** — не переписываем, подхватывают legacy-алиасы из `tokens.css`.
- **5 под-дней:** 53.4a (✅), 53.4a-доп (✅, 62-минутный фикс-спринт), 53.4b (login/dashboard/resources/findings), 53.4c (finding_detail/catalog/audit/scanners/access), 53.4d (roles/users/settings/footer/графики), 53.4e (полировка + скриншоты в `docs/ui-screenshots/` + `docs/DESIGN.md`).
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

### День 53.4a — WebUI-редизайн, этап 1 (v3.13.37)
- `webui/static/vendor/fonts/` — NEW: `inter.woff2` (352 KB), `inter.css`, `jetbrains-mono.woff2` (40 KB), `jetbrains-mono.css`.
- `webui/static/css/tokens.css` — NEW, дизайн-токены Dovetail (dark-only) + legacy-алиасы (171 строка).
- `webui/static/css/base.css` — NEW, глобальные стили/шрифты/скроллбар (73 строки).
- `webui/static/css/components.css` — NEW, override Bootstrap (288 строк).
- `webui/static/css/grid-wireframe.css` — NEW, blueprint-сетка `body::before` (34 строки).
- `webui/templates/base.html`, `webui/templates/login.html` — `data-theme="dark"`, новые `<link>`, без `theme.js`.
- `webui/static/css/main.css` — обновлённые `@import`, без дублей глобальных правил и `.btn*`.
- Удалены: `webui/static/css/variables.css`, `webui/static/css/theme-dark.css`, `webui/static/js/theme.js`.
- `DESIGN.md` — коммит `34e3383` (референс Dovetail, **в корне**; перенести в `docs/` в 53.4e).

### День 53.4a-доп — WebUI-фиксы BUG-138/139/140 (v3.13.38)
- `webui/static/vendor/webfonts/` — NEW: FA 6.4.0 (`fa-solid-900.woff2` 150 KB, `fa-regular-400.woff2` 24 KB, `fa-brands-400.woff2` 108 KB + ttf) — `fontawesome.min.css` уже ссылался на `../webfonts/`.
- `webui/static/js/finding_detail.js` — BUG-138: `onerror="..."` убран, обработка через `addEventListener('error')`; BUG-140: кнопка reveal скрыта для `image_region`, toggle + кэш (`cachedReveal`), подсветка match внутри line (`<mark>`), без дублей.
- `webui/static/css/findings.css` — `.reveal-block` + `mark` (вместо `bg-light`, тёмная тема).
- `.env`/`.env.example`/compose — `VERSION=3.13.38`.

### B (ручной FS-регресс после BUG-137, v3.13.36)
- Тест-корпус: `E:\projects\dcap-system\temp\fs-regress\` — 10 файлов.
- Чек-лист 12/12: PII/credentials/cp1251 (BUG-136)/PDF/DOCX/XLSX/OCR-параллельно (BUG-137)/catalog/дедуп/FP/source_type.
- TEST-NOTE-10.14 (files_scanned=10 вместо 9 — 2 PNG в корпусе), TEST-NOTE-10.15 (~40% ложных — Presidio en), TEST-NOTE-10.16 (`person` не маскируется — связано с BUG-117).

### День 53.3-fs-regress-ocr-diag (BUG-137, v3.13.36)
- `scanner/utils/ocr_engine.py` — `_work_dir`-изоляция temp (uuid-подпапка на движок).
- `scanner/classifiers/pii_classifier.py` — WARNING при потере OCR-ответа.
- `scanner/connectors/_text_scanner.py` — WARNING при пустом документ-OCR с `error`.
- `tests/unit/test_ocr_worker_race_v31336.py` — NEW, 3 прошли.

### День 53.3-test-stand-fix (v3.13.34)
- `docker-compose.test.yml` — healthcheck `manager_test`/`webui_test` + `depends_on: service_healthy`.
- `scripts/run-tests.sh` — режимы `stand`/`all` (`down -v` + `up -d --wait`).
- `docker-compose.yml` / `docker-compose.s3.yml` — теги образов и in-container `VERSION` на `${VERSION:-3.13.34}` (сейчас → 3.13.37).
- `docs/testing.md` — автоматический запуск, требования.

### День 53.3-fix — bucket только из scan_config (v3.13.35)
- `scanner/connectors/s3_line_connector.py` — убрано сравнение `parsed.netloc != self._bucket` и ложный WARNING.
- `tests/unit/test_s3_line_connector_v31331.py` — +3 теста.
- `docs/admin-guide/06-scanner.md` §8.1 — контракт bucket/prefix.

### День 53.3 — E2E на MinIO + форма S3/MinIO в WebUI (v3.13.32)
- `tests/e2e/test_s3_e2e.py` — NEW, полный живой цикл S3.
- `manager/src/api/resources.py` — вариант B endpoint.
- `webui/templates/resources.html` — типы `filesystem`/`s3`/`minio`, блок `#s3-fields`.
- `tests/unit/test_s3_resource_v31329.py` — 22 теста.
- `.env.example` — секция `SCANNER: S3/MinIO`.
- `docs/admin-guide/06-scanner.md` — §8 «S3/MinIO-сканирование».

### День 53.2 — S3LineConnector (v3.13.31)
- `scanner/connectors/s3_line_connector.py` — NEW, построчный S3/MinIO-коннектор.
- `scanner/connectors/_text_scanner.py` — BUG-136 fix.
- `scanner/connectors/factory.py` — регистрация `s3`/`minio`.
- `scanner/src/managed_scanner.py` — `_current_source_type`, `_current_scan_config`, `_parent_of_path`.
- `tests/unit/test_s3_line_connector_v31331.py` — 16 тестов.
- `tests/unit/test_decode_text_cp1251_v31331.py` — 5 тестов.

### День 53.1b — Scanner ядро (v3.13.30)
- `scanner/connectors/_text_scanner.py` — NEW, 5 функций.
- `scanner/connectors/factory.py` — NEW, реестр коннекторов.
- `scanner/connectors/filesystem.py` — рефакторинг.
- `scanner/src/config_loader.py` — `S3ConnectorConfig`.
- `scanner/requirements.txt` — `boto3`.

### День 53.1a — Manager (v3.13.29)
- `manager/src/db/migrations/versions/006_add_source_type.py` — NEW.
- `manager/src/db/models.py` — `ScanTask.source_type`.
- `manager/src/api/resources.py` — S3/MinIO-ресурсы.
- `manager/src/api/scanner.py` — `source_type` в payload.
- `tests/unit/test_s3_resource_v31329.py` — 19 тестов.

### Тесты
- `tests/unit/` — **433 passed** (с v3.13.36).
- `tests/e2e/` — **53 passed, 7 skipped** (эталон 53.3). В повторных прогонах 4 теста
  (`test_full_scan_cycle`, `test_s3_scan_full_cycle`, `test_real_scanner_end_to_end`,
  `test_scanner_heartbeat`) флакают без живого сканера на `:18000`.

---

## 📌 Рекомендации архитектору

1. **Следующий день — 53.4b** (WebUI-редизайн, этап 2: login, dashboard, resources, findings). ТЗ — `prompts/tz/day_53_4b_webui_pages_1.md`.
2. **Затем** — 53.4c (finding_detail/catalog/audit/scanners/access), 53.4d (roles/users/settings/footer/графики), 53.4e (полировка + скриншоты + `docs/DESIGN.md`).
3. **После 53.4e — 55** (GitHub-пакет), **затем 56** (BUG-117 hotfix), **57** (релиз v3.0.0).
4. **Chore после 53.4a:** расширить `unicode-range` в `inter.css` / `jetbrains-mono.css` до кириллицы (`U+0400-04FF`) — v3.1.0.
5. **DESIGN.md** — перенести из корня в `docs/` (`git mv`) в 53.4e.
6. **BUG-135** (BOM в JSON S3-агента) — v3.1.0.
7. **BUG-123** (сбор прав Windows) — Блок 6.5 (52.2).
8. **Linux-агент — дотест** (метрики `:9102` из WSL, сквозной поток после restart, BUG-130) — 52.1.
9. **Rate-limit** — увеличить до 10000 для тестов через `.env` (TEST-NOTE-6.10).

---

**Актуально на:** 10.10.2026
**Версия:** v3.13.38
**Следующий шаг:** 53.4b (WebUI-редизайн, этап 2) → 53.4c → 53.4d → 53.4e → 55 (GitHub-пакет)