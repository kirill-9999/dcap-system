📋 ТЗ: ВИДИМОСТЬ АГЕНТОВ АУДИТА НА ДАШБОРДЕ (ДЕНЬ 19.6)
Файл: prompts/tz/day_19.6_audit_agents_dashboard.md

🎯 ЦЕЛЬ
Добавить видимость агентов аудита в WebUI:

Блок на дашборде с количеством агентов (онлайн/офлайн/ошибка)

Расширить вкладку «Сканеры» до «Сканеры и агенты» (или создать отдельную вкладку)

Таблица со списком всех агентов аудита и их статусом

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Изменить:
text
webui/main.py                 # Добавить блок на дашборде, расширить вкладку «Сканеры»
webui/api/routes.py           # Добавить GET /api/audit/agents
📋 ДЕТАЛЬНОЕ ТЗ
1. API для агентов аудита (webui/api/routes.py)
Добавить эндпоинт:

python
@router.get("/api/audit/agents")
def get_audit_agents(db: Session = Depends(get_db)):
    """
    Получить список всех агентов аудита с их статусом
    """
    from manager.src.db.models import AuditAgent

    agents = db.query(AuditAgent).all()

    total = len(agents)
    online = sum(1 for a in agents if a.status == "online")
    offline = sum(1 for a in agents if a.status == "offline")
    error = sum(1 for a in agents if a.status == "error")

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "error": error,
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "hostname": a.hostname,
                "status": a.status,
                "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                "events_sent": a.events_sent,
                "registered_at": a.registered_at.isoformat() if a.registered_at else None,
                "version": a.version,
            }
            for a in agents
        ]
    }
2. Дашборд — добавить блок «Агенты аудита»
В webui/main.py, в секции дашборда, добавить новый блок:

html
<!-- Блок: Агенты аудита -->
<div class="dashboard-card">
    <div class="card-icon">🤖</div>
    <div class="card-value" id="dashboard-audit-agents">0</div>
    <div class="card-label">Агентов аудита</div>
    <div class="card-sub">
        <span id="dashboard-audit-online">0</span> онлайн,
        <span id="dashboard-audit-offline">0</span> офлайн
        <span id="dashboard-audit-error" style="color:#dc3545;display:none;">
            , <span id="dashboard-audit-error-count">0</span> ошибка
        </span>
    </div>
</div>
3. Вкладка «Сканеры» → «Сканеры и агенты»
Обновить навигацию:

html
<a href="#scanners" class="nav-link" data-page="scanners">🤖 Сканеры и агенты</a>
В секции вкладки #scanners-page добавить блок «Агенты аудита»:

html
<!-- Вкладка: Сканеры и агенты -->
<div id="scanners-page" class="page">
    <div class="page-header">
        <h1>🤖 Сканеры и агенты аудита</h1>
    </div>

    <!-- Сканеры (существующие) -->
    <h2>📡 Сканеры</h2>
    <div id="scanners-list">
        <!-- таблица сканеров -->
    </div>

    <!-- Агенты аудита (НОВЫЕ) -->
    <h2>📋 Агенты аудита</h2>
    <div id="audit-agents-container">
        <div class="agents-stats">
            <span>Всего: <strong id="agents-total">0</strong></span>
            <span>🟢 Онлайн: <strong id="agents-online">0</strong></span>
            <span>🔴 Офлайн: <strong id="agents-offline">0</strong></span>
            <span>🔴 Ошибка: <strong id="agents-error">0</strong></span>
        </div>
        <table class="agents-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Имя</th>
                    <th>Хост</th>
                    <th>Статус</th>
                    <th>Событий</th>
                    <th>Версия</th>
                    <th>Последний heartbeat</th>
                    <th>Зарегистрирован</th>
                </tr>
            </thead>
            <tbody id="audit-agents-table-body">
                <tr><td colspan="8" class="text-center">Загрузка...</td></tr>
            </tbody>
        </table>
    </div>
</div>
4. JavaScript функции (webui/main.py, инлайн-секция)
Добавить в существующую JS-секцию:

javascript
// ==================== АГЕНТЫ АУДИТА ====================

async function loadAuditAgents() {
    try {
        const response = await fetch('/api/audit/agents');
        const data = await response.json();
        renderAuditAgentsDashboard(data);
        renderAuditAgentsTable(data);
        return data;
    } catch (e) {
        console.error('Ошибка загрузки агентов аудита:', e);
    }
}

function renderAuditAgentsDashboard(data) {
    const total = data.total || 0;
    const online = data.online || 0;
    const offline = data.offline || 0;
    const error = data.error || 0;

    document.getElementById('dashboard-audit-agents').textContent = total;
    document.getElementById('dashboard-audit-online').textContent = online;
    document.getElementById('dashboard-audit-offline').textContent = offline;

    const errorEl = document.getElementById('dashboard-audit-error');
    const errorCountEl = document.getElementById('dashboard-audit-error-count');
    if (error > 0) {
        errorEl.style.display = 'inline';
        errorCountEl.textContent = error;
    } else {
        errorEl.style.display = 'none';
    }

    // Обновить статистику на странице агентов
    document.getElementById('agents-total').textContent = total;
    document.getElementById('agents-online').textContent = online;
    document.getElementById('agents-offline').textContent = offline;
    document.getElementById('agents-error').textContent = error;
}

function renderAuditAgentsTable(data) {
    const tbody = document.getElementById('audit-agents-table-body');
    const agents = data.agents || [];

    if (agents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">Нет зарегистрированных агентов аудита</td></tr>';
        return;
    }

    let html = '';
    for (const agent of agents) {
        const statusClass = agent.status === 'online' ? 'status-online' :
                            agent.status === 'error' ? 'status-error' :
                            'status-offline';
        const statusIcon = agent.status === 'online' ? '🟢' :
                           agent.status === 'error' ? '🔴' : '🔴';
        const lastHeartbeat = agent.last_heartbeat ? new Date(agent.last_heartbeat).toLocaleString() : '—';
        const registeredAt = agent.registered_at ? new Date(agent.registered_at).toLocaleString() : '—';

        html += `
            <tr>
                <td>${agent.id}</td>
                <td><strong>${escapeHtml(agent.name)}</strong></td>
                <td>${escapeHtml(agent.hostname)}</td>
                <td><span class="status-badge ${statusClass}">${statusIcon} ${agent.status}</span></td>
                <td>${agent.events_sent || 0}</td>
                <td>${agent.version || '—'}</td>
                <td>${lastHeartbeat}</td>
                <td>${registeredAt}</td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

// Обновить функцию loadDashboardStats() — добавить loadAuditAgents()
async function loadDashboardStats() {
    // ... существующий код (resources, findings, tasks) ...
    await loadAuditAgents();
}
5. Стили (webui/main.py, инлайн-секция)
Добавить в секцию стилей:

css
/* ==================== АГЕНТЫ АУДИТА ==================== */

.agents-stats {
    display: flex;
    gap: 20px;
    padding: 12px 0;
    flex-wrap: wrap;
}

.agents-stats span {
    font-size: 0.95em;
    color: #495057;
}

.agents-stats strong {
    color: #2c3e50;
}

.agents-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
}

.agents-table th {
    background: #f8f9fa;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 2px solid #dee2e6;
}

.agents-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #eee;
}

.agents-table tr:hover td {
    background: #f5f7fa;
}

.status-badge {
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 500;
}

.status-online {
    background: #d4edda;
    color: #155724;
}

.status-offline {
    background: #f8d7da;
    color: #721c24;
}

.status-error {
    background: #f8d7da;
    color: #721c24;
}
✅ КРИТЕРИИ ПРИЕМКИ
□ API /api/audit/agents возвращает список агентов с их статусом
□ На дашборде появился блок «Агенты аудита» с количеством
□ В блоке отображается: всего, онлайн, офлайн
□ Вкладка «Сканеры» переименована в «Сканеры и агенты»
□ В вкладке отображается таблица со всеми агентами
□ В таблице указаны: ID, имя, хост, статус, события, версия, последний heartbeat, регистрация
□ Данные загружаются при открытии дашборда и вкладки
□ При ошибках отображается понятное сообщение
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Открыть http://localhost:8001
# Проверить дашборд — блок «Агенты аудита»

# 4. Перейти на вкладку «🤖 Сканеры и агенты»
# Проверить таблицу агентов аудита

# 5. Если нет агентов — добавить тестового через API (см. День 16)
curl -X POST http://localhost:8000/api/audit/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name":"test-agent","hostname":"TEST-PC"}'

# 6. Обновить страницу — агент должен появиться
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
webui/
├── main.py                 # ✅ + блок агентов на дашборде, вкладка «Сканеры и агенты»
├── api/routes.py           # ✅ + GET /api/audit/agents
└── static/vendor/          # ✅ (без изменений)
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_19.6_audit_agents_dashboard
git add webui/
git commit -m "feat: День 19.6 — видимость агентов аудита на дашборде и вкладке «Сканеры и агенты»"
Разработчик (кодер), приступай! 🚀