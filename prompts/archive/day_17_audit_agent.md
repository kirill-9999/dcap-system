📋 ТЗ: АГЕНТ АУДИТА — СБОР, БУФЕРИЗАЦИЯ И ОТПРАВКА (ДЕНЬ 17)
Файл: prompts/tz/day_17_audit_agent.md

🎯 ЦЕЛЬ
Реализовать ядро легкого агента аудита, который будет запускаться на файловых серверах (и на ноутбуке разработчика для отладки). Агент должен:

Читать Security Log через wevtutil (Windows)

Буферизировать события локально (при потере связи с Manager)

Отправлять события в Manager по протоколу HTTP (с подтверждением)

Работать как фоновый процесс (или служба Windows)

Важно: Агент должен быть максимально легким — без Tesseract, spaCy, Presidio и других тяжелых зависимостей. Только Python + requests + pywin32 (опционально) или ctypes.

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ
Создать:
text
audit-agent/
├── main.py                    # Точка входа (цикл, инициализация)
├── config.json                # Конфигурация агента (Manager URL, интервал, буфер)
├── collector.py               # Чтение Security Log (wevtutil)
├── buffer.py                  # Локальное хранение событий (SQLite или JSONL)
├── sender.py                  # Отправка событий в Manager
├── heartbeat.py               # Отправка heartbeat
├── state.json                 # Локальное состояние (последнее время чтения, буфер)
├── requirements.txt           # requests (и всё)
└── README.md                  # Инструкция по установке и настройке
📋 ДЕТАЛЬНОЕ ТЗ
1. Структура агента
text
audit-agent/
├── main.py                    # Основной цикл, инициализация
├── config.json                # Конфигурация
├── collector.py               # WindowsAuditCollector (читать Security Log)
├── buffer.py                  # BufferManager (сохранять/читать события)
├── sender.py                  # Sender (отправлять в Manager)
├── heartbeat.py               # HeartbeatSender (отправлять статус)
├── state.json                 # Локальное состояние
└── requirements.txt           # requests
2. Конфигурация (config.json)
json
{
    "manager_url": "http://localhost:8000",
    "agent_name": "audit-agent-01",
    "hostname": "SERVER01",
    "read_interval": 60,
    "batch_size": 100,
    "buffer_size": 10000,
    "heartbeat_interval": 30,
    "event_filters": [4656, 4660, 4663, 4670, 5140, 5145],
    "paths": ["D:\\test_audit"],
    "log_level": "INFO"
}
3. Модуль collector.py
Реализовать класс WindowsAuditCollector для чтения Security Log через wevtutil.

python
import subprocess
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class WindowsAuditCollector:
    def __init__(self):
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            subprocess.run(['wevtutil', '--help'], capture_output=True, timeout=5)
            return True
        except:
            return False

    def collect_events(self, since: datetime, event_ids: List[int], limit: int = 1000) -> List[Dict]:
        if not self._available:
            return []

        time_filter = since.strftime("%Y-%m-%dT%H:%M:%S")
        query = f"*[System[TimeCreated[@SystemTime>='{time_filter}']]]"

        try:
            result = subprocess.run(
                ['wevtutil', 'qe', 'Security',
                 '/q', query,
                 '/e', 'Events',
                 '/f', 'Text',
                 '/c', str(limit)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            return self._parse_events(result.stdout, event_ids)
        except Exception as e:
            print(f"[Collector] Ошибка: {e}")
            return []

    def _parse_events(self, output: str, event_ids: List[int]) -> List[Dict]:
        events = []
        current = {}
        in_event = False

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('Event['):
                if current and in_event:
                    events.append(self._normalize_event(current))
                    current = {}
                in_event = True
                continue

            if not in_event:
                continue

            if line.startswith('EventId:'):
                try:
                    eid = int(line.split(':', 1)[1].strip())
                    if eid not in event_ids:
                        in_event = False
                        current = {}
                        continue
                    current['event_id'] = eid
                except:
                    pass

            elif line.startswith('TimeCreated:'):
                current['timestamp'] = line.split(':', 1)[1].strip()

            elif 'SubjectUserName:' in line:
                current['user'] = line.split(':', 1)[1].strip()

            elif 'ObjectName:' in line:
                current['file_path'] = line.split(':', 1)[1].strip()

            elif 'OldPath:' in line:
                current['old_path'] = line.split(':', 1)[1].strip()

            elif 'NewPath:' in line:
                current['new_path'] = line.split(':', 1)[1].strip()

        if current and in_event:
            events.append(self._normalize_event(current))

        return events

    def _normalize_event(self, raw: Dict) -> Dict:
        event_id = raw.get('event_id')
        event_type_map = {
            4656: 'read',
            4660: 'delete',
            4663: 'write',
            4670: 'write',
            5140: 'read',
            5145: 'read',
        }
        return {
            'event_type': event_type_map.get(event_id, 'unknown'),
            'user': raw.get('user'),
            'file_path': raw.get('file_path', ''),
            'old_path': raw.get('old_path'),
            'metadata': {
                'event_id': event_id,
                'raw': raw
            },
            'created_at': raw.get('timestamp')
        }
4. Модуль buffer.py
Реализовать класс BufferManager для локального хранения событий (SQLite или JSONL).

python
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
            "DELETE FROM events WHERE sent=0 ORDER BY id LIMIT ?",
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
5. Модуль sender.py
Реализовать класс Sender для отправки событий в Manager.

python
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

    def send_heartbeat(self, stats: Dict) -> bool:
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
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
6. Модуль main.py
Реализовать основной цикл работы агента.

python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

from collector import WindowsAuditCollector
from buffer import BufferManager
from sender import Sender

class AuditAgent:
    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self.state = self._load_state()

        self.collector = WindowsAuditCollector()
        self.buffer = BufferManager(
            buffer_dir=Path(self.config.get("buffer_dir", "buffer")),
            max_size=self.config.get("buffer_size", 10000)
        )
        self.sender = Sender(
            manager_url=self.config["manager_url"],
            agent_id=self.state.get("agent_id", 0)
        )

        self.running = True
        self.last_read = self._parse_timestamp(self.state.get("last_read"))

    def _load_config(self, path: Path) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_state(self) -> Dict:
        state_path = Path("state.json")
        if state_path.exists():
            with open(state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"agent_id": 0, "last_read": None}

    def _save_state(self):
        state_path = Path("state.json")
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _parse_timestamp(self, ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except:
            return None

    def register(self) -> bool:
        """Зарегистрировать агент в Manager"""
        payload = {
            "name": self.config["agent_name"],
            "hostname": self.config.get("hostname", "unknown"),
            "version": "1.0.0"
        }
        try:
            import requests
            response = requests.post(
                f"{self.config['manager_url']}/api/audit/agents/register",
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.state["agent_id"] = data["agent_id"]
                self.sender.agent_id = data["agent_id"]
                self._save_state()
                print(f"[Agent] Зарегистрирован, ID: {data['agent_id']}")
                return True
        except Exception as e:
            print(f"[Agent] Ошибка регистрации: {e}")
        return False

    def collect_and_send(self):
        """Собрать события и отправить в Manager"""
        # 1. Чтение Security Log
        since = self.last_read or (datetime.utcnow() - timedelta(hours=1))
        event_ids = self.config.get("event_filters", [4656, 4663, 4660, 5140, 5145])

        events = self.collector.collect_events(since, event_ids)

        if events:
            # 2. Добавить в буфер
            for event in events:
                self.buffer.add(event)

            # 3. Обновить last_read
            if events:
                self.last_read = datetime.utcnow()
                self.state["last_read"] = self.last_read.isoformat()
                self._save_state()

        # 4. Отправить из буфера
        unsent = self.buffer.get_unsent(limit=self.config.get("batch_size", 100))
        if unsent:
            event_list = [e["event"] for e in unsent]
            if self.sender.send_events(event_list):
                self.buffer.mark_sent([e["id"] for e in unsent])
                print(f"[Agent] Отправлено {len(unsent)} событий")

        # 5. Очистить отправленные
        self.buffer.clear_sent()

    def run(self):
        """Основной цикл"""
        print(f"[Agent] Запуск: {self.config['agent_name']}")

        # Регистрация
        if self.state["agent_id"] == 0:
            if not self.register():
                print("[Agent] Регистрация не удалась. Выход.")
                sys.exit(1)

        # Основной цикл
        while self.running:
            try:
                # Heartbeat
                stats = {
                    "events_sent": 0,  # TODO: счетчики
                    "last_event_at": datetime.utcnow().isoformat()
                }
                self.sender.send_heartbeat(stats)

                # Сбор и отправка
                self.collect_and_send()

                # Пауза
                time.sleep(self.config.get("read_interval", 60))

            except KeyboardInterrupt:
                print("[Agent] Остановка...")
                self.running = False
            except Exception as e:
                print(f"[Agent] Ошибка: {e}")
                time.sleep(5)

        # Завершение
        self.buffer.close()
        print("[Agent] Завершен")

if __name__ == "__main__":
    config_path = Path("config.json")
    if not config_path.exists():
        print("config.json не найден")
        sys.exit(1)

    agent = AuditAgent(config_path)
    agent.run()
7. requirements.txt
txt
requests>=2.28.0
✅ КРИТЕРИИ ПРИЕМКИ
□ Агент запускается и регистрируется в Manager
□ Агент читает Security Log через wevtutil
□ События буферизируются в SQLite
□ События отправляются в Manager батчами
□ При недоступности Manager события сохраняются в буфере
□ При восстановлении связи буфер отправляется
□ Heartbeat отправляется регулярно
□ Агент работает как фоновый процесс
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Настроить аудит на тестовой папке
#    - Создать папку D:\test_audit
#    - В свойствах → Безопасность → Дополнительно → Аудит
#    - Добавить правило для "Everyone" на "Создание файлов", "Удаление"

# 2. Включить политику аудита (администратор)
auditpol /set /subcategory:"File System" /success:enable /failure:enable

# 3. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 4. Запустить агент
cd audit-agent
python main.py

# 5. Создать файлы в тестовой папке
echo test > D:\test_audit\test.txt
del D:\test_audit\test.txt

# 6. Проверить, что события появились в Manager
curl http://localhost:8000/api/audit?limit=10
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
dcap-system/
├── audit-agent/
│   ├── main.py              # ✅ создан
│   ├── config.json          # ✅ создан
│   ├── collector.py         # ✅ создан
│   ├── buffer.py            # ✅ создан
│   ├── sender.py            # ✅ создан
│   ├── heartbeat.py         # ✅ создан (или в sender.py)
│   ├── requirements.txt     # ✅ создан
│   └── README.md            # ✅ создан
├── manager/
│   └── src/
│       ├── api/audit.py     # ✅ уже есть
│       └── connectors/audit/windows_audit.py  # ✅ уже есть
└── prompts/
    └── tz/day_17_audit_agent.md  # ✅ это ТЗ
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_17_audit_agent
git add audit-agent/
git commit -m "feat: День 17 — ядро агента аудита (сбор, буферизация, отправка)"
Разработчик (кодер), приступай! 🚀

