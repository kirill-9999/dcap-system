# audit-agent-s3/src/heartbeat.py
import threading
import time
import logging

from .sender import Sender

logger = logging.getLogger(__name__)


class HeartbeatThread(threading.Thread):
    """Heartbeat в отдельном потоке."""

    def __init__(self, sender: Sender, interval: int = 30):
        super().__init__()
        self.sender = sender
        self.interval = interval
        self.running = False
        self.daemon = True
        self.name = "HeartbeatThread"

    def start(self):
        self.running = True
        super().start()
        logger.info("Heartbeat thread started")

    def stop(self):
        self.running = False
        logger.info("Heartbeat thread stopped")

    def run(self):
        while self.running:
            try:
                if not self.sender.send_heartbeat():
                    logger.warning("Heartbeat failed")
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                time.sleep(5)
