# test_parse.py

import sys
import subprocess
sys.path.insert(0, 'manager/src')

from connectors.permissions.local import LocalPermissionCollector

path = r"D:\Projects\dcap-system\test_files"

# Получаем вывод icacls напрямую
result = subprocess.run(['icacls', path], capture_output=True, text=True, encoding='cp866')
print("=== RAW ICACLS OUTPUT ===")
print(result.stdout)
print("\n=== PARSED ENTRIES ===")

collector = LocalPermissionCollector()
entries = collector.collect(path)
for entry in entries:
    print(f"Principal: {entry['principal']}")
    print(f"  Permissions: {entry['permissions']}")
    print(f"  Is Inherited: {entry['is_inherited']}")
    print()