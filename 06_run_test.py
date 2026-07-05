#!/usr/bin/env python3
"""Шаг 6: Интеграционный тест"""

import subprocess
import sys

print("🧪 ИНТЕГРАЦИОННЫЙ ТЕСТ")
print("=" * 40)

print("   Запуск test_integration_simple.py...")
print("=" * 40)

result = subprocess.run(["python", "test_integration_simple.py"])
sys.exit(result.returncode)