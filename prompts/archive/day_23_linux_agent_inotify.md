📋 ТЗ: LINUX-АГЕНТ АУДИТА С INOTIFY (ДЕНЬ 23)
Файл: prompts/tz/day_23_linux_agent_inotify.md

🎯 ЦЕЛЬ
Реализовать ядро легкого агента аудита для Linux с использованием inotify (вместо auditd). Агент должен:

Отслеживать файловые события в реальном времени через pyinotify

Буферизировать события локально (SQLite) при потере связи с Manager

Отправлять события в Manager по HTTP (с подтверждением)

Работать как фоновый процесс (без systemd, через nohup или screen)

Важно: Агент должен быть максимально легким — только Python + requests + pyinotify.

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ
Создать в audit-agent-linux/ (в корне проекта):
text
audit-agent-linux/
├── main.py                 # Основной цикл, инициализация
├── collector.py            # InotifyCollector (pyinotify)
├── buffer.py               # BufferManager (SQLite)
├── sender.py               # Отправка в Manager
├── heartbeat.py            # Heartbeat
├── config.json             # Конфигурация
├── requirements.txt        # Зависимости
├── start.sh                # Скрипт запуска (nohup)
├── stop.sh                 # Скрипт остановки
└── README.md               # Инструкция
📋 ДЕТАЛЬНОЕ ТЗ
1. Структура audit-agent-linux/
text
audit-agent-linux/
├── main.py                 # Точка входа
├── collector.py            # InotifyCollector (pyinotify)
├── buffer.py               # BufferManager (SQLite)
├── sender.py               # Sender (HTTP → Manager)
├── heartbeat.py            # HeartbeatSender
├── config.json             # Конфигурация агента
├── requirements.txt        # requests, pyinotify
├── start.sh                # Запуск в фоне (nohup)
├── stop.sh                 # Остановка по PID
├── logs/                   # Логи (создается при запуске)
└── buffer/                 # Буфер SQLite (создается при запуске)
2. Конфигурация (config.json)
json
{
    "manager_url": "http://localhost:8000",
    "agent_name": "linux-agent-01",
    "hostname": "linux-server",
    "watch_paths": ["/home/kirill/test_audit"],
    "read_interval": 5,
    "batch_size": 50,
    "buffer_size": 10000,
    "heartbeat_interval": 30,
    "log_level": "INFO",
    "log_file": "logs/audit_agent.log"
}
3. Модуль collector.py (inotify)
python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable

try:
    import pyinotify
except ImportError:
    print("[Collector] pyinotify не установлен. Установите: pip install pyinotify")
    raise


class InotifyCollector:
    """Сбор файловых событий через inotify (без systemd)"""

    def __init__(self, watch_paths: List[str], callback: Optional[Callable] = None):
        self.watch_paths = [str(Path(p).resolve()) for p in watch_paths]
        self.callback = callback
        self.running = False
        self.wm = None
        self.notifier = None

        self.event_map = {
            pyinotify.IN_OPEN: 'read',
            pyinotify.IN_MODIFY: 'write',
            pyinotify.IN_CLOSE_WRITE: 'write',
            pyinotify.IN_DELETE: 'delete',
            pyinotify.IN_DELETE_SELF: 'delete',
            pyinotify.IN_MOVED_FROM: 'move',
            pyinotify.IN_MOVED_TO: 'move',
            pyinotify.IN_CREATE: 'write',
        }

    def start(self):
        if not self.watch_paths:
            print("[Collector] Нет путей для мониторинга")
            return

        for path in self.watch_paths:
            if not os.path.exists(path):
                print(f"[Collector] ❌ Путь не существует: {path}")
                return

        print(f"[Collector] Запуск мониторинга: {self.watch_paths}")

        self.wm = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(self.wm, self._event_handler, timeout=10)

        mask = (
            pyinotify.IN_OPEN |
            pyinotify.IN_MODIFY |
            pyinotify.IN_CLOSE_WRITE |
            pyinotify.IN_DELETE |
            pyinotify.IN_DELETE_SELF |
            pyinotify.IN_MOVED_FROM |
            pyinotify.IN_MOVED_TO |
            pyinotify.IN_CREATE
        )

        for path in self.watch_paths:
            self.wm.add_watch(path, mask, rec=True, auto_add=True)
            print(f"[Collector]   Мониторинг: {path}")

        self.running = True
        try:
            while self.running:
                self.notifier.process_events()
                if self.notifier.check_events():
                    self.notifier.read_events()
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"[Collector] Ошибка: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self.notifier:
            self.notifier.stop()
        print("[Collector] Остановлен")

    def _event_handler(self, event: pyinotify.Event):
        if any(x in event.pathname for x in ['.git', '__pycache__', '.swp', '~']):
            return

        event_type = self._get_event_type(event)
        if not event_type:
            return

        user = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))

        audit_event = {
            'event_type': event_type,
            'user': user,
            'file_path': event.pathname,
            'old_path': None,
            'metadata': {
                'event_mask': event.maskname,
                'pid': event.pid
            },
            'created_at': datetime.utcnow().isoformat()
        }

        if event.mask & pyinotify.IN_MOVED_FROM:
            self._pending_move = {'pathname': event.pathname, 'cookie': event.cookie}
            return

        if event.mask & pyinotify.IN_MOVED_TO:
            if hasattr(self, '_pending_move') and self._pending_move.get('cookie') == event.cookie:
                audit_event['old_path'] = self._pending_move['pathname']
                del self._pending_move

        if self.callback:
            self.callback(audit_event)

    def _get_event_type(self, event: pyinotify.Event) -> Optional[str]:
        for mask, etype in self.event_map.items():
            if event.mask & mask:
                return etype
        return None
4. Модуль buffer.py
python
import sqlite3
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime

class BufferManager:
    def __init__(self, buffer_dir: Path, max_size: int = 10000):
        self.buffer_dir = Path(buffer_dir)
        self.buffer_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.buffer_dir / "buffer.db"
        self.max_size = max_size
        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(str(self.db_path))
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
        event_json = json.dumps(event, ensure_ascii=False)
        created_at = datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT INTO events (event_json, created_at) VALUES (?, ?)",
            (event_json, created_at)
        )
        self.conn.commit()

        count = self.conn.execute("SELECT COUNT(*) FROM events WHERE sent=0").fetchone()[0]
        if count > self.max_size:
            self._trim_buffer()

    def get_unsent(self, limit: int = 100) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT id, event_json FROM events WHERE sent=0 ORDER BY id LIMIT ?",
            (limit,)
        )
        return [{"id": row[0], "event": json.loads(row[1])} for row in cursor.fetchall()]

    def mark_sent(self, ids: List[int]):
        if not ids:
            return
        placeholders = ','.join('?' * len(ids))
        self.conn.execute(
            f"UPDATE events SET sent=1 WHERE id IN ({placeholders})",
            ids
        )
        self.conn.commit()

    def clear_sent(self):
        self.conn.execute("DELETE FROM events WHERE sent=1")
        self.conn.commit()

    def count_unsent(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM events WHERE sent=0")
        return cursor.fetchone()[0]

    def _trim_buffer(self):
        to_delete = self.max_size // 10
        self.conn.execute(
            "DELETE FROM events WHERE id IN (SELECT id FROM events WHERE sent=0 ORDER BY id LIMIT ?)",
            (to_delete,)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
5. Модуль sender.py
python
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
        except:
            return False

    def send_heartbeat(self, stats: Dict) -> bool:
        payload = {"agent_id": self.agent_id, "status": "online", "stats": stats}
        try:
            resp = self.session.post(
                f"{self.manager_url}/api/audit/agents/heartbeat",
                json=payload,
                timeout=10
            )
            return resp.status_code == 200
        except:
            return False
6. Модуль main.py
python
#!/usr/bin/env python3
import json
import time
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

from collector import InotifyCollector
from buffer import BufferManager
from sender import Sender

class AuditAgent:
    def __init__(self, config_path: Path):
        with open(config_path) as f:
            self.config = json.load(f)

        self.buffer = BufferManager(
            buffer_dir=Path("buffer"),
            max_size=self.config.get("buffer_size", 10000)
        )
        self.sender = Sender(
            manager_url=self.config["manager_url"],
            agent_id=0
        )
        self.running = True
        self.log = self._setup_logging()
        self.agent_id = 0

    def _setup_logging(self):
        log_level = getattr(logging, self.config.get("log_level", "INFO"))
        log_file = self.config.get("log_file", "logs/audit_agent.log")
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
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

        # Запуск inotify
        def on_event(event):
            self.buffer.add(event)
            self.log.debug(f"Событие: {event['event_type']} {event['file_path']}")

        collector = InotifyCollector(
            watch_paths=self.config.get("watch_paths", []),
            callback=on_event
        )

        import threading
        collector_thread = threading.Thread(target=collector.start, daemon=True)
        collector_thread.start()

        self.log.info(f"Мониторинг: {self.config.get('watch_paths', [])}")

        # Основной цикл
        last_heartbeat = datetime.utcnow() - timedelta(seconds=60)
        heartbeat_interval = self.config.get("heartbeat_interval", 30)

        while self.running:
            try:
                now = datetime.utcnow()
                if (now - last_heartbeat).seconds >= heartbeat_interval:
                    self.sender.send_heartbeat({"events_sent": 0})
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
    config_path = Path("config.json")
    if not config_path.exists():
        print("config.json не найден")
        sys.exit(1)

    agent = AuditAgent(config_path)
    agent.run()
7. Скрипты запуска
start.sh
bash
#!/bin/bash
cd "$(dirname "$0")"
nohup python3 main.py >> logs/agent.out 2>&1 &
echo $! > agent.pid
echo "Агент запущен, PID: $(cat agent.pid)"
stop.sh
bash
#!/bin/bash
if [ -f agent.pid ]; then
    kill $(cat agent.pid) 2>/dev/null && echo "Агент остановлен"
    rm -f agent.pid
else
    echo "PID-файл не найден"
fi
8. requirements.txt
txt
requests>=2.28.0
pyinotify>=0.9.6
✅ КРИТЕРИИ ПРИЕМКИ
□ Агент запускается и регистрируется в Manager
□ Агент отслеживает события в реальном времени через inotify
□ События сохраняются в SQLite-буфер
□ События отправляются в Manager батчами
□ При недоступности Manager события остаются в буфере
□ Heartbeat отправляется регулярно
□ Скрипты start.sh и stop.sh работают
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запустить Manager (Windows)
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI (Windows)
python run_webui.py

# 3. В WSL перейти в папку агента
cd ~/dcap-system/audit-agent-linux

# 4. Установить зависимости
pip install -r requirements.txt

# 5. Запустить агент
python main.py

# 6. Создать события
echo "test" > ~/test_audit/file1.txt
rm ~/test_audit/file1.txt

# 7. Проверить в WebUI
# http://localhost:8001 → Аудит
💾 КОМАНДА ДЛЯ КОММИТА
bash
git add audit-agent-linux/
git commit -m "feat: День 23 — Linux-агент аудита с inotify"
Разработчик (кодер), приступай! 🚀