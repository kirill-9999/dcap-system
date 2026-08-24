# Агент аудита DCAP

Легкий агент для сбора событий файловой системы Windows: читает Security Log через
`wevtutil`, буферизирует события локально (SQLite) и отправляет их в Manager батчами.
Без тяжелых зависимостей (Tesseract, spaCy, Presidio) — только Python + requests.

## Структура

```
audit-agent/
├── main.py                 # Точка входа, основной цикл
├── config.json             # Конфигурация (включая секцию service)
├── config_loader.py        # Загрузка конфига с дефолтами
├── collector.py            # WindowsAuditCollector — чтение Security Log (wevtutil)
├── buffer.py               # BufferManager — локальное хранение событий (SQLite)
├── sender.py               # Sender — отправка событий в Manager
├── heartbeat.py            # HeartbeatSender — регулярный heartbeat
├── service.py              # Обертка Windows-службы (pywin32)
├── install_service.bat     # Установка службы
├── uninstall_service.bat   # Удаление службы
├── start_service.bat       # Запуск службы
├── stop_service.bat        # Остановка службы
├── restart_service.bat     # Перезапуск службы
├── state.json              # Локальное состояние (создается при первом запуске)
├── logs/                   # Папка логов (создается службой)
└── requirements.txt        # requests, pywin32
```

## Установка

```powershell
pip install -r requirements.txt
```

## Настройка

Отредактируйте `config.json`:

| Поле | Описание | По умолчанию |
|------|----------|--------------|
| `manager_url` | URL Manager'а | `http://localhost:8000` |
| `agent_name` | Уникальное имя агента (для регистрации) | `audit-agent-01` |
| `hostname` | Имя хоста, которое увидят в Manager | `SERVER01` |
| `read_interval` | Секунд между чтением Security Log | 60 |
| `batch_size` | Сколько событий отправлять за раз | 100 |
| `buffer_size` | Максимум неотправленных событий в буфере | 10000 |
| `heartbeat_interval` | Секунд между heartbeat | 30 |
| `event_filters` | Event ID для сбора | `[4656, 4660, 4663, 4670, 5140, 5145]` |
| `paths` | Какие папки аудировать (SACL) | `D:\test_audit` |
| `log_level` | Уровень лога | `INFO` |
| `service.*` | Параметры Windows-службы (см. ниже) | см. config.json |

## Установка как служба Windows

### Требования
- Python 3.8+
- pywin32: `pip install pywin32`

### Установка

```powershell
cd audit-agent
pip install -r requirements.txt
python service.py install
python service.py start
```

### Управление

| Команда | Описание |
|---------|----------|
| `python service.py start` | Запуск службы |
| `python service.py stop` | Остановка службы |
| `python service.py restart` | Перезапуск службы |
| `python service.py remove` | Удаление службы |

Также доступны бат-файлы: `install_service.bat`, `start_service.bat`, `stop_service.bat`,
`restart_service.bat`, `uninstall_service.bat`.

### Просмотр логов

Логи пишутся в `logs/audit_agent.log`. Также можно просмотреть в Windows Event Viewer:
- Открыть Event Viewer
- Windows Logs → Application
- Искать события от источника DCAPAuditAgent

### Параметры службы (config.json)

| Поле | Описание |
|------|----------|
| `service.display_name` | Имя службы в системе |
| `service.description` | Описание службы |
| `service.log_file` | Путь к файлу лога (относительно папки агента) |
| `service.max_log_size_mb` | Максимальный размер лога (заготовка под ротацию) |
| `service.restart_on_failure` | Автоперезапуск агента при сбое |
| `service.restart_interval_sec` | Пауза перед перезапуском, сек |

### Удаление

```powershell
python service.py stop
python service.py remove
```

## Настройка аудита Windows (один раз, от администратора)

```powershell
# 1. Включить политику аудита "File System" (GUID работает на любой локали)
auditpol /set /subcategory:{0CCE921D-69AE-11D9-BED3-505054503030} /success:enable /failure:enable

# 2. Назначить SACL на аудируемую папку (например D:\test_audit)
icacls "D:\test_audit" /grant *S-1-1-0:(OI)(CI)(RX,W,DE,DC,WDAC,WO,WA) /T
```

> Чтение Security Log требует прав администратора. Если запустить агента без прав,
> он работает штатно, но собирает 0 событий.

## Запуск

```powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить агент (из папки audit-agent)
cd audit-agent
python main.py

# 3. Либо как Windows-службу (от администратора)
cd audit-agent
python service.py install
python service.py start
```

## Проверка

```powershell
# События появились в Manager
curl "http://localhost:8000/api/audit?limit=10"

# Статус агента в БД
curl "http://localhost:8000/api/audit/stats"
```

## Поведение при потере связи

Если Manager недоступен, события не удаляются: они копятся в SQLite-буфере
(`buffer/buffer.db`, максимум `buffer_size`) и отправляются при восстановлении связи.
