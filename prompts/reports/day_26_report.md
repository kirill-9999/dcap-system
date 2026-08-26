# Отчет: День 26 — WebUI фильтр по источнику событий

**Дата:** 26.08.2026
**ТЗ:** `prompts/tz/day_26_webui_event_source_filter.md`
**Статус:** Выполнено

---

## Результат

Фильтр по `event_source` на странице «Аудит» в WebUI. Пользователь может выбрать: Все источники, Windows Agent, Linux Agent, Agent (legacy). В таблице отображается иконка источника. На дашборде — карточки Windows/Linux событий.

---

## Измененные файлы

| Файл | Изменение |
|------|-----------|
| `webui/api/routes.py` | `event_source` параметр в `GET /api/audit`; `by_source` статистика в `GET /api/audit/stats` |
| `webui/main.py` | HTML dropdown «Источник», JS `loadAuditEvents()`, `getEventSourceIcon()`, `renderAuditTable()`, `resetAuditFilters()`, `renderAuditStats()`, dashboard cards |

---

## Миграция данных

Все 688 исторических событий имели `event_source='agent'` (старый формат до Дня 25). Миграция по agent_id:

| agent_id | source_host | event_source (было) | event_source (стало) | Кол-во |
|----------|-------------|---------------------|----------------------|--------|
| 1 | SERVER01 | agent | windows_agent | 667 |
| 5 | TEST-PC | agent | agent (тест) | 6 |
| 6 | E2E-TEST | agent | agent (тест) | 3 |
| 7 | linux-server | agent | linux_agent | 12 |

---

## Проверка

- `GET /api/audit?event_source=windows_agent` → **667**
- `GET /api/audit?event_source=linux_agent` → **12**
- `GET /api/audit?event_source=agent` → **9** (тестовые)
- `GET /api/audit` → **688**

---

## Идея для архитектора: события от сканнеров и API

Сейчас `event_source` поддерживает 4 варианта, но реально работает только 2 (`windows_agent`, `linux_agent`). Scanner и API — заглушки. Предлагаю продумать:

### Scanner events (event_source='scanner')

Сканер уже генерирует findings при сканировании, но это **не аудит-события**. Аудит-события от сканера — это другой контекст:

- **Сканирование как доступ к файлам**: когда сканер читает файл для анализа — это событие `read`. Можно логировать: какой сканер, когда, какой файл прочитал. Полезно для аудита «кто/что трогал файлы».
- **Обнаружение PII/credentials как событие**: находка сканера — это潜在的に security-event. Например: сканер нашёл пароль в файле → событие `write` или `alert` с метаданными finding_id.
- **Сканирование как modificar**: если сканер в будущем будет авто-fixить (удалять secrets из кода) — это событие `write`/`delete`.

**Реализация:** в `scanner/src/managed_scanner.py` при successfully scan задачи — отправлять batch audit events с `event_source='scanner'` в Manager. Один эндпоинт `POST /api/audit/events` уже принимает `event_source`.

### API events (event_source='api')

Операции через Manager API, которые модифицируют данные:

- **Создание/удаление ресурса** (`POST /api/resources`, `DELETE`): событие `write`/`delete` на уровне системы, не на уровне файла.
- **Создание задачи сканирования** (`POST /api/tasks`): событие `read` (инициировано сканирование).
- **Изменение конфигурации** (PUT config): событие `write` с метаданными `{key, old_value, new_value}`.
- **Управление доступом** (permissions): события `grant`/`revoke` — уже есть в `audit_logs`, но через отдельную таблицу `access_audit_logs`.

**Реализация:** декоратор или middleware на FastAPI, который логирует mutation-запросы в `audit_logs` с `event_source='api'`. Или хук в каждом mutation-эндпоинте.

### Когда это может понадобиться

| Сценарий | Без scanner/API events | С scanner/API events |
|----------|----------------------|---------------------|
| «Кто читал файл X?» | Только агенты ОС | + сканер, который сканировал |
| «Когда в последний раз меняли конфиг?» | Неизвестно | API events покажут |
| «Кто создал задачу на сканирование?» | Неизвестно | API events покажут |
| «Полный audit trail» | 80% картины | 100% картины |

### Приоритет

**Низкий.** Сейчас хватает Windows/Linux агентов. Scanner и API events — это v3.x фича, когда появится реальная потребность в полном audit trail.

---

## Команда для коммита (уже выполнен)

```bash
git add webui/main.py webui/api/routes.py
git commit -m "feat: День 26 — WebUI фильтр по источнику событий (event_source)"
```
