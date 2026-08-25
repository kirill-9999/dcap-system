#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Агент аудита: сбор Security Log, буферизация, отправка в Manager."""

import json
import time
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

from collector import WindowsAuditCollector
from buffer import BufferManager
from sender import Sender
from heartbeat import HeartbeatSender


class AuditAgent:
    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self.base_dir = config_path.parent
        self.state = self._load_state()

        self.collector = WindowsAuditCollector()
        self.buffer = BufferManager(
            buffer_dir=self.base_dir / self.config.get("buffer_dir", "buffer"),
            max_size=self.config.get("buffer_size", 10000)
        )
        self.sender = Sender(
            manager_url=self.config["manager_url"],
            agent_id=self.state.get("agent_id", 0)
        )
        self.heartbeat = HeartbeatSender(
            manager_url=self.config["manager_url"],
            agent_id=self.state.get("agent_id", 0)
        )

        self.running = True
        self.last_read = self._parse_timestamp(self.state.get("last_read"))
        self.last_heartbeat = None
        self._events_sent_total = 0
        self._events_failed_total = 0

        logging.basicConfig(
            level=getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO),
            format="[%(asctime)s] %(levelname)s %(message)s",
            datefmt="%H:%M:%S"
        )
        self.log = logging.getLogger("audit-agent")
        self.logger = self.log  # алиас для совместимости со службой (service.py)

    def _load_config(self, path: Path) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_state(self) -> Dict:
        state_path = self.base_dir / "state.json" if hasattr(self, 'base_dir') else Path("state.json")
        if state_path.exists():
            with open(state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"agent_id": 0, "last_read": None}

    def _save_state(self):
        state_path = self.base_dir / "state.json"
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _parse_timestamp(self, ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except:
            return None

    def register(self) -> bool:
        """Зарегистрировать агент в Manager"""
        payload = {
            "name": self.config["agent_name"],
            "hostname": self.config.get("hostname", "unknown"),
            "version": "1.0.0"
        }
        try:
            import requests
            response = requests.post(
                f"{self.config['manager_url']}/api/audit/agents/register",
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.state["agent_id"] = data["agent_id"]
                self.sender.agent_id = data["agent_id"]
                self.heartbeat.agent_id = data["agent_id"]
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
        event_ids = self.config.get("event_filters", [4656, 4663, 4660, 5140, 5145])

        events = self.collector.collect_events(since, event_ids)

        if events:
            # 2. Добавить в буфер
            for event in events:
                self.buffer.add(event)

            # 3. Обновить last_read
            self.last_read = datetime.utcnow()
            self.state["last_read"] = self.last_read.isoformat()
            self._save_state()

        # 4. Отправить из буфера
        unsent = self.buffer.get_unsent(limit=self.config.get("batch_size", 100))
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

        heartbeat_interval = self.config.get("heartbeat_interval", 30)

        # Основной цикл
        while self.running:
            try:
                # Heartbeat (по интервалу)
                now = datetime.utcnow()
                if (
                    self.last_heartbeat is None
                    or (now - self.last_heartbeat).total_seconds() >= heartbeat_interval
                ):
                    stats = {
                        "events_sent": self._events_sent_total,
                        "events_failed": self._events_failed_total,
                        "last_event_at": now.isoformat()
                    }
                    if self.heartbeat.send(stats):
                        self.last_heartbeat = now
                    else:
                        self.log.warning("Heartbeat не отправлен (Manager недоступен?)")

                # Сбор и отправка
                self.collect_and_send()

                # Пауза
                time.sleep(self.config.get("read_interval", 60))

            except KeyboardInterrupt:
                self.log.info("Остановка...")
                self.running = False
            except Exception as e:
                self.log.error("Ошибка: %s", e)
                time.sleep(5)

        # Завершение
        self.buffer.close()
        self.log.info("Завершен")


def main():
    """Точка входа агента аудита"""
    config_path = Path("config.json")
    if not config_path.exists():
        print("config.json не найден")
        sys.exit(1)

    agent = AuditAgent(config_path)
    agent.run()


if __name__ == "__main__":
    main()
