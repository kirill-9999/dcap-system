# Отчет: День 19 — WebUI для аудита

**Дата:** 2026-08-24
**Файл ТЗ:** `prompts/tz/day_19_webui_audit.md`

## 🎯 Цель

Страница «Аудит» в WebUI (:8001): просмотр событий агентов аудита с фильтрацией
(период, тип, пользователь, путь), статистика, пагинация, детали события, поиск.

## 📁 Созданные/измененные файлы

```
webui/
├── main.py                 # ✅ изменен — навигация + страница "Аудит" + JS + стили (инлайн)
├── api/routes.py           # ✅ изменен — GET /api/audit, GET /api/audit/stats (raw sqlite)
├── static/js/app.js        # ✅ изменен — секция АУДИТ (по ТЗ; файл легаси, не подключен)
└── static/css/style.css    # ✅ изменен — секция СТРАНИЦА АУДИТА (по ТЗ; файл легаси, не подключен)
run_webui.py                # ✅ создан — отсутствовал в репо (упомянут в AGENTS.md и сценарии ТЗ)
AGENTS.md                   # ✅ обновлен
```

## 🔄 Адаптации/исправления (отклонения от буквы ТЗ)

1. **Бэкенд для страницы**: ТЗ не меняло `webui/api/routes.py`, но JS из ТЗ делает
   `fetch('/api/audit')` на тот же origin (:8001), где такого роута не было (он есть только у
   Manager на :8000). Добавлены `GET /api/audit` и `GET /api/audit/stats` в WebUI — читают те же
   таблицы `audit_logs`/`audit_agents` из общей БД, форматы ответов повторяют Manager
   (`{total, limit, offset, events}`, `{total, days, by_type, top_users}` + `agents_total/online`).
2. **Актуальный UI инлайн**: по AGENTS.md вся страница (`webui/main.py`) — HTML/CSS/JS в
   Python-строке. Разметка из ТЗ адаптирована под существующие конвенции файла:
   `page-content`/`switchPage()` вместо `page`/`showPage()`, `.filter-card`+bootstrap-grid для
   фильтров, модалки через `showModal/closeModal`. Все id и логика из ТЗ сохранены.
3. **Фикс бага ТЗ в `showAuditDetail`**: вариант ТЗ делал `fetch('?limit=1&offset=0')` и искал
   событие в единственном ответе — детали работали бы только для первого события. Сделан кэш
   `auditEventsCache`, наполняемый при рендере таблицы; детали берутся из него.
4. `initAuditPage()`: обработчики навешиваются один раз (guard `auditInitialized`) — иначе
   каждый показ страницы дублировал бы listeners (ТЗ вызывало бы initAuditPage из showPage
   многократно).
5. Добавлены `escapeHtml()` для пользовательских данных (путь/юзер) и `showToast()`
   (в файле его не было, а ТЗ на него ссылается) + стили тостов.
6. Статик-файлы `app.js`/`style.css`: секции добавлены по букве ТЗ, но это легаси от старого UI —
   актуальной страницей они НЕ подключаются (зафиксировано в AGENTS.md). Рабочий код — инлайн.
7. `event-type-move` цвет #b58900 вместо #ffc107 из ТЗ (жёлтый нечитаем на белом фоне).
8. Восстановлен отсутствующий `run_webui.py` (простой launcher `webui.main:app` через
   конфиг `WEBUI_HOST/PORT`).

## 📊 Результаты прогона

Окружение: Windows, Python 3.13, WebUI :8001 запущен (`python run_webui.py`),
Manager :8000 жив (не требовался — WebUI читает БД напрямую). Тестовые данные вставлялись
напрямую в `manager/dcap.db` (агент webui-test-agent + 5 событий: write/read/delete/move/rename,
2 пользователя, одно событие 20-дневной давности).

### API WebUI (14/14 OK)
```
OK since=7d total==4            (delete-20д отфильтрован)
OK metadata is dict             (JSON из колонки metadata парсится)
OK event_type=write -> 1
OK user=ivan LIKE -> 1 / no-since -> 2
OK path~secret -> 2
OK page1 len=2 total=5 / offset=4 len=1
OK order DESC
OK stats 7d total==4 / stats 30d total==5
OK stats by_type read/write/move/rename==1, delete absent
OK top_users[0]==petrov (count=2)
OK agents_total>=1 online>=1
```

### Страница HTML (34 чека OK)
```
OK nav data-page=audit, id=page-audit
OK все 22 id из разметки присутствуют (фильтры, stat-*, пагинация, таблица, модалка)
OK все функции JS секции аудита + switchPage('audit')
OK кросс-чек: каждый getElementById('X') из inline JS имеет id="X" в HTML (missing: none)
OK баланс скобок JS-секции аудита ({38/38}, (150/150))
```

После проверок тестовые данные вычищены (0 events, агент тестовый удалён;
оставшийся `audit-agent-01` — не тестовый, не тронут), WebUI остановлен.

## ⚠️ Замечания

1. **`since` и UTC**: JS шлёт `new Date().toISOString()` (UTC с Z); WebUI нормализует к naive-UTC
   строке для сравнения с SQLite DATETIME. Manager хранит `datetime.utcnow()` (naive) — расхождений нет.
2. **Пагинация**: total считается отдельным COUNT(*) поверх тех же фильтров; кнопки ◀/▶
   управляются из JS (disabled на границах).
3. **Автообновление**: страница аудита НЕ добавлена в 30-сек интервал автообновления
   (по ТЗ не требуется; обновление — кнопкой «Обновить» и при каждом открытии страницы).
4. `webui/static/index*.html`, `main_final.py` и пр. — легаси, не тронуты.

## 🧪 Как проверить (сценарий из ТЗ)

```powershell
# 1. Manager
python -m uvicorn manager.src.main:app --port 8000
# 2. WebUI
python run_webui.py
# 3. Открыть http://localhost:8001 → пункт меню "Аудит"
#    - статистика, таблица, фильтры (период/тип/юзер/путь), пагинация,
#      клик по событию -> детали, Обновить/Сбросить
# (без событий в БД страница покажет нули и "Нет событий за выбранный период")
```

## 🔧 Хотфикс: «не нажимаются ссылки» + ругань антивируса (после приёмки)

**Причина №1 (ссылки): SyntaxError во всём inline-JS.** HTML лежит в Python-строке, и
`'\n'` / `\'` внутри JS-литералов (алерты `showFindingDetail`/`createTask`/`showTaskDetail`,
onclick-кнопки алертов) Python съедал → браузер получал реальные переводы строк внутри
строковых литералов и сломанные кавычки. Один битый скрипт = ни одной определённой функции =
все onclick мертвы (баг существовал до Дня 19). Исправлено экранированием (`\\n`, `\\'`),
20+6 мест; проверено `node --check` → «JS SYNTAX OK».

**Причина №2 (антивирус): внешние CDN.** Страница тянула bootstrap/font-awesome/chart.js с
jsdelivr/cdnjs — частые мишени веб-фильтров АВ (блокируются → голая страница, квадратики вместо
иконок, мёртвые графики). Переведено на локальные копии:
```
webui/static/vendor/css/bootstrap.min.css      (232 KB)
webui/static/vendor/css/fontawesome.min.css    (102 KB)
webui/static/vendor/js/chart.umd.min.js        (205 KB)
webui/static/vendor/webfonts/*                 (woff2/ttf, 6 файлов)
```
Плюс `WEBUI_HOST` по умолчанию теперь `127.0.0.1` вместо `0.0.0.0` (локальный UI не выглядит
сетевым сервисом для файрвола/АВ), и `/` отдаётся с `Cache-Control: no-store` (защита от
устаревшего HTML в кэше).

Проверки после фикса: 10/10 (нет внешних CDN, все vendor-файлы 200, FA webfonts резолвятся,
/api/audit работает, JS синтаксис OK).

⚠️ Остаточный артефакт среды: старый uvicorn-процесс висит на `0.0.0.0:8001` и не убивается
из этой сессии (Terminate=0, но сокет держит). На работу через `127.0.0.1:8001` не влияет;
исчезнет после перезагрузки либо `taskkill /PID <pid> /F` от администратора.

## 💾 Команда для коммита

```bash
git checkout -b feature/day_19_webui_audit
git add webui/main.py webui/api/routes.py webui/static/js/app.js webui/static/css/style.css webui/config.py webui/static/vendor/ run_webui.py AGENTS.md
git commit -m "feat: День 19 — WebUI для аудита (страница, таблица, фильтры, статистика)"
```
