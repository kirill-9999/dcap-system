# Отчет: День 17 — Агент аудита (сбор, буферизация, отправка)

**Дата:** 2026-08-15
**Файл ТЗ:** `prompts/tz/day_17_audit_agent.md`

## 🎯 Цель

Реализовать ядро легкого агента аудита для файловых серверов (и ноутбука разработчика):
чтение Security Log через wevtutil, локальная буферизация (SQLite) при потере связи с
Manager, отправка событий батчами по HTTP с подтверждением, регулярный heartbeat.
Без тяжелых зависимостей — только Python + requests.

## 📁 Созданные файлы

```
audit-agent/
├── main.py            # ✅ создан — AuditAgent, основной цикл (регистрация, heartbeat, сбор+отправка)
├── config.json        # ✅ создан — конфигурация (по ТЗ)
├── collector.py       # ✅ создан — WindowsAuditCollector (wevtutil Security Log)
├── buffer.py          # ✅ создан — BufferManager (SQLite, буфер с trim/очисткой)
├── sender.py          # ✅ создан — Sender (POST /api/audit/events, send_heartbeat)
├── heartbeat.py       # ✅ создан — HeartbeatSender (POST /api/audit/agents/heartbeat)
├── requirements.txt   # ✅ создан — requests>=2.28.0
└── README.md          # ✅ создан — установка, настройка, запуск
```

`state.json` и `buffer/` генерируются при запуске и уже покрыты `.gitignore`
(`state*.json`, `*.db`) — в коммит не попадают.

## 🔄 Адаптации/исправления (отклонения от буквы ТЗ)

1. **Баг ТЗ в `buffer.py`**: `DELETE FROM events WHERE sent=0 ORDER BY id LIMIT ?` — SQLite не
   поддерживает `ORDER BY` в `DELETE` (проверено: `sqlite3.OperationalError: near "ORDER": syntax error`).
   Исправлено через подзапрос:
   `DELETE FROM events WHERE id IN (SELECT id FROM events WHERE sent=0 ORDER BY id LIMIT ?)`.
2. **`heartbeat_interval` не использовался в ТЗ main.py** (heartbeat слался каждую итерацию цикла).
   Реализован по смыслу конфига: heartbeat отправляется раз в `heartbeat_interval` секунд.
3. **`heartbeat.py` подключен в main.py** через `HeartbeatSender` (файл из списка ТЗ задействован,
   не мёртвый код); `Sender.send_heartbeat` также сохранён (по секции 5 ТЗ).
4. Логирование — через `logging` с уровнем из конфига (`log_level`), вместо `print` из ТЗ
   (сообщения по смыслу те же).
5. Регистрация прокидывает `agent_id` в `Sender` и `HeartbeatSender`, сохраняет в `state.json`.

## 📊 Результаты прогона

Окружение: Windows, Python 3.13 (`/d/dev/anaconda3/python`, PYTHONUTF8=1), живой Manager
:8000 (PID 27468).

### Unit-тесты (12/12 OK)
```
OK collector: 2 события (9999 отфильтрован)
OK collector: event[0] = write, event[1] = delete
OK collector: old_path сохранен, created_at сохранен
OK buffer: trim до max_size=10
OK buffer: get_unsent(3) старые первыми (f5,f6,f7)
OK buffer: mark_sent -> 7 unsent
OK buffer: clear_sent -> 7 rows
OK sender: недоступный Manager -> False
OK buffer: события остаются в буфере при недоступном Manager
```

### E2E (реальный `main.py` против живого Manager, 10/10 OK)
```
✅ state.json: agent_id записан (agent_id=1)
✅ Manager: агент зарегистрирован (e2e-audit-test, E2E-TEST-HOST, online)
✅ Manager: events_sent >= 3 (события из предзаполненного буфера отправлены)
✅ Manager: 3 события в audit_logs
✅ last_read обновлен при сборе событий (фейковый коллектор)
✅ событие из буфера отправлено (0 unsent)
✅ буфер опустошен и очищен (clear_sent)
✅ тестовые данные вычищены из БД Manager
```
Лог агента: `Запуск: e2e-audit-test → Зарегистрирован, ID: 1 → Отправлено 3 событий`.

### Прогон из `audit-agent/`
`cd audit-agent; python main.py` — стартует, находит `config.json`, регистрирует
`audit-agent-01` (ID 1, hostname SERVER01, online). После проверки агент удалён из БД,
`state.json`/`buffer/` удалены.

## ⚠️ Замечания

1. **Security Log требует прав администратора.** На этой машине `wevtutil qe Security` даёт
   "Access is denied" → агент собирает 0 событий (штатное поведение). Для реального сбора —
   запускать агента от администратора + включить аудит:
   `auditpol /set /subcategory:{0CCE921D-69AE-11D9-BED3-505054503030} /success:enable /failure:enable`
   + SACL: `icacls "D:\test_audit" /grant *S-1-1-0:(OI)(CI)(RX,W,DE,DC,WDAC,WO,WA) /T`.
2. **`datetime.utcnow()`** — DeprecationWarning на Python 3.12+. Оставлено для единообразия с
   кодовой базой (`manager/src/db/models.py` и др. используют `datetime.utcnow`).
3. **Неиспользуемый импорт** `json` в `collector.py` — по ТЗ дословно (ruff F401 при будущем прогоне).
4. **Буферизация при потере связи** проверена на уровне Sender (Manager недоступен → события
   остаются в буфере); при восстановлении связи батч отправляется (E2E: предзаполненный буфер
   отправлен первым циклом).

## 🧪 Как проверить (сценарий из ТЗ)

```powershell
# 1. Настроить аудит (администратор): auditpol + SACL на D:\test_audit (см. README)
# 2. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000
# 3. Запустить агент
cd audit-agent
python main.py
# 4. Создать/удалить файлы в тестовой папке
# 5. Проверить события
curl "http://localhost:8000/api/audit?limit=10"
```

## 📁 Структура после выполнения

```
dcap-system/
├── audit-agent/                       # ✅ агент аудита
│   ├── main.py  config.json  collector.py  buffer.py
│   ├── sender.py  heartbeat.py  requirements.txt  README.md
│   └── state.json, buffer/            # runtime, gitignored
├── manager/src/
│   ├── api/audit.py                   # ✅ (День 16)
│   └── connectors/audit/windows_audit.py  # ✅ (День 16)
└── prompts/tz/day_17_audit_agent.md   # ✅ это ТЗ
```

## 💾 Команда для коммита

```bash
git checkout -b feature/day_17_audit_agent
git add audit-agent/ AGENTS.md
git commit -m "feat: День 17 — ядро агента аудита (сбор, буферизация, отправка)"
```
