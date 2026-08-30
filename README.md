# DCAP System

Система сканирования и аудита данных (PII/credentials/code) для Windows и Linux.

## Компоненты

| Компонент | Описание | Порт |
|-----------|----------|------|
| `manager/` | FastAPI control-plane | :8000 |
| `webui/` | Дашборд (Jinja2, прокси API на Manager) | :8001 |
| `scanner/` | Агент сканирования | — |
| `audit-agent-windows/` | Windows-агент аудита (wevtutil) | — |
| `audit-agent-linux/` | Linux-агент аудита (watchdog) | — |
| `audit-agent-s3/` | S3/MinIO агент аудита (polling) | — |
| `shared/` | Единая схема событий (UnifiedEvent) | — |

## Запуск

```bash
# Инициализация БД
python init_db.py

# Единый запуск Manager + WebUI (порты из конфигов)
python run_all.py

# или по отдельности:
python run_manager.py        # Manager API (порт из manager/config/config.json, :8000)
python run_webui.py          # WebUI (порт из webui/config/config.json, :8001)

# Сканер
python run_scanner.py scanner/config/scanner_config.json

# Windows-агент аудита
cd audit-agent-windows && python main.py config.json

# Linux-агент аудита
cd audit-agent-linux && ./start.sh --daemon

# S3/MinIO агент аудита
cd audit-agent-s3 && python -m src.main --config config/config.json
```

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ audit-agent │────▶│   Manager   │◀────│ audit-agent │
│  (Windows)  │     │   :8000     │     │   (Linux)   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │    WebUI    │
                    │   :8001     │
                    └─────────────┘
```

- **Manager** — REST API, прием событий от агентов, хранение в SQLite
- **WebUI** — дашборд с фильтрацией по источнику (Windows/Linux), удаление агентов/сканеров. Все `/api/*` запросы проксируются в Manager (нет прямого доступа к БД)
- **Агенты** — легкие компоненты, буферизуют события в SQLite, отправляют батчами

## Единый формат событий

Все агенты (Windows, Linux, S3, scanner) используют формат `UnifiedEvent`:

- `event_type`: read, write, delete, move, rename
- `event_source`: windows_agent, linux_agent, scanner, s3_agent
- `user`, `user_sid`, `file_path`, `source_host`, `metadata`

## Версии

| Версия | Описание |
|--------|----------|
| v1.0.0 | Базовый функционал (обнаружение + классификация + каталог) |
| v2.0.0 | Управление доступом + Аудит Windows (ядро) |
| v2.0.1 | Windows-стек полностью готов |
| v2.1.0 | Linux-агент + унифицированный формат + WebUI фильтр |
| v3.0.0 | Унификация Manager и WebUI: WebUI — Jinja2 + прокси API на Manager, конфиги портов, run_all.py |
| v3.1.0 | Гибридная аутентификация (JWT+Bcrypt/SPNEGO) + роли; S3/MinIO агент аудита (polling, буфер, heartbeat, JWT); Windows + Linux аудит |

## Требования

- Python 3.8+
- Windows: wevtutil (встроен), права администратора для аудита
- Linux: watchdog, optional: paramiko (SSH-мониторинг)
