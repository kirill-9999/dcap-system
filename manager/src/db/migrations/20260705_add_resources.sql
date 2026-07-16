-- Добавить таблицу resources
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path VARCHAR(500) UNIQUE NOT NULL,
    type VARCHAR(50) DEFAULT 'filesystem',
    status VARCHAR(50) DEFAULT 'active',
    last_scan DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Добавить колонку resource_id в scan_tasks
ALTER TABLE scan_tasks ADD COLUMN resource_id INTEGER REFERENCES resources(id);

-- Создать индексы
CREATE INDEX idx_resources_path ON resources(path);
CREATE INDEX idx_scan_tasks_resource_id ON scan_tasks(resource_id);