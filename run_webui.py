#!/usr/bin/env python3
"""Запуск WebUI DCAP (webui.main:app).

Порт/хост читаются из webui/config/config.json (секция server).
"""
import sys
import json
import uvicorn
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "webui" / "config" / "config.json"


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    server = data.get("server", {})
    return server.get("host", "127.0.0.1"), server.get("port", 8001)


if __name__ == "__main__":
    host, port = load_config()
    uvicorn.run(
        "webui.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
