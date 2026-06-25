#!/usr/bin/env python3
"""Шаг 1: Очистка"""

import shutil
from pathlib import Path

print("🧹 ОЧИСТКА")
print("=" * 40)

files_to_delete = [
    Path("state.json"),
    Path("manager/src/db/dcap.db"),
    Path("scanner_data"),
    Path("logs"),
    Path("catalog")
]

for item in files_to_delete:
    if item.exists():
        try:
            if item.is_dir():
                shutil.rmtree(item)
                print(f"   ✅ {item} удалён")
            else:
                item.unlink()
                print(f"   ✅ {item} удалён")
        except Exception as e:
            print(f"   ⚠️ Не удалось удалить {item}: {e}")
    else:
        print(f"   ⏭️ {item} не найден")

print("\n✅ Очистка завершена")