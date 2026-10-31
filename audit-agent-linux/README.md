# DCAP Audit Agent — Linux (inotify)

Легкий агент аудита файловой системы для Linux. Отслеживает события через inotify (watchdog), буферизирует в SQLite, отправляет в Manager по HTTP.

## Установка

```bash
cd ~/dcap-system/audit-agent-linux
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
# Консольный режим (отладка)
./start.sh

# Фоновый режим (продакшн)
./start.sh --daemon
```

## Управление

| Команда | Действие |
|---------|----------|
| `./start.sh` | Запуск (консоль) |
| `./start.sh --daemon` | Запуск (фон) |
| `./stop.sh` | Остановка |
| `./status.sh` | Проверка статуса |

## Установка как сервис

### systemd (полноценный Linux)

```bash
cd service
./install.sh
sudo systemctl start dcap-audit-agent
sudo systemctl status dcap-audit-agent
sudo journalctl -u dcap-audit-agent -f
```

### WSL (без systemd)

```bash
cd service
./install_cron.sh
crontab -l
```

## Архитектура

```
main.py          — точка входа, основной цикл
collector.py     — сбор событий через inotify (watchdog)
buffer.py        — буферизация в SQLite
sender.py        — отправка events/heartbeat в Manager
heartbeat.py     — периодический heartbeat
config.json      — конфигурация
service/         — systemd + crontab установка
```

## События

| Тип | Описание |
|-----|----------|
| read | Открытие файла |
| write | Запись / создание |
| delete | Удаление |
| move | Перемещение |

## Буферизация

При недоступности Manager события копятся в `buffer/buffer.db`. При восстановлении связи автоматически отправляются. Старые отправленные события удаляются.

## Логи

- Файл: `logs/agent.out`
- systemd: `sudo journalctl -u dcap-audit-agent -f`
- Cron: `tail -f logs/agent.out`
