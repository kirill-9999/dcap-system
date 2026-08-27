#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from typing import List, Dict


class Sender:
    def __init__(self, manager_url: str, agent_id: int, timeout: int = 30):
        self.manager_url = manager_url.rstrip('/')
        self.agent_id = agent_id
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def send_events(self, events: List[Dict]) -> bool:
        if not events:
            return True

        payload = {"agent_id": self.agent_id, "events": events}

        try:
            resp = self.session.post(
                f"{self.manager_url}/api/audit/events",
                json=payload,
                timeout=self.timeout
            )
            return resp.status_code == 200 and resp.json().get("saved", 0) == len(events)
        except Exception:
            return False

    def send_heartbeat(self, status: str = "online", stats: Dict = None) -> bool:
        payload = {"agent_id": self.agent_id, "status": status, "stats": stats or {}}
        try:
            resp = self.session.post(
                f"{self.manager_url}/api/audit/agents/heartbeat",
                json=payload,
                timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False
