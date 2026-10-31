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
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict

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
from main import REQUIRED_CONFIG_KEYS

def _load_config(config_path: Path) -> Dict:
    """Строгая загрузка конфига (без значений по умолчанию)."""
    with open(config_path, 'r', encoding='utf-8-sig') as f:
        config = json.load(f)

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        raise ValueError(
            f"В конфиге {config_path} отсутствуют обязательные параметры: "
            f"{', '.join(missing)}"
        )
    return config


class AuditAgentService(win32serviceutil.ServiceFramework):
    """Windows-служба для агента аудита"""

    _svc_name_ = "DCAPAuditAgent"
    _svc_display_name_ = "DCAP Audit Agent"
    _svc_description_ = "Сбор событий файловой системы для DCAP (PII/credentials/code)"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.config_path = Path(__file__).parent / "config.json"
        self.config = _load_config(self.config_path)
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
            config = self.config
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
            self.agent.log = self.logger     # основной логгер агента

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
                    self.agent.log = self.logger
                else:
                    break

def main():
    """Точка входа для установки/запуска службы"""
    if not WIN32_AVAILABLE:
        print("pywin32 не установлен. Установите: pip install pywin32")
        sys.exit(1)

    if len(sys.argv) == 1:
        # Запуск агента в консольном режиме (для отладки)
        from main import run as agent_run
        from main import REQUIRED_CONFIG_KEYS
        agent_run(Path(__file__).parent / "config.json")
    else:
        win32serviceutil.HandleCommandLine(AuditAgentService)

if __name__ == '__main__':
    main()
