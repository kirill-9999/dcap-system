"""Отправка heartbeat в Manager."""

import requests
from typing import Dict


class HeartbeatSender:
    def __init__(self, manager_url: str, agent_id: int, timeout: int = 10):
        self.manager_url = manager_url.rstrip('/')
        self.agent_id = agent_id
        self.timeout = timeout
        self.session = requests.Session()

    def send(self, stats: Dict) -> bool:
        """Отправить heartbeat"""
        payload = {
            "agent_id": self.agent_id,
            "status": "online",
            "stats": stats
        }
        try:
            response = self.session.post(
                f"{self.manager_url}/api/audit/agents/heartbeat",
                json=payload,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception:
            return False
