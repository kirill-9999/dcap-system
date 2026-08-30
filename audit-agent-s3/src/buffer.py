# audit-agent-s3/src/buffer.py
import sqlite3
from pathlib import Path
from typing import List, Tuple
import logging

from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)


class BufferManager:
    """SQLite буфер для хранения событий (с отложенной отправкой)."""

    def __init__(self, config: dict):
        self.config = config
        self.db_path = Path(config.get("path", "data/buffer/buffer.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_events = int(config.get("max_events", 10000))
        self.cleanup_days = int(config.get("cleanup_days", 7))

        self._init_db()

    def _init_db(self):
        """Инициализация таблицы."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0,
                retries INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sent ON events(sent)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON events(created_at)")
        self.conn.commit()

        logger.info(f"Buffer initialized: {self.db_path}")

    def _serialize(self, event: UnifiedEvent) -> str:
        return event.model_dump_json()

    def _deserialize(self, json_str: str) -> UnifiedEvent:
        return UnifiedEvent.model_validate_json(json_str)

    def store_event(self, event: UnifiedEvent):
        """Сохранение события."""
        try:
            cursor = self.conn.execute("SELECT COUNT(*) FROM events WHERE sent=0")
            pending = cursor.fetchone()[0]

            if pending >= self.max_events:
                logger.warning(f"Buffer full ({pending}/{self.max_events}), dropping oldest")
                self._drop_oldest()

            self.conn.execute(
                "INSERT INTO events (event_json) VALUES (?)",
                (self._serialize(event),),
            )
            self.conn.commit()
            logger.debug(f"Event stored: {event.event_type} {event.file_path}")
        except Exception as e:
            logger.error(f"Error storing event: {e}")

    def _drop_oldest(self):
        """Удаление самых старых неотправленных событий."""
        self.conn.execute(
            "DELETE FROM events WHERE id IN (SELECT id FROM events WHERE sent=0 ORDER BY id LIMIT 100)"
        )
        self.conn.commit()

    def get_unsent(self, limit: int = 100) -> List[Tuple[int, UnifiedEvent]]:
        """Получение неотправленных событий."""
        try:
            cursor = self.conn.execute(
                "SELECT id, event_json FROM events WHERE sent=0 ORDER BY id LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()

            result = []
            for row_id, json_str in rows:
                try:
                    event = self._deserialize(json_str)
                    result.append((row_id, event))
                except Exception as e:
                    logger.error(f"Error parsing event {row_id}: {e}")
                    self.conn.execute(
                        "UPDATE events SET retries = retries + 1 WHERE id = ?",
                        (row_id,),
                    )
                    self.conn.commit()

            return result
        except Exception as e:
            logger.error(f"Error getting unsent events: {e}")
            return []

    def mark_sent(self, event_ids: List[int]):
        """Пометить события как отправленные."""
        if not event_ids:
            return
        try:
            self.conn.executemany(
                "UPDATE events SET sent=1 WHERE id=?",
                [(id_,) for id_ in event_ids],
            )
            self.conn.commit()
            logger.debug(f"Marked {len(event_ids)} events as sent")
        except Exception as e:
            logger.error(f"Error marking events as sent: {e}")

    def get_stats(self) -> dict:
        """Статистика буфера."""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN sent=0 THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN sent=1 THEN 1 ELSE 0 END) as sent,
                SUM(retries) as total_retries
            FROM events
        """)
        row = cursor.fetchone()
        return {
            "total": row[0] or 0,
            "pending": row[1] or 0,
            "sent": row[2] or 0,
            "retries": row[3] or 0,
        }

    def cleanup_old_events(self):
        """Очистка старых отправленных событий."""
        self.conn.execute(
            "DELETE FROM events WHERE sent=1 AND created_at < datetime('now', ?)",
            (f"-{self.cleanup_days} days",),
        )
        self.conn.commit()
        logger.info(f"Cleaned up events older than {self.cleanup_days} days")

    def close(self):
        """Закрытие соединения."""
        if hasattr(self, "conn"):
            self.conn.close()
            logger.info("Buffer closed")
