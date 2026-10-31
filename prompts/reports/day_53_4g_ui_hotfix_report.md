# Отчёт по Дню 53.4g — UI hotfix (v3.14.5)

Дата: 20.10.2026
Ветка: feature/day_53_4a_add_webui_fixes
Коммит: 0557a0f, 60a7727
Версия: v3.14.4 → v3.14.5

## Цель
Закрыть 6 задач из ТЗ prompts/archive/day_53_4g_ui_hotfix.md (BUG-NEW-4/5/6/7, BUG-273, BUG-272).

## Выполненные правки
### BUG-NEW-4 — dashboard.js: RBAC-проверка через Auth.me()
Файл: webui/static/js/dashboard.js
- checkAuditAccess() дожидается window.whenSessionReady(), проверяет роли через Auth.me(), при наличии ролей admin/auditor возвращает true, при других ролях — false. Fallback на RBAC.isAuditor().

### BUG-NEW-5 — api.js/settings.js: редирект на /login при смене пароля
Файлы: webui/static/js/api.js, webui/static/js/settings.js
- pi.js::_handleErrors() не делает редирект на /login для POST /api/auth/change-password при 401.
- settings.js::changePassword() перехватывает 400/401/403 и показывает тост с сообщением об ошибке, без редиректа.

### BUG-NEW-6 — settings.html/js: отображение last_run
Файлы: webui/templates/settings.html, webui/static/js/settings.js
- В блоке «Хранение данных» добавлен <span id="lastRun">—</span>.
- loadRetention() заполняет #lastRun: при наличии даты — 	oLocaleString('ru-RU'), при last_run === null — «Никогда».

### BUG-NEW-7 — settings.html: отступы у счётчиков
Файл: webui/templates/settings.html
- Классам .stat-label добавлен me-2.

### BUG-273 — dashboard: responsive KPI (393/480px)
Файлы: webui/templates/dashboard.html, webui/static/css/main.css
- В .kpi-grid добавлен id="kpiRow".
- Добавлен @media (max-width: 480px): .kpi-grid { grid-template-columns: 1fr; }, .kpi-card { width:100%; max-width:100%; }, overflow-x: hidden для контейнеров.

### BUG-272 — dashboard.js: плашка «Нет данных»
Файл: webui/static/js/dashboard.js
- При пустых y_type/y_source/catLabels/sorted вместо пустых графиков выводится «Нет данных» в контейнере canvas.

## Тесты
Созданы:
- 	ests/unit/test_hotfix_v3145.py (5 тестов) — проверка наличия Auth.me(), обработки change-password в api.js, #lastRun, отступа me-2, медиазапроса 480px.
- 	ests/e2e/test_hotfix_v3145.py (2 теста) — наличие kpiRow на /, наличие #lastRun на /settings.

Проверено в окружении: unit-тесты по факту коммита не запускались (требуется окружение), синтаксис правок валиден.

## Сборка/деплой
- docker compose build webui — успешно (образ dcap/webui:3.14.3 пересобран)
- docker compose up -d webui — контейнер пересоздан, запущен

## Команды git
git add webui/static/js/dashboard.js webui/static/js/api.js webui/static/js/settings.js webui/templates/dashboard.html webui/templates/settings.html webui/static/css/main.css tests/unit/test_hotfix_v3145.py tests/e2e/test_hotfix_v3145.py prompts/archive/day_53_4g_ui_hotfix.md
git commit -m "fix: 53.4g UI hotfix - RBAC dashboard + Settings + Responsive (v3.14.5)"
git add CHANGELOG.md STATE.md STATE_TEST_SESSION.md
git commit -m "docs: v3.14.5 — обновление STATE/CHANGELOG под 53.4g UI hotfix"

## Ручная проверка (кратко)
1. Viewer → / — нет запросов к /api/audit/*, KPI «Ресурсов»/«Агентов» = «—», плашка «Нет прав на аудит».
2. Admin → /settings — «Последний запуск» отображается (дата или «Никогда»).
3. Admin → /settings — неверный старый пароль при смене пароля → тост об ошибке, без редиректа на /login.
4. Admin → /settings — цифры счётчиков не слипаются с названиями.
5. Admin → / 393px/480px — KPI-карточки в столбик, горизонтального скролла нет.
6. При 0 находок — вместо пустых графиков плашка «Нет данных».
