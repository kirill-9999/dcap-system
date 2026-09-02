#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Linux-агент аудита: мониторинг файловой системы, буферизация, отправка в Manager.

Запуск:
    python main.py <config.json>

Конфиг обязателен. Без конфига агент не запускается. Все обязательные
параметры конфига должны присутствовать, иначе агент завершается с ошибкой.
"""

import json
import time
import sys
import signal
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

from collector import InotifyCollector
from buffer import BufferManager
from sender import Sender

# Обязательные параметры конфига (без значений по умолчанию)
REQUIRED_CONFIG_KEYS = [
    "manager_url",
    "agent_name",
    "hostname",
    "watch_paths",
    "read_interval",
    "batch_size",
    "buffer_size",
    "heartbeat_interval",
    "log_level",
    "log_file",
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

        self.buffer = BufferManager(
            buffer_dir=self.data_dir / "buffer", max_size=self.config["buffer_size"]
        )
        self.sender = Sender(
            manager_url=self.config["manager_url"], agent_id=self.state.get("agent_id", 0),
            cert_path=self.config.get("cert_path"),
            key_path=self.config.get("key_path"),
            ca_path=self.config.get("ca_path"),
        )
        self.agent_id = self.state.get("agent_id", 0)
        self.running = True
        self.log = self._setup_logging()
        # Сбор прав (День 33) — необязательные параметры
        self.permission_paths = (
            self.config.get("permission_paths") or self.config.get("watch_paths") or []
        )
        self.permissions_interval = self.config.get("permissions_interval", 3600)
        self.last_permissions_collect = None

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

    def _setup_logging(self):
        log_level = getattr(logging, self.config["log_level"].upper(), logging.INFO)
        log_path = self.base_dir / self.config["log_file"]
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(str(log_path), encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        return logging.getLogger("AuditAgent")

    def register(self) -> bool:
        payload = {
            "name": self.config["agent_name"],
            "hostname": self.config["hostname"],
            "version": "3.0.0",
        }
        try:
            import requests

            resp = requests.post(
                f"{self.config['manager_url']}/api/audit/agents/register", json=payload, timeout=10
            )
            if resp.status_code == 200:
                self.agent_id = resp.json()["agent_id"]
                self.sender.agent_id = self.agent_id
                self.state["agent_id"] = self.agent_id
                self._save_state()
                self.log.info(f"Зарегистрирован, ID: {self.agent_id}")
                return True
        except Exception as e:
            self.log.error(f"Ошибка регистрации: {e}")
        return False

    def _send_heartbeat(self, status: str = "online") -> bool:
        """Отправка heartbeat (через sender)"""
        unsent_count = self.buffer.count_unsent()
        return self.sender.send_heartbeat(status, {"events_pending": unsent_count})

    def collect_and_send_permissions(self):
        """Сбор POSIX-прав по путям и отправка в Manager (День 33)."""
        if not self.permission_paths:
            self.log.debug("Нет путей для сбора прав (permission_paths/watch_paths) — пропуск")
            return

        collector = InotifyCollector(watch_paths=self.permission_paths)
        all_entries = []
        for path in self.permission_paths:
            try:
                entries = collector.collect_permissions(path)
                all_entries.extend(entries)
                self.log.info("Собрано прав для %s: %s", path, len(entries))
            except Exception as e:
                self.log.error("Ошибка сбора прав для %s: %s", path, e)

        if all_entries and self.sender.send_permissions(all_entries, agent_type="linux_agent"):
            self.log.info("Отправлено прав: %s", len(all_entries))
            self.last_permissions_collect = datetime.now()
        else:
            self.log.warning("Права не отправлены (Manager недоступен?)")

    def run(self):
        self.log.info(f"Запуск: {self.config['agent_name']}")

        if self.agent_id == 0:
            if not self.register():
                self.log.error("Регистрация не удалась. Выход.")
                sys.exit(1)

        def on_event(event):
            self.buffer.add(event)
            self.log.debug(f"Событие: {event['event_type']} {event['file_path']}")

        collector = InotifyCollector(watch_paths=self.config["watch_paths"], callback=on_event)

        collector_thread = threading.Thread(target=collector.start, daemon=True)
        collector_thread.start()

        self.log.info(f"Мониторинг: {self.config['watch_paths']}")

        last_heartbeat = datetime.now() - timedelta(seconds=self.config["heartbeat_interval"])
        heartbeat_interval = self.config["heartbeat_interval"]

        while self.running:
            try:
                now = datetime.now()
                if (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                    self._send_heartbeat()
                    last_heartbeat = now

                unsent = self.buffer.get_unsent(limit=self.config["batch_size"])
                if unsent:
                    events = [e["event"] for e in unsent]
                    if self.sender.send_events(events):
                        self.buffer.mark_sent([e["id"] for e in unsent])
                        self.log.info(f"Отправлено {len(unsent)} событий")
                    else:
                        self.log.warning("Не удалось отправить события")

                self.buffer.clear_sent()

                # Сбор прав (периодически)
                now = datetime.now()
                if self.permission_paths and (
                    self.last_permissions_collect is None
                    or (now - self.last_permissions_collect).total_seconds()
                    >= self.permissions_interval
                ):
                    self.collect_and_send_permissions()

                time.sleep(self.config["read_interval"])

            except KeyboardInterrupt:
                self.log.info("Остановка...")
                self.running = False
                collector.stop()
            except Exception as e:
                self.log.error(f"Ошибка: {e}")
                time.sleep(5)

        self._send_heartbeat(status="offline")
        self.buffer.close()
        self.log.info("Завершен")


def run(config_path: Path):
    agent = AuditAgent(config_path)
    agent.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ошибка: не указан путь к конфигу")
        print("Использование: python main.py <config.json>")
        sys.exit(1)

    run(Path(sys.argv[1]))
