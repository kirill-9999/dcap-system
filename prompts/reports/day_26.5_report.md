# Отчет: День 26.5 — Управление агентами и сканерами (удаление)

**Дата:** 27.08.2026
**ТЗ:** `prompts/tz/day_26.5_agent_scanner_management.md`
**Статус:** Выполнено

---

## Результат

Удаление агентов аудита и сканеров через WebUI. Кнопки 🗑️ в таблицах, confirm-диалог,.toast-уведомления. DELETE-эндпоинты в Manager API и WebUI routes.

---

## Измененные файлы

| Файл | Изменение |
|------|-----------|
| `manager/src/api/audit.py` | `DELETE /api/audit/agents/{id}` — отвязка событий (agent_id=NULL), удаление |
| `manager/src/api/scanner.py` | `DELETE /api/scanner/{id}` — освобождение задач при force=true |
| `webui/api/routes.py` | `DELETE /api/scanners/{id}`, `DELETE /api/audit/agents/{id}` (raw SQLite) |
| `webui/main.py` | Кнопки 🗑️ в таблицах, JS deleteScanner/deleteAuditAgent, confirm() |

---

## Проверка

- `DELETE /api/audit/agents/999` → 404 (Agent not found)
- `DELETE /api/scanners/999` → 404 (Scanner not found)
- `DELETE /api/audit/agents/2` → 200 (deleted), agent 2 удалён
- `DELETE /api/scanners/5` → 200 (deleted), scanner 5 удалён
- События удалённого агента сохранились в БД (agent_id=NULL)

---

## Удаленные записи

| Тип | ID | Имя |
|-----|----|-----|
| Агент | 2 | test-reg-agent |
| Сканер | 5 | hb-check-scanner |

---

## Команда для коммита (уже выполнен)

```bash
git add webui/main.py webui/api/routes.py manager/src/api/audit.py manager/src/api/scanner.py
git commit -m "feat: День 26.5 — удаление агентов и сканеров через WebUI"
```
