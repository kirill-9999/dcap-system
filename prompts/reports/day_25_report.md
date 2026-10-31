# Отчет: День 25 — Унифицированный формат событий

**Дата:** 26.08.2026
**ТЗ:** `prompts/tz/day_25_unified_event_format.md`
**Статус:** Выполнено

---

## Результат

Единый формат событий для Windows и Linux-агентов. Модель `UnifiedEvent` определяет контракт, оба агента отправляют в этом формате, Manager API принимает и хранит.

---

## Измененные файлы

| Файл | Изменение |
|------|-----------|
| `shared/__init__.py` | Новый |
| `shared/event_schema.py` | UnifiedEvent: event_type, event_source, user, user_sid, file_path, old_path, source_host, metadata, created_at |
| `audit-agent/collector.py` | +event_source="windows_agent", +user_sid, +source_host (socket.gethostname) |
| `audit-agent-linux/collector.py` | +event_source="linux_agent", +source_host (platform.node()) |
| `manager/src/api/audit.py` | AuditEventPayload +event_source, +source_host; ingest сохраняет event_source; GET возвращает event_source |

---

## Не изменено (уже совместимо)

| Файл | Причина |
|------|---------|
| `manager/src/db/models.py` | AuditLog уже имеет event_source column (День 16) |
| `webui/api/routes.py` | SELECT * уже включает event_source |
| `webui/main.py` | Детали события уже показывают event_source |

---

## Формат события

```json
{
    "event_type": "write",
    "event_source": "linux_agent",
    "user": "kirill",
    "file_path": "/home/kirill/test_audit/file.txt",
    "old_path": null,
    "source_host": "LAPTOP-P73QJI5T",
    "metadata": {},
    "created_at": "2026-08-26T21:49:09.232"
}
```

---

## Команда для коммита (уже выполнен)

```bash
git checkout -b feature/day_25_unified_format
git add shared/ audit-agent/collector.py audit-agent-linux/collector.py manager/src/api/audit.py
git commit -m "feat: День 25 — унифицированный формат событий (Windows + Linux)"
```
