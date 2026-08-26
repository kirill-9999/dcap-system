📋 ТЗ: УПРАВЛЕНИЕ АГЕНТАМИ И СКАНЕРАМИ — УДАЛЕНИЕ ЧЕРЕЗ UI (ДЕНЬ 26.5)
Файл: prompts/tz/day_26.5_agent_scanner_management.md

🎯 ЦЕЛЬ
Добавить возможность удалять агентов аудита и сканеры через WebUI. Администратор должен иметь возможность очищать систему от тестовых и неиспользуемых записей без прямого доступа к БД.

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Изменить:
text
webui/main.py                    # Добавить кнопки удаления и JS-функции
webui/api/routes.py              # Добавить DELETE эндпоинты
manager/src/api/audit.py         # Добавить DELETE /api/audit/agents/{id}
manager/src/api/scanner.py       # Добавить DELETE /api/scanners/{id}
📋 ДЕТАЛЬНОЕ ТЗ
1. API для удаления сканера (manager/src/api/scanner.py)
python
@router.delete("/api/scanners/{scanner_id}")
def delete_scanner(
    scanner_id: int,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Удалить сканер по ID.

    Args:
        scanner_id: ID сканера
        force: если True — удалить даже при наличии активных заданий
    """
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, f"Scanner {scanner_id} not found")

    # Проверить активные задания
    active_tasks = db.query(models.ScanTask).filter(
        models.ScanTask.scanner_id == scanner_id,
        models.ScanTask.status.in_(["pending", "in_progress", "assigned"])
    ).first()

    if active_tasks and not force:
        raise HTTPException(
            409,
            f"Scanner {scanner_id} has active task {active_tasks.id}. "
            "Use force=true to delete anyway."
        )

    # Освободить задания (если force)
    if force:
        db.query(models.ScanTask).filter(
            models.ScanTask.scanner_id == scanner_id,
            models.ScanTask.status.in_(["in_progress", "assigned"])
        ).update({"scanner_id": None, "status": "pending"})

    db.delete(scanner)
    db.commit()

    return {"status": "deleted", "scanner_id": scanner_id}
2. API для удаления агента аудита (manager/src/api/audit.py)
python
@router.delete("/api/audit/agents/{agent_id}")
def delete_audit_agent(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить агент аудита по ID.
    Связанные события остаются в БД (agent_id становится NULL).
    """
    agent = db.query(AuditAgent).filter(AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    # Отвязать события от агента
    db.query(AuditLog).filter(AuditLog.agent_id == agent_id).update(
        {"agent_id": None}
    )

    db.delete(agent)
    db.commit()

    return {"status": "deleted", "agent_id": agent_id}
3. API для WebUI (webui/api/routes.py)
Проксировать DELETE-запросы к Manager:

python
import requests

@router.delete("/api/scanners/{scanner_id}")
def delete_scanner_via_manager(scanner_id: int):
    """Прокси-запрос для удаления сканера"""
    response = requests.delete(
        f"{MANAGER_URL}/api/scanners/{scanner_id}"
    )
    return response.json()

@router.delete("/api/audit/agents/{agent_id}")
def delete_audit_agent_via_manager(agent_id: int):
    """Прокси-запрос для удаления агента аудита"""
    response = requests.delete(
        f"{MANAGER_URL}/api/audit/agents/{agent_id}"
    )
    return response.json()
4. WebUI — вкладка «Сканеры и агенты» (webui/main.py)
4.1. Добавить кнопки удаления в таблицу сканеров
html
<td>
    <button class="btn btn-sm btn-danger" onclick="deleteScanner(${scanner.id})">
        🗑️
    </button>
</td>
4.2. Добавить кнопки удаления в таблицу агентов
html
<td>
    <button class="btn btn-sm btn-danger" onclick="deleteAuditAgent(${agent.id})">
        🗑️
    </button>
</td>
5. JavaScript функции (webui/main.py)
javascript
// ==================== УПРАВЛЕНИЕ СКАНЕРАМИ ====================

async function deleteScanner(id) {
    if (!confirm(`Удалить сканер ${id}? Это действие необратимо.`)) return;

    try {
        const response = await fetch(`/api/scanners/${id}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('✅ Сканер удален', 'success');
            loadScanners();
        } else {
            const error = await response.json();
            showToast(`❌ ${error.detail || 'Ошибка удаления'}`, 'error');
        }
    } catch (e) {
        showToast('❌ Ошибка удаления', 'error');
    }
}

// ==================== УПРАВЛЕНИЕ АГЕНТАМИ ====================

async function deleteAuditAgent(id) {
    if (!confirm(`Удалить агент аудита ${id}? Это действие необратимо.`)) return;

    try {
        const response = await fetch(`/api/audit/agents/${id}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('✅ Агент удален', 'success');
            loadAuditAgents();
        } else {
            const error = await response.json();
            showToast(`❌ ${error.detail || 'Ошибка удаления'}`, 'error');
        }
    } catch (e) {
        showToast('❌ Ошибка удаления', 'error');
    }
}
6. Стили для кнопок (webui/main.py)
css
.btn-danger {
    background: #dc3545;
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

.btn-danger:hover {
    background: #c82333;
}
✅ КРИТЕРИИ ПРИЕМКИ
□ В таблице сканеров появилась кнопка удаления (🗑️)
□ В таблице агентов появилась кнопка удаления (🗑️)
□ При нажатии появляется подтверждение
□ Удаление сканера работает
□ Удаление агента работает
□ Активные задания блокируют удаление сканера (если не force)
□ Связанные события не теряются при удалении агента
□ Тосты об успехе/ошибке работают
□ Таблицы обновляются после удаления
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Открыть http://localhost:8001 → "Сканеры и агенты"

# 4. Найти тестового агента (например, "test-reg-agent") и нажать 🗑️
# Должно появиться подтверждение, после удаления агент исчезает из таблицы

# 5. Найти тестовый сканер и нажать 🗑️
# Должно появиться подтверждение, после удаления сканер исчезает из таблицы

# 6. Проверить, что события от удаленного агента сохранились
# Перейти в "Аудит" — события должны быть, но без агента
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_26.5_agent_scanner_management
git add webui/main.py webui/api/routes.py manager/src/api/audit.py manager/src/api/scanner.py
git commit -m "feat: День 26.5 — управление агентами и сканерами (удаление через UI)"
Разработчик (кодер), приступай! 🚀