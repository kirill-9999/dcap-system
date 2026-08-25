"""Локальное хранение событий аудита (SQLite)."""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class BufferManager:
    def __init__(self, buffer_dir: Path, max_size: int = 10000):
        self.buffer_dir = Path(buffer_dir)
        self.buffer_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.buffer_dir / "buffer.db"
        self.max_size = max_size
        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sent INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sent ON events(sent)")
        self.conn.commit()

    def add(self, event: Dict):
        """Добавить событие в буфер"""
        event_json = json.dumps(event, ensure_ascii=False)
        created_at = datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT INTO events (event_json, created_at) VALUES (?, ?)",
            (event_json, created_at)
        )
        self.conn.commit()

        # Ограничить размер буфера
        count = self.conn.execute("SELECT COUNT(*) FROM events WHERE sent=0").fetchone()[0]
        if count > self.max_size:
            self._trim_buffer()

    def get_unsent(self, limit: int = 100) -> List[Dict]:
        """Получить неотправленные события (старые первыми)"""
        cursor = self.conn.execute(
            "SELECT id, event_json FROM events WHERE sent=0 ORDER BY id LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [{"id": row[0], "event": json.loads(row[1])} for row in rows]

    def mark_sent(self, ids: List[int]):
        """Отметить события как отправленные"""
        if not ids:
            return
        placeholders = ','.join('?' * len(ids))
        self.conn.execute(
            f"UPDATE events SET sent=1 WHERE id IN ({placeholders})",
            ids
        )
        self.conn.commit()

    def _trim_buffer(self):
        """Удалить старые события при переполнении"""
        to_delete = self.max_size // 10  # Удаляем 10% самых старых
        self.conn.execute(
            "DELETE FROM events WHERE id IN "
            "(SELECT id FROM events WHERE sent=0 ORDER BY id LIMIT ?)",
            (to_delete,)
        )
        self.conn.commit()

    def count_unsent(self) -> int:
        """Количество неотправленных событий"""
        cursor = self.conn.execute("SELECT COUNT(*) FROM events WHERE sent=0")
        return cursor.fetchone()[0]

    def clear_sent(self):
        """Очистить отправленные события (для экономии места)"""
        self.conn.execute("DELETE FROM events WHERE sent=1")
        self.conn.commit()

    def close(self):
        self.conn.close()
