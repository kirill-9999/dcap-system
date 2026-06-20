#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запуск Managed Scanner
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.managed_scanner import ManagedScanner


async def main():
    scanner = ManagedScanner(
        name="real-scanner-1",
        manager_endpoint="localhost:50051"
    )
    
    try:
        await scanner.run()
    except KeyboardInterrupt:
        print("\n⏹️ Остановка...")
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())