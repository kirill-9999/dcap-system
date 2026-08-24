# Отчет: День 16 — Модель AuditLog и архитектура агента аудита (скорректированное ТЗ)

**Дата:** 2026-08-15
**Файл ТЗ:** `prompts/tz/day_16_auditlog.md` (скорректированное)

## 🎯 Цель

Заложить фундамент системы аудита DCAP: модели `AuditAgent` и `AuditLog`, API для
регистрации агентов/heartbeat/приёма событий, чтение Security Log через wevtutil
(`auditpol` + SACL, без secpol.msc — Windows 10 Home).

## 📁 Измененные/созданные файлы

| Файл | Статус |
|------|--------|
| `manager/src/db/models.py` | ✅ изменен — модели `AuditAgent` и `AuditLog` (агентная схема) |
| `manager/src/api/audit.py` | ✅ переписан — API агентов и аудита (5 эндпоинтов) |
| `manager/src/connectors/audit/windows_audit.py` | ✅ обновлен — wevtutil с limit, новые Event ID |
| `manager/src/connectors/audit/__init__.py` | ✅ без изменений |
| `manager/src/main.py` | ✅ без изменений (роутер уже подключен) |
| `AGENTS.md` | ✅ обновлен (структура, агентная модель аудита) |

`init_db.py` не менялся: `init_db()` → `models.Base.metadata.create_all()` автоматически
создаёт `audit_agents` и `audit_logs` (критерий приёмки выполнен через create_all).

## 🔄 Адаптация под реальный код (отклонения от буквы ТЗ)

1. **`metadata` зарезервировано в SQLAlchemy Declarative.** `metadata = Column(JSON, ...)`
   → `InvalidRequestError`. Решение: имя колонки в БД по ТЗ (`metadata`), имя Python-атрибута —
   `metadata_json` (`Column("metadata", JSON, default={})`). JSON-ответы API возвращают ключ `metadata`.
2. **Тестовый сценарий vs сигнатуры эндпоинтов.** В ТЗ сигнатуры register/heartbeat/events —
   простые аргументы (FastAPI трактует как query), но сценарий приёмки шлёт JSON-body
   (`-d '{"name":...}'`), что давало 422. Решено в пользу сценария приёмки: введены body-модели
   `RegisterAgentRequest`, `HeartbeatRequest`, `IngestEventsRequest`.
3. **Старые эндпоинты удалены.** `/api/audit/resource/{id}`, `/api/audit/user/{user}` и
   `POST /api/audit/sync` (pull-архитектура) заменены на агентную модель по скорректированному ТЗ.
4. **Схема БД `audit_logs` изменена** (агентная): добавлены `agent_id` (FK `audit_agents.id`),
   `source_host`; убраны `resource_id` и связь `Resource.audit_logs`. Таблица была пустой —
   `DROP TABLE audit_logs` и пересоздание через `create_all`.

## 📊 Результаты прогона (TestClient + live :8000)

Окружение: Windows, Python `/d/dev/anaconda3/python` (PYTHONUTF8=1), БД `manager/dcap.db`.

```
✅ audit_agents: id, name, hostname, ip_address, status, version, config, last_heartbeat,
                 registered_at, last_error, events_sent, events_failed, last_event_at
✅ audit_logs: id, agent_id, event_type, event_source, user, user_sid, file_path,
               old_path, source_host, metadata, created_at
✅ POST /api/audit/agents/register        → 200 {status:"registered", agent_id:1}
✅ POST /api/audit/agents/register (дубль) → 200 {status:"updated", agent_id:1}
✅ POST /api/audit/agents/heartbeat       → 200 {status:"ok"} (stats: events_sent, last_event_at)
✅ POST /api/audit/agents/heartbeat (нет агента) → 404
✅ POST /api/audit/events                 → 200 {status:"accepted", saved:3}, source_host=hostname агента
✅ POST /api/audit/events (нет агента)    → 404
✅ GET /api/audit                         → total=3; фильтры agent_id/event_type/user/file_path/since; пагинация; bad since игнорируется
✅ GET /api/audit/stats                   → total=3, by_type, top_users
✅ Тестовые данные вычищены (agents=0, logs=0)
✅ Живой Manager :8000 перезапущен (PID 27468): register → registered, ingest → accepted, stats → total=1, затем очищено
```

## ⚠️ Замечания (найти/дефекты)

1. **`GET /api/audit?agent_id=` (пустой query)** → 422 (FastAPI не парсит пустую строку в int).
   В реальном WebUI параметр просто опускается — не блокер.
2. **Security Log по-прежнему требует прав администратора** — чтение через wevtutil без прав даёт
   "Access is denied", `collect_events` вернёт `[]`. Настройка аудита на Windows 10 Home:
   `auditpol /set /subcategory:{0CCE921D-69AE-11D9-BED3-505054503030} /success:enable /failure:enable`
   + SACL через `icacls /grant *S-1-1-0:(OI)(CI)(RX,W,DE,DC,WDAC,WO,WA) /T`.
3. **Неиспользуемый импорт** `import re` в `windows_audit.py` — оставлен дословно по ТЗ
   (ruff F401 при будущем прогоне).
4. **Фактический агент** (сбор/буферизация/отправка) — по ТЗ только каркас; сам агент будет в
   следующих днях. `POST /api/audit/events` уже принимает события по контракту.
5. **TODO в коде**: генерация API key для агентов (по ТЗ — в Дни 35-37).

## 🧪 Как проверить (сценарий из ТЗ)

```powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Зарегистрировать агента
curl -X POST http://localhost:8000/api/audit/agents/register `
  -H "Content-Type: application/json" `
  -d '{"name":"test-agent","hostname":"DESKTOP-ABC"}'

# 3. Отправить тестовое событие
curl -X POST http://localhost:8000/api/audit/events `
  -H "Content-Type: application/json" `
  -d '{"agent_id":1,"events":[{"event_type":"read","user":"test","file_path":"D:\\test.txt"}]}'

# 4. Проверить сохранение
curl "http://localhost:8000/api/audit?limit=10"
```

## 📁 Структура после выполнения

```
dcap-system/
├── manager/
│   └── src/
│       ├── db/models.py              # ✅ + AuditAgent, AuditLog (агентная)
│       ├── api/audit.py              # ✅ создан (register, heartbeat, events, audit, stats)
│       ├── connectors/audit/
│       │   ├── __init__.py           # ✅
│       │   └── windows_audit.py      # ✅ создан (WindowsAuditCollector, wevtutil)
│       └── main.py                   # ✅ + audit_router
├── prompts/
│   └── tz/day_16_auditlog.md         # ✅ это ТЗ (скорректированное)
└── test_files/
```

## 💾 Команда для коммита

```bash
git checkout -b feature/day_16_auditlog
git add manager/src/db/models.py manager/src/main.py manager/src/api/audit.py manager/src/connectors/audit/ AGENTS.md
git commit -m "feat: День 16 — модель AuditLog и архитектура агента аудита"
```
