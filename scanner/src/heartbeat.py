#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Выделенный daemon-поток heartbeat для сканера (День 39).

Во время длительного задания (например, 22 500 файлов ~1.5 часа) обычный
heartbeat в основном цикле не успевает отправляться — Manager помечает сканер
inactive, хотя он работает. HeartbeatThread шлёт POST /api/scanner/heartbeat
независимо от основного цикла сканирования, с опциональным прогрессом задания.
Fail-open: при ошибке сети/Manager поток просто логирует предупреждение.
"""

import threading
import time
import logging
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)


class HeartbeatThread(threading.Thread):
    """Выделенный поток heartbeat. Fail-open, daemon."""

    def __init__(self, manager_url: str, scanner_id: int, interval: int = 30):
        super().__init__(daemon=True, name="HeartbeatThread")
        self.manager_url = manager_url.rstrip("/")
        self.scanner_id = scanner_id
        self.interval = interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._current_task_id: Optional[int] = None
        self._current_progress: Optional[Dict[str, Any]] = None
        # {"files_scanned": int, "total": int|None}

    def set_task(self, task_id: Optional[int]):
        with self._lock:
            self._current_task_id = task_id

    def set_progress(self, files_scanned: int, total: Optional[int] = None):
        with self._lock:
            self._current_progress = {
                "files_scanned": int(files_scanned),
                "total": int(total) if total is not None else None,
            }

    def _build_payload(self) -> Dict[str, Any]:
        with self._lock:
            payload: Dict[str, Any] = {
                "scanner_id": self.scanner_id,
                "status": "busy" if self._current_task_id is not None else "idle",
                "current_task_id": self._current_task_id,
            }
            if self._current_progress:
                payload["progress"] = dict(self._current_progress)
            return payload

    def run(self):
        logger.info("HeartbeatThread started (interval=%ss)", self.interval)
        while not self._stop.wait(self.interval):
            try:
                resp = requests.post(
                    f"{self.manager_url}/api/scanner/heartbeat",
                    json=self._build_payload(),
                    timeout=5,
                )
                if resp.status_code != 200:
                    logger.warning("Heartbeat failed: HTTP %s", resp.status_code)
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)  # fail-open
        logger.info("HeartbeatThread stopped")

    def stop(self):
        self._stop.set()