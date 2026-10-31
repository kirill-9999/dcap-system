# Инструкция по запуску компонентов DCAP System

Способы запуска всех компонентов системы:

1. **Скриптами `run_<модуль>.py`** (локально, из корня репо) — основной способ.
2. **Как сервисы** — Windows-агент через pywin32 (`service.py`), Linux-агент через systemd/cron.

---

## 1. Общие принципы

- Все компоненты запускаются единообразно скриптами `run_<модуль>.py` из корня репо (`D:\Projects\dcap-system`).
- **Порядок запуска:** Manager → WebUI / Scanner / агенты.
- Компоненты, принимающие конфиг, — **конфиг обязателен** (без него запуск невозможен, значений по умолчанию нет).
- Компоненты делят одну БД — `manager/src/db/dcap.db` (создаётся `init_db.py` при первом запуске).

| Компонент | Скрипт запуска | Порт/конфиг |
|-----------|----------------|-------------|
| Manager | `run_manager.py` | API на `:8000` |
| WebUI | `run_webui.py` | UI на `:8001` |
| Scanner | `run_scanner.py` | конфиг обязателен |
| Windows-агент аудита | `run_audit_agent.py` | конфиг обязателен |
| Linux-агент аудита | `start.sh` (внутри Linux) | конфиг обязателен |

---

## 2. Запуск скриптами (локально, Windows)

Выполнять из корня репо `D:\Projects\dcap-system`.

### 2.1 База данных (только первый раз)

```powershell
python init_db.py
```

Создаёт `manager/src/db/dcap.db`. Manager и WebUI используют эту же БД.

### 2.2 Manager (API на :8000)

```powershell
python run_manager.py
```

Обёртка над `manager.src.main:app` (uvicorn, host `127.0.0.1`, port `8000`). Без конфига-аргумента.

### 2.3 WebUI (дашборд на :8001)

```powershell
python run_webui.py
```

Обёртка над `webui.main:app` (uvicorn, `:8001`). Слушает только `127.0.0.1`.

### 2.4 Scanner (ждёт Manager на :8000)

```powershell
python run_scanner.py scanner/config/scanner_config.json
```

Конфиг обязателен и должен содержать все обязательные секции/параметры (строгая валидация в `scanner/src/config_loader.py`).
Оффлайн-режим: при недоступности Manager результаты сохраняются в `scanner/data/offline/` и автоматически отправляются при восстановлении связи.

Примечание для Windows: при проблемах с кириллицей в консоли используйте

```powershell
PYTHONUTF8=1 python run_scanner.py scanner/config/scanner_config.json
```

### 2.5 Windows-агент аудита

```powershell
python run_audit_agent.py audit-agent-windows/config.json
```

- Конфиг обязателен (`audit-agent-windows/config.json`).
- Скрипт добавляет `audit-agent-windows/` в `sys.path` и вызывает `main.run(config)`.
- Runtime-данные (`data/state.json`, `data/buffer/`) создаются в `audit-agent-windows/data/`.
- События шлются в `POST /api/audit/events` батчами; при недоступности Manager копятся в буфере.

### 2.6 Linux-агент аудита

Запускается **внутри Linux-окружения** (на Windows сработает только подсказка через `run_audit_agent_linux.py`):

```bash
cd audit-agent-linux
./start.sh --daemon
```

или вручную:

```bash
cd audit-agent-linux
python main.py config.json
```

- Конфиг обязателен (`audit-agent-linux/config.json`).
- Runtime-данные (`data/state.json`) создаются в `audit-agent-linux/data/`.
- Heartbeat: `POST /api/audit/agents/heartbeat` с `agent_type="linux_agent"`.

---

## 3. Запуск как сервис

### 3.1 Windows-агент (Windows-служба через pywin32)

Все операции выполняются **от имени администратора** (PowerShell/cmd «Запуск от имени администратора»), из папки агента:

```bat
cd /d D:\Projects\dcap-system\audit-agent-windows
```

#### Через service.py

```bat
python service.py install    REM установить службу
python service.py start      REM запустить
python service.py stop       REM остановить
python service.py restart    REM перезапустить
python service.py remove     REM удалить
```

#### Через bat-файлы

```bat
install_service.bat   REM установить
start_service.bat     REM запустить
stop_service.bat      REM остановить
restart_service.bat   REM перезапустить
uninstall_service.bat REM удалить
```

#### Через sc (тоже от администратора)

```bat
sc query DCAPAuditAgent
sc start DCAPAuditAgent
sc stop DCAPAuditAgent
sc delete DCAPAuditAgent
```

- Имя службы: `DCAPAuditAgent` (отображаемое «DCAP Audit Agent»).
- Требуются права администратора.
- Логи службы — `audit-agent-windows/logs/audit_agent.log` (служба также пишет в Event Viewer → Application).
- **Важно после переименования `audit-agent` → `audit-agent-windows`:** ранее установленная служба указывает на старый каталог. Для корректной работы из новой папки переустановите службу:

```bat
cd /d D:\Projects\dcap-system\audit-agent-windows
python service.py remove
python service.py install
python service.py start
```

Это также освобождает блокировку на старом `audit-agent/buffer/buffer.db`, после чего старый каталог `audit-agent/` можно удалить вручную.

### 3.2 Linux-агент (systemd или cron)

Файлы службы — в `audit-agent-linux/service/`.

#### systemd (рекомендуется)

```bash
cd audit-agent-linux/service

./install.sh          # установить и включить (systemd-юнит dcap-audit-agent)
./uninstall.sh        # остановить и удалить
```

Управление вручную (от sudo):

```bash
sudo systemctl enable --now dcap-audit-agent
sudo systemctl restart dcap-audit-agent
sudo systemctl status dcap-audit-agent
sudo systemctl stop dcap-audit-agent
```

#### cron (альтернатива без systemd, например WSL)

```bash
cd audit-agent-linux/service

./install_cron.sh     # добавить задание в crontab
./uninstall_cron.sh   # убрать задание
```

> Примечание: проверьте настройку systemd-юнита `dcap-audit-agent.service` — `ExecStart` может содержать абсолютный путь проекта (например `/home/<user>/dcap-system/audit-agent-linux/...`) и должен указывать на ваш рабочий каталог, а также передавать конфиг как аргумент (`main.py config.json`).

---

## 4. Быстрая памятка (полный запуск всей системы на Windows)

```powershell
cd D:\Projects\dcap-system

python init_db.py                                    # только первый раз

# Терминал 1:
python run_manager.py                                # Manager :8000

# Терминал 2:
python run_webui.py                                  # WebUI :8001

# Терминал 3:
python run_scanner.py scanner/config/scanner_config.json

# Терминал 4:
python run_audit_agent.py audit-agent-windows/config.json
```

После запуска:
- WebUI: `http://localhost:8001`
- Manager `/` редиректит на WebUI
- Health API Manager: `http://localhost:8000/api/health`

---

## 5. Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `Unexpected UTF-8 BOM` при чтении state/config | Файл записан с BOM (PowerShell `Set-Content -Encoding utf8`). Использовать загрузчики с `utf-8-sig` либо пересохранить файл без BOM |
| Сканер не подключается к Manager | Убедиться, что Manager запущен на `:8000` и в конфиге сканера верный `manager_url` |
| Windows-агент получает 0 событий | Чтение журнала Security требует прав администратора |
| Служба не обновляет данные после переименования папки | Переустановить службу из `audit-agent-windows` (см. п. 3.1) |
| Нельзя удалить старый `audit-agent/` | Это runtime-файлы, заблокированы работающей службой `DCAPAuditAgent` — остановить/удалить службу с правами администратора |
| Нет прав администратора у текущей сессии | Проверить: `[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)` → `False` означает, что операции со службой требуют запуска от администратора |

---

## 6. Компоненты и их назначение

| Компонент | Назначение |
|-----------|------------|
| `manager/` | FastAPI control-plane, API на `:8000`, БД `manager/src/db/dcap.db` |
| `webui/` | Дашборд (HTML инлайн в Python), `:8001` |
| `scanner/` | Тяжёлый агент сканирования (ManagedScanner, presidio/spacy) |
| `audit-agent-windows/` | Лёгкий Windows-агент аудита (wevtutil Security Log) |
| `audit-agent-linux/` | Лёгкий Linux-агент аудита (watchdog/inotify + SSH) |
| `shared/` | Единая схема событий `UnifiedEvent` |
