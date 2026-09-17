# fix_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("manager/src/db/dcap.db")

def fix_database():
    """Исправление данных в БД"""
    if not DB_PATH.exists():
        print(f"[ERROR] БД не найдена: {DB_PATH}")
        return False
    
    print(f"[X] Исправление БД: {DB_PATH}")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id, path, type FROM resources')
        resources = cursor.fetchall()
        print(f"\n[X] Текущие ресурсы ({len(resources)}):")
        for row in resources:
            print(f'   ID={row[0]}, path={row[1]}, type={row[2]}')
        
        cursor.execute('UPDATE resources SET type = "FILESYSTEM" WHERE type = "filesystem" OR type = "FILESYSTEM"')
        updated = cursor.rowcount
        print(f'\n  [OK] Обновлено ресурсов: {updated}')
        
        cursor.execute('SELECT id, path, type FROM resources')
        print('\n[X] Ресурсы после исправления:')
        for row in cursor.fetchall():
            print(f'   ID={row[0]}, path={row[1]}, type={row[2]}')
        
        cursor.execute('SELECT id, resource_id, status FROM scan_tasks')
        tasks = cursor.fetchall()
        print(f'\n[X] Задания ({len(tasks)}):')
        for row in tasks:
            print(f'   ID={row[0]}, resource_id={row[1]}, status={row[2]}')
        
        cursor.execute('SELECT id, name, status FROM scanners')
        scanners = cursor.fetchall()
        print(f'\n[X] Сканеры ({len(scanners)}):')
        for row in scanners:
            print(f'   ID={row[0]}, name={row[1]}, status={row[2]}')
        
        conn.commit()
        print("\n" + "=" * 60)
        print("[OK] БД успешно исправлена!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database()