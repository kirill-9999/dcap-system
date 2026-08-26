# DCAP Audit Agent — Linux (inotify)

Легкий агент аудита файловой системы для Linux. Отслеживает события через inotify, буферизирует в SQLite, отправляет в Manager по HTTP.

## Зависимости

- Python 3.8+
- pyinotify (inotify API)
- requests (HTTP)

## Установка

```bash
pip install -r requirements.txt
```

## Конфигурация

Редактируйте `config.json`:

| Параметр | Описание | Дефолт |
|----------|----------|--------|
| `manager_url` | URL Manager API | `http://localhost:8000` |
| `agent_name` | Имя агента | `linux-agent-01` |
| `hostname` | Имя хоста | `linux-server` |
| `watch_paths` | Пути для мониторинга | `["/home/kirill/test_audit"]` |
| `read_interval` | Интервал проверки буфера (сек) | `5` |
| `batch_size` | Размер батча для отправки | `50` |
| `buffer_size` | Макс. событий в буфере | `10000` |
| `heartbeat_interval` | Интервал heartbeat (сек) | `30` |

## Запуск

```bash
# Фоновый режим
bash start.sh

# Прямой запуск
python main.py
```

## Остановка

```bash
bash stop.sh
```

## Архитектура

```
main.py          — точка входа, основной цикл
collector.py     — сбор событий через inotify (pyinotify)
buffer.py        — буферизация в SQLite
sender.py        — отправка events/heartbeat в Manager
heartbeat.py     — периодический heartbeat
config.json      — конфигурация
```

## События

| inotify mask | Тип события |
|-------------|-------------|
| IN_OPEN | read |
| IN_MODIFY, IN_CLOSE_WRITE, IN_CREATE | write |
| IN_DELETE, IN_DELETE_SELF | delete |
| IN_MOVED_FROM, IN_MOVED_TO | move |

## Буферизация

При недоступности Manager события копятся в `buffer/buffer.db`. При восстановлении связи автоматически отправляются. Старые отправленные события удаляются.
