> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 14.10.2026
**Текущая версия:** v3.14.1
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) закрыт полностью. WebUI-редизайн этапы 1–5 (53.4a, 53.4a-доп, доп3, доп4, доп5, 53.4b/c/d/e) закрыты — **REDESIGN COMPLETE (v3.14.1)**. Unit **460 passed**, e2e **53/7** (эталон). **Следующий шаг — 53.4e-grafana (тестирование Grafana + RBAC, BACKLOG-307).**

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.4e (WebUI-редизайн, этап 5) — **завершён** |
| Статус дня | ✅ Выполнено (53.4c/d/e, v3.14.1) |
| Последний принятый отчёт | `day_53_4cde_webui_pages_2_5_report.md` (v3.14.1) |
| Следующий шаг | **53.4e-grafana** (тестирование Grafana + RBAC, BACKLOG-307) |
| Затем | 53.4e-grafana → 55 → 57 |
| Открытых BUG | ~11 (закрыто в 53.4c/d/e: ~50) |
| Открытых BACKLOG | ~50 (BACKLOG-131…314 — v3.1.0/бэклог) |
| ТЗ собраны | 1 файл в `prompts/tz/` (53.4c/d/e — архивируется) |
| Открытые вопросы к архитектору | 1) Формальные грамматики (v3.1.0); 2) `DESIGN.md` — перенесён в `docs/` (53.4e); 3) E2E-артефакты — очищены (53.4e); 4) Grafana RBAC — Auth Proxy (53.4e-grafana), OAuth (v3.1.0); 5) BACKLOG-101/102 — отложены |

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
| **53.4a-доп (BACKLOG-093)** | **WebUI-фиксы: BUG-139 (webfonts FA 6.4.0), BUG-138 (Console/finding_detail), BUG-140 (reveal toggle + кэш)** | **v3.13.38** | `day_53_4a_add_webui_fixes_report.md` |
| **53.4a-доп3 (hotfix)** | **Backend-critical hotfix: BUG-201/202/214/223/181/168/142/148** | **v3.13.39** | `day_53_4a_add3_hotfix_report.md` |
| **53.4a-доп4 (fonts, BUG-212)** | **unicode-range кириллицы + замена jetbrains-mono.woff2 (v2.304 variable) + OFL.txt** | **v3.13.40** | `day_53_4a_add4_fonts_report.md` |
| **53.4a-доп5 (hotfix + sync)** | **BUG-150/149 + BACKLOG-121/119 + sync ARCHITECTURE.md** | **v3.13.41** | `day_53_4a_add5_hotfix_and_sync_report.md` |
| **53.4b (BACKLOG-093, этап 2/5)** | **WebUI-редизайн: login, dashboard, resources, findings + RBAC frontend + Responsive** | **v3.14.0** | `day_53_4b_webui_pages_1_report.md` |
| **53.4c (BACKLOG-093, этап 3/5)** | **Страницы: `/catalog` (пагинация), `/resources` (форма Filesystem/MinIO, статусы, удаление), `/access` (замена заглушки), `/audit` (фильтр по роли, metadata), `/scanners` (массовое удаление inactive), `/findings`+`/false-positives` (FP по умолчанию скрыты)** | **v3.14.1** | `day_53_4cde_webui_pages_2_5_report.md` |
| **53.4d (BACKLOG-093, этап 4/5)** | **Роли/пользователи/настройки (RU, `domain_user`, self-защита, пароль+подтверждение, BUG-170 активные роли, `GET /api/retention/stats`), футер (BUG-185), монохромная палитра Chart.js, Dovetail-тост** | **v3.14.1** | `day_53_4cde_webui_pages_2_5_report.md` |
| **53.4e (BACKLOG-093, этап 5/5)** | **Полировка: favicon (BUG-104), CSP + security-заголовки + вынос inline `<script>` (BUG-126), унификация модалок (BACKLOG-138), `DESIGN.md → docs/DESIGN.md`, 39 скриншотов, sync docs, E2E-очистка (BUG-166/183) — REDESIGN COMPLETE** | **v3.14.1** | `day_53_4cde_webui_pages_2_5_report.md` |
| **Мастер-сессия v3.13.38** | **WebUI 1–17 + RBAC-прогон — найдено ~100 BUG + ~40 BACKLOG; пакет из 4 ТЗ собран** | — | `STATE_TEST_SESSION.md` (12.10.2026) |

---

## 🔴 Открытые проблемы (накопительно, топ-30)

### 🔴🔴 Критичные (блокеры v3.0.0)

| ID | Проблема | Статус | ТЗ |
|----|----------|--------|-----|
| **BUG-147** | Frontend `/resources` — limit=100 | ✅ **v3.14.1** | 53.4c |
| **BUG-151** | `/resources` (viewer): кнопки видны | ✅ **v3.14.0** | 53.4b |
| **BUG-152** | `/access` — заглушка | ✅ **v3.14.1** | 53.4c |
| **BUG-153** | Ресурс 133: `type=FILESYSTEM` uppercase | ✅ **v3.14.1** | 53.4c |
| **BUG-232** | Модалки ломаются на mobile | ✅ **v3.14.0** | 53.4b |
| **BUG-233** | Гамбургер `☰` не работает | ✅ **v3.14.0** | 53.4b |
| **BUG-213** | Frontend RBAC не работает | ✅ **v3.14.0** | 53.4b |
| **BUG-172** | Нет `permissions` в RBAC | 📋 | архитектура |
| **BUG-156** | `auth_source='ad'` без привязки к AD | ✅ **v3.14.1** | 53.4d |
| **BUG-162** | Форма редактирования → лок-аут | ✅ **v3.14.1** | 53.4d |
| **BUG-117** | Manager не маскирует контексты сам | 📋 | день 56 |
| **BUG-118** | Auth middleware держит 2 соединения | 📋 | v3.1.0 |
| **BUG-135** | S3-агент: BOM | 📋 | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | 📋 | production |
| **TEST-NOTE-8.1…8.6** | Grafana: тестирование | 📋 | 53.4e |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC (Auth Proxy) | 📋 | 53.4e |

### 🔴 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-147 | `/resources` limit=100 | ✅ 53.4c |
| BUG-150 | DELETE resource 500 | ✅ 53.4a-доп5 |
| BUG-155 | password вне `<form>` | ✅ 53.4d |
| BUG-157…200 | (см. STATE_TEST_SESSION) | ✅ 53.4c/d |
| BUG-203/204/205/206/207/208/216 | Dashboard/Findings/RBAC | ✅ 53.4b |
| BUG-209…234 | (см. STATE_TEST_SESSION) | ✅ 53.4c/d/e |
| BACKLOG-131…155 | (см. STATE_TEST_SESSION) | ✅ 53.4c/d/e |

### 🟢 Мелкие

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-104 | favicon.ico отсутствует | ✅ 53.4e |
| BUG-126 | CSP | ✅ 53.4e |
| BUG-193 | Console — 4 проблемы | ✅ 53.4e |
| BUG-230 | Таблицы не адаптируются | ✅ 53.4e |
| BUG-234 | `/users` на mobile — обрезка | ✅ 53.4e |
| BACKLOG-138 | Унификация модалок | ✅ 53.4e |
| BUG-221 | Reveal — странные email | v3.1.0 |
| BUG-235 | SIEM-страницы 404 | v3.1.0 |
| BACKLOG-101/102/103 | (см. STATE_TEST_SESSION; 101/102 — отложены) | v3.1.0 |

---

## 🎯 Ключевые решения (обновление)

**Мастер-сессия v3.13.38:**
- **Найдено:** ~100 BUG + ~40 BACKLOG.
- **Собрано:** 4 ТЗ (53.4a-доп3, 53.4a-доп4, 53.4b, 53.4c/d/e).
- **Приоритет:** hotfix → 53.4b → 53.4c/d/e → 55 → 57.

**Закрыто в 53.4a-доп3/4/5 (v3.13.39–41):**
- BUG-201/202/214/223/181/168/142/148 — backend-critical.
- BUG-212 — шрифты кириллицы.
- BUG-150/149, BACKLOG-121/119 — hotfix + sync ARCHITECTURE.md.

**Закрыто в 53.4b (v3.14.0):**
- BUG-213 — Frontend RBAC.
- BUG-228/233 — Sidebar + гамбургер.
- BUG-229 — Chart.js адаптив.
- BUG-232 — Модалки mobile.
- BUG-216 — Ошибки RBAC на русском.
- BUG-141 — UTC → local (`datetime.js`).
- BUG-142 — KPI «Ресурсов».
- BUG-203/204 — Dashboard KPI.
- BUG-205/206/207 — Findings UI.
- BUG-146 — Login mobile.

**Закрыто в 53.4c/d/e (v3.14.1):**
- 53.4c — `/catalog`, `/resources`, `/access`, `/audit`, `/scanners`, `/false-positives`, `/findings` (RU-статусы, пагинация, фильтр по роли, metadata-модалка, форма Filesystem/MinIO, массовое удаление inactive, замена заглушки `/access`).
- 53.4d — роли/пользователи/настройки (RU, `domain_user` BUG-156, self-защита, пароль+подтверждение, `auth_mode` read-only BUG-187, BUG-170 активные роли, `GET /api/retention/stats` BUG-199), футер BUG-185, монохромная палитра Chart.js, Dovetail-тост.
- 53.4e — favicon (BUG-104), CSP + security-заголовки + вынос inline `<script>` (BUG-126), унификация модалок (BACKLOG-138), `DESIGN.md → docs/DESIGN.md`, 39 скриншотов, E2E-очистка (BUG-166/183).
- **REDESIGN COMPLETE.** Образы пересобраны (manager/webui 3.14.1), `/api/health`=3.14.1.

**Grafana (решения 14.10.2026):**
- **RBAC:** Auth Proxy (`X-WEBAUTH-USER`) — 53.4e.
- **Маппинг:** admin→Admin, auditor→Editor, scanner/viewer→Viewer.
- **OAuth** — v3.1.0 (BACKLOG-310…314).
- **Тестирование:** TEST-NOTE-8.1…8.6 — 53.4e.
- **Хотфикс:** `53.4e-grafana-hotfix` — если найдены баги.

**Формальные грамматики для DLP (обсуждено 11.10.2026):**
- **CFG-парсеры** (JSON/XML/CSV) — **v3.1.0**.
- **AST** (tree-sitter) — **v3.1.0**.
- **Post-Processor** (NER + relations) — **v3.1.0**.
- **ML** (embeddings, MinHash) — **v3.2.0**.
- **«Символическая логика»** / **«онтографы»** — **не нужно**.

---

## 📌 Рекомендации архитектору

1. **Следующий день — 53.4e-grafana** (тестирование Grafana TEST-NOTE-8.1…8.6 + RBAC Auth Proxy BACKLOG-307).
2. **Затем — 55** (GitHub-пакет) → **56** (BUG-117 hotfix) → **57** (релиз).
3. **ARCHITECTURE.md** — синхронизирован (v3.14.1: 53.4b–e, `docs/DESIGN.md`, `docs/ui-screenshots/`).
4. **Формальные грамматики** — зафиксировать в бэклоге v3.1.0.
5. **BUG-123/125/130/135** — v3.1.0 (агенты).
6. **E2E-артефакты** — ✅ очищены в 53.4e (BUG-166, BUG-183, TEST-NOTE-10.2).
7. **13 направлений v3.1.0** — зафиксированы в ROADMAP.md (BACKLOG-156…314).
8. **BACKLOG-101 (stroke-SVG) / BACKLOG-102 (light-тема)** — отложены по решению пользователя.

---

**Актуально на:** 14.10.2026
**Версия:** v3.14.1
**Следующий шаг:** 53.4e-grafana → 55 → 56 → 57