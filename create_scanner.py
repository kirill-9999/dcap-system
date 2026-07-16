import sqlite3 
conn = sqlite3.connect('manager/src/db/dcap.db') 
cursor = conn.cursor() 
cursor.execute('INSERT OR IGNORE INTO scanners (id, name, status, scan_interval) VALUES (1, "scanner-1", "idle", 10)') 
conn.commit() 
print('? Scanner created') 
conn.close() 
