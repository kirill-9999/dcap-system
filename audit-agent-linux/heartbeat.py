#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Callable


class HeartbeatSender:
    """Периодическая отправка heartbeat в Manager"""

    def __init__(self, send_fn: Callable[[Dict], bool], interval: int = 30):
        self.send_fn = send_fn
        self.interval = interval
        self.last_send = datetime.utcnow() - timedelta(seconds=interval * 2)
        self.log = logging.getLogger("Heartbeat")

    def tick(self, stats: Dict) -> bool:
        now = datetime.utcnow()
        if (now - self.last_send).seconds >= self.interval:
            ok = self.send_fn(stats)
            self.last_send = now
            if ok:
                self.log.debug("Heartbeat отправлен")
            else:
                self.log.warning("Heartbeat не отправлен")
            return ok
        return True
