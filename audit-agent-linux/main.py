#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import sys
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta

from collector import InotifyCollector
from buffer import BufferManager
from sender import Sender


class AuditAgent:
    def __init__(self, config_path: Path):
        with open(config_path) as f:
            self.config = json.load(f)

        base_dir = config_path.parent

        self.buffer = BufferManager(
            buffer_dir=base_dir / "buffer",
            max_size=self.config.get("buffer_size", 10000)
        )
        self.sender = Sender(
            manager_url=self.config["manager_url"],
            agent_id=0
        )
        self.running = True
        self.log = self._setup_logging(base_dir)
        self.agent_id = 0

    def _setup_logging(self, base_dir: Path):
        log_level = getattr(logging, self.config.get("log_level", "INFO"))
        log_file = self.config.get("log_file", "logs/audit_agent.log")
        log_path = base_dir / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(str(log_path), encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger("AuditAgent")

    def register(self) -> bool:
        payload = {
            "name": self.config["agent_name"],
            "hostname": self.config.get("hostname", "localhost"),
            "version": "1.0.0"
        }
        try:
            import requests
            resp = requests.post(
                f"{self.config['manager_url']}/api/audit/agents/register",
                json=payload,
                timeout=10
            )
            if resp.status_code == 200:
                self.agent_id = resp.json()["agent_id"]
                self.sender.agent_id = self.agent_id
                self.log.info(f"Зарегистрирован, ID: {self.agent_id}")
                return True
        except Exception as e:
            self.log.error(f"Ошибка регистрации: {e}")
        return False

    def run(self):
        self.log.info(f"Запуск: {self.config['agent_name']}")

        if not self.register():
            self.log.error("Регистрация не удалась. Выход.")
            sys.exit(1)

        def on_event(event):
            self.buffer.add(event)
            self.log.debug(f"Событие: {event['event_type']} {event['file_path']}")

        collector = InotifyCollector(
            watch_paths=self.config.get("watch_paths", []),
            callback=on_event
        )

        collector_thread = threading.Thread(target=collector.start, daemon=True)
        collector_thread.start()

        self.log.info(f"Мониторинг: {self.config.get('watch_paths', [])}")

        last_heartbeat = datetime.now() - timedelta(seconds=60)
        heartbeat_interval = self.config.get("heartbeat_interval", 30)

        while self.running:
            try:
                now = datetime.now()
                if (now - last_heartbeat).seconds >= heartbeat_interval:
                    unsent_count = self.buffer.count_unsent()
                    self.sender.send_heartbeat({"events_pending": unsent_count})
                    last_heartbeat = now

                unsent = self.buffer.get_unsent(limit=self.config.get("batch_size", 50))
                if unsent:
                    events = [e["event"] for e in unsent]
                    if self.sender.send_events(events):
                        self.buffer.mark_sent([e["id"] for e in unsent])
                        self.log.info(f"Отправлено {len(unsent)} событий")
                    else:
                        self.log.warning("Не удалось отправить события")

                self.buffer.clear_sent()
                time.sleep(self.config.get("read_interval", 5))

            except KeyboardInterrupt:
                self.log.info("Остановка...")
                self.running = False
                collector.stop()
            except Exception as e:
                self.log.error(f"Ошибка: {e}")
                time.sleep(5)

        self.buffer.close()
        self.log.info("Завершен")


if __name__ == "__main__":
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("config.json не найден")
        sys.exit(1)

    agent = AuditAgent(config_path)
    agent.run()
