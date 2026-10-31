#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Агент аудита: сбор Security Log, буферизация, отправка в Manager.

Запуск:
    python main.py <config.json>

Конфиг обязателен. Без конфига агент не запускается. Все обязательные
параметры конфига должны присутствовать, иначе агент завершается с ошибкой.
"""

import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

from collector import WindowsAuditCollector
from buffer import BufferManager
from sender import Sender


# Обязательные параметры конфига (без значений по умолчанию)
REQUIRED_CONFIG_KEYS = [
    "manager_url",
    "agent_name",
    "hostname",
    "read_interval",
    "batch_size",
    "buffer_size",
    "heartbeat_interval",
    "event_filters",
    "log_level",
]


def _load_config(config_path: Path) -> Dict:
    """Строгая загрузка конфига.

    Конфиг обязателен и должен содержать все обязательные параметры.
    Значений по умолчанию нет — отсутствующий параметр вызывает ошибку.
    """
    if not config_path.exists():
        print(f"Ошибка: конфиг не найден: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка: невалидный JSON в конфиге {config_path}: {e}")
        sys.exit(1)

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        print(
            f"Ошибка: в конфиге {config_path} отсутствуют обязательные "
            f"параметры: {', '.join(missing)}"
        )
        sys.exit(1)

    return config


class AuditAgent:
    def __init__(self, config_path: Path):
        self.config = _load_config(config_path)
        self.base_dir = config_path.parent
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

        self.collector = WindowsAuditCollector()
        self.buffer = BufferManager(
            buffer_dir=self.data_dir / "buffer", max_size=self.config["buffer_size"]
        )
        self.sender = Sender(
            manager_url=self.config["manager_url"], agent_id=self.state.get("agent_id", 0),
            cert_path=self.config.get("cert_path"),
            key_path=self.config.get("key_path"),
            ca_path=self.config.get("ca_path"),
        )

        self.running = True
        self.last_read = self._parse_timestamp(self.state.get("last_read"))
        self.last_heartbeat = None
        self.last_permissions_collect = None
        self._events_sent_total = 0
        self._events_failed_total = 0

        # Сбор прав (День 33) — необязательные параметры
        self.permission_paths = (
            self.config.get("permission_paths") or self.config.get("paths") or []
        )
        self.permissions_interval = self.config.get("permissions_interval", 3600)

        logging.basicConfig(
            level=getattr(logging, self.config["log_level"].upper(), logging.INFO),
            format="[%(asctime)s] %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
        self.log = logging.getLogger("audit-agent")
        self.logger = self.log  # алиас для совместимости со службой (service.py)

    def _load_state(self) -> Dict:
        state_path = self.data_dir / "state.json"
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        return {"agent_id": 0, "last_read": None}

    def _save_state(self):
        state_path = self.data_dir / "state.json"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _parse_timestamp(self, ts) -> "datetime | None":
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    def register(self) -> bool:
        """Зарегистрировать агент в Manager"""
        payload = {
            "name": self.config["agent_name"],
            "hostname": self.config["hostname"],
            "version": "3.0.0",
        }
        try:
            import requests

            response = requests.post(
                f"{self.config['manager_url']}/api/audit/agents/register", json=payload, timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.state["agent_id"] = data["agent_id"]
                self.sender.agent_id = data["agent_id"]
                self._save_state()
                self.log.info("Зарегистрирован, ID: %s", data["agent_id"])
                return True
            else:
                self.log.error("Регистрация: HTTP %s %s", response.status_code, response.text)
        except Exception as e:
            self.log.error("Ошибка регистрации: %s", e)
        return False

    def collect_and_send(self):
        """Собрать события и отправить в Manager"""
        # 1. Чтение Security Log
        since = self.last_read or (datetime.utcnow() - timedelta(hours=1))
        events = self.collector.collect_events(since, self.config["event_filters"])

        if events:
            # 2. Добавить в буфер
            for event in events:
                self.buffer.add(event)

            # 3. Обновить last_read
            self.last_read = datetime.utcnow()
            self.state["last_read"] = self.last_read.isoformat()
            self._save_state()

        # 4. Отправить из буфера
        unsent = self.buffer.get_unsent(limit=self.config["batch_size"])
        if unsent:
            event_list = [e["event"] for e in unsent]
            if self.sender.send_events(event_list):
                self.buffer.mark_sent([e["id"] for e in unsent])
                self._events_sent_total += len(unsent)
                self.log.info("Отправлено %s событий", len(unsent))
            else:
                self._events_failed_total += len(unsent)

        # 5. Очистить отправленные
        self.buffer.clear_sent()

    def _send_heartbeat(self, status: str = "online") -> bool:
        """Отправка heartbeat (через sender, без отдельного heartbeat.py)"""
        stats = {
            "events_sent": self._events_sent_total,
            "events_failed": self._events_failed_total,
            "last_event_at": datetime.utcnow().isoformat(),
        }
        return self.sender.send_heartbeat(status, stats)

    def collect_and_send_permissions(self):
        """Сбор NTFS прав по настроенным путям и отправка в Manager (День 33)."""
        if not self.permission_paths:
            self.log.debug("Нет путей для сбора прав (permission_paths/paths) — пропуск")
            return

        all_entries = []
        for path in self.permission_paths:
            try:
                entries = self.collector.collect_permissions(path)
                all_entries.extend(entries)
                self.log.info("Собрано прав для %s: %s", path, len(entries))
            except Exception as e:
                self.log.error("Ошибка сбора прав для %s: %s", path, e)

        if all_entries and self.sender.send_permissions(all_entries, agent_type="windows_agent"):
            self.log.info("Отправлено прав: %s", len(all_entries))
            self.last_permissions_collect = datetime.utcnow()
        else:
            self.log.warning("Права не отправлены (Manager недоступен?)")

    def run(self):
        """Основной цикл"""
        self.log.info("Запуск: %s", self.config["agent_name"])
        if not self.collector._available:
            self.log.warning("wevtutil недоступен — события собираться не будут")

        # Регистрация
        if self.state["agent_id"] == 0:
            if not self.register():
                self.log.error("Регистрация не удалась. Выход.")
                sys.exit(1)

        heartbeat_interval = self.config["heartbeat_interval"]

        # Основной цикл
        while self.running:
            try:
                # Heartbeat (по интервалу)
                now = datetime.utcnow()
                if (
                    self.last_heartbeat is None
                    or (now - self.last_heartbeat).total_seconds() >= heartbeat_interval
                ):
                    if self._send_heartbeat():
                        self.last_heartbeat = now
                    else:
                        self.log.warning("Heartbeat не отправлен (Manager недоступен?)")

                # Сбор и отправка
                self.collect_and_send()

                # Сбор прав (периодически)
                now = datetime.utcnow()
                if self.permission_paths and (
                    self.last_permissions_collect is None
                    or (now - self.last_permissions_collect).total_seconds()
                    >= self.permissions_interval
                ):
                    self.collect_and_send_permissions()

                # Пауза
                time.sleep(self.config["read_interval"])

            except KeyboardInterrupt:
                self.log.info("Остановка...")
                self.running = False
            except Exception as e:
                self.log.error("Ошибка: %s", e)
                time.sleep(5)

        # Завершение
        self._send_heartbeat(status="offline")
        self.buffer.close()
        self.log.info("Завершен")


def run(config_path: Path):
    """Запуск агента по переданному пути к конфигу."""
    agent = AuditAgent(config_path)
    agent.run()


def main():
    """Точка входа агента аудита"""
    if len(sys.argv) < 2:
        print("Ошибка: не указан путь к конфигу")
        print("Использование: python main.py <config.json>")
        sys.exit(1)

    run(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
