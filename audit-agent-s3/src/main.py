# audit-agent-s3/src/main.py
import sys
import argparse
import signal
import time
import logging
import socket
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Добавляем корень проекта для импорта shared/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config_loader import ConfigLoader
from .collector import S3LogCollector
from .buffer import BufferManager
from .sender import Sender
from .heartbeat import HeartbeatThread
from .state import StateManager

VERSION = "3.0.0"
logger = None


def setup_logging(config: dict):
    """Настройка логирования с ротацией файла."""
    global logger

    log_level = config.get("logging", {}).get("level", "INFO")
    log_format = config.get("logging", {}).get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    log_file = config.get("logging", {}).get("file", "logs/s3_agent.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, str(log_level).upper(), logging.INFO))

    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        max_bytes = int(config.get("logging", {}).get("max_bytes", 10 * 1024 * 1024))
        backup_count = int(config.get("logging", {}).get("backup_count", 5))
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handlers.append(file_handler)
    except Exception as e:
        logger.warning(f"Cannot create file handler: {e}")

    formatter = logging.Formatter(log_format)
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger = logging.getLogger(__name__)


def print_status(state: StateManager, buffer: BufferManager, collector: S3LogCollector):
    """Вывод статуса агента."""
    if logger is None:
        return
    logger.info("=" * 60)
    logger.info(f"Agent ID: {state.get_agent_id()}")
    logger.info(f"Last processed: {state.get_last_processed()}")
    logger.info(f"Buffer stats: {buffer.get_stats()}")
    logger.info(f"Collector: bucket={collector.bucket}, prefix={collector.prefix}")
    logger.info("=" * 60)


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser(description="S3/MinIO Audit Agent")
    parser.add_argument(
        "--config", "-c", default="config/config.json",
        help="Path to config file",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run once and exit",
    )
    args = parser.parse_args()

    config_loader = ConfigLoader(args.config)
    config = config_loader.load()

    setup_logging(config)

    logger.info("=" * 60)
    logger.info(f"S3/MinIO Audit Agent v{VERSION}")
    logger.info(f"Config: {args.config}")
    logger.info("=" * 60)

    state = StateManager(state_dir=config.get("state_dir", "data/state"))
    collector = S3LogCollector(config)
    buffer = BufferManager(config["buffer"])
    sender = Sender(config)

    # Регистрация агента
    agent_id = state.get_agent_id()
    if agent_id:
        logger.info(f"Using existing agent_id: {agent_id}")
        sender.agent_id = agent_id
    else:
        agent_data = {
            "name": config["agent"]["name"],
            "hostname": config["agent"].get("hostname", socket.gethostname()),
            "version": config["agent"].get("version", VERSION),
            "source_type": "s3",
        }
        result = sender.register_agent(agent_data)
        if result and sender.agent_id is not None:
            state.set_agent_id(sender.agent_id)
            logger.info(f"Registered with agent_id: {sender.agent_id}")
        else:
            logger.error("Registration failed, exiting...")
            sys.exit(1)

    # Heartbeat в отдельном потоке
    heartbeat_interval = int(config.get("heartbeat", {}).get("interval", 30))
    heartbeat = HeartbeatThread(sender, heartbeat_interval)
    heartbeat.start()

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Received shutdown signal...")
        running = False
        heartbeat.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Agent started, entering main loop...")
    print_status(state, buffer, collector)

    # Параметры экспоненциальной задержки при ошибках
    error_delay = 1
    max_error_delay = int(config.get("main", {}).get("max_error_delay", 300))  # 5 минут

    while running:
        try:
            # 1. Сбор событий
            events = collector.poll()
            if events:
                logger.info(f"Collected {len(events)} events")
                error_delay = 1  # Сброс задержки при успехе

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
                    error_delay = 1  # Сброс при успехе
                else:
                    logger.warning(
                        f"Failed to send {len(event_ids)} events, will retry"
                    )
                    # Задержка при неудаче отправки
                    error_delay = min(error_delay * 2, max_error_delay)

            # 4. Очистка старых событий
            buffer.cleanup_old_events()

            if args.once:
                logger.info("Run once mode, exiting...")
                break

            # 5. Ожидание с учётом экспоненциальной задержки
            delay = int(config["s3"].get("poll_interval", 60))
            if error_delay > 1:
                delay = min(delay, error_delay)
                logger.info(f"Backoff active, next poll in {delay}s")

            time.sleep(delay)

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            error_delay = min(error_delay * 2, max_error_delay)
            time.sleep(error_delay)

    # Graceful shutdown
    logger.info("Shutting down...")
    heartbeat.stop()

    unsent = buffer.get_unsent()
    if unsent:
        event_ids = [e[0] for e in unsent]
        events_to_send = [e[1] for e in unsent]
        if sender.send_events_batch(events_to_send):
            buffer.mark_sent(event_ids)
            logger.info(f"Sent {len(event_ids)} events during shutdown")
        else:
            logger.warning(f"Failed to send {len(event_ids)} events during shutdown")

    sender.send_heartbeat(status="offline")

    buffer.close()
    logger.info("S3 Agent stopped")


if __name__ == "__main__":
    main()
