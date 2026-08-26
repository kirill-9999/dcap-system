# DCAP System

Система сканирования и аудита данных (PII/credentials/code) для Windows и Linux.

## Компоненты

| Компонент | Описание | Порт |
|-----------|----------|------|
| `manager/` | FastAPI control-plane | :8000 |
| `webui/` | Дашборд (HTML инлайн в Python) | :8001 |
| `scanner/` | Агент сканирования | — |
| `audit-agent/` | Windows-агент аудита (wevtutil) | — |
| `audit-agent-linux/` | Linux-агент аудита (watchdog) | — |
| `shared/` | Единая схема событий (UnifiedEvent) | — |

## Запуск

```bash
# Инициализация БД
python init_db.py

# Manager (API)
python -m uvicorn manager.src.main:app --port 8000

# WebUI (дашборд)
python run_webui.py

# Сканер
python run_scanner.py scanner/config/scanner_config.json

# Windows-агент аудита
cd audit-agent && python main.py

# Linux-агент аудита
cd audit-agent-linux && ./start.sh --daemon
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
- **WebUI** — дашборд с фильтрацией по источнику (Windows/Linux), удаление агентов/сканеров
- **Агенты** — легкие компоненты, буферизуют события в SQLite, отправляют батчами

## Единый формат событий

Все агенты (Windows, Linux, scanner) используют формат `UnifiedEvent`:

- `event_type`: read, write, delete, move, rename
- `event_source`: windows_agent, linux_agent, scanner, api
- `user`, `user_sid`, `file_path`, `source_host`, `metadata`

## Версии

| Версия | Описание |
|--------|----------|
| v1.0.0 | Базовый функционал (обнаружение + классификация + каталог) |
| v2.0.0 | Управление доступом + Аудит Windows (ядро) |
| v2.0.1 | Windows-стек полностью готов |
| v2.1.0 | Linux-агент + унифицированный формат + WebUI фильтр |

## Требования

- Python 3.8+
- Windows: wevtutil (встроен), права администратора для аудита
- Linux: watchdog, optional: paramiko (SSH-мониторинг)
