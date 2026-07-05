#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_scanner.py - Запуск Scanner в непрерывном режиме
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.managed_scanner import ManagedScanner


async def main():
    scanner = ManagedScanner(
        name="scanner-1",
        manager_endpoint="localhost:50051"
    )
    
    try:
        await scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n⏹️ Остановка...")
        await scanner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Прервано")