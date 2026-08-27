"""Отправка событий в Manager."""

import requests
import time
from typing import List, Dict
from datetime import datetime


class Sender:
    def __init__(self, manager_url: str, agent_id: int, timeout: int = 30):
        self.manager_url = manager_url.rstrip('/')
        self.agent_id = agent_id
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def send_events(self, events: List[Dict]) -> bool:
        """Отправить события в Manager (одним батчем)"""
        if not events:
            return True

        payload = {
            "agent_id": self.agent_id,
            "events": events
        }

        try:
            response = self.session.post(
                f"{self.manager_url}/api/audit/events",
                json=payload,
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("saved", 0) == len(events)
            else:
                print(f"[Sender] Ошибка {response.status_code}: {response.text}")
                return False
        except requests.exceptions.Timeout:
            print("[Sender] Таймаут")
            return False
        except Exception as e:
            print(f"[Sender] Ошибка: {e}")
            return False

    def send_heartbeat(self, status: str = "online", stats: Dict = None) -> bool:
        """Отправить heartbeat"""
        payload = {
            "agent_id": self.agent_id,
            "status": status,
            "stats": stats or {}
        }
        try:
            response = self.session.post(
                f"{self.manager_url}/api/audit/agents/heartbeat",
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
