> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 13.10.2026
**Текущая версия:** v3.14.0
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) закрыт полностью (v3.13.29–v3.13.32 + v3.13.35). BUG-137 закрыт (v3.13.36). WebUI-редизайн этап 1 (53.4a) + фиксы (53.4a-доп) закрыты (v3.13.37/38). 53.4a-доп3 (hotfix backend-critical) закрыт (v3.13.39): BUG-201/202/214/223/181/168/142/148. 53.4a-доп4 (fonts) закрыт (v3.13.40): BUG-212 — кириллица в font-face. unit **460 passed**, e2e **53/7** (эталон). 53.4a-доп5 (hotfix + sync) закрыт (v3.13.41): BUG-150 — DELETE → **204** (миграция 007: 11 FK ON DELETE CASCADE); BUG-149 — S3-скан 0 files (bucket-фолбэк + legacy WebUI→connector.s3); BACKLOG-121 (.btn-primary white); BACKLOG-119 (badge /login); ARCHITECTURE.md синхронизирован. **🆕 53.4b (WebUI-редизайн, этап 2) закрыт (v3.14.0)**: frontend RBAC (sidebar/router/кнопки, 403 → «/», ошибки на русском); sidebar responsive (рельсы 769–1024, off-canvas ≤768 + гамбургер + оверлей); Chart.js адаптив (maintainAspectRatio:false, legendPosition, обёртки height:300px); модалки ≤480px full-width; BUG-142 KPI «Ресурсов» через total_resources; datetime.js (UTC→local) в /audit, /scanners, /findings/{id}, /false-positives, дашборд; BUG-205/206/207 findings (placeholder, ✓/✗ Dovetail, статусы на русском); BUG-146 login mobile; BUG-203 KPI «Алертов»; фикс битого false_positives.js (HEAD: дубль `},` — страница не работала). WebUI-образ пересобран (dcap/webui:3.14.0), менеджер пере-тегирован, /api/health = 3.14.0, 9 скриншотов (1920/768/393). **Следующий шаг — 53.4c (WebUI, этап 3).**

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.4b (WebUI-редизайн, этап 2: login/dashboard/findings + RBAC frontend + Responsive) — **завершён** |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_53_4b_webui_pages_1_report.md` (v3.14.0) |
| Следующий шаг | **53.4c** (WebUI, этап 3 — вероятно фиксы, оставшиеся после 53.4b) |
| Затем | 53.4c → 53.4d → 53.4e → 55 → 57 |
| Открытых BUG | ~87 (закрыто в 53.4b: BUG-213, 228/233, 229, 232, 216, 142, 141, 205/206/207, 146, 203/204) |
| Открытых BACKLOG | ~39 (в 53.4b: BACKLOG-119/121 пропущены — уже закрыты в доп5) |
| ТЗ собраны | 3 файла в `prompts/tz/` (53.4c/d/e) |
| Открытые вопросы к архитектору | 1) Формальные грамматики для DLP (обсуждено, приоритет v3.1.0); 2) `DESIGN.md` — `git mv` в `docs/` в 53.4e; 3) Chart.js палитра — 53.4d; 4) E2E-артефакты — очистка в 53.4e; 5) BUG-223 (frontend детали события) — отложен в 53.4c; 6) false_positives.js в HEAD был битым (`},` дубль) — починено в 53.4b |

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
| **53.4a-доп4 (fonts, BUG-212)** | **unicode-range кириллицы в inter.css/jetbrains-mono.css + замена jetbrains-mono.woff2 на официальный (v2.304 variable, кириллица) + OFL.txt** | **v3.13.40** | `day_53_4a_add4_fonts_report.md` |
| **53.4a-доп5 (hotfix + sync)** | **BUG-150 (CASCADE 007, DELETE→204), BUG-149 (S3 bucket-фолбэк из path + legacy WebUI→connector.s3), BACKLOG-121 (.btn-primary white), BACKLOG-119 (badge /login), sync ARCHITECTURE.md** | **v3.13.41** | `day_53_4a_add5_hotfix_and_sync_report.md` |
| **53.4b (WebUI, этап 2)** | **Frontend RBAC (sidebar/роутер/кнопки, 403→«/», ошибки RU) + sidebar/гамбургер (769–1024 рельсы, ≤768 off-canvas) + Chart.js адаптив + модалки ≤480px + BUG-142 KPI (total_resources) + datetime.js (UTC→local) + findings (BUG-205/206/207) + login (BUG-146) + KPI «Алертов» (BUG-203) + фикс false_positives.js** | **v3.14.0** | `day_53_4b_webui_pages_1_report.md` |
| **Мастер-сессия v3.13.38** | **WebUI 1–17 + RBAC-прогон — найдено ~100 BUG + ~40 BACKLOG; пакет из 4 ТЗ собран** | — | `STATE_TEST_SESSION.md` (12.10.2026) |

---

## 🔴 Открытые проблемы (накопительно, топ-30)

### 🔴🔴 Критичные (блокеры v3.0.0)

| ID | Проблема | Статус | ТЗ |
|----|----------|--------|-----|
| **BUG-201** | Смена пароля не работает (пароль не меняется, UI говорит OK) | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-202** | Audit-log пишется при провале транзакции | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-212** | Inter / JetBrains Mono не применяются к кириллице | ✅ **v3.13.40** | 53.4a-доп4 |
| **BUG-214** | `/api/audit` доступен viewer / scanner | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-223** | `GET /api/audit/{id}` — 404 (metadata недоступна) | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-181** | Нет аудита ролей (`role_created/updated/deleted`) | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-168** | Системные роли редактируются (RBAC риск) | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-142** | Dashboard KPI «Ресурсов» = 0 | ✅ **v3.13.39** | 53.4a-доп3 + 53.4b |
| **BUG-148** | Scanner не читает `.env` (S3-секреты) | ✅ **v3.13.39** | 53.4a-доп3 |
| **BUG-150** | `DELETE /api/resources/{id}` → 500 (9+ FK NO ACTION) | ✅ **v3.13.41** | 53.4a-доп5 |
| **BUG-149** | S3-скан возвращал 0 files (WebUI-ресурсы без `connector.s3`) | ✅ **v3.13.41** | 53.4a-доп5 |
| **BUG-232** | Модалки ломаются на mobile (393px) | ✅ **v3.14.0** | 53.4b |
| **BUG-233** | Гамбургер `☰` не работает | ✅ **v3.14.0** | 53.4b |
| **BUG-213** | Frontend RBAC не работает (sidebar + страницы) | ✅ **v3.14.0** | 53.4b |
| **BUG-172** | Нет `permissions` в модели RBAC (кастомные роли бесполезны) | 📋 | архитектура |
| **BUG-156** | `auth_source='ad'` без привязки к AD | 📋 | 53.4d |
| **BUG-162** | Форма редактирования не грузит roles/is_active → лок-аут | 📋 | 53.4d |
| **BUG-117** | Manager не маскирует контексты сам | 📋 | v3.0.0 hotfix (день 56) |
| **BUG-118** | Auth middleware держит 2 соединения | 📋 | v3.1.0 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM | 📋 | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | 📋 | production |

### 🔴 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-141 | Время в UTC, не local — ✅ v3.14.0 (datetime.js) | 53.4b |
| BUG-146 | Login: надписи наезжают — ✅ v3.14.0 (mobile flex) | 53.4b |
| BUG-147 | `/resources` limit=100 | 53.4c |
| BUG-151 | `/resources` (viewer): кнопки видны — ✅ v3.14.0 (Add — admin, Scan — scanner+) | 53.4b |
| BUG-152 | `/access` — заглушка | 53.4c |
| BUG-153 | Ресурс 133: `type=FILESYSTEM` uppercase | 53.4c |
| BUG-155 | `<input type="password">` вне `<form>` | 53.4d |
| BUG-157 | Подсказка про пароль — неверна для создания | 53.4d |
| BUG-158 | Нет выбора ролей при создании | 53.4d |
| BUG-159 | «Активен» снят по умолчанию | 53.4d |
| BUG-160 | `[object Object]` — 422 не разворачивается | 53.4d |
| BUG-161 | Чекбокс не переключается | 53.4d |
| BUG-164 | Подтверждение удаления: `#17`, `localhost` | 53.4d |
| BUG-165 | Ошибки API на английском + alert-danger — ✅ v3.14.0 (errorToRussian; стиль alert — 53.4d) | 53.4b |
| BUG-166 | E2E-артефакты в `/users` | 53.4e |
| BUG-167 | `/roles` — AD-группа `viewer` = `—` | 53.4d |
| BUG-170 | Счётчик ролей включает заблокированных | 53.4d |
| BUG-171 | Badge `системная` без tooltip | 53.4d |
| BUG-173 | Валидация `name` роли отсутствует | 53.4d |
| BUG-174 | `test group` (с пробелом) сохранён | 53.4d |
| BUG-176 | `ARCHITECTURE.md` устарел — ✅ закрыт (v3.13.41, sync 10 пунктов; PUT/DELETE `/roles` отражены) | docs ✅ |
| BUG-177 | Success-alert не в стиле Dovetail | 53.4d |
| BUG-178 | Placeholder `DCAP_Admins` как значение | 53.4d |
| BUG-179 | «Маппинг AD-группы» — англицизм | 53.4d |
| BUG-180 | Подтверждение удаления `#5` | 53.4d |
| BUG-182 | `/audit` — нет фильтра по роли | 53.4c |
| BUG-183 | `/audit` — мусорные `test_event*` | 53.4c |
| BUG-184 | `/audit` — плоский список типов | 53.4c |
| BUG-185 | Футер — UTC или local? | 53.4d |
| BUG-186 | Rate-limit не логируется | 53.4c |
| BUG-187 | Смена `auth_mode` из UI → лок-аут | 53.4d |
| BUG-188 | «Информация» о пользователе — не на месте | 53.4d |
| BUG-189 | «Аудит-события» → «События аудита»; TTL без пояснений | 53.4d |
| BUG-190 | «Куда архивируется?» — нет информации | 53.4d |
| BUG-191 | «Dry-run» без пояснения | 53.4d |
| BUG-194 | password вне `<form>` (settings) | 53.4d |
| BUG-195 | Нет подсказок о требованиях к паролю | 53.4d |
| BUG-196 | Валидация совпадения пароля не клиентская | 53.4d |
| BUG-197 | «Сменить пароль» не на месте | 53.4d |
| BUG-198 | Toast `Пароль изменён` не в стиле Dovetail | 53.4d |
| BUG-199 | Счётчики retention = 0 | 53.4d |
| BUG-200 | Секция «Информация» — путаница | 53.4d |
| BUG-203 | `/` — KPI `Алертов: 0` — неясно — ✅ v3.14.0 (реализован + «из N» у агентов) | 53.4b |
| BUG-204 | `/` — секция `Находки по ресурсам` пуста — ✅ v3.14.0 (строится из /api/findings) | 53.4b |
| BUG-205 | `/findings` — placeholder overflow — ✅ v3.14.0 | 53.4c |
| BUG-206 | `/findings` — `✓/✗` не Dovetail — ✅ v3.14.0 | 53.4c |
| BUG-207 | `/findings` — badge `new` не переведён — ✅ v3.14.0 | 53.4c |
| BUG-208 | `/scanners` — heartbeat UTC — ✅ v3.14.0 (formatDate) | 53.4c |
| BUG-209 | `/scanners` — «Заданий» без уточнения | 53.4c |
| BUG-210 | `/catalog` — 703 находки без пагинации | 53.4c |
| BUG-211 | `/resources` — статус `✔` непонятен | 53.4c |
| BUG-215 | `/api/resources` — 200 для viewer | 53.4c |
| BUG-216 | RBAC-ошибки на английском — ✅ v3.14.0 (errorToRussian + 403→«/») | 53.4b |
| BUG-217 | `/findings/{id}` — viewer видит `✓/✗` — ✅ v3.14.0 (только Auditor+) | 53.4b |
| BUG-218 | `/scanners` — read-only | 53.4c |
| BUG-219 | `/resources` — `+Добавить` видна — ✅ v3.14.0 (admin) | 53.4b |
| BUG-222 | Sidebar: viewer видит больше, чем auditor — ✅ v3.14.0 (RBAC-фильтр) | 53.4b |
| BUG-224 | `/users`, `/settings` — открываются под auditor/viewer — ✅ v3.14.0 (nav скрыт, 403→«/») | 53.4b |
| BUG-225 | `/settings` — TTL `—` под auditor — ✅ v3.14.0 (недоступно не-админам) | 53.4b |
| BUG-226 | Модалка `+Добавить ресурс` — черновик | 53.4c |
| BUG-227 | Sidebar scanner — `Аудит` виден — ✅ v3.14.0 (RBAC-фильтр) | 53.4b |
| BUG-228 | Sidebar не адаптируется — ✅ v3.14.0 (рельсы 769–1024, ≤768 off-canvas) | 53.4e |
| BUG-229 | Chart.js не адаптируется — ✅ v3.14.0 (maintainAspectRatio:false + legendPosition) | 53.4d |
| BUG-230 | Таблицы не адаптируются | 53.4e |
| BUG-231 | Гамбургер — работает? — ✅ v3.14.0 (toggle + оверлей) | 53.4e |
| BUG-234 | `/users` на mobile — обрезка | 53.4e |

### 🟢 Мелкие

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-104 | favicon.ico отсутствует | 53.4e |
| BUG-126 | CSP | 53.4e |
| BUG-193 | Console — 4 проблемы | 53.4e |
| BUG-220 | Reveal аудит | ✅ закрыт |
| BACKLOG-121 | `.btn-primary` white filled — ✅ закрыт (v3.13.41) | 53.4a-доп5 ✅ |
| BACKLOG-119 | Badge режима /login — ✅ закрыт (v3.13.41, только windows_integrated) | 53.4a-доп5 ✅ |
| BACKLOG-129 | FK без CASCADE — ✅ закрыт (v3.13.41, миграция 007) | 53.4a-доп5 ✅ |
| BACKLOG-128 | Нет кнопки удаления ресурса в UI | 53.4c |
| BUG-221 | Reveal — странные email | v3.1.0 |
| BUG-235 | SIEM-страницы 404 (BACKLOG-072) | v3.1.0 |
| BACKLOG-101 | stroke-SVG иконки | v3.1.0 |
| BACKLOG-102 | light-тема | v3.1.0 |
| BACKLOG-103 | S3 fallback на config-секреты | v3.1.0 |
| BACKLOG-131 | «Вкл/Выкл» → «Активен/Заблокирован» | 53.4d |
| BACKLOG-132 | «Источник» → «Тип учётки» | 53.4d |
| BACKLOG-133 | Bootstrap перебивает base.css | 53.4b |
| BACKLOG-134 | «Привязать AD-пользователя» | v3.1.0 |
| BACKLOG-135 | Подтверждение пароля (`/users`) | 53.4d |
| BACKLOG-136 | Placeholder'ы | 53.4d |
| BACKLOG-137 | Валидация username | 53.4d |
| BACKLOG-138 | Унификация модалок | 53.4e |
| BACKLOG-139 | Единый стиль обязательных полей | 53.4d |
| BACKLOG-140 | `from?get&nocache=` | 53.4b |
| BACKLOG-141 | Self-edit username disabled | 53.4d |
| BACKLOG-142 | auth_source read-only в edit | 53.4d |
| BACKLOG-143 | «Сбросить пароль» | v3.1.0 |
| BACKLOG-144 | Показать created_at / last_login | 53.4d |
| BACKLOG-145 | Frontend-защита себя/последнего админа | 53.4d |
| BACKLOG-146 | Нормализация badge ролей | 53.4d |
| BACKLOG-147 | Кнопка «Сбросить» в фильтрах | 53.4d |
| BACKLOG-148 | Удаление кастомных ролей (backend + UI) | v3.1.0 |
| BACKLOG-149 | «Удалить» в модалке edit | 53.4d |
| BACKLOG-150 | Локализация описаний системных ролей | 53.4d |
| BACKLOG-151 | Toast с именем роли | 53.4d |
| BACKLOG-152 | Визуальное различие системных/кастомных | 53.4d |
| BACKLOG-153 | Единый toast/alert-компонент Dovetail | 53.4d |
| BACKLOG-154 | Chart.js — цвета/локализация | 53.4d |
| BACKLOG-155 | `/scanners` — массовое удаление inactive | 53.4c |

---

## 🎯 Ключевые решения (обновление)

**Мастер-сессия v3.13.38:**
- **Найдено:** ~100 BUG + ~40 BACKLOG.
- **Собрано:** 4 ТЗ (53.4a-доп3, 53.4a-доп4, 53.4b, 53.4c/d/e).
- **Приоритет:** hotfix (53.4a-доп3/4) → 53.4b → 53.4c/d/e → 55 → 57.
- **Backend:** работает (96%), критичные дыры (BUG-201/202/214/223/181) закрыты в v3.13.39.
- **Frontend:** требует редизайна + RBAC + Responsive.
- **Дизайн:** 53.4a — цвета, сетка (да, v3.13.37), шрифты — да (v3.13.40, BUG-212).
- **Шрифты (v3.13.40):** Inter variable + JetBrains Mono variable с кириллицей; `unicode-range` расширен (Latin + Cyrillic base/ext + Latin Extended Additional).

**53.4a-доп5 (v3.13.41):**
- **BUG-150:** ON DELETE CASCADE миграцией `007_add_cascade_deletes` (11 FK) — `DELETE /api/resources/{id}` → 204; для SQLite (dev) — ручное удаление связанных записей в `delete_resource`. `audit_logs`/`findings_old`/`reviewed_by` не тронуты.
- **BUG-149:** S3-скан 0 files — `S3LineConnector` берёт bucket из path при отсутствии в config (config приоритетнее); legacy WebUI-эндпоинты (`/api/tasks/create`, `/api/resources/create`) строят `connector.s3` (endpoint: `S3_DEFAULT_ENDPOINT` → `host.docker.internal:9000`); DEBUG-логи `list_objects_v2`, таймауты re-raise.
- **BACKLOG-121:** `.btn-primary` — white filled `#ffffff`, возврат к DESIGN.md (отклонение 53.4a отменено).
- **BACKLOG-119:** badge режима на /login — только `windows_integrated`; `hybrid` в коде остаётся до v3.1.0 (B.1).
- **ARCHITECTURE.md:** синхронизирован с кодом (чек-лист 10 пунктов); unit **460 passed**; VERSION=3.13.41.
- **⚠️ Блокер окружения:** Docker-демон завис (диск C: почти полон) — живой E2E по S3 и 204 на контейнере закрыты кодом/unit/PG-верификацией, подтверждение на контейнере — после перезапуска Docker Desktop.

**53.4b (v3.14.0):**
- **BUG-213 (frontend RBAC):** `ROLES_PAGES`/`RBAC`/`applyRBACNav`/`initSession`/`window.whenSessionReady`; sidebar фильтруется по ролям; **403 → редирект на `/`** (api.js, guard pathname); кнопки по ролям (export/bulk/статусы — Auditor+, «Добавить ресурс» — admin, «Сканировать» — scanner+).
- **BUG-228/233 (sidebar/гамбургер):** рельсы 769–1024px (width 60), off-canvas drawer ≤768px (`left:-250px` → `.open`), оверлей `#sidebarOverlay`, `#mobileSidebarToggle`; desktop — collapsed + localStorage.
- **BUG-229 (Chart.js):** `maintainAspectRatio:false`, обёртки `<div style="height:300px">`, `legendPosition()` (bottom ≤768 / right).
- **BUG-232 (модалки ≤480px):** full-width, border-radius 0, скролл body (`max-height:calc(100vh - 200px)`).
- **BUG-216:** `errorToRussian()` в auth.js (единая для api.js и /login); применяется ко всем ошибкам API, входу, экспорту.
- **BUG-142:** KPI «Ресурсов» = `s.total_resources` из `/api/audit/stats` (бэкенд v3.13.39; /api/resources?limit=1 не нужен).
- **BUG-141:** новый `datetime.js` (`parseUtc`/`formatDate`) — UTC без 'Z' → локальная timezone; применён в /audit, /scanners, /findings/{id}, /false-positives, дашборд.
- **BUG-205/206/207:** placeholder overflow; кнопки `finding-act` (иконка + подпись, `.act-label` скрыт ≤480px); статусы на русском (новое/подтверждено/ложное/архив/дубликат).
- **BUG-146:** login mobile — `overflow-y:auto`, `align-items:flex-start`, max-width 100%.
- **BUG-203/204:** KPI «Алертов» = `/api/access/alerts/stats`; диаграмма «Находки по ресурсам» (из /api/findings) — строится.
- **Фикс:** `false_positives.js` в HEAD был битым (дубль `},`) — страница падала; починено.
- **Верификация:** WebUI-образ пересобран `dcap/webui:3.14.0`, менеджер пере-тегирован `3.14.0` без пересборки; `/api/health`=3.14.0; CDP-пробы (RBAC-viewer/auditor, гамбургер, оверлей, 4 чарта, KPI) + 9 скриншотов (login/dashboard/findings × 1920/768/393).

**Формальные грамматики для DLP (обсуждено 11.10.2026):**
- **CFG-парсеры** (JSON/XML/CSV) — **v3.1.0**.
- **AST** (tree-sitter) — **v3.1.0**.
- **Post-Processor** (NER + relations) — **v3.1.0**.
- **ML** (embeddings, MinHash) — **v3.2.0**.
- **«Символическая логика»** / **«онтографы»** — **не нужно** (переоценено).

---

## 📌 Рекомендации архитектору

1. **Следующий день — 53.4c** (WebUI, этап 3: BUG-147/152/153/182/183/184/186/209/210/211/215/218/226, BACKLOG-128; frontend BUG-223). ТЗ — `prompts/tz/day_53_4cde_webui_pages_2_5.md`.
2. **Затем — 53.4d/e**. ТЗ — `prompts/tz/day_53_4cde_webui_pages_2_5.md`.
3. **Затем — 55** (GitHub-пакет) → **56** (BUG-117 hotfix) → **57** (релиз).
4. **ARCHITECTURE.md в переработке** — патчи передать из отчётов: 53.4a-доп3 (with_audit/аудит-роуты/роли), 53.4a-доп4 (шрифты), 53.4b (RBAC-матрица страниц, datetime.js, version 3.14.0).
5. **Формальные грамматики** — зафиксировать в бэклоге v3.1.0.
6. **BUG-123/125/130/135, BACKLOG-103/134/143/148** — v3.1.0 (агенты).
7. **E2E-артефакты** — очистка в 53.4e (BUG-166, BUG-183, TEST-NOTE-10.2).
8. **BUG-117** — Manager не маскирует контексты сам (hotfix день 56, блокер v3.0.0).

---

**Актуально на:** 13.10.2026
**Версия:** v3.14.0
**Следующий шаг:** 53.4c → 53.4d/e → 55 → 57