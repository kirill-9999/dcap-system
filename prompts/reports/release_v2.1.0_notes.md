# Release Notes — DCAP System v2.1.0

**Дата:** 2026-08-27
**Версия:** v2.1.0
**Статус:** ✅ Стабильный релиз

---

## Обзор

DCAP System v2.1.0 — завершение Linux-фазы. Система теперь поддерживает аудит файловой системы на Windows и Linux через легкие агенты, с единым форматом событий и единой точкой управления в WebUI.

---

## Что нового

### Linux-агент аудита (`audit-agent-linux/`)
- Мониторинг файловой системы через watchdog (inotify)
- SSH-мониторинг для Colab-режима (paramiko)
- Буферизация событий в SQLite
- Автозапуск через `start.sh --daemon`
- Systemd-сервис (`dcap-audit.service`) + crontab-совместимость
- Уникальное имя агента: `dcap-audit-linux-{hostname}`

### Унифицированный формат событий (`shared/event_schema.py`)
- Единая Pydantic-схема `UnifiedEvent` для всех агентов
- `event_source`: windows_agent, linux_agent, scanner, api
- `user_sid` — Windows-only (SID пользователя)
- `source_host` — имя хоста, где произошло событие
- Обратная совместимость с историческими данными (legacy `agent`)

### WebUI (`webui/main.py`)
- Фильтр по источнику событий (Windows/Linux/Все)
- Иконки для Windows и Linux в таблице аудита
- Dashboard cards с разбивкой по источникам
- Удаление агентов и сканеров через UI (кнопки)
- Автоматический offline-статус по heartbeat (>2 минут)

### Manager API
- `GET /api/audit` — фильтр по `event_source`
- `GET /api/audit/stats` — статистика `by_source`
- `GET /api/audit/agents` — список агентов с heartbeat-проверкой
- `DELETE /api/audit/agents/{id}` — удаление агента
- `DELETE /api/scanner/{id}` — удаление сканера

---

## Ключевые изменения

| Изменение | Описание |
|-----------|----------|
| watchdog вместо pyinotify | pyinotify удалён (asyncore в Python 3.12+) |
| Event source в БД | Столбец `event_source` в `audit_logs` (миграция: agent_id 1→windows_agent, 7→linux_agent) |
| Heartbeat offline | При GET-чтении проверка `last_heartbeat < now - 120s` |
| data-name атрибуты | onclick deleteScanner/deleteAuditAgent используют data-* атрибуты вместо inline-кавычек |

---

## Структура проекта

```
dcap-system/
├── manager/           # FastAPI :8000 (чистое API)
├── scanner/           # тяжелый агент сканирования
├── audit-agent/       # Windows-агент аудита
├── audit-agent-linux/ # Linux-агент аудита (NEW)
├── webui/             # каноничный UI :8001
├── shared/            # общие компоненты (event_schema)
└── prompts/           # ТЗ и отчеты по дням
```

---

## Как запустить

### Windows
```bash
python init_db.py
python -m uvicorn manager.src.main:app --port 8000
python run_webui.py
cd audit-agent && python main.py
```

### Linux
```bash
cd audit-agent-linux
./start.sh --daemon
# или systemd:
sudo cp dcap-audit.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start dcap-audit
```

---

## Тестирование

| Компонент | Статус |
|-----------|--------|
| Windows-агент (heartbeat + events) | ✅ |
| Linux-агент (watchdog + events) | ✅ |
| WebUI (фильтр по источнику) | ✅ |
| WebUI (удаление агентов/сканеров) | ✅ |
| Dashboard (статус агентов) | ✅ |
| UnifiedEvent (единый формат) | ✅ |

---

## Следующие планы

**v3.0.0** — Промышленная система:
- S3/MinIO аудит (Server Access Logs)
- Webhook для MinIO
- Безопасность (mTLS, шифрование)
- Масштабирование (PostgreSQL, Redis)
- Мониторинг (Prometheus/Grafana)
