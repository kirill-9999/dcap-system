# init_db.py

import sys
import os

# Добавляем путь к manager/src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'manager', 'src'))

from db.session import init_db

if __name__ == "__main__":
    print("🔄 Инициализация базы данных...")
    init_db()
    print("✅ База данных успешно инициализирована")
    print("📁 Создан файл: dcap.db")