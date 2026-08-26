# Отчет: День 26 — WebUI фильтр по источнику событий

**Дата:** 26.08.2026
**ТЗ:** `prompts/tz/day_26_webui_event_source_filter.md`
**Статус:** Выполнено

---

## Результат

Фильтр по `event_source` на странице «Аудит» в WebUI. Пользователь может выбрать: Все источники, Windows Agent, Linux Agent, Scanner, API. В таблице отображается иконка источника. На дашборде — карточки Windows/Linux событий.

---

## Измененные файлы

| Файл | Изменение |
|------|-----------|
| `webui/api/routes.py` | `event_source` параметр в `GET /api/audit`; `by_source` статистика в `GET /api/audit/stats` |
| `webui/main.py` | HTML dropdown «Источник», JS `loadAuditEvents()`, `getEventSourceIcon()`, `renderAuditTable()`, `resetAuditFilters()`, `renderAuditStats()`, dashboard cards |

---

## Проверка

- `GET /api/audit?event_source=windows_agent` → 0 (все события старого формата `agent`)
- `GET /api/audit?event_source=linux_agent` → 0
- `GET /api/audit` → 688 (все события)
- `GET /api/audit/stats?days=30` → `by_source: [{'source': 'agent', 'count': 688}]`

Новые события от агентов с `event_source=windows_agent`/`linux_agent` будут видны при перезапуске агентов с кодом Дня 25.

---

## Команда для коммита (уже выполнен)

```bash
git add webui/main.py webui/api/routes.py
git commit -m "feat: День 26 — WebUI фильтр по источнику событий (event_source)"
```
