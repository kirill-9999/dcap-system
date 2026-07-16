import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "dcap.db"

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def run_migration():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 1. Таблица resources
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path VARCHAR(500) UNIQUE NOT NULL,
            type VARCHAR(50) DEFAULT 'filesystem',
            status VARCHAR(50) DEFAULT 'active',
            last_scan DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Table 'resources' created (or already exists)")
    
    # 2. Колонка resource_id в scan_tasks
    if not column_exists(cursor, 'scan_tasks', 'resource_id'):
        cursor.execute("ALTER TABLE scan_tasks ADD COLUMN resource_id INTEGER REFERENCES resources(id)")
        print("✅ Column 'resource_id' added to scan_tasks")
    else:
        print("⏭️ Column 'resource_id' already exists, skipping")
    
    # 3. Индексы
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resources_path ON resources(path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_tasks_resource_id ON scan_tasks(resource_id)")
    print("✅ Indexes created")
    
    conn.commit()
    conn.close()
    print("✅ Migration completed successfully!")

if __name__ == "__main__":
    run_migration()