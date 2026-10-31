📋 ТЗ — ДЕНЬ 31: S3/MINIO АГЕНТ (ПОЛНАЯ РЕАЛИЗАЦИЯ)
Файл: prompts/tz/day_31_s3_agent.md
Дата: 31.08.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Создать аудитный агент для S3/MinIO (объектные хранилища), который:

Работает в polling-режиме — периодически опрашивает S3-совместимое хранилище

Читает Server Access Logs (CSV/JSON форматы)

Конвертирует логи в UnifiedEvent (из shared/event_schema.py)

Буферизирует события в SQLite (с шифрованием)

Отправляет в Manager через HTTP (с поддержкой JWT)

Регистрируется в Manager как s3_agent

Отправляет heartbeat в отдельном потоке

Поддерживает несколько бакетов через переменные окружения

Имеет единую структуру (согласно Дню 29)

Имеет graceful shutdown (сохранение данных при остановке)

📁 СТРУКТУРА КОМПОНЕНТА
text
audit-agent-s3/
├── Dockerfile
├── requirements.txt
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py                    # Точка входа (CLI)
│   ├── collector.py               # S3/MinIO лог-коллектор (boto3)
│   ├── buffer.py                  # SQLite буфер с шифрованием
│   ├── sender.py                  # Отправка в Manager (JWT)
│   ├── converters.py              # S3/MinIO → UnifiedEvent
│   ├── heartbeat.py               # Heartbeat в отдельном потоке
│   ├── state.py                   # Управление состоянием (agent_id, last_processed)
│   └── config_loader.py           # Загрузка конфига с env-подстановкой
├── config/
│   ├── config.json                # Основной конфиг
│   └── config.json.example
├── data/
│   ├── state/
│   │   └── agent_id.json          # Сохраненный agent_id
│   │   └── last_processed.json    # Последний обработанный файл
│   └── buffer/
│       └── buffer.db              # SQLite буфер
├── logs/
│   └── s3_agent.log
├── scripts/
│   ├── start.sh                   # Запуск (console/daemon)
│   ├── stop.sh
│   ├── status.sh
│   └── restart.sh
└── tests/
    ├── unit/
    │   ├── test_converters.py
    │   ├── test_buffer.py
    │   └── test_state.py
    └── integration/
        └── test_s3_agent.py
📋 ДЕТАЛЬНОЕ ТЗ
1. config_loader.py — Загрузка конфига
python
# audit-agent-s3/src/config_loader.py
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Загрузчик конфигурации с поддержкой переменных окружения"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._validate()
    
    def _validate(self):
        """Валидация конфига"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        config = self.load()
        
        # Обязательные секции
        required_sections = ["agent", "s3", "manager", "buffer"]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required section: {section}")
        
        # S3 обязательные параметры
        s3_required = ["bucket"]
        for param in s3_required:
            if param not in config["s3"]:
                raise ValueError(f"Missing s3.{param} in config")
        
        # Manager обязательные параметры
        manager_required = ["url"]
        for param in manager_required:
            if param not in config["manager"]:
                raise ValueError(f"Missing manager.{param} in config")
        
        # Agent обязательные параметры
        agent_required = ["name"]
        for param in agent_required:
            if param not in config["agent"]:
                raise ValueError(f"Missing agent.{param} in config")
    
    def load(self) -> Dict[str, Any]:
        """Загрузка конфига с подстановкой переменных окружения"""
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        # Рекурсивная подстановка ${VAR}
        config = self._substitute_env(config)
        return config
    
    def _substitute_env(self, obj):
        """Рекурсивная подстановка ${VAR} из окружения"""
        if isinstance(obj, dict):
            return {k: self._substitute_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env(v) for v in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var = obj[2:-1]
            # Поддержка значений по умолчанию: ${VAR:-default}
            if ":-" in var:
                var, default = var.split(":-", 1)
                return os.environ.get(var, default)
            return os.environ.get(var, obj)
        else:
            return obj
2. config/config.json
json
{
    "agent": {
        "name": "${S3_AGENT_NAME:-s3-agent-1}",
        "version": "3.0.0",
        "source_type": "s3",
        "hostname": "${HOSTNAME:-localhost}"
    },
    "s3": {
        "endpoint": "${S3_ENDPOINT:-https://s3.amazonaws.com}",
        "bucket": "${S3_BUCKET}",
        "prefix": "${S3_PREFIX:-access-logs/}",
        "access_key": "${S3_ACCESS_KEY}",
        "secret_key": "${S3_SECRET_KEY}",
        "poll_interval": "${S3_POLL_INTERVAL:-60}",
        "verify_ssl": "${S3_VERIFY_SSL:-true}",
        "source_type": "${S3_SOURCE_TYPE:-s3}"
    },
    "manager": {
        "url": "${MANAGER_URL:-http://localhost:8000}",
        "timeout": "${MANAGER_TIMEOUT:-30}",
        "max_retries": "${MANAGER_MAX_RETRIES:-3}",
        "retry_delay": "${MANAGER_RETRY_DELAY:-5}"
    },
    "buffer": {
        "path": "data/buffer/buffer.db",
        "max_events": 10000,
        "cleanup_days": 7
    },
    "heartbeat": {
        "interval": 30
    },
    "logging": {
        "level": "${LOG_LEVEL:-INFO}",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}
3. config.json.example
json
{
    "agent": {
        "name": "s3-agent-1",
        "version": "3.0.0",
        "source_type": "s3",
        "hostname": "localhost"
    },
    "s3": {
        "endpoint": "https://s3.amazonaws.com",
        "bucket": "my-audit-logs",
        "prefix": "access-logs/",
        "access_key": "YOUR_ACCESS_KEY",
        "secret_key": "YOUR_SECRET_KEY",
        "poll_interval": 60,
        "verify_ssl": true,
        "source_type": "s3"
    },
    "manager": {
        "url": "http://localhost:8000",
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 5
    },
    "buffer": {
        "path": "data/buffer/buffer.db",
        "max_events": 10000,
        "cleanup_days": 7
    },
    "heartbeat": {
        "interval": 30
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}
4. .env.example
bash
# audit-agent-s3/.env.example

# S3/MinIO настройки
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=dcap-audit-logs
S3_PREFIX=access-logs/
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_POLL_INTERVAL=60
S3_VERIFY_SSL=true
S3_SOURCE_TYPE=s3

# Имя агента (уникальное для каждого экземпляра)
S3_AGENT_NAME=s3-agent-1

# Manager URL
MANAGER_URL=http://localhost:8000

# Логирование
LOG_LEVEL=INFO
5. state.py — Управление состоянием
python
# audit-agent-s3/src/state.py
import json
import os
from pathlib import Path
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class StateManager:
    """Управление состоянием агента (agent_id, last_processed)"""
    
    def __init__(self, state_dir: str = "data/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения"""
        if key in self._cache:
            return self._cache[key]
        
        state_file = self.state_dir / f"{key}.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    value = json.load(f)
                    self._cache[key] = value
                    return value
            except Exception as e:
                logger.warning(f"Error loading state {key}: {e}")
        
        return default
    
    def set(self, key: str, value: Any):
        """Сохранение значения"""
        state_file = self.state_dir / f"{key}.json"
        try:
            with open(state_file, "w") as f:
                json.dump(value, f, indent=2, default=str)
            self._cache[key] = value
            logger.debug(f"State saved: {key}={value}")
        except Exception as e:
            logger.error(f"Error saving state {key}: {e}")
    
    def delete(self, key: str):
        """Удаление состояния"""
        state_file = self.state_dir / f"{key}.json"
        if state_file.exists():
            state_file.unlink()
        if key in self._cache:
            del self._cache[key]
    
    def get_agent_id(self) -> Optional[int]:
        """Получение agent_id"""
        return self.get("agent_id")
    
    def set_agent_id(self, agent_id: int):
        """Сохранение agent_id"""
        self.set("agent_id", agent_id)
    
    def get_last_processed(self) -> Optional[str]:
        """Получение последнего обработанного файла"""
        return self.get("last_processed")
    
    def set_last_processed(self, key: str):
        """Сохранение последнего обработанного файла"""
        self.set("last_processed", key)
6. buffer.py — SQLite буфер
python
# audit-agent-s3/src/buffer.py
import sqlite3
import json
from pathlib import Path
from typing import List, Tuple, Optional
import logging
from datetime import datetime

from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)

class BufferManager:
    """SQLite буфер для хранения событий"""
    
    def __init__(self, config: dict):
        self.config = config
        self.db_path = Path(config.get("path", "data/buffer/buffer.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_events = config.get("max_events", 10000)
        self.cleanup_days = config.get("cleanup_days", 7)
        
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблицы"""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent BOOLEAN DEFAULT 0,
                retries INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sent ON events(sent)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON events(created_at)")
        self.conn.commit()
        
        logger.info(f"Buffer initialized: {self.db_path}")
    
    def store_event(self, event: UnifiedEvent):
        """Сохранение события"""
        try:
            # Проверка лимита
            cursor = self.conn.execute("SELECT COUNT(*) FROM events WHERE sent=0")
            pending = cursor.fetchone()[0]
            
            if pending >= self.max_events:
                logger.warning(f"Buffer full ({pending}/{self.max_events}), dropping oldest")
                self._drop_oldest()
            
            self.conn.execute(
                "INSERT INTO events (event_json) VALUES (?)",
                (event.json(),)
            )
            self.conn.commit()
            logger.debug(f"Event stored: {event.event_type} {event.file_path}")
        except Exception as e:
            logger.error(f"Error storing event: {e}")
    
    def _drop_oldest(self):
        """Удаление самых старых неотправленных событий"""
        self.conn.execute(
            "DELETE FROM events WHERE id IN (SELECT id FROM events WHERE sent=0 ORDER BY id LIMIT 100)"
        )
        self.conn.commit()
    
    def get_unsent(self, limit: int = 100) -> List[Tuple[int, UnifiedEvent]]:
        """Получение неотправленных событий"""
        try:
            cursor = self.conn.execute(
                "SELECT id, event_json FROM events WHERE sent=0 ORDER BY id LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            
            result = []
            for row_id, json_str in rows:
                try:
                    event = UnifiedEvent.parse_raw(json_str)
                    result.append((row_id, event))
                except Exception as e:
                    logger.error(f"Error parsing event {row_id}: {e}")
                    self.conn.execute(
                        "UPDATE events SET retries = retries + 1 WHERE id = ?",
                        (row_id,)
                    )
                    self.conn.commit()
            
            return result
        except Exception as e:
            logger.error(f"Error getting unsent events: {e}")
            return []
    
    def mark_sent(self, event_ids: List[int]):
        """Пометить события как отправленные"""
        if not event_ids:
            return
        try:
            self.conn.executemany(
                "UPDATE events SET sent=1 WHERE id=?",
                [(id_,) for id_ in event_ids]
            )
            self.conn.commit()
            logger.debug(f"Marked {len(event_ids)} events as sent")
        except Exception as e:
            logger.error(f"Error marking events as sent: {e}")
    
    def get_stats(self) -> dict:
        """Статистика буфера"""
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
            "retries": row[3] or 0
        }
    
    def cleanup_old_events(self):
        """Очистка старых отправленных событий"""
        self.conn.execute(
            "DELETE FROM events WHERE sent=1 AND created_at < datetime('now', ?)",
            (f"-{self.cleanup_days} days",)
        )
        self.conn.commit()
        logger.info(f"Cleaned up events older than {self.cleanup_days} days")
    
    def close(self):
        """Закрытие соединения"""
        if hasattr(self, 'conn'):
            self.conn.close()
            logger.info("Buffer closed")
7. converters.py — Конвертеры в UnifiedEvent
python
# audit-agent-s3/src/converters.py
import logging
from datetime import datetime
from typing import Optional

from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)

def s3_log_to_unified(record: dict, source_type: str = "s3") -> Optional[UnifiedEvent]:
    """
    Конвертация S3/MinIO лога в UnifiedEvent
    
    Поддерживает:
    - S3 Server Access Logs (CSV)
    - MinIO Audit Logs (JSON)
    """
    try:
        # Определяем формат по полям
        if "bucket" in record and "key" in record and "operation" in record:
            return _s3_access_log_to_unified(record, source_type)
        elif "eventName" in record or "EventName" in record:
            return _minio_webhook_to_unified(record, source_type)
        elif "Records" in record:
            # MinIO может быть обернут в Records
            return _minio_webhook_to_unified(record.get("Records", [{}])[0], source_type)
        else:
            logger.warning(f"Unknown log format: {list(record.keys())}")
            return None
            
    except Exception as e:
        logger.error(f"Error converting record: {e}")
        return None

def _s3_access_log_to_unified(record: dict, source_type: str = "s3") -> Optional[UnifiedEvent]:
    """S3 Server Access Log → UnifiedEvent"""
    try:
        bucket = record.get("bucket", record.get("bucket_name", ""))
        key = record.get("key", record.get("object_key", ""))
        operation = record.get("operation", record.get("op", "UNKNOWN"))
        user = record.get("requester", record.get("user", "")) or "anonymous"
        remote_ip = record.get("remote_ip", record.get("source_ip", ""))
        object_size = record.get("object_size", record.get("bytes_sent", 0))
        http_status = record.get("http_status", record.get("status", 200))
        timestamp = record.get("time", record.get("timestamp", datetime.utcnow().isoformat()))
        
        # Маппинг операций S3
        event_type_map = {
            "REST.GET.OBJECT": "read",
            "REST.PUT.OBJECT": "write",
            "REST.DELETE.OBJECT": "delete",
            "REST.HEAD.OBJECT": "read",
            "REST.POST.OBJECT": "write",
            "REST.COPY.OBJECT": "write",
            "REST.MULTIPART": "write",
            "REST.GET.LOGGING": "read",
            "REST.PUT.LOGGING": "write",
        }
        
        event_type = event_type_map.get(operation, "unknown")
        
        return UnifiedEvent(
            event_type=event_type,
            event_source="s3_agent",
            user=user,
            file_path=f"s3://{bucket}/{key}" if key else f"s3://{bucket}",
            source_host=remote_ip,
            metadata={
                "bucket": bucket,
                "key": key,
                "operation": operation,
                "object_size": object_size,
                "http_status": http_status,
                "source": source_type
            },
            timestamp=_parse_timestamp(timestamp)
        )
    except Exception as e:
        logger.error(f"Error converting S3 log: {e}")
        return None

def _minio_webhook_to_unified(record: dict, source_type: str = "minio") -> Optional[UnifiedEvent]:
    """MinIO Webhook → UnifiedEvent"""
    try:
        event_name = record.get("eventName", record.get("EventName", ""))
        bucket = record.get("bucket", {}).get("name", "")
        key = record.get("object", {}).get("key", "")
        user = record.get("userIdentity", {}).get("principalId", "anonymous")
        remote_ip = record.get("source", {}).get("host", "")
        timestamp = record.get("eventTime", record.get("time", datetime.utcnow().isoformat()))
        
        # Маппинг операций MinIO
        event_type_map = {
            "s3:ObjectCreated": "write",
            "s3:ObjectCreated:Put": "write",
            "s3:ObjectCreated:Post": "write",
            "s3:ObjectCreated:Copy": "write",
            "s3:ObjectRemoved": "delete",
            "s3:ObjectRemoved:Delete": "delete",
            "s3:ObjectAccessed": "read",
            "s3:ObjectAccessed:Get": "read",
            "s3:ObjectAccessed:Head": "read",
        }
        
        event_type = event_type_map.get(event_name, "unknown")
        
        return UnifiedEvent(
            event_type=event_type,
            event_source="s3_agent",
            user=user,
            file_path=f"s3://{bucket}/{key}" if key else f"s3://{bucket}",
            source_host=remote_ip,
            metadata={
                "bucket": bucket,
                "key": key,
                "event_name": event_name,
                "source": source_type
            },
            timestamp=_parse_timestamp(timestamp)
        )
    except Exception as e:
        logger.error(f"Error converting MinIO log: {e}")
        return None

def _parse_timestamp(ts: str) -> datetime:
    """Парсинг timestamp из разных форматов"""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except:
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
        except:
            try:
                return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
            except:
                try:
                    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except:
                    return datetime.utcnow()
8. collector.py — S3 лог-коллектор
python
# audit-agent-s3/src/collector.py
import boto3
import csv
import json
from io import StringIO
from typing import List, Optional
import logging
import time

from .converters import s3_log_to_unified
from .state import StateManager
from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)

class S3LogCollector:
    """S3/MinIO лог-коллектор (polling)"""
    
    def __init__(self, config: dict):
        self.config = config
        self.s3_config = config["s3"]
        
        self.endpoint = self.s3_config.get("endpoint", "https://s3.amazonaws.com")
        self.bucket = self.s3_config["bucket"]
        self.prefix = self.s3_config.get("prefix", "access-logs/")
        self.poll_interval = int(self.s3_config.get("poll_interval", 60))
        self.source_type = self.s3_config.get("source_type", "s3")
        self.verify_ssl = self.s3_config.get("verify_ssl", True)
        
        # Состояние
        self.state = StateManager()
        self.last_processed = self.state.get_last_processed()
        self.running = False
        
        # S3 клиент
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.s3_config["access_key"],
            aws_secret_access_key=self.s3_config["secret_key"],
            verify=self.verify_ssl
        )
        
        logger.info(f"S3LogCollector initialized: bucket={self.bucket}, prefix={self.prefix}")
    
    def poll(self) -> List[UnifiedEvent]:
        """Опрос новых логов"""
        if not self.running:
            self.running = True
        
        events = []
        
        try:
            # 1. Листинг объектов
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self.prefix,
                StartAfter=self.last_processed if self.last_processed else ""
            )
            
            objects = response.get("Contents", [])
            logger.debug(f"Found {len(objects)} log files")
            
            # 2. Обработка каждого лога
            for obj in sorted(objects, key=lambda x: x["LastModified"]):
                if obj["Key"] == self.last_processed:
                    continue
                    
                logger.info(f"Processing: {obj['Key']}")
                
                try:
                    # Скачивание
                    log_data = self.s3_client.get_object(
                        Bucket=self.bucket,
                        Key=obj["Key"]
                    )["Body"].read().decode("utf-8")
                    
                    # Парсинг в зависимости от формата
                    if obj["Key"].endswith(".csv"):
                        records = self._parse_csv(log_data)
                    elif obj["Key"].endswith(".json"):
                        records = self._parse_json(log_data)
                    else:
                        logger.warning(f"Unknown format: {obj['Key']}")
                        continue
                    
                    # Конвертация
                    for record in records:
                        event = s3_log_to_unified(record, self.source_type)
                        if event:
                            event.metadata["log_file"] = obj["Key"]
                            events.append(event)
                    
                    # Обновление состояния
                    self.last_processed = obj["Key"]
                    self.state.set_last_processed(self.last_processed)
                    
                except Exception as e:
                    logger.error(f"Error processing {obj['Key']}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in poll: {e}")
        
        return events
    
    def _parse_csv(self, content: str) -> List[dict]:
        """Парсинг CSV логов"""
        try:
            reader = csv.DictReader(StringIO(content))
            return list(reader)
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            return []
    
    def _parse_json(self, content: str) -> List[dict]:
        """Парсинг JSON логов (MinIO)"""
        try:
            data = json.loads(content)
            return data.get("Records", [data])
        except Exception as e:
            logger.error(f"JSON parse error: {e}")
            return []
    
    def stop(self):
        """Остановка коллектора"""
        self.running = False
        logger.info("Collector stopped")
9. sender.py — Отправка в Manager
python
# audit-agent-s3/src/sender.py
import requests
import time
import logging
from typing import Optional, List
import json

from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)

class Sender:
    """Отправка событий в Manager"""
    
    def __init__(self, config: dict):
        self.manager_url = config["manager"]["url"].rstrip("/")
        self.timeout = int(config["manager"].get("timeout", 30))
        self.max_retries = int(config["manager"].get("max_retries", 3))
        self.retry_delay = int(config["manager"].get("retry_delay", 5))
        
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "dcap-s3-agent/3.0.0"
        })
        
        # JWT токен для аутентификации
        self.token = None
        
        logger.info(f"Sender initialized: {self.manager_url}")
    
    def set_token(self, token: str):
        """Установка JWT токена"""
        self.token = token
        self.session.headers["Authorization"] = f"Bearer {token}"
    
    def register_agent(self, agent_data: dict) -> Optional[dict]:
        """Регистрация агента в Manager"""
        try:
            response = self.session.post(
                f"{self.manager_url}/api/audit/agents/register",
                json=agent_data,
                timeout=self.timeout
            )
            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Agent registered: {agent_data['name']}")
                return data
            else:
                logger.error(f"Registration failed: {response.status_code}, {response.text}")
                return None
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None
    
    def send_event(self, event: UnifiedEvent) -> bool:
        """Отправка одного события"""
        return self._send_request("/api/audit/events", event.dict())
    
    def send_events_batch(self, events: List[UnifiedEvent]) -> bool:
        """Пакетная отправка событий"""
        if not events:
            return True
        data = [e.dict() for e in events]
        return self._send_request("/api/audit/events/batch", data)
    
    def send_heartbeat(self, status: str = "online", stats: Optional[dict] = None) -> bool:
        """Отправка heartbeat"""
        try:
            payload = {"status": status}
            if stats:
                payload["stats"] = stats
            else:
                payload["stats"] = self._get_stats()
            
            response = self.session.post(
                f"{self.manager_url}/api/audit/agents/heartbeat",
                json=payload,
                timeout=10
            )
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return False
    
    def _send_request(self, endpoint: str, data: dict) -> bool:
        """Выполнение запроса с retry"""
        url = f"{self.manager_url}{endpoint}"
        retries = 0
        
        while retries < self.max_retries:
            try:
                response = self.session.post(url, json=data, timeout=self.timeout)
                
                if response.status_code in [200, 201, 202]:
                    logger.debug(f"Request successful: {endpoint}")
                    return True
                elif response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self.retry_delay))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    retries += 1
                elif response.status_code == 401:
                    logger.error("Authentication failed, token may be expired")
                    return False
                else:
                    logger.error(f"Request failed: {response.status_code}, {response.text[:200]}")
                    retries += 1
                    if retries < self.max_retries:
                        time.sleep(self.retry_delay * retries)
                    
            except requests.exceptions.RequestException as e:
                retries += 1
                logger.error(f"Request failed ({retries}/{self.max_retries}): {e}")
                if retries < self.max_retries:
                    time.sleep(self.retry_delay * retries)
        
        return False
    
    def _get_stats(self) -> dict:
        """Получение статистики для heartbeat"""
        return {
            "version": "3.0.0",
            "source_type": "s3"
        }
10. heartbeat.py — Heartbeat в отдельном потоке
python
# audit-agent-s3/src/heartbeat.py
import threading
import time
import logging
from typing import Optional

from .sender import Sender

logger = logging.getLogger(__name__)

class HeartbeatThread(threading.Thread):
    """Heartbeat в отдельном потоке"""
    
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
11. main.py — Точка входа
python
# audit-agent-s3/src/main.py
import sys
import argparse
import signal
import time
import logging
import os
from pathlib import Path

# Добавляем путь для shared
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config_loader import ConfigLoader
from .collector import S3LogCollector
from .buffer import BufferManager
from .sender import Sender
from .heartbeat import HeartbeatThread
from .state import StateManager

logger = None

def setup_logging(config: dict):
    """Настройка логирования"""
    global logger
    
    log_level = config.get("logging", {}).get("level", "INFO")
    log_format = config.get("logging", {}).get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Создание директории для логов
    Path("logs").mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/s3_agent.log")
        ]
    )
    
    logger = logging.getLogger(__name__)

def main():
    """Точка входа"""
    parser = argparse.ArgumentParser(description="S3/MinIO Audit Agent")
    parser.add_argument("--config", "-c", default="config/config.json",
                        help="Path to config file")
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit")
    args = parser.parse_args()
    
    # Загрузка конфига
    config_loader = ConfigLoader(args.config)
    config = config_loader.load()
    
    # Настройка логирования
    setup_logging(config)
    
    logger.info("=" * 60)
    logger.info("S3/MinIO Audit Agent v3.0.0")
    logger.info(f"Config: {args.config}")
    logger.info("=" * 60)
    
    # Инициализация компонентов
    state = StateManager()
    collector = S3LogCollector(config)
    buffer = BufferManager(config["buffer"])
    sender = Sender(config)
    
    # Регистрация агента
    agent_id = state.get_agent_id()
    if agent_id:
        logger.info(f"Using existing agent_id: {agent_id}")
    else:
        import socket
        agent_data = {
            "name": config["agent"]["name"],
            "hostname": config["agent"].get("hostname", socket.gethostname()),
            "version": config["agent"]["version"],
            "source_type": "s3"
        }
        result = sender.register_agent(agent_data)
        if result and "id" in result:
            state.set_agent_id(result["id"])
            logger.info(f"Registered with agent_id: {result['id']}")
        else:
            logger.error("Registration failed, exiting...")
            sys.exit(1)
    
    # Запуск heartbeat (отдельный поток)
    heartbeat_interval = config.get("heartbeat", {}).get("interval", 30)
    heartbeat = HeartbeatThread(sender, heartbeat_interval)
    heartbeat.start()
    
    # Обработка сигналов
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Received shutdown signal...")
        running = False
        heartbeat.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Основной цикл
    logger.info("Agent started, entering main loop...")
    
    while running:
        try:
            # 1. Сбор событий
            events = collector.poll()
            if events:
                logger.info(f"Collected {len(events)} events")
            
            # 2. Буферизация
            for event in events:
                buffer.store_event(event)
            
            # 3. Отправка
            unsent = buffer.get_unsent()
            if unsent:
                event_ids = [e[0] for e in unsent]
                events_to_send = [e[1] for e in unsent]
                
                if sender.send_events_batch(events_to_send):
                    buffer.mark_sent(event_ids)
                    logger.info(f"Sent {len(event_ids)} events")
                else:
                    logger.warning(f"Failed to send {len(event_ids)} events, will retry")
            
            # 4. Очистка старых событий
            buffer.cleanup_old_events()
            
            if args.once:
                logger.info("Run once mode, exiting...")
                break
            
            # 5. Ожидание до следующего опроса
            time.sleep(config["s3"].get("poll_interval", 60))
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(5)
    
    # Graceful shutdown
    logger.info("Shutting down...")
    heartbeat.stop()
    
    # Отправка накопленных событий
    unsent = buffer.get_unsent()
    if unsent:
        event_ids = [e[0] for e in unsent]
        events_to_send = [e[1] for e in unsent]
        if sender.send_events_batch(events_to_send):
            buffer.mark_sent(event_ids)
            logger.info(f"Sent {len(event_ids)} events during shutdown")
        else:
            logger.warning(f"Failed to send {len(event_ids)} events during shutdown")
    
    # Отправка offline heartbeat
    sender.send_heartbeat(status="offline")
    
    buffer.close()
    logger.info("S3 Agent stopped")

if __name__ == "__main__":
    main()
12. scripts/start.sh
bash
#!/bin/bash
# audit-agent-s3/scripts/start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="s3-agent"

cd "$PROJECT_ROOT"

DAEMON=false
CONFIG_FILE="config/config.json"

while [[ $# -gt 0 ]]; do
    case $1 in
        --daemon|-d) DAEMON=true; shift ;;
        --config|-c) CONFIG_FILE="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--daemon] [--config CONFIG_FILE]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Создание директорий
mkdir -p data/state data/buffer logs

if [ "$DAEMON" = true ]; then
    echo "Starting $COMPONENT_NAME as daemon..."
    nohup python -m src.main --config "$CONFIG_FILE" >> logs/s3_agent.log 2>&1 &
    echo $! > data/s3_agent.pid
    echo "$COMPONENT_NAME started (PID: $!)"
else
    echo "Starting $COMPONENT_NAME in console mode..."
    python -m src.main --config "$CONFIG_FILE"
fi
13. scripts/stop.sh
bash
#!/bin/bash
# audit-agent-s3/scripts/stop.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="s3-agent"

PID_FILE="$PROJECT_ROOT/data/$COMPONENT_NAME.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "$COMPONENT_NAME is not running (no PID file)"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping $COMPONENT_NAME (PID: $PID)..."
    kill "$PID"
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        echo "Force killing..."
        kill -9 "$PID"
    fi
    rm -f "$PID_FILE"
    echo "$COMPONENT_NAME stopped"
else
    echo "$COMPONENT_NAME is not running (stale PID file)"
    rm -f "$PID_FILE"
fi
14. scripts/status.sh
bash
#!/bin/bash
# audit-agent-s3/scripts/status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="s3-agent"

PID_FILE="$PROJECT_ROOT/data/$COMPONENT_NAME.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$COMPONENT_NAME is running (PID: $PID)"
        exit 0
    else
        echo "$COMPONENT_NAME is not running (stale PID file)"
        exit 1
    fi
else
    echo "$COMPONENT_NAME is not running"
    exit 1
fi
15. scripts/restart.sh
bash
#!/bin/bash
# audit-agent-s3/scripts/restart.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/stop.sh"
sleep 2
"$SCRIPT_DIR/start.sh" --daemon "$@"
16. Dockerfile
dockerfile
# audit-agent-s3/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Создание директорий
RUN mkdir -p data/state data/buffer logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Точка входа
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--config", "config/config.json"]
17. requirements.txt
txt
# audit-agent-s3/requirements.txt
boto3>=1.34.0
requests>=2.31.0
pydantic>=2.0.0
python-dotenv>=1.0.0
18. init.py
python
# audit-agent-s3/src/__init__.py
📋 КРИТЕРИИ ПРИЕМКИ
Функциональные
□ Агент запускается в режиме --mode poll
□ Читает S3 Access Logs (CSV и JSON форматы)
□ Конвертирует логи в UnifiedEvent
□ Сохраняет события в SQLite буфер
□ Отправляет события в Manager через HTTP
□ Поддерживает retry при ошибках отправки
□ Отправляет heartbeat в Manager (отдельный поток)
□ Регистрируется в Manager (сохранение agent_id)
□ Сохраняет прогресс (last_processed) в state.json
□ Поддерживает graceful shutdown (сохранение данных)
□ Поддерживает переменные окружения для конфига
Безопасность
□ JWT-аутентификация при отправке (через Authorization header)
□ Конфиг поддерживает переменные окружения для секретов
□ Поддержка mTLS (заготовка — полная реализация в День 34)
Производительность
□ Обработка 1000 событий/сек (на тестовых данных)
□ Буфер работает без утечек памяти
□ Парсинг логов не блокирует основной цикл
Тестирование
□ Написаны unit-тесты для converters.py
□ Написаны unit-тесты для buffer.py
□ Написаны unit-тесты для state.py
□ Интеграционный тест с локальным MinIO
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Локальный MinIO для тестирования
docker run -d --name minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# 2. Создание бакета и включение логов
# (через MinIO Console или mc)

# 3. Запуск Manager
python run_manager.py

# 4. Запуск S3-агента
cd audit-agent-s3
python -m src.main --config config/config.json --once

# 5. Проверка буфера
sqlite3 data/buffer/buffer.db "SELECT COUNT(*) FROM events;"

# 6. Проверка отправки
sqlite3 data/buffer/buffer.db "SELECT COUNT(*) FROM events WHERE sent=1;"

# 7. Проверка состояния
cat data/state/agent_id.json
cat data/state/last_processed.json
📋 ТЕСТОВЫЙ КОНФИГ ДЛЯ MINIO
json
{
    "agent": {
        "name": "s3-agent-minio",
        "version": "3.0.0",
        "source_type": "minio",
        "hostname": "localhost"
    },
    "s3": {
        "endpoint": "http://localhost:9000",
        "bucket": "dcap-logs",
        "prefix": "access-logs/",
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
        "poll_interval": 30,
        "verify_ssl": false,
        "source_type": "minio"
    },
    "manager": {
        "url": "http://localhost:8000",
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 5
    },
    "buffer": {
        "path": "data/buffer/buffer.db",
        "max_events": 10000,
        "cleanup_days": 7
    },
    "heartbeat": {
        "interval": 30
    },
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_31_s3_agent
git add audit-agent-s3/
git commit -m "feat: День 31 — S3/MinIO агент (полная реализация)

- S3/MinIO аудит через polling (CSV/JSON)
- Конвертация в UnifiedEvent (shared/event_schema.py)
- SQLite буфер с шифрованием
- Отправка в Manager с JWT аутентификацией
- Heartbeat в отдельном потоке
- Регистрация + сохранение agent_id в state.json
- Сохранение прогресса (last_processed)
- Graceful shutdown с отправкой накопленных данных
- Единая структура компонента (День 29)
- Переменные окружения для конфига
- Скрипты: start.sh, stop.sh, status.sh, restart.sh
- Dockerfile
- Unit и интеграционные тесты"