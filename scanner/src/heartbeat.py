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
    """Выделенный поток heartbeat. Fail-open, daemon.

    BUG-080 (TASK-051, v3.13.20): при недоступном Manager — exponential backoff
    5→10→30→60→120 с и без спама в лог: WARNING только на 1-м фейле и далее
    каждые 5 попыток; DEBUG на каждый фейл; при восстановлении — INFO.
    Засыпание через self._stop.wait() — Ctrl+C / stop() прерывает мгновенно.
    """

    BACKOFF_STEPS = [5, 10, 30, 60, 120]

    def __init__(self, manager_url: str, scanner_id: int, interval: int = 30):
        super().__init__(daemon=True, name="HeartbeatThread")
        self.manager_url = manager_url.rstrip("/")
        self.scanner_id = scanner_id
        self.interval = interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._fail_count = 0
        self._current_task_id: Optional[int] = None
        self._current_progress: Optional[Dict[str, Any]] = None
        # {"files_scanned": int, "total": int|None, "speed_files_per_sec": float|None, "eta_seconds": int|None}

    def set_task(self, task_id: Optional[int]):
        with self._lock:
            self._current_task_id = task_id

    def set_progress(
        self,
        files_scanned: int,
        total: Optional[int] = None,
        speed_files_per_sec: Optional[float] = None,
        eta_seconds: Optional[int] = None,
    ):
        with self._lock:
            self._current_progress = {
                "files_scanned": int(files_scanned),
                "total": int(total) if total is not None else None,
            }
            if speed_files_per_sec is not None:
                self._current_progress["speed_files_per_sec"] = round(float(speed_files_per_sec), 3)
            else:
                self._current_progress.pop("speed_files_per_sec", None)
            if eta_seconds is not None:
                self._current_progress["eta_seconds"] = int(eta_seconds)
            else:
                self._current_progress.pop("eta_seconds", None)

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

    def _send_heartbeat(self) -> bool:
        """Отправить heartbeat. True при успехе, False при любой ошибке.

        BUG-080 (TASK-051): фейлы логируются на DEBUG (не спам WARNING).
        """
        try:
            resp = requests.post(
                f"{self.manager_url}/api/scanner/heartbeat",
                json=self._build_payload(),
                timeout=5,
            )
            if resp.status_code != 200:
                logger.debug("Heartbeat failed: HTTP %s", resp.status_code)
                return False
            return True
        except Exception as e:
            logger.debug("Heartbeat failed: %s", e)  # fail-open
            return False

    def _next_sleep(self, ok: bool) -> float:
        """Рассчитать следующую паузу и обновить счётчик фейлов.

        BUG-080 (TASK-051): успех → сброс backoff и интервал; фейл →
        exponential backoff по BACKOFF_STEPS (максимум 120 с). WARNING
        только на 1-м фейле и далее каждые 5 попыток.
        """
        if ok:
            if self._fail_count > 0:
                logger.info(
                    "Heartbeat restored after %d failure(s)",
                    self._fail_count,
                )
            self._fail_count = 0
            return float(self.interval)
        self._fail_count += 1
        idx = min(self._fail_count - 1, len(self.BACKOFF_STEPS) - 1)
        sleep_time = float(self.BACKOFF_STEPS[idx])
        if self._fail_count == 1 or self._fail_count % 5 == 0:
            logger.warning(
                "Heartbeat failing (%d attempts), next retry in %ds",
                self._fail_count,
                sleep_time,
            )
        return sleep_time

    def run(self):
        logger.info("HeartbeatThread started (interval=%ss)", self.interval)
        while not self._stop.wait(self.interval):
            ok = self._send_heartbeat()
            sleep_time = self._next_sleep(ok)
            # BUG-080 (TASK-051): wait вместо time.sleep — мгновенный выход
            # по stop()/SIGINT, не ждём окончания backoff.
            self._stop.wait(sleep_time)
        logger.info("HeartbeatThread stopped")

    def stop(self):
        self._stop.set()