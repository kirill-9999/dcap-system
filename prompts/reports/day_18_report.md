# Отчет: День 18 — Агент аудита как Windows-служба

**Дата:** 2026-08-16
**Файл ТЗ:** `prompts/tz/day_18_audit_agent_service.md`

## 🎯 Цель

Превратить агент аудита в полноценную Windows-службу: автозапуск при старте системы,
фоновая работа без консоли, управление через стандартные команды (start/stop/restart),
логирование в файл, автоматический перезапуск при сбоях. Без лишних зависимостей —
только Python + requests + pywin32.

## 📁 Созданные/измененные файлы

```
audit-agent/
├── main.py                 # ✅ изменен — добавлена функция main() + алиас self.logger
├── config.json             # ✅ обновлен — добавлена секция "service"
├── config_loader.py        # ✅ создан — load_config с рекурсивным merge дефолтов
├── service.py              # ✅ создан — Windows-служба (pywin32)
├── install_service.bat     # ✅ создан
├── uninstall_service.bat   # ✅ создан
├── start_service.bat       # ✅ создан
├── stop_service.bat        # ✅ создан
├── restart_service.bat     # ✅ создан
├── requirements.txt        # ✅ обновлен — + pywin32>=305
└── README.md               # ✅ обновлен — раздел "Установка как служба Windows"
```

Также обновлен корневой `.gitignore` (секция «Агент аудита (runtime)») и `AGENTS.md`.

## 🔄 Адаптации/исправления (отклонения от буквы ТЗ)

1. **Баг ТЗ в `service.py`**: `_run_agent()` обращается к `self.config`, но ТЗ нигде его не
   присваивал (`config = load_config(...)` был локальной переменной в `SvcDoRun`) →
   AttributeError при сбое агента. Исправлено: `self.config = load_config(self.config_path)`
   в `__init__`, `SvcDoRun` использует `self.config`.
2. **Логгер агента**: в ТЗ `service.py` передаёт логгер в `self.agent.logger`, но агент дня 17
   логирует через `self.log`. В `service.py` теперь переприсваиваются **оба**
   (`self.agent.logger` и `self.agent.log`), в `main.py` добавлен алиас `self.logger = self.log`
   для совместимости. Логи агента идут в `logs/audit_agent.log`.
3. **`main()` в `main.py`**: ТЗ `service.py` вызывает `from main import main as agent_main` —
   раньше цикл был под `if __name__ == "__main__"`. Вынесен в функцию `main()`.
4. Бат-файлы дополнены `chcp 65001` (кириллица в консоли) и `cd /d "%~dp0"` (работа из любой
   папки).
5. `logging.basicConfig` в `AuditAgent.__init__` при запуске в службе — no-op (root-хендлеры
   уже настроены службой), так что дублирования логов в файл нет.

## 📊 Результаты прогона

Окружение: Windows, Python 3.13 (`/d/dev/anaconda3/python`), pywin32 установлен.
Оболочка — **НЕ под администратором**.

```
OK compile: main.py / config_loader.py / service.py
OK config_loader: секция service загружена (display_name, log_file, restart_*)
OK config_loader: read_interval=60, heartbeat_interval=30, event_filters совпали
OK import service: WIN32_AVAILABLE=True, _svc_name_=DCAPAuditAgent, display=DCAP Audit Agent
OK main.main() существует (для консольного режима службы)
OK python service.py garbage -> usage pywin32 (HandleCommandLine работает)
OK python service.py install -> найден pythonservice.exe, штатная установка pywin32,
   затем "Отказано в доступе. (5)" — ожидаемо (нет прав администратора), служба НЕ создана
   (sc query DCAPAuditAgent -> 1060)
```

Полноценная установка/запуск службы невозможна в этой сессии — требуется администратор.

## ⚠️ Замечания

1. **Установка службы требует прав администратора** (SCM). На этой машине оболочка без
   администрирования → `python service.py install` падает с «Отказано в доступе» до создания
   службы. Проверено, что путь установки pywin32 отрабатывает корректно.
2. **Автоперезапуск при сбоях** реализован в `_run_agent`: при `Exception` агент
   пересоздаётся через `restart_interval_sec` (по умолчанию 60). Примечание: агент при
   неудачной регистрации вызывает `sys.exit(1)` (SystemExit не перехватывается
   `except Exception`) — это поведение унаследовано от ТЗ дня 17 и оставлено как есть.
3. **`max_log_size_mb`** — заготовка под ротацию (значение хранится в конфиге, ротация не
   реализована по ТЗ).
4. `logs/audit_agent.log` создается службой при запуске (в этой сессии папки `logs/` нет —
   запуска службы не было).
5. При неудачной попытке `install` pywin32 скопировал `pythonservice.exe`/`pywintypes313.dll`
   в `d:\dev\anaconda3\` — это стандартные артефакты установки pywin32, вне репозитория.

## 🧪 Как проверить (сценарий из ТЗ, от администратора)

```powershell
cd audit-agent
pip install pywin32
python service.py install
python service.py start
sc query DCAPAuditAgent
type logs\audit_agent.log
python service.py stop
python service.py remove
```

## 📁 Структура после выполнения

```
audit-agent/
├── main.py                 # ✅ (изменен: main(), self.logger)
├── config.json             # ✅ (обновлен: секция service)
├── config_loader.py        # ✅ новый
├── collector.py  buffer.py  sender.py  heartbeat.py   # ✅ (День 17)
├── service.py              # ✅ новый
├── install_service.bat     # ✅ новый
├── uninstall_service.bat   # ✅ новый
├── start_service.bat       # ✅ новый
├── stop_service.bat        # ✅ новый
├── restart_service.bat     # ✅ новый
├── requirements.txt        # ✅ (+ pywin32)
├── README.md               # ✅ (обновлен)
└── logs/audit_agent.log    # создается службой при запуске
```

Критерии приемки: ✅ service.py, ✅ config_loader.py, ✅ 5 бат-файлов,
⬜ установка/работа службы и файловый лог (не проверено — нет прав администратора),
✅ автоперезапуск в коде `_run_agent`, ✅ `.gitignore`, ✅ `README.md`.

## 💾 Команда для коммита

```bash
git checkout -b feature/day_18_audit_agent_service
git add audit-agent/ .gitignore AGENTS.md
git commit -m "feat: День 18 — агент аудита как Windows-служба"
```
