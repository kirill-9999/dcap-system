#!/usr/bin/env python3
"""Запуск Manager DCAP (manager.src.main:app).

Порт/хост читаются из manager/config/config.json (секция server).
"""
import sys
import json
import uvicorn
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "manager" / "config" / "config.json"


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    server = data.get("server", {})
    return server.get("host", "127.0.0.1"), server.get("port", 8000)


if __name__ == "__main__":
    host, port = load_config()
    uvicorn.run(
        "manager.src.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
