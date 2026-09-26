# 📓 CHANGELOG.md — История версий DCAP

> Формат — по мотивам [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
> Версионирование — SemVer.

---

## [Unreleased] — v3.0.0 (release)

**Осталось:** Блок 5 (WebUI), Блок 7 (Retention), Блок 6 (Агенты), GitHub-пакет.

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