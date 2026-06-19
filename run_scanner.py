#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запуск Managed Scanner
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.managed_scanner import main

if __name__ == "__main__":
    asyncio.run(main())