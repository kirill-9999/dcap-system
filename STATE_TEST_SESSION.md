# 🧪 DCAP Test Session — Состояние на 14.10.2026

> **Мастер-сессия ручного тестирования DCAP v3.13.38**
> Блок 1 (Smoke) — ✅
> Блок 2 (Auth/RBAC) — ✅
> Блок 3 (Scanner deep) — ✅
> Блок 4 (Findings API) — ✅
> Блок 5 (WebUI) — ⚠️ (блоки 1–11 из 17)
> Блок 6 (Агенты) — ⚠️ 5/6 под-блоков
> Блок 7 (Retention) — ✅
> Блок 8 (Мониторинг) — ⚠️ частично (Prometheus ✅, Grafana ❌ — тестирование + RBAC в 53.4e)
> Блок 9 (Безопасность) — ✅
> 53.1a–53.3-fix (BACKLOG-097) — ✅
> 53.4a (WebUI-редизайн, этап 1) — ✅
> 53.4a-доп (BUG-138/139/140) — ✅
> 53.4a-доп3 (hotfix backend-critical) — ✅ v3.13.39
> 53.4a-доп4 (шрифты) — ✅ v3.13.40
> 53.4a-доп5 (hotfix + sync) — ✅ v3.13.41
> 53.4b (WebUI-редизайн, этап 2) — ✅ v3.14.0
> **WebUI-прогон: блоки 1–11 — ✅ (закрыты 10–12.10.2026)**
> **WebUI-прогон: блоки 12–17 — ⏸️ следующий чат**

---

## 🎯 Текущее состояние

| Параметр | Значение |
|----------|----------|
| **Версия** | v3.14.0 |
| **Целевая версия** | v3.0.0 (релиз) |
| **Пройдено** | Блоки 1–9; 53.1a–53.3; 53.4a; 53.4a-доп; 53.4a-доп3/4/5; 53.4b; **WebUI 1–11** |
| **Следующий блок** | **WebUI 12–17** (Users, Roles, Settings, Console, Network, Responsive) |
| **Auth mode** | hybrid (SPNEGO → JWT fallback) |
| **Контейнеров** | 15 |
| **Сканер** | На хосте, `3.14.0`, `S3_*` ENV — ✅ (BUG-148 закрыт в v3.13.39) |
| **Unit** | **460 passed** |
| **E2E** | **53 passed, 7 skipped** (эталон) |
| **Docker Compose** | v5.5.1 |

---

## 📊 РЕЗУЛЬТАТЫ ТЕСТА WEBUI (блоки 1–11)

### Сводная таблица

| Блок | Задача | Статус | Находки |
|------|--------|--------|---------|
| **1** | База Dovetail (шрифты, цвета, sidebar, grid) | ✅ | — |
| **2** | Login / Auth | ⚠️ | BUG-146, BACKLOG-106/119/120/121 |
| **3** | Dashboard | ✅ | **BUG-142 ✅ FIXED**, **BUG-143 ✅ FIXED** |
| **4** | Findings (список, фильтры, экспорт) | ⚠️ | BACKLOG-107/108/109 |
| **5** | Finding detail (reveal, PATCH, fragment) | ✅ | BACKLOG-110 |
| **6** | Catalog | ⚠️ | BACKLOG-111/112/113/114/115/116 |
| **7** | False positives | ✅ | BACKLOG-117/118 |
| **8** | Resources + scan + MinIO | ⚠️ | BUG-147/148/149/150/151, BACKLOG-122/123/124/125/128/129 |
| **9** | Audit | ✅ | BUG-141 |
| **10** | Access | ❌ | BUG-152, BUG-153 |
| **11** | Scanners | ✅ | BUG-141, BACKLOG-130 |
| **12–17** | Users / Roles / Settings / Console / Network / Responsive | ⏸️ | — |

---

## ✅ ЗАКРЫТО В ЭТОЙ СЕССИИ (10–13.10.2026)

### 53.4a-доп (v3.13.38)

| ID | Название | Дата |
|----|----------|------|
| **BUG-139** | Font Awesome `webfonts/` пусто → иконки-emoji | 10.10.2026 |
| **BUG-138** | `finding_detail.js:137` — `onerror` с HTML внутри атрибута → `SyntaxError` | 10.10.2026 |
| **BUG-140** | Reveal-логика: toggle, скрытие для `image_region`, кэш, устранение дублей, `.reveal-block` | 10.10.2026 |
| **BUG-145** | `/false-positives` — лишняя `},` в `false_positives.js:70` → `SyntaxError` | 11.10.2026 |

### 53.4a-доп3 (v3.13.39)

| ID | Название |
|----|----------|
| **BUG-201** | Смена пароля не работает (пароль не меняется, UI говорит OK) |
| **BUG-202** | Audit-log пишется при провале транзакции |
| **BUG-214** | `/api/audit` доступен viewer / scanner |
| **BUG-223** | `GET /api/audit/{id}` — 404 (metadata недоступна) |
| **BUG-181** | Нет аудита ролей (`role_created/updated/deleted`) |
| **BUG-168** | Системные роли редактируются (RBAC риск) |
| **BUG-142** | Dashboard KPI «Ресурсов» = 0 |
| **BUG-148** | Scanner не читает `.env` (S3-секреты) |

### 53.4a-доп4 (v3.13.40)

| ID | Название |
|----|----------|
| **BUG-212** | Inter / JetBrains Mono не применяются к кириллице |

### 53.4a-доп5 (v3.13.41)

| ID | Название |
|----|----------|
| **BUG-150** | `DELETE /api/resources/{id}` → 500 (FK violation) |
| **BUG-149** | S3LineConnector возвращает 0 files |
| **BACKLOG-121** | `.btn-primary` → white filled |
| **BACKLOG-119** | Убрать hybrid badge из `/login` |
| **BACKLOG-129** | FK без CASCADE (закрыт миграцией 007) |

### 53.4b (v3.14.0)

| ID | Название |
|----|----------|
| **BUG-213** | Frontend RBAC не работает |
| **BUG-228/233** | Sidebar + гамбургер |
| **BUG-229** | Chart.js адаптив |
| **BUG-232** | Модалки на mobile |
| **BUG-216** | Ошибки RBAC на русском |
| **BUG-142** | Dashboard KPI «Ресурсов» (frontend) |
| **BUG-141** | Время UTC → локализовать |
| **BUG-205/206/207** | Findings UI (placeholder, ✓/✗, badge) |
| **BUG-146** | Login наезжает |
| **BUG-203/204** | Dashboard KPI (Алерты, Находки по ресурсам) |
| **BUG-143** | `/api/findings/count → 404` |

### Проверено через DevTools Console (12.10.2026)

- **BUG-142** — Dashboard KPI «Ресурсов» = 0 — **✅ FIXED**.
- **BUG-143** — `/api/findings/count → 404` — **✅ FIXED**.
- **BACKLOG-131** — `/api/audit/{id}` не существует — **✅ FIXED**.
- **BUG-155** — `localStorage['token'] = null` — **❌ НЕ БАГ** (правильный ключ — `dcap_access_token`).

---

## 🔴 ОТКРЫТЫЕ ПРОБЛЕМЫ

### 🔴 Критичные (блокеры v3.0.0)

| ID | Название | Блок | Фаза |
|----|----------|------|------|
| **BUG-147** | Frontend `/resources` — `api.get('/api/resources')` без `limit` → видит 100, MinIO теряется | 8 | 53.4c |
| **BUG-151** | `/resources` (viewer): видны кнопки «Добавить ресурс» и «▶» | 8 | 53.4c |
| **BUG-152** | `/access` — заглушка «Раздел в разработке» | 10 | 53.4c |
| **BUG-153** | Ресурс 133: `type=FILESYSTEM` (uppercase) | 10 | 53.4c |
| **BUG-232** | Модалки ломаются на mobile (393px) | — | 53.4c |
| **BUG-233** | Гамбургер `☰` не работает | — | 53.4c |
| **BUG-213** | Frontend RBAC не работает (sidebar + страницы) | — | ✅ 53.4b |
| **BUG-172** | Нет `permissions` в модели RBAC (кастомные роли бесполезны) | — | архитектура |
| **BUG-156** | `auth_source='ad'` без привязки к AD | — | 53.4d |
| **BUG-162** | Форма редактирования не грузит roles/is_active → лок-аут | — | 53.4d |
| **BUG-117** | Manager не маскирует контексты сам | — | v3.0.0 hotfix (день 56) |
| **BUG-118** | Auth middleware держит 2 соединения | — | v3.1.0 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM | — | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | — | production |

### 🔴 Grafana (блокеры v3.0.0)

| ID | Название | Блок | Фаза |
|----|----------|------|------|
| **TEST-NOTE-8.1…8.6** | Grafana: тестирование (smoke, дашборды, метрики, алерты, RBAC, производительность) | 8 | 53.4e |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC (Auth Proxy) | 8 | 53.4e |

### 🔴 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-141 | Время в UTC, не local | ✅ 53.4b |
| BUG-146 | Login: надписи наезжают | ✅ 53.4b |
| BUG-147 | `/resources` limit=100 | 53.4c |
| BUG-150 | `DELETE /api/resources/{id}` → 500 (FK) | ✅ 53.4a-доп5 |
| BUG-151 | `/resources` (viewer): кнопки видны | 53.4c |
| BUG-152 | `/access` — заглушка | 53.4c |
| BUG-153 | Ресурс 133: `type=FILESYSTEM` uppercase | 53.4c |
| BUG-155 | `<input type="password">` вне `<form>` | 53.4d |
| BUG-156 | `auth_source='ad'` без привязки к AD | 53.4d |
| BUG-157 | Подсказка про пароль — неверна для создания | 53.4d |
| BUG-158 | Нет выбора ролей при создании | 53.4d |
| BUG-159 | «Активен» снят по умолчанию | 53.4d |
| BUG-160 | `[object Object]` — 422 не разворачивается | 53.4d |
| BUG-161 | Чекбокс не переключается | 53.4d |
| BUG-162 | Форма редактирования не грузит roles/is_active → лок-аут | 53.4d |
| BUG-164 | Подтверждение удаления: `#17`, `localhost` | 53.4d |
| BUG-165 | Ошибки API на английском + alert-danger | ✅ 53.4b |
| BUG-166 | E2E-артефакты в `/users` | 53.4e |
| BUG-167 | `/roles` — AD-группа `viewer` = `—` | 53.4d |
| BUG-170 | Счётчик ролей включает заблокированных | 53.4d |
| BUG-171 | Badge `системная` без tooltip | 53.4d |
| BUG-173 | Валидация `name` роли отсутствует | 53.4d |
| BUG-174 | `test group` (с пробелом) сохранён | 53.4d |
| BUG-176 | `ARCHITECTURE.md` устарел (`PUT/DELETE /roles` есть) | ✅ docs |
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
| BUG-203 | `/` — KPI `Алертов: 0` — неясно | ✅ 53.4b |
| BUG-204 | `/` — секция `Находки по ресурсам` пуста | ✅ 53.4b |
| BUG-205 | `/findings` — placeholder overflow | ✅ 53.4b |
| BUG-206 | `/findings` — `✓/✗` не Dovetail | ✅ 53.4b |
| BUG-207 | `/findings` — badge `new` не переведён | ✅ 53.4b |
| BUG-208 | `/scanners` — heartbeat UTC | ✅ 53.4b |
| BUG-209 | `/scanners` — «Заданий» без уточнения | 53.4c |
| BUG-210 | `/catalog` — 703 находки без пагинации | 53.4c |
| BUG-211 | `/resources` — статус `✔` непонятен | 53.4c |
| BUG-215 | `/api/resources` — 200 для viewer | 53.4c |
| BUG-216 | RBAC-ошибки на английском | ✅ 53.4b |
| BUG-217 | `/findings/{id}` — viewer видит `✓/✗` | 53.4c |
| BUG-218 | `/scanners` — read-only | 53.4c |
| BUG-219 | `/resources` — `+Добавить` видна | 53.4c |
| BUG-222 | Sidebar: viewer видит больше, чем auditor | ✅ 53.4b |
| BUG-224 | `/users`, `/settings` — открываются под auditor/viewer | ✅ 53.4b |
| BUG-225 | `/settings` — TTL `—` под auditor | ✅ 53.4b |
| BUG-226 | Модалка `+Добавить ресурс` — черновик | 53.4c |
| BUG-227 | Sidebar scanner — `Аудит` виден | ✅ 53.4b |
| BUG-228 | Sidebar не адаптируется | ✅ 53.4b |
| BUG-229 | Chart.js не адаптируется | ✅ 53.4b |
| BUG-230 | Таблицы не адаптируются | 53.4e |
| BUG-231 | Гамбургер — работает? | 53.4e |
| BUG-234 | `/users` на mobile — обрезка | 53.4e |

### 🟢 Мелкие

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-104 | favicon.ico отсутствует | 53.4e |
| BUG-126 | CSP | 53.4e |
| BUG-193 | Console — 4 проблемы | 53.4e |
| BUG-220 | Reveal аудит | ✅ закрыт |
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

## ✅ ЧТО ПОДТВЕРЖДЕНО РАБОТАЮЩИМ

### Блок 1 (База Dovetail)
- ✅ Шрифты: Inter + JetBrains Mono (кириллица — v3.13.40)
- ✅ Цвета: `#0a0a0a` фон, `#1e1e1e` карточки, `#6798ff` accent
- ✅ Grid-wireframe видна
- ✅ Sidebar: иконки серые (BUG-139 закрыт)
- ✅ `data-theme="dark"`

### Блок 2 (Login / Auth)
- ✅ Тёмная карточка, mode badge, dark carbon кнопка (white filled — 53.4a-доп5)
- ✅ Ошибка входа (тёмный alert) + русский (BUG-216, 53.4b)
- ✅ Logout работает (audit `auth_logout`)
- ✅ viewer не видит админ-разделы (BUG-213, 53.4b)
- ✅ auditor видит reveal

### Блок 3 (Dashboard)
- ✅ KPI «Ресурсов» = 127 (BUG-142 закрыт)
- ✅ KPI «Находок» = 906
- ✅ KPI «Агентов» = 1 из 5
- ✅ KPI «Алертов» = 0 (BUG-203 закрыт, 53.4b)
- ✅ Графики Chart.js отрисовываются (адаптив — 53.4b; палитра — 53.4d)

### Блок 4 (Findings)
- ✅ Список, фильтры (категория через запятую, детектор, фрагмент, задание, статус, тип, severity)
- ✅ Экспорт CSV / JSON
- ✅ Bulk actions (чекбоксы)
- ✅ Статусы на русском (BUG-207, 53.4b)
- ⚠️ BACKLOG-107/108/109

### Блок 5 (Finding detail) — после 53.4a-доп
- ✅ text_line (2043): `<mark>` вокруг match, reveal toggle
- ✅ image_region (2046): PNG, **без кнопки reveal** (BUG-140 закрыт)
- ✅ PATCH: 2046 → confirmed, `reviewed_by=35=auditor`
- ✅ Console: чисто (BUG-138 закрыт)
- ✅ Reveal для credentials (1995): показал реальный Slack-токен

### Блок 6 (Catalog)
- ✅ Дерево раскрывается
- ✅ Поиск `fs-regress` работает
- ✅ Клик на строку → `/findings/{id}`
- ✅ 19 категорий (совпадает с БД)

### Блок 7 (False positives)
- ✅ 2 FP (1987, 2035) с `reviewed_by_username`
- ✅ `file_path` = путь файла (BUG-098 закрыт)
- ✅ Кнопка «Восстановить»
- ✅ Console чисто (BUG-145 закрыт)

### Блок 8 (Resources + scan)
- ✅ 127 ресурсов, создание MinIO (144) — backend ОК
- ✅ Задачи 201–205 созданы
- ✅ RBAC: viewer → 403, scanner → 403 (create), 200 (scan)
- ✅ MinIO-скан: BUG-148/149 закрыты (v3.13.39/41)
- ✅ Delete ресурса: BUG-150 закрыт (v3.13.41)
- ⚠️ Frontend: BUG-147 (limit 100), BUG-151 (viewer-кнопки)

### Блок 8 (Мониторинг)
- ✅ Prometheus targets (6/6 up)
- ✅ Метрики Manager (`:8000/metrics`)
- ✅ Метрики сканера (`:9101`)
- ✅ Метрики агентов (`:9102`, `:9103`)
- ✅ Алерты (Prometheus rules)
- ❌ **Grafana — не тестировалась** (TEST-NOTE-8.1…8.6, 53.4e)
- ❌ **Grafana RBAC — не тестировался** (BACKLOG-307, 53.4e)

### Блок 9 (Audit)
- ✅ 1908 событий, 20 типов
- ✅ Фильтры: Источник, Тип, Пользователь
- ✅ Счётчики, badges
- ✅ Время локализовано (BUG-141, 53.4b)
- ✅ Viewer/scanner → 403 (BUG-214, v3.13.39)
- ✅ Деталь события (BUG-223, v3.13.39)

### Блок 10 (Access)
- ✅ Backend `/api/access/resources` работает (127 ресурсов, `entries_count` для 133 = 84)
- ❌ Frontend — заглушка (BUG-152)

### Блок 11 (Scanners)
- ✅ 1 active (scanner-1, 199 задач), 106 inactive
- ✅ SQL: `1 active`, `106 inactive`
- ✅ Heartbeat локализован (BUG-141, 53.4b)

---

## 🔍 КЛЮЧЕВЫЕ ДИАГНОСТИКИ

### BUG-141 (UTC) — ✅ закрыт 53.4b
**Доказательство:** `GET /api/audit?limit=1` → `"created_at":"2026-10-10T05:35:20.838384"` (без `Z`).
**Решение:** `datetime.js` (`parseUtc`/`formatDate`), применён в `/audit`, `/scanners`, `/findings/{id}`, `/false-positives`, дашборд.

### BUG-147 (limit) — 📋 53.4c
**Доказательство:** Manager `/api/resources` → 100 (default limit), `?limit=200` → 127 (MinIO=1).
**Frontend `resources.html:126`** — `api.get('/api/resources')` **без limit**.
**Фикс:** `api.get('/api/resources', { limit: 1000 })` или пагинация в UI.

### BUG-148 (ENV) — ✅ закрыт v3.13.39
**Решение:** `run_scanner.py` — `load_dotenv()`; `start_scanner.bat` — блок `.env`.

### BUG-150 (500 delete) — ✅ закрыт v3.13.41
**Решение:** Alembic-миграция `007_add_cascade_deletes.py` (11 FK → CASCADE).

### JWT-хранилище (ФИНАЛ)
- **Ключ:** `localStorage['dcap_access_token']` (префикс `dcap_`).
- **Дополнительно:** `localStorage['dcap-sidebar']` — sidebar state.
- **`auth.js`** — корректный.

---

## 🎯 КЛЮЧЕВЫЕ АРХИТЕКТУРНЫЕ РЕШЕНИЯ (приняты в сессии)

### 1. `.btn-primary` → **white filled** (BACKLOG-121) — ✅ закрыто 53.4a-доп5
### 2. `hybrid` auth → **убрать badge** (BACKLOG-119) — ✅ закрыто 53.4a-доп5
### 3. `start_scanner.bat` — **S3-ENV** (BUG-148) — ✅ закрыто v3.13.39
### 4. `delete_resource` — **ON DELETE CASCADE** (BUG-150) — ✅ закрыто 53.4a-доп5
### 5. Grafana RBAC — **Auth Proxy** (BACKLOG-307, 53.4e). **OAuth** — v3.1.0.
### 6. Маппинг ролей Grafana: **admin→Admin, auditor→Editor, scanner/viewer→Viewer**.

---

## 📋 СЛЕДУЮЩИЕ ШАГИ

### Следующий чат (WebUI блоки 12–17)

**Порядок:**
1. **Блок 12 (Users)** — `/users` (admin): CRUD, роли, пароль, GMT, локализация.
2. **Блок 13 (Roles)** — `/roles` (admin): список, создание.
3. **Блок 14 (Settings)** — `/settings` (admin): retention policies.
4. **Блок 15 (Console)** — все страницы: `favicon.ico 404` (BACKLOG-104).
5. **Блок 16 (Network)** — woff2 + API-запросы.
6. **Блок 17 (Responsive 768px)** — sidebar collapse, таблицы.

**После 12–17 — Grafana (53.4e-grafana):**
- TEST-NOTE-8.1…8.6.
- BACKLOG-307 (RBAC через Auth Proxy).
- Хотфикс `53.4e-grafana-hotfix` — если найдены баги.

**Затем:** 53.4c/d/e → 55 (GitHub) → 56 (BUG-117) → 57 (релиз).

### Долгосрочно

- **v3.1.0** — 13 направлений (IoC, специализация, диагностика, экспорт каталога, лёгкий агент, шина, Model Registry, обновление, бэкап, Key Store, регулярки, метрики, OAuth).
- **v3.2.0** — ML, Kafka, Vault, HSM, PITR, macOS.
- **v4.0.0** — Zero-Trust, распределённый Manager.

---

## 🔧 СТЕК

| Компонент | Версия | Статус |
|-----------|--------|--------|
| Manager | `dcap/manager:3.14.0` | healthy |
| WebUI | `dcap/webui:3.14.0` | healthy |
| Celery worker/beat | `dcap/manager:3.14.0` | healthy |
| Postgres | 16-alpine | healthy |
| Redis | 7-alpine | healthy |
| Scanner | v3.14.0 (host) | running |
| MinIO | native `localhost:9000` | running |
| Grafana | `:3000` | ⚠️ не тестировалась |
| Prometheus | `:9090` | healthy |
| Alertmanager | `:9093` | healthy |
| Docker Compose | v5.5.1 | up |

**Порты:**
- WebUI: 8001
- Manager: 8000
- Grafana: 3000
- Prometheus: 9090
- Alertmanager: 9093
- PostgreSQL: 5432
- MinIO: 9000 (console 9001)

**Роли и пароли (тестовые):**
- `admin` / `admin123`
- `auditor` / `auditor123`
- `viewer` / `viewer123`
- `scanner` / `scanner123`

**Тестовые данные:**
- Resources: 142 (fs-regress, 210 findings), 143 (png-only, 4 findings), 144 (minio)
- Findings: 2043 (text_line, person), 2044/2045/2046 (image_region, OCR), 1995 (high_entropy), 1987 (aws_key FP), 2035 (phone FP)
- MinIO: 4 объекта в `dcap-audit-logs/access-logs/`
- Audit: 1908 событий, 20 типов

---

## 📌 ИНСТРУКЦИЯ ДЛЯ НОВОЙ БЕСЕДЫ

**Приложить:**
1. `STATE_TEST_SESSION.md` (этот файл).
2. `STATE.md`.
3. `ROADMAP.md`.
4. `ARCHITECTURE.md`.
5. `DESIGN.md` (для 53.4b–53.4e).

**Триггер:**
Продолжаем мастер-сессию DCAP v3.14.0.
Приложены: STATE_TEST_SESSION.md, STATE.md, ROADMAP.md, ARCHITECTURE.md, DESIGN.md.

Пройдено: Блоки 1–9; 53.1a–53.3; 53.4a; 53.4a-доп; 53.4a-доп3/4/5; 53.4b; WebUI-прогон (блоки 1–11).

Пройдены WebUI-блоки 1–11. Найдено 30+ находок (BUG-141…153, BACKLOG-104…130, TEST-NOTE-NEW 1–7).
BUG-142, BUG-143, BACKLOG-131 — ✅ FIXED.
BUG-138/139/140/145 — ✅ FIXED (53.4a-доп).
BUG-201…223 — ✅ FIXED (53.4a-доп3, v3.13.39).
BUG-212 — ✅ FIXED (53.4a-доп4, v3.13.40).
BUG-150/149, BACKLOG-121/119 — ✅ FIXED (53.4a-доп5, v3.13.41).
BUG-141/203/204/205/206/207/216/228/229/232/233 — ✅ FIXED (53.4b, v3.14.0).

Следующий: WebUI блоки 12–17 (Users, Roles, Settings, Console, Network, Responsive).
Затем — Grafana-тестирование (53.4e-grafana) + RBAC (BACKLOG-307).
Затем — сборка ТЗ для разработчика (53.4a-доп3, 53.4b–53.4e, scanner-fix, delete-fix).

Unit: 460 passed. E2E: 53 passed, 7 skipped.
Стек: v3.14.0 (Docker Compose v5.5.1). Scanner (host): 3.14.0.

Начни с проверки: git log --oneline -10.

---

**Конец STATE_TEST_SESSION.md** (14.10.2026)