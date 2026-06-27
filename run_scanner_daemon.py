#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_scanner_daemon.py - Запуск Scanner как демона (Linux) или фонового процесса (Windows)
"""

import sys
import os
import subprocess
import time
import signal
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def run_daemon():
    """Запуск как демона"""
    if sys.platform == "win32":
        # Windows: запуск в фоновом окне
        subprocess.Popen(
            ["python", str(PROJECT_ROOT / "run_scanner.py")],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✅ Scanner запущен в фоновом режиме")
    else:
        # Linux: запуск через nohup
        log_file = PROJECT_ROOT / "data" / "logs" / "scanner_daemon.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        subprocess.Popen(
            ["nohup", "python", str(PROJECT_ROOT / "run_scanner.py"), "&"],
            stdout=open(log_file, 'a'),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid
        )
        print(f"✅ Scanner запущен в фоновом режиме")
        print(f"   Лог: {log_file}")


def stop_daemon():
    """Остановка демона"""
    if sys.platform == "win32":
        os.system("taskkill /F /IM python.exe /FI \"WINDOWTITLE eq DCAP Scanner*\"")
    else:
        os.system("pkill -f run_scanner.py")
    print("✅ Scanner остановлен")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_daemon()
    else:
        run_daemon()