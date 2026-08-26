# Отчет: День 23 — Linux-агент аудита с inotify

**Дата:** 26.08.2026
**ТЗ:** `prompts/tz/day_23_linux_agent_inotify.md`
**Статус:** Выполнено, протестировано на реальном Linux

---

## Результат

Создан легкий Linux-агент аудита (`audit-agent-linux/`) — отслеживает файловые события через inotify (watchdog), буферизирует в SQLite, отправляет в Manager по HTTP. Протестирован в WSL, события видны в WebUI-дашборде.

---

## Структура

```
audit-agent-linux/
├── main.py           # AuditAgent — register → collector thread → send loop
├── collector.py      # InotifyCollector — watchdog (inotify, rec=True)
├── buffer.py         # BufferManager — SQLite, check_same_thread=False
├── sender.py         # Sender — batch events + heartbeat
├── heartbeat.py      # HeartbeatSender — периодический tick
├── config.json       # Конфигурация
├── requirements.txt  # requests, watchdog
├── start.sh          # Запуск (авто-sоздание venv)
├── stop.sh           # Остановка по PID
└── README.md
```

---

## Исправления во время разработки

| Проблема | Решение |
|----------|---------|
| `pyinotify` → `ModuleNotFoundError: asyncore` | Замена на `watchdog` (asyncore удалён в Python 3.12+) |
| PEP 668 `externally-managed-environment` | `start.sh` создаёт venv автоматически |
| `datetime.utcnow()` DeprecationWarning | Замена на `datetime.now()` (локальное время) |
| Время UTC вместо локального | `datetime.now()` — берёт TZ с хоста |

---

## Коммиты

```
6bf73ff feat: День 23 — Linux-агент аудита с inotify
51da6d1 fix: pyinotify → watchdog (asyncore удалён в Python 3.12+)
a18e65b fix: datetime.utcnow() deprecation
2cd159c fix: время UTC → локальное время
3396cf5 chore: удалить мусорный файл =4.0.0
```

---

## Как запустить

```bash
cd ~/dcap-system/audit-agent-linux
bash start.sh    # venv + зависимости + запуск
bash stop.sh     # остановка
```

---

## Проверка

```bash
# События в WebUI
http://localhost:8001 → Аудит

# Логи
tail -f logs/agent.out

# Буфер
sqlite3 buffer/buffer.db "SELECT COUNT(*) FROM events WHERE sent=0;"
```

---

## Метрики

| Параметр | Значение |
|----------|----------|
| Файлов | 10 |
| Строк кода | ~450 |
| Зависимости | requests, watchdog |
| Python | 3.8+ (протестировано на 3.13) |
| Размер агента | ~2 MB (с venv) |

---

## Следующий день (24)

Согласно ТЗ: Служба systemd для Linux агента (BACKLOG-010, v2.1.0).
