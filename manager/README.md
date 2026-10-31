# DCAP Manager

FastAPI-сервер (:8000), чистое API без UI. WebUI живёт отдельно на :8001.

## Запуск

```powershell
# Инициализация БД
python init_db.py

# Запуск
python -m uvicorn manager.src.main:app --port 8000 --reload
```

`/` редиректит на `http://localhost:8001` (WebUI).

## Структура

```
manager/src/
├── main.py              # FastAPI app, подключение роутеров
├── api/
│   ├── resources.py     # /api/resources — CRUD ресурсов для сканирования
│   ├── tasks.py         # /api/tasks — задания сканеру
│   ├── findings.py      # /api/findings — находки (PII, credentials, code)
│   ├── catalog.py       # /api/catalog — файловый каталог
│   ├── scanner.py       # /api/scanner — регистрация/heartbeat сканеров
│   ├── permissions.py   # /api/permissions — управление доступом
│   └── audit.py         # /api/audit — агенты аудита, события, статистика
├── db/
│   ├── models.py        # SQLAlchemy модели (10 таблиц)
│   ├── session.py       # Сессия SQLite
│   └── migrations/      # Миграции
├── connectors/
│   └── permissions/     # Коллекторы прав: local (icacls), remote, ad
├── services/
│   └── access_service.py # Логика анализа прав
└── core/                # Ядро
```

## API Эндпоинты

### Ресурсы
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/resources` | Список ресурсов |
| POST | `/api/resources?path=...&type=...` | Создать ресурс |
| DELETE | `/api/resources/{id}` | Удалить ресурс |
| POST | `/api/resources/{id}/scan` | Запустить сканирование |

### Задания
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/tasks` | Список заданий |

### Находки
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/findings` | Список находок |

### Каталог
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/catalog` | Список каталога |
| GET | `/api/catalog/tree` | Дерево каталога |

### Сканеры
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/scanner/register` | Регистрация сканера |
| POST | `/api/scanner/heartbeat` | Heartbeat сканера |

### Управление доступом
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/permissions/mode` | Режим доступа |

### Аудит
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/audit/agents/register` | Регистрация агента аудита |
| POST | `/api/audit/agents/heartbeat` | Heartbeat агента |
| POST | `/api/audit/events` | Приём событий |
| GET | `/api/audit` | Просмотр событий |
| GET | `/api/audit/stats` | Статистика |
| POST | `/api/audit/report/preview` | Предпросмотр отчёта |
| GET | `/api/audit/report/export/excel` | Экспорт Excel |
| GET | `/api/audit/report/export/pdf` | Экспорт PDF |

### Системные
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | Health check |
| GET | `/api/root` | Информация API |
| GET | `/docs` | Swagger UI |

## БД

SQLite: `manager/dcap.db` (создаётся `init_db.py`).

Таблицы: resources, tasks, findings, catalog, scanners, audit_agents, audit_logs, access_entries, access_alerts, permission_changes.

## Зависимости

- FastAPI, uvicorn, SQLAlchemy, aiosqlite
- openpyxl (Excel), reportlab (PDF)
- pyinotify/watchdog не нужны — Manager только API
