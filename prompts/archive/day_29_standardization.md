📋 ТЗ — ДЕНЬ 29: СТАНДАРТИЗАЦИЯ СТРУКТУРЫ КОМПОНЕНТОВ
Файл: prompts/tz/day_29_standardization.md
Дата: 29.08.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Привести все компоненты системы к единому стандарту на основе анализа текущей структуры:

Очистка мертвого кода — удаление неиспользуемых файлов

Единая структура директорий — одинаковые имена и иерархия для всех компонентов

Единые скрипты запуска — start.sh, stop.sh, status.sh, restart.sh

Единое хранение состояния — data/ для state, buffer, cache

Единая загрузка конфигов — ConfigLoader из shared/

Устранение дубликатов — удаление легаси-файлов и дублирующихся entry points

Подключение shared/event_schema.py — интеграция UnifiedEvent во все компоненты

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ / УДАЛЕНИЯ / СОЗДАНИЯ
1. УДАЛИТЬ (Мертвый код — 13 файлов)
Файл	Причина
scanner/core/test_source.py	Не импортируется
scanner/core/dispatcher.py	Не импортируется
scanner/core/config_manager.py	Не импортируется, дублирует config_loader
scanner/core/resource_manager.py	Не импортируется
scanner/core/memory_profiler.py	Не импортируется
scanner/utils/ocr_pool.py	Не импортируется
scanner/utils/safe_ocr_worker.py	Не импортируется
scanner/classifiers/model_worker.py	Не импортируется
scanner/src/offline/detector.py	Импортирует несуществующий dcap/manager_pb2
scanner/src/offline/sync.py	Импортирует несуществующий dcap/manager_pb2
shared/event_schema.py	НЕ УДАЛЯТЬ — подключить к компонентам
audit-agent-linux/heartbeat.py	Не импортируется main.py
manager/src/core/scheduler.py	Импортирует несуществующие get_session, TaskStatus
2. УДАЛИТЬ (Дубликаты и легаси — 5 файлов)
Файл	Причина
webui/run_webui.py	Дубликат корневого run_webui.py
state.json (корень)	Принадлежит audit-agent, должен лежать в audit-agent/data/
dcap.db (корень)	Устаревшая копия БД
structure.txt	Устарел
Makefile	Фикция — docker-compose.yml отсутствует
3. ПЕРЕМЕСТИТЬ
Файл	Откуда	Куда
state.json (корень)	/	audit-agent/data/state.json
buffer/ (корень)	/buffer/	audit-agent/data/buffer/
4. СОЗДАТЬ (Новые файлы)
Файл	Назначение
shared/config_loader.py	Единая загрузка конфигов для всех компонентов
shared/logging.py	Единая настройка логирования
shared/state_manager.py	Единое управление состоянием (state.json)
audit-agent/data/	Директория для состояния и буфера
audit-agent-linux/data/	Директория для состояния и буфера
audit-agent-linux/data/state.json	Файл состояния для Linux-агента
scanner/data/	Директория для состояния
scanner/data/state.json	Файл состояния для сканера
manager/data/	Директория для состояния
webui/data/	Директория для состояния
5. ОБНОВИТЬ (Существующие файлы)
Файл	Изменение
audit-agent/main.py	Использовать shared/config_loader.py, shared/logging.py, shared/state_manager.py. Удалить прямой json.load. Подключить UnifiedEvent.
audit-agent/collector.py	Использовать UnifiedEvent вместо сырых dict
audit-agent/buffer.py	Использовать UnifiedEvent
audit-agent/sender.py	Использовать UnifiedEvent, shared/config_loader.py
audit-agent/service.py	Использовать shared/config_loader.py
audit-agent/config_loader.py	УДАЛИТЬ (заменен на shared/config_loader.py)
audit-agent/heartbeat.py	УДАЛИТЬ (дублирует sender.send_heartbeat)
audit-agent-linux/main.py	Использовать shared/config_loader.py, shared/state_manager.py. Добавить сохранение agent_id. Подключить UnifiedEvent.
audit-agent-linux/collector.py	Использовать UnifiedEvent
audit-agent-linux/buffer.py	Использовать UnifiedEvent
audit-agent-linux/sender.py	Использовать UnifiedEvent
audit-agent-linux/config_loader.py	УДАЛИТЬ (заменен на shared/config_loader.py)
scanner/src/managed_scanner.py	Использовать shared/config_loader.py, shared/state_manager.py. Подключить offline/queue.py для сохранения результатов при ошибке.
scanner/src/config_loader.py	УДАЛИТЬ (заменен на shared/config_loader.py)
scanner/src/core/orchestrator.py	Использовать shared/logging.py, UnifiedEvent для результатов
scanner/src/core/state_manager.py	УДАЛИТЬ (заменен на shared/state_manager.py)
scanner/src/core/metrics.py	Использовать shared/logging.py
scanner/src/handlers/finding_collector.py	Использовать UnifiedEvent
manager/src/main.py	Использовать shared/config_loader.py, shared/logging.py
manager/src/api/audit.py	Использовать UnifiedEvent для валидации входящих событий
manager/src/api/scanner.py	Использовать UnifiedEvent
manager/src/db/models.py	Добавить поле event_source если отсутствует
webui/main.py	Использовать shared/config_loader.py, shared/logging.py
webui/config.py	УДАЛИТЬ (заменен на shared/config_loader.py)
webui/api/routes.py	Использовать shared/logging.py
run_scanner.py	Обновить пути для новой структуры
run_webui.py	Обновить пути для новой структуры
requirements.txt	Добавить pydantic если отсутствует
.gitignore	Обновить для новых путей (data/, *.db, *.log)
6. ОСТАВИТЬ (Заглушки для v3.0)
Файл	Причина
scanner/connectors/s3_connector.py	Запланирован на v3.0 (S3/MinIO)
manager/src/connectors/permissions/remote.py	Заглушка, будет доработана в День 33
scanner/src/modes/*.py	Альтернативная архитектура — оставить для возможного рефакторинга
📋 ДЕТАЛЬНОЕ ТЗ
1. Создать shared/config_loader.py
python
# shared/config_loader.py
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigLoader:
    """Единый загрузчик конфигурации для всех компонентов"""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.root_dir = Path(__file__).parent.parent
        self.config_dir = self.root_dir / component_name / "config"
        self.data_dir = self.root_dir / component_name / "data"
        self.logs_dir = self.root_dir / component_name / "logs"
        
        # Создание директорий
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Создание всех необходимых директорий"""
        for dir_path in [self.data_dir, self.logs_dir, self.config_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Поддиректории
        (self.data_dir / "buffer").mkdir(exist_ok=True)
        (self.data_dir / "cache").mkdir(exist_ok=True)
        (self.data_dir / "state").mkdir(exist_ok=True)
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Загрузка конфига с переопределениями"""
        # 1. Базовый конфиг
        if config_path:
            base_path = Path(config_path)
        else:
            base_path = self.config_dir / "config.json"
        
        if not base_path.exists():
            raise FileNotFoundError(f"Config file not found: {base_path}")
        
        with open(base_path) as f:
            config = json.load(f)
        
        # 2. Локальное переопределение
        local_path = self.config_dir / "config.local.json"
        if local_path.exists():
            with open(local_path) as f:
                local_config = json.load(f)
                self._deep_merge(config, local_config)
        
        # 3. Переменные окружения
        self._apply_env_overrides(config)
        
        # 4. Добавление стандартных путей
        config.setdefault("paths", {})
        config["paths"]["data_dir"] = str(self.data_dir)
        config["paths"]["logs_dir"] = str(self.logs_dir)
        config["paths"]["config_dir"] = str(self.config_dir)
        
        return config
    
    def _deep_merge(self, base: dict, override: dict):
        """Рекурсивное слияние словарей"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self, config: dict, prefix: str = ""):
        """Применение переменных окружения"""
        env_prefix = self.component_name.upper().replace("-", "_")
        for key, value in config.items():
            env_key = f"{env_prefix}_{key.upper()}" if not prefix else f"{env_prefix}_{prefix}_{key.upper()}"
            if isinstance(value, dict):
                self._apply_env_overrides(value, key)
            elif isinstance(value, (str, int, float, bool)):
                env_value = os.environ.get(env_key)
                if env_value is not None:
                    if isinstance(value, bool):
                        config[key] = env_value.lower() in ("true", "1", "yes")
                    elif isinstance(value, int):
                        config[key] = int(env_value)
                    elif isinstance(value, float):
                        config[key] = float(env_value)
                    else:
                        config[key] = env_value
2. Создать shared/state_manager.py
python
# shared/state_manager.py
import json
import os
from pathlib import Path
from typing import Any, Optional

class StateManager:
    """Единое управление состоянием для всех компонентов"""
    
    def __init__(self, component_name: str, data_dir: Optional[str] = None):
        self.component_name = component_name
        
        if data_dir:
            self.state_dir = Path(data_dir) / "state"
        else:
            self.state_dir = Path(__file__).parent.parent / component_name / "data" / "state"
        
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения по ключу"""
        if key in self._cache:
            return self._cache[key]
        
        state_file = self.state_dir / f"{key}.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    value = json.load(f)
                    self._cache[key] = value
                    return value
            except:
                pass
        
        return default
    
    def set(self, key: str, value: Any):
        """Сохранение значения"""
        state_file = self.state_dir / f"{key}.json"
        with open(state_file, "w") as f:
            json.dump(value, f, indent=2, default=str)
        self._cache[key] = value
    
    def delete(self, key: str):
        """Удаление состояния"""
        state_file = self.state_dir / f"{key}.json"
        if state_file.exists():
            state_file.unlink()
        if key in self._cache:
            del self._cache[key]
    
    def get_agent_id(self) -> Optional[int]:
        """Получение agent_id (для агентов)"""
        return self.get("agent_id")
    
    def set_agent_id(self, agent_id: int):
        """Сохранение agent_id (для агентов)"""
        self.set("agent_id", agent_id)
    
    def get_task_progress(self, task_id: int) -> Optional[dict]:
        """Получение прогресса задачи (для сканера)"""
        return self.get(f"task_{task_id}")
    
    def set_task_progress(self, task_id: int, progress: dict):
        """Сохранение прогресса задачи (для сканера)"""
        self.set(f"task_{task_id}", progress)
3. Создать shared/logging.py
python
# shared/logging.py
import logging
import sys
from pathlib import Path
from typing import Optional

def setup_logging(
    component_name: str,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
):
    """Единая настройка логирования для всех компонентов"""
    
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )
    
    return logging.getLogger(component_name)
4. Обновить audit-agent/main.py
Ключевые изменения:

Использовать shared/config_loader.py вместо прямого json.load

Использовать shared/state_manager.py для сохранения agent_id

Использовать shared/logging.py

Подключить UnifiedEvent из shared/event_schema.py

Удалить прямой импорт heartbeat.py (использовать sender.send_heartbeat())

python
# audit-agent/main.py (ОБНОВЛЕННЫЙ)
import sys
import time
import signal
from pathlib import Path

# Добавляем shared в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config_loader import ConfigLoader
from shared.state_manager import StateManager
from shared.logging import setup_logging
from shared.event_schema import UnifiedEvent

from collector import WindowsAuditCollector
from buffer import BufferManager
from sender import Sender

class AuditAgent:
    def __init__(self):
        # Загрузка конфига
        self.config_loader = ConfigLoader("audit-agent")
        self.config = self.config_loader.load_config()
        
        # Настройка логирования
        log_level = self.config.get("logging", {}).get("level", "INFO")
        log_file = self.config.get("logging", {}).get("file")
        if log_file:
            log_file = str(self.config_loader.logs_dir / log_file)
        self.logger = setup_logging("audit-agent", log_level, log_file)
        
        # Состояние
        self.state = StateManager("audit-agent")
        self.agent_id = self.state.get_agent_id()
        
        # Компоненты
        self.collector = WindowsAuditCollector(self.config)
        self.buffer = BufferManager(self.config)
        self.sender = Sender(self.config)
        
        self.running = False
    
    def register(self):
        """Регистрация в Manager"""
        if self.agent_id:
            self.logger.info(f"Using existing agent_id: {self.agent_id}")
            return
        
        response = self.sender.register_agent({
            "name": self.config["agent"]["name"],
            "hostname": self.config["agent"]["hostname"],
            "version": "3.0.0"
        })
        
        if response and "id" in response:
            self.agent_id = response["id"]
            self.state.set_agent_id(self.agent_id)
            self.logger.info(f"Registered with agent_id: {self.agent_id}")
    
    def run(self):
        """Основной цикл"""
        self.running = True
        self.register()
        
        while self.running:
            try:
                # Сбор событий
                events = self.collector.collect()
                
                # Конвертация в UnifiedEvent
                unified_events = [UnifiedEvent(**e) for e in events]
                
                # Буферизация
                for event in unified_events:
                    self.buffer.store_event(event)
                
                # Отправка
                unsent = self.buffer.get_unsent()
                if unsent:
                    self.sender.send_events(unsent)
                    self.buffer.mark_sent([e.id for e in unsent])
                
                # Heartbeat
                self.sender.send_heartbeat()
                
                time.sleep(self.config.get("interval", 60))
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(5)
        
        # Graceful shutdown
        self._shutdown()
    
    def _shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        self.running = False
        
        # Отправка накопленных событий
        unsent = self.buffer.get_unsent()
        if unsent:
            self.sender.send_events(unsent)
            self.buffer.mark_sent([e.id for e in unsent])
        
        # Отправка offline heartbeat
        self.sender.send_heartbeat(status="offline")
        
        # Закрытие буфера
        self.buffer.close()
        
        self.logger.info("Shutdown complete")

if __name__ == "__main__":
    agent = AuditAgent()
    
    # Signal handlers
    def signal_handler(sig, frame):
        agent._shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    agent.run()
5. Обновить audit-agent-linux/main.py
Ключевые изменения:

Использовать shared/config_loader.py

Использовать shared/state_manager.py для сохранения agent_id

Использовать shared/logging.py

Подключить UnifiedEvent

Удалить heartbeat.py (использовать sender.send_heartbeat())

python
# audit-agent-linux/main.py (ОБНОВЛЕННЫЙ)
import sys
import time
import signal
from pathlib import Path
from threading import Thread

# Добавляем shared в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config_loader import ConfigLoader
from shared.state_manager import StateManager
from shared.logging import setup_logging
from shared.event_schema import UnifiedEvent

from collector import InotifyCollector
from buffer import BufferManager
from sender import Sender

class AuditAgentLinux:
    def __init__(self):
        # Загрузка конфига
        self.config_loader = ConfigLoader("audit-agent-linux")
        self.config = self.config_loader.load_config()
        
        # Настройка логирования
        log_level = self.config.get("logging", {}).get("level", "INFO")
        log_file = self.config.get("logging", {}).get("file")
        if log_file:
            log_file = str(self.config_loader.logs_dir / log_file)
        self.logger = setup_logging("audit-agent-linux", log_level, log_file)
        
        # Состояние
        self.state = StateManager("audit-agent-linux")
        self.agent_id = self.state.get_agent_id()
        
        # Компоненты
        self.collector = InotifyCollector(self.config)
        self.buffer = BufferManager(self.config)
        self.sender = Sender(self.config)
        self.collector_thread = None
        
        self.running = False
    
    def register(self):
        """Регистрация в Manager"""
        if self.agent_id:
            self.logger.info(f"Using existing agent_id: {self.agent_id}")
            return
        
        response = self.sender.register_agent({
            "name": self.config["agent"]["name"],
            "hostname": self.config["agent"]["hostname"],
            "version": "3.0.0"
        })
        
        if response and "id" in response:
            self.agent_id = response["id"]
            self.state.set_agent_id(self.agent_id)
            self.logger.info(f"Registered with agent_id: {self.agent_id}")
    
    def run(self):
        """Основной цикл"""
        self.running = True
        self.register()
        
        # Запуск collector в отдельном потоке
        self.collector_thread = Thread(target=self._collector_loop, daemon=True)
        self.collector_thread.start()
        
        # Основной цикл: отправка и heartbeat
        while self.running:
            try:
                # Отправка накопленных событий
                unsent = self.buffer.get_unsent()
                if unsent:
                    self.sender.send_events(unsent)
                    self.buffer.mark_sent([e.id for e in unsent])
                
                # Heartbeat
                self.sender.send_heartbeat()
                
                time.sleep(self.config.get("heartbeat_interval", 30))
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(5)
        
        # Graceful shutdown
        self._shutdown()
    
    def _collector_loop(self):
        """Цикл сбора событий (в отдельном потоке)"""
        while self.running:
            try:
                events = self.collector.collect()
                for event in events:
                    unified = UnifiedEvent(**event)
                    self.buffer.store_event(unified)
            except Exception as e:
                self.logger.error(f"Collector error: {e}")
                time.sleep(1)
    
    def _shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        self.running = False
        
        # Остановка collector
        if self.collector:
            self.collector.stop()
        
        # Отправка накопленных событий
        unsent = self.buffer.get_unsent()
        if unsent:
            self.sender.send_events(unsent)
            self.buffer.mark_sent([e.id for e in unsent])
        
        # Отправка offline heartbeat
        self.sender.send_heartbeat(status="offline")
        
        # Закрытие буфера
        self.buffer.close()
        
        self.logger.info("Shutdown complete")

if __name__ == "__main__":
    agent = AuditAgentLinux()
    
    def signal_handler(sig, frame):
        agent._shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    agent.run()
6. Обновить scanner/src/managed_scanner.py
Ключевые изменения:

Использовать shared/config_loader.py

Использовать shared/state_manager.py

Использовать shared/logging.py

Подключить offline/queue.py для сохранения результатов при ошибке

python
# scanner/src/managed_scanner.py (ОБНОВЛЕННЫЙ)
import sys
import time
import signal
from pathlib import Path

# Добавляем shared в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.config_loader import ConfigLoader
from shared.state_manager import StateManager
from shared.logging import setup_logging
from shared.event_schema import UnifiedEvent

from core.orchestrator import Orchestrator
from core.heartbeat import HeartbeatThread
from offline.queue import OfflineQueue

class ManagedScanner:
    def __init__(self, config_path: Optional[str] = None):
        # Загрузка конфига
        self.config_loader = ConfigLoader("scanner")
        self.config = self.config_loader.load_config(config_path)
        
        # Настройка логирования
        log_level = self.config.get("logging", {}).get("level", "INFO")
        log_file = self.config.get("logging", {}).get("file")
        if log_file:
            log_file = str(self.config_loader.logs_dir / log_file)
        self.logger = setup_logging("scanner", log_level, log_file)
        
        # Состояние
        self.state = StateManager("scanner")
        self.scanner_id = self.state.get("scanner_id")
        
        # Компоненты
        self.orchestrator = Orchestrator(self.config)
        self.offline_queue = OfflineQueue(self.config)
        self.heartbeat_thread = None
        
        self.running = False
        self.current_task_id = None
    
    def register(self):
        """Регистрация в Manager"""
        if self.scanner_id:
            self.logger.info(f"Using existing scanner_id: {self.scanner_id}")
            return
        
        response = self._register()
        if response and "id" in response:
            self.scanner_id = response["id"]
            self.state.set("scanner_id", self.scanner_id)
            self.logger.info(f"Registered with scanner_id: {self.scanner_id}")
    
    def run(self):
        """Основной цикл"""
        self.running = True
        self.register()
        
        # Запуск heartbeat в отдельном потоке
        self.heartbeat_thread = HeartbeatThread(self)
        self.heartbeat_thread.start()
        
        while self.running:
            try:
                # Проверка наличия задания
                task = self._get_task()
                if task:
                    self.current_task_id = task["id"]
                    self.state.set_task_progress(task["id"], {"status": "started"})
                    
                    # Выполнение задания
                    result = self.orchestrator.execute(task)
                    
                    # Отправка результатов
                    if not self._submit_results(result):
                        # Сохранение в offline-буфер
                        self.offline_queue.save(result)
                        self.logger.warning("Results saved to offline queue")
                    
                    # Завершение задания
                    self._complete_task(task["id"])
                    self.state.delete(f"task_{task['id']}")
                
                time.sleep(self.config.get("poll_interval", 30))
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(5)
        
        # Graceful shutdown
        self._shutdown()
    
    def _submit_results(self, results) -> bool:
        """Отправка результатов с сохранением в offline-буфер при ошибке"""
        try:
            response = self.sender.post("/api/scanner/results", results)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error submitting results: {e}")
            self.offline_queue.save(results)
            return False
    
    def _shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        self.running = False
        
        # Сохранение прогресса текущей задачи
        if self.current_task_id:
            progress = self.orchestrator.get_progress()
            self.state.set_task_progress(self.current_task_id, progress)
            self.logger.info(f"Task {self.current_task_id} progress saved")
        
        # Отправка offline heartbeat
        self.sender.send_heartbeat(status="offline")
        
        self.logger.info("Shutdown complete")
7. Подключить shared/event_schema.py
Ключевые изменения:

Обновить manager/src/api/audit.py для валидации входящих событий через UnifiedEvent

Обновить audit-agent/collector.py для возврата UnifiedEvent

Обновить audit-agent-linux/collector.py для возврата UnifiedEvent

Обновить scanner/src/handlers/finding_collector.py для возврата UnifiedEvent

8. Создать единые скрипты для каждого компонента
bash
# audit-agent/scripts/start.sh
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="audit-agent"

DAEMON=false
CONFIG_FILE="$PROJECT_ROOT/config/config.json"

while [[ $# -gt 0 ]]; do
    case $1 in
        --daemon|-d) DAEMON=true; shift ;;
        --config|-c) CONFIG_FILE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ "$DAEMON" = true ]; then
    cd "$PROJECT_ROOT"
    nohup python -m src.main --config "$CONFIG_FILE" >> logs/audit-agent.log 2>&1 &
    echo $! > data/audit-agent.pid
    echo "Started $COMPONENT_NAME (PID: $!)"
else
    cd "$PROJECT_ROOT"
    python -m src.main --config "$CONFIG_FILE"
fi
📋 КРИТЕРИИ ПРИЕМКИ
Структура
□ Все мертвые файлы удалены (13 файлов)
□ Все дубликаты удалены (5 файлов)
□ shared/config_loader.py создан
□ shared/state_manager.py создан
□ shared/logging.py создан
□ shared/event_schema.py подключен ко всем компонентам
Конфигурация
□ Все компоненты используют shared/config_loader.py
□ Все компоненты используют shared/state_manager.py
□ Все компоненты используют shared/logging.py
□ audit-agent/config_loader.py удален
□ audit-agent-linux/config_loader.py удален
□ scanner/src/config_loader.py удален
□ webui/config.py удален
Состояние
□ audit-agent/data/state.json создан (с agent_id)
□ audit-agent-linux/data/state.json создан (с agent_id)
□ scanner/data/state.json создан (с scanner_id)
□ state.json (корень) удален
□ buffer/ (корень) перемещен в audit-agent/data/buffer/
Единообразие
□ Все компоненты имеют структуру src/, config/, data/, logs/, scripts/
□ Все компоненты имеют scripts/start.sh, scripts/stop.sh, scripts/status.sh, scripts/restart.sh
□ Все компоненты имеют config/config.json и config/config.json.example
□ .gitignore обновлен
Функциональность
□ Windows-агент запускается и работает с новой структурой
□ Linux-агент запускается и работает с новой структурой
□ Сканер запускается и работает с новой структурой
□ Manager запускается и работает с новой структурой
□ WebUI запускается и работает с новой структурой
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Проверка удаления мертвого кода
find . -name "test_source.py" -o -name "dispatcher.py" -o -name "scheduler.py"
# Должно быть пусто

# 2. Проверка структуры
ls -la audit-agent/data/state/    # должно существовать
ls -la audit-agent-linux/data/state/  # должно существовать
ls -la scanner/data/state/        # должно существовать

# 3. Проверка Windows-агента
cd audit-agent
python -m src.main --config config/config.json
# Должен зарегистрироваться, сохранить agent_id в data/state/agent_id.json

# 4. Проверка Linux-агента
cd audit-agent-linux
python -m src.main --config config/config.json
# Должен зарегистрироваться, сохранить agent_id в data/state/agent_id.json

# 5. Проверка сканера
cd scanner
python -m src.managed_scanner --config config/config.json
# Должен зарегистрироваться, сохранить scanner_id в data/state/scanner_id.json

# 6. Проверка скриптов
cd audit-agent
./scripts/start.sh --daemon
./scripts/status.sh
./scripts/stop.sh
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_29_standardization
git add .
git commit -m "feat: День 29 — Стандартизация структуры компонентов

- Удален мертвый код (13 файлов)
- Удалены дубликаты и легаси (5 файлов)
- Создан shared/config_loader.py — единая загрузка конфигов
- Создан shared/state_manager.py — единое управление состоянием
- Создан shared/logging.py — единая настройка логирования
- Подключен shared/event_schema.py (UnifiedEvent) ко всем компонентам
- Все компоненты приведены к единой структуре: src/, config/, data/, logs/, scripts/
- Созданы единые скрипты запуска: start.sh, stop.sh, status.sh, restart.sh
- audit-agent: сохранение agent_id в state.json
- audit-agent-linux: сохранение agent_id в state.json
- scanner: сохранение scanner_id в state.json"