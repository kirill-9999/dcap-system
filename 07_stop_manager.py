#!/usr/bin/env python3
"""Шаг 7: Остановка Manager"""

import subprocess
import time

print("🛑 ОСТАНОВКА MANAGER")
print("=" * 40)

# Находим процесс на порту 8000
result = subprocess.run(
    'netstat -ano | findstr :8000',
    shell=True,
    capture_output=True,
    text=True
)

pids = set()
for line in result.stdout.split('\n'):
    if 'LISTENING' in line:
        parts = line.split()
        if len(parts) >= 5:
            pid = parts[-1]
            if pid.isdigit():
                pids.add(int(pid))

if pids:
    for pid in pids:
        try:
            subprocess.run(f'taskkill /PID {pid} /F', shell=True)
            print(f"   ✅ Процесс {pid} остановлен")
        except:
            print(f"   ❌ Не удалось остановить процесс {pid}")
else:
    print("   ⏭️ Процесс не найден")

# Останавливаем все python процессы с dcap
result = subprocess.run(
    'tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH',
    shell=True,
    capture_output=True,
    text=True
)

for line in result.stdout.split('\n'):
    if 'python.exe' in line and 'dcap' in line.lower():
        parts = line.split(',')
        if len(parts) >= 2:
            pid = parts[1].strip('"')
            try:
                subprocess.run(f'taskkill /PID {pid} /F', shell=True)
                print(f"   ✅ Процесс {pid} остановлен")
            except:
                pass

print("\n✅ Manager остановлен")