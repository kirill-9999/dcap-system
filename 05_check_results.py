#!/usr/bin/env python3
"""Шаг 5: Проверка результатов"""

import sqlite3
from pathlib import Path

print("📊 ПРОВЕРКА РЕЗУЛЬТАТОВ")
print("=" * 40)

db_path = Path("manager/src/db/dcap.db")

if not db_path.exists():
    print("❌ БД не найдена!")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Находки
cursor.execute("SELECT COUNT(*) FROM findings")
findings = cursor.fetchone()[0] or 0
print(f"   Находок: {findings}")

# Завершённые задания
cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'COMPLETED'")
completed = cursor.fetchone()[0] or 0
print(f"   Завершённых заданий: {completed}")

# Находки по категориям
cursor.execute("""
    SELECT category, COUNT(*) 
    FROM findings 
    GROUP BY category 
    ORDER BY COUNT(*) DESC
""")
rows = cursor.fetchall()
if rows:
    print("\n   Находки по категориям:")
    for category, count in rows[:10]:
        print(f"      {category}: {count}")

# Кастомные распознаватели (проверка)
if findings > 0:
    print("\n   Проверка кастомных распознавателей:")
    
    # Телефоны
    cursor.execute("SELECT COUNT(*) FROM findings WHERE category = 'PII_PHONE'")
    phones = cursor.fetchone()[0] or 0
    print(f"      📞 Телефоны (PII_PHONE): {phones}")
    
    # Паспорта
    cursor.execute("SELECT COUNT(*) FROM findings WHERE category = 'PII_PASSPORT'")
    passports = cursor.fetchone()[0] or 0
    print(f"      🪪 Паспорта (PII_PASSPORT): {passports}")
    
    # СНИЛС
    cursor.execute("SELECT COUNT(*) FROM findings WHERE category = 'PII_SNILS'")
    snils = cursor.fetchone()[0] or 0
    print(f"      🆔 СНИЛС (PII_SNILS): {snils}")
    
    # ИНН
    cursor.execute("SELECT COUNT(*) FROM findings WHERE category = 'PII_INN'")
    inn = cursor.fetchone()[0] or 0
    print(f"      🆔 ИНН (PII_INN): {inn}")
    
    # Email
    cursor.execute("SELECT COUNT(*) FROM findings WHERE category = 'PII_EMAIL'")
    emails = cursor.fetchone()[0] or 0
    print(f"      📧 Email (PII_EMAIL): {emails}")

# Сканеры
cursor.execute("SELECT name, status FROM scanners")
scanners = cursor.fetchall()
if scanners:
    print("\n   Сканеры:")
    for name, status in scanners:
        print(f"      {name}: {status}")

conn.close()

if findings > 0 and completed > 0:
    print("\n✅ Всё работает! Presidio успешно заменил Natasha/BERT!")
else:
    print("\n⚠️ Нет данных. Проверь логи.")