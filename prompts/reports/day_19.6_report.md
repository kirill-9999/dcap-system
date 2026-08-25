# Отчет: День 19.6 — Видимость агентов аудита на дашборде

**Дата:** 25.08.2026
**ТЗ:** `prompts/tz/day_19.6_audit_agents_dashboard.md`
**Статус:** Выполнено полностью

---

## Что сделано

### 1. API: `GET /api/audit/agents` (`webui/api/routes.py`)

Добавлен эндпоинт:
- Запрос из таблицы `audit_agents` (SQL raw sqlite)
- Ответ: `total`, `online`, `offline`, `error`, `agents[]`
- Поля агента: `id`, `name`, `hostname`, `status`, `last_heartbeat`, `events_sent`, `registered_at`, `version`

### 2. Дашборд — блок «Агенты аудита» (`webui/main.py`)

Добавлена седьмая stat-карточка:
- Иконка `fas fa-robot`, фиолетовый цвет
- Значение `id="dashboard-audit-agents"` — общее число
- Подпись: `dashboard-audit-online` (зелёный) онлайн, `dashboard-audit-offline` (красный) офлайн
- `loadDashboard()` вызывает `loadAuditAgents()` — данные загружаются при открытии

### 3. Вкладка «Сканеры» → «Сканеры и агенты»

- Навигация: `<a ...> Сканеры и агенты</a>`
- Секция scanners-page разделена на два блока:
  - **Сканеры** — карточка с существующей таблицей `scanners-table`
  - **Агенты аудита** — карточка с:
    - Строка статистики: `agents-total`, `agents-online`, `agents-offline`, `agents-error`
    - Таблица `audit-agents-table-container`: ID, имя, хост, статус (badge), событий, версия, heartbeat, регистрация
- `switchPage('scanners')` и auto-refresh вызывают `loadScanners()` + `loadAuditAgents()`

### 4. JavaScript (`webui/main.py`, inline)

Функция `loadAuditAgents()`:
- `fetch('/api/audit/agents')`
- Обновляет 6 элементов дашборда + 4 элемента статистики
- Рендерит таблицу с badge-статусами (`status-online`/`status-offline`/`status-error`)
- `escapeHtml()` для имени и хоста (XSS-safe)
- Даты форматируются через `toLocaleString('ru-RU')`

### 5. CSS (`webui/main.py`, inline)

Добавлены стили:
- `.agents-stats` — flex-контейнер для статистики
- `.agents-table` — таблица с hover-эффектом
- `.status-badge`, `.status-online`, `.status-offline`, `.status-error` — цветные badge'и

### 6. Хотфикс: pre-existing JS баг

3 строки с `\\'acknowledged\\'` в `updateAlertStatus` onclick ломали JS syntax (Node.js SyntaxError). Заменены на `\\x27acknowledged\\x27`.

---

## Тестирование

### API — 4/4 OK
```
GET /api/audit/agents → 200, total=1, online=1, agent: audit-agent-01 online
GET /api/stats → 200
GET /api/audit/stats → 200
GET /api/audit → 200
```

### HTML — 4/4 OK
```
dashboard-audit-agents — PRESENT
agents-total — PRESENT
audit-agents-table-container — PRESENT
tab "Сканеры и агенты" — PRESENT
```

### JS — syntax OK
```
node -c check.js → (no errors)
loadAuditAgents function — PRESENT
status-online, status-offline — PRESENT
```

### Python compile — 2/2 OK
```
webui/main.py — OK
webui/api/routes.py — OK
```

---

## Критерии приемки ТЗ — все OK

- [x] API `/api/audit/agents` возвращает список агентов со статусом
- [x] На дашборде блок «Агенты аудита» с количеством
- [x] В блоке: всего, онлайн, офлайн
- [x] Вкладка «Сканеры» → «Сканеры и агенты»
- [x] Таблица со всеми агентами
- [x] Таблица: ID, имя, хост, статус, события, версия, heartbeat, регистрация
- [x] Данные загружаются при открытии дашборда и вкладки
- [x] При ошибках — нет данных (пустая таблица с сообщением)

---

## Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `webui/api/routes.py` | +`GET /api/audit/agents` |
| `webui/main.py` | +dashboard card, +tab rename, +agents table, +JS `loadAuditAgents`, +CSS, +hotfix 3 onclick |

---

## Команда для коммита

```bash
git checkout -b feature/day_19.6_audit_agents_dashboard
git add webui/main.py webui/api/routes.py prompts/tz/day_19.6_audit_agents_dashboard.md
git commit -m "feat: День 19.6 — видимость агентов аудита на дашборде и вкладке «Сканеры и агенты»"
```
