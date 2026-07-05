#!/usr/bin/env python3
"""Шаг 4: Запуск Scanner"""

import subprocess
import time

print("🔍 ЗАПУСК SCANNER")
print("=" * 40)

print("   Запуск Scanner...")
print("   Сканирование займёт 1-3 минуты")
print("   Дождись сообщения '✅ Сканирование завершено!'")
print("=" * 40)

subprocess.run(["python", "run_scanner.py"])

print("\n✅ Scanner завершил работу!")
print("   Переходи к ШАГУ 5: проверка результатов")