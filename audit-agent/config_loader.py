"""Загрузка конфигурации агента из JSON-файла с дефолтами."""

import json
import logging
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: Path) -> Dict[str, Any]:
    """Загрузка конфигурации из JSON-файла"""
    if not config_path.exists():
        raise FileNotFoundError(f"Конфиг не найден: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Значения по умолчанию
    defaults = {
        "manager_url": "http://localhost:8000",
        "agent_name": "audit-agent-01",
        "hostname": "localhost",
        "read_interval": 60,
        "batch_size": 100,
        "buffer_size": 10000,
        "heartbeat_interval": 30,
        "event_filters": [4656, 4660, 4663, 4670, 5140, 5145],
        "paths": [],
        "log_level": "INFO",
        "service": {
            "display_name": "DCAP Audit Agent",
            "description": "Сбор событий файловой системы для DCAP",
            "log_file": "logs/audit_agent.log",
            "max_log_size_mb": 100,
            "restart_on_failure": True,
            "restart_interval_sec": 60
        }
    }

    # Рекурсивное заполнение
    def merge_defaults(target, source):
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target.get(key), dict):
                merge_defaults(target[key], value)

    merge_defaults(config, defaults)
    return config
