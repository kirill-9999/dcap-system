ТЗ: АГЕНТ АУДИТА — СЛУЖБА WINDOWS И АВТОМАТИЧЕСКИЙ ЗАПУСК (ДЕНЬ 18)
Файл: prompts/tz/day_18_audit_agent_service.md

🎯 ЦЕЛЬ
Превратить агент аудита в полноценную Windows-службу, которая:

Запускается автоматически при старте системы

Работает в фоновом режиме (без консоли)

Имеет управление через стандартные команды (start/stop/restart)

Пишет логи в файл (Event Log или файловый лог)

Автоматически перезапускается при сбоях

Важно: Агент должен быть максимально легким и не требовать установки дополнительных компонентов (кроме Python).

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ/ИЗМЕНЕНИЯ
Создать/изменить:
text
audit-agent/
├── service.py                 # Обертка для запуска как Windows-служба
├── install_service.bat        # Установка службы
├── uninstall_service.bat      # Удаление службы
├── start_service.bat          # Запуск службы
├── stop_service.bat           # Остановка службы
├── restart_service.bat        # Перезапуск службы
├── audit_agent_service.exe    # (опционально) упакованный exe через PyInstaller
├── config.json                # обновлен (добавлены параметры службы)
└── logs/                      # папка для логов (создается автоматически)
    └── audit_agent.log
📋 ДЕТАЛЬНОЕ ТЗ
1. Обновление config.json
Добавить секцию service:

json
{
    "manager_url": "http://localhost:8000",
    "agent_name": "audit-agent-01",
    "hostname": "SERVER01",
    "read_interval": 60,
    "batch_size": 100,
    "buffer_size": 10000,
    "heartbeat_interval": 30,
    "event_filters": [4656, 4660, 4663, 4670, 5140, 5145],
    "paths": ["D:\\test_audit"],
    "log_level": "INFO",
    "service": {
        "display_name": "DCAP Audit Agent",
        "description": "Сбор событий файловой системы для DCAP",
        "log_file": "logs/audit_agent.log",
        "max_log_size_mb": 100,
        "restart_on_failure": true,
        "restart_interval_sec": 60
    }
}
2. Модуль service.py (обертка для Windows-службы)
python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Windows-служба для агента аудита DCAP.

Установка:
    python service.py install
    python service.py start

Удаление:
    python service.py stop
    python service.py remove
"""

import sys
import os
import time
import logging
import threading
from pathlib import Path
from datetime import datetime

# Добавляем текущую папку в путь
sys.path.insert(0, str(Path(__file__).parent))

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("pywin32 not found. Run: pip install pywin32")

from main import AuditAgent
from config_loader import load_config

class AuditAgentService(win32serviceutil.ServiceFramework):
    """Windows-служба для агента аудита"""

    _svc_name_ = "DCAPAuditAgent"
    _svc_display_name_ = "DCAP Audit Agent"
    _svc_description_ = "Сбор событий файловой системы для DCAP (PII/credentials/code)"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.config_path = Path(__file__).parent / "config.json"
        self.running = True
        self.agent = None
        self.agent_thread = None

    def SvcStop(self):
        """Остановка службы"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        if self.agent:
            self.agent.running = False
        if self.agent_thread and self.agent_thread.is_alive():
            self.agent_thread.join(timeout=10)

    def SvcDoRun(self):
        """Запуск службы"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "Запуск службы...")
        )

        # Загрузка конфига
        try:
            config = load_config(self.config_path)
            service_config = config.get("service", {})
            log_file = service_config.get("log_file", "logs/audit_agent.log")
            log_level = config.get("log_level", "INFO")

            # Настройка логирования
            log_path = Path(__file__).parent / log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)
            logging.basicConfig(
                level=getattr(logging, log_level.upper(), logging.INFO),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_path, encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)
                ]
            )
            self.logger = logging.getLogger("AuditAgentService")

            # Создание и запуск агента
            self.agent = AuditAgent(self.config_path)
            self.agent.logger = self.logger  # передаем логгер

            # Запуск агента в отдельном потоке
            self.agent_thread = threading.Thread(
                target=self._run_agent,
                daemon=True
            )
            self.agent_thread.start()

            self.logger.info(f"Служба {self._svc_name_} запущена")

            # Ожидание сигнала остановки
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

        except Exception as e:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_ERROR_TYPE,
                servicemanager.PYS_SERVICE_FAILED,
                (self._svc_name_, str(e))
            )
            raise

    def _run_agent(self):
        """Запуск агента с перезапуском при сбоях"""
        service_config = self.config.get("service", {})
        restart_on_failure = service_config.get("restart_on_failure", True)
        restart_interval = service_config.get("restart_interval_sec", 60)

        while self.running:
            try:
                if self.agent:
                    self.agent.run()
                else:
                    time.sleep(1)
            except Exception as e:
                self.logger.error(f"Ошибка в агенте: {e}")
                if restart_on_failure and self.running:
                    self.logger.info(f"Перезапуск через {restart_interval} сек...")
                    time.sleep(restart_interval)
                    # Пересоздаем агента
                    self.agent = AuditAgent(self.config_path)
                    self.agent.logger = self.logger
                else:
                    break

def main():
    """Точка входа для установки/запуска службы"""
    if not WIN32_AVAILABLE:
        print("pywin32 не установлен. Установите: pip install pywin32")
        sys.exit(1)

    if len(sys.argv) == 1:
        # Запуск агента в консольном режиме (для отладки)
        from main import main as agent_main
        agent_main()
    else:
        win32serviceutil.HandleCommandLine(AuditAgentService)

if __name__ == '__main__':
    main()
3. Модуль config_loader.py (загрузка конфига)
python
import json
import logging
from pathlib import Path
from typing import Dict, Any

def load_config(config_path: Path) -> Dict[str, Any]:
    """Загрузка конфигурации из JSON-файла"""
    if not config_path.exists():
        raise FileNotFoundError(f"Конфиг не найден: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Значения по умолчанию
    defaults = {
        "manager_url": "http://localhost:8000",
        "agent_name": "audit-agent-01",
        "hostname": "localhost",
        "read_interval": 60,
        "batch_size": 100,
        "buffer_size": 10000,
        "heartbeat_interval": 30,
        "event_filters": [4656, 4660, 4663, 4670, 5140, 5145],
        "paths": [],
        "log_level": "INFO",
        "service": {
            "display_name": "DCAP Audit Agent",
            "description": "Сбор событий файловой системы для DCAP",
            "log_file": "logs/audit_agent.log",
            "max_log_size_mb": 100,
            "restart_on_failure": True,
            "restart_interval_sec": 60
        }
    }

    # Рекурсивное заполнение
    def merge_defaults(target, source):
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target.get(key), dict):
                merge_defaults(target[key], value)

    merge_defaults(config, defaults)
    return config
4. Скрипты установки/управления
install_service.bat
batch
@echo off
echo Установка службы DCAP Audit Agent...
python service.py install
echo Служба установлена.
echo Для запуска выполните: python service.py start
pause
uninstall_service.bat
batch
@echo off
echo Остановка и удаление службы DCAP Audit Agent...
python service.py stop
python service.py remove
echo Служба удалена.
pause
start_service.bat
batch
@echo off
echo Запуск службы DCAP Audit Agent...
python service.py start
pause
stop_service.bat
batch
@echo off
echo Остановка службы DCAP Audit Agent...
python service.py stop
pause
restart_service.bat
batch
@echo off
echo Перезапуск службы DCAP Audit Agent...
python service.py stop
timeout /t 3
python service.py start
pause
5. Обновленный .gitignore
Добавить:

gitignore
# Агент аудита (runtime)
audit-agent/state.json
audit-agent/state*.json
audit-agent/buffer/
audit-agent/logs/
audit-agent/*.db
audit-agent/*.log
audit-agent/*.exe
audit-agent/build/
audit-agent/dist/
audit-agent/*.spec
6. Документация (README.md)
Обновить раздел "Установка как служба Windows":

markdown
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
Управление
Команда	Описание
python service.py start	Запуск службы
python service.py stop	Остановка службы
python service.py restart	Перезапуск службы
python service.py remove	Удаление службы
Просмотр логов
Логи пишутся в logs/audit_agent.log. Также можно просмотреть в Windows Event Viewer:

Открыть Event Viewer

Windows Logs → Application

Искать события от источника DCAPAuditAgent

Удаление
powershell
python service.py stop
python service.py remove
text

---

## ✅ КРИТЕРИИ ПРИЕМКИ

- [ ] Создан модуль `service.py` (Windows-служба)
- [ ] Создан `config_loader.py` (загрузка конфига с дефолтами)
- [ ] Созданы бат-файлы: install, uninstall, start, stop, restart
- [ ] Агент запускается как Windows-служба
- [ ] Агент работает в фоновом режиме
- [ ] Логи пишутся в файл (`logs/audit_agent.log`)
- [ ] При сбое агент автоматически перезапускается
- [ ] Обновлен `.gitignore`
- [ ] Обновлен `README.md`

---

## 🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

```powershell
# 1. Установка службы
cd audit-agent
pip install pywin32
python service.py install

# 2. Запуск службы
python service.py start

# 3. Проверка статуса
sc query DCAPAuditAgent

# 4. Просмотр логов
type logs\audit_agent.log

# 5. Остановка
python service.py stop

# 6. Удаление
python service.py remove
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
audit-agent/
├── main.py                 # ✅
├── config.json             # ✅ (обновлен)
├── config_loader.py        # ✅ новый
├── collector.py            # ✅
├── buffer.py               # ✅
├── sender.py               # ✅
├── heartbeat.py            # ✅
├── service.py              # ✅ новый
├── install_service.bat     # ✅ новый
├── uninstall_service.bat   # ✅ новый
├── start_service.bat       # ✅ новый
├── stop_service.bat        # ✅ новый
├── restart_service.bat     # ✅ новый
├── requirements.txt        # ✅ + pywin32
├── README.md               # ✅ обновлен
└── logs/                   # ✅ создается при запуске
    └── audit_agent.log
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_18_audit_agent_service
git add audit-agent/
git commit -m "feat: День 18 — агент аудита как Windows-служба"
Разработчик (кодер), приступай! 🚀