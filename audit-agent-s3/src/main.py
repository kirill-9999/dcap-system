# audit-agent-s3/src/main.py
import sys
import argparse
import signal
import time
import logging
import socket
from pathlib import Path

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
    """Настройка логирования."""
    global logger

    log_level = config.get("logging", {}).get("level", "INFO")
    log_format = config.get("logging", {}).get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    log_file = config.get("logging", {}).get("file", "logs/s3_agent.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except Exception as e:
        logging.warning(f"Cannot create file handler: {e}")

    logging.basicConfig(
        level=getattr(logging, str(log_level).upper(), logging.INFO),
        format=log_format,
        handlers=handlers,
    )

    logger = logging.getLogger(__name__)


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

    while running:
        try:
            events = collector.poll()
            if events:
                logger.info(f"Collected {len(events)} events")

            for event in events:
                buffer.store_event(event)

            unsent = buffer.get_unsent()
            if unsent:
                event_ids = [e[0] for e in unsent]
                events_to_send = [e[1] for e in unsent]

                if sender.send_events_batch(events_to_send):
                    buffer.mark_sent(event_ids)
                    logger.info(f"Sent {len(event_ids)} events")
                else:
                    logger.warning(f"Failed to send {len(event_ids)} events, will retry")

            buffer.cleanup_old_events()

            if args.once:
                logger.info("Run once mode, exiting...")
                break

            time.sleep(int(config["s3"].get("poll_interval", 60)))

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(5)

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
