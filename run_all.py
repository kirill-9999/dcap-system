#!/usr/bin/env python3
# run_all.py — Единый запуск Manager + WebUI
#
# Читает порты из manager/config/config.json и webui/config/config.json,
# стартует оба процесса (run_manager.py и run_webui.py) и следит за ними.
# При падении одного процесса останавливает второй. Ctrl+C — graceful shutdown.

import subprocess
import sys
import time
import signal
import json
from pathlib import Path


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_manager_config():
    cfg = load_json(
        Path(__file__).parent / "manager" / "config" / "config.json",
        {"server": {"host": "127.0.0.1", "port": 8000}},
    )
    return cfg.get("server", {}).get("host", "127.0.0.1"), cfg.get("server", {}).get("port", 8000)


def load_webui_config():
    cfg = load_json(
        Path(__file__).parent / "webui" / "config" / "config.json",
        {"server": {"host": "127.0.0.1", "port": 8001}},
    )
    return cfg.get("server", {}).get("host", "127.0.0.1"), cfg.get("server", {}).get("port", 8001)


def main():
    print("=" * 60)
    print("DCAP System — запуск Manager + WebUI")
    print("=" * 60)

    manager_host, manager_port = load_manager_config()
    webui_host, webui_port = load_webui_config()

    print(f"Manager: http://{manager_host}:{manager_port}")
    print(f"WebUI:   http://{webui_host}:{webui_port}")
    print("=" * 60)

    print("Starting Manager...")
    manager_process = subprocess.Popen(
        [sys.executable, "run_manager.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    time.sleep(2)

    print("Starting WebUI...")
    webui_process = subprocess.Popen(
        [sys.executable, "run_webui.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    print("=" * 60)
    print("DCAP System запущена!")
    print(f"Manager API: http://{manager_host}:{manager_port}")
    print(f"WebUI:       http://{webui_host}:{webui_port}")
    print("=" * 60)
    print("Нажмите Ctrl+C для остановки")
    print("=" * 60)

    def signal_handler(sig, frame):
        print("\nОстановка...")
        manager_process.terminate()
        webui_process.terminate()
        manager_process.wait()
        webui_process.wait()
        print("Все процессы остановлены")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)

            if manager_process.poll() is not None:
                print(f"Manager завершился с кодом {manager_process.returncode}")
                print("Остановка WebUI...")
                webui_process.terminate()
                webui_process.wait()
                sys.exit(1)

            if webui_process.poll() is not None:
                print(f"WebUI завершился с кодом {webui_process.returncode}")
                print("Остановка Manager...")
                manager_process.terminate()
                manager_process.wait()
                sys.exit(1)

    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
