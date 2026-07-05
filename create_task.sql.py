import sqlite3

conn = sqlite3.connect('manager/src/db/dcap.db')
c = conn.cursor()

c.execute("DELETE FROM catalog_entries")
c.execute("DELETE FROM findings")
c.execute("DELETE FROM scan_tasks")

path = r'D:\Projects\dcap-system\test_files'
c.execute("SELECT id FROM resources WHERE path=?", (path,))
row = c.fetchone()
if not row:
    c.execute("INSERT INTO resources (type,path,enabled,created_at) VALUES ('FILESYSTEM',?,1,datetime('now'))", (path,))
    rid = c.lastrowid
else:
    rid = row[0]

c.execute("INSERT INTO scan_tasks (resource_id,status,files_total,files_scanned,findings_count,created_at) VALUES (?,'PENDING',0,0,0,datetime('now'))", (rid,))
conn.commit()
conn.close()
print(f"Task created: resource_id={rid}, path={path}")
