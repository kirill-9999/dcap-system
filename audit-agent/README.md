# Агент аудита DCAP

Легкий агент для сбора событий файловой системы Windows: читает Security Log через
`wevtutil`, буферизирует события локально (SQLite) и отправляет их в Manager батчами.
Без тяжелых зависимостей (Tesseract, spaCy, Presidio) — только Python + requests.

## Структура

```
audit-agent/
├── main.py            # Точка входа, основной цикл
├── config.json        # Конфигурация
├── collector.py       # WindowsAuditCollector — чтение Security Log (wevtutil)
├── buffer.py          # BufferManager — локальное хранение событий (SQLite)
├── sender.py          # Sender — отправка событий в Manager
├── heartbeat.py       # HeartbeatSender — регулярный heartbeat
├── state.json         # Локальное состояние (создается при первом запуске)
└── requirements.txt   # requests
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
