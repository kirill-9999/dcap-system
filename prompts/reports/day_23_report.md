# Отчет: День 23 — Linux-агент аудита с inotify

**Дата:** 25.08.2026
**ТЗ:** `prompts/tz/day_23_linux_agent_inotify.md`
**Статус:** Выполнено

---

## Результат

Создан легкий Linux-агент аудита (`audit-agent-linux/`) с отслеживанием файловых событий через inotify.

---

## Созданные файлы

```
audit-agent-linux/
├── main.py           # AuditAgent — точка входа, основной цикл
├── collector.py      # InotifyCollector — сбор событий через pyinotify
├── buffer.py         # BufferManager — буферизация в SQLite
├── sender.py         # Sender — отправка events/heartbeat в Manager
├── heartbeat.py      # HeartbeatSender — периодический heartbeat
├── config.json       # Конфигурация (manager_url, watch_paths, интервалы)
├── requirements.txt  # requests, pyinotify
├── start.sh          # Запуск в фоне (nohup)
├── stop.sh           # Остановка по PID
└── README.md         # Инструкция
```

---

## Критерии приемки

| Критерий | Статус |
|----------|--------|
| Агент запускается и регистрируется в Manager | Да |
| Отслеживает события через inotify | Да |
| События сохраняются в SQLite-буфер | Да |
| События отправляются в Manager батчами | Да |
| При недоступности Manager события в буфере | Да |
| Heartbeat отправляется регулярно | Да |
| start.sh и stop.sh работают | Да |

---

## Архитектура

```
inotify (pyinotify) → BufferManager (SQLite) → Sender (HTTP) → Manager :8000
```

- **collector.py** — WatchManager + Notifier, маски IN_OPEN/IN_MODIFY/IN_DELETE/IN_MOVED/IN_CREATE
- **buffer.py** — SQLite буфер с trim при переполнении (10% самых старых)
- **sender.py** — batch отправка, heartbeat, retry
- **main.py** — register → collector (thread) → send loop + heartbeat

---

## Изменения в .gitignore

Добавлены runtime-файлы `audit-agent-linux/` (buffer/, logs/, *.db, agent.pid).

---

## Команда для коммита

```bash
git checkout -b feature/day_23_linux_agent
git add audit-agent-linux/ .gitignore
git commit -m "feat: День 23 — Linux-агент аудита с inotify"
```
