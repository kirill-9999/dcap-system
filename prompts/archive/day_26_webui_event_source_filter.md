📋 ТЗ: WEBUI — ФИЛЬТР ПО ИСТОЧНИКУ СОБЫТИЙ (ДЕНЬ 26)
Файл: prompts/tz/day_26_webui_event_source_filter.md

🎯 ЦЕЛЬ
Добавить в WebUI (страница «Аудит») фильтр по источнику событий (event_source). Пользователь должен иметь возможность просматривать события только от Windows-агентов, только от Linux-агентов или от всех источников вместе.

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Изменить:
text
webui/main.py                 # Добавить фильтр в HTML и JS
webui/api/routes.py           # Добавить поддержку фильтра в API
📋 ДЕТАЛЬНОЕ ТЗ
1. Обновить фильтры на странице аудита (webui/main.py)
Добавить новый фильтр в блок фильтров:

html
<div class="filter-group">
    <label>💻 Источник:</label>
    <select id="audit-source-filter" class="form-select">
        <option value="">Все источники</option>
        <option value="windows_agent">🪟 Windows Agent</option>
        <option value="linux_agent">🐧 Linux Agent</option>
        <option value="scanner">📡 Scanner</option>
        <option value="api">🔌 API</option>
    </select>
</div>
2. Обновить JavaScript функцию loadAuditEvents() (webui/main.py)
Добавить параметр event_source в запрос:

javascript
async function loadAuditEvents() {
    const days = document.getElementById('audit-days-filter').value;
    const eventType = document.getElementById('audit-type-filter').value;
    const user = document.getElementById('audit-user-filter').value;
    const filePath = document.getElementById('audit-path-filter').value;
    const eventSource = document.getElementById('audit-source-filter').value; // 🆕

    const since = new Date();
    since.setDate(since.getDate() - parseInt(days));
    const sinceStr = since.toISOString();

    const params = new URLSearchParams({
        limit: AUDIT_PAGE_SIZE,
        offset: auditCurrentPage * AUDIT_PAGE_SIZE,
        since: sinceStr
    });
    if (eventType) params.append('event_type', eventType);
    if (user) params.append('user', user);
    if (filePath) params.append('file_path', filePath);
    if (eventSource) params.append('event_source', eventSource); // 🆕

    try {
        const response = await fetch(`${AUDIT_API}?${params}`);
        const data = await response.json();
        renderAuditTable(data);
        return data;
    } catch (e) {
        console.error('Ошибка загрузки аудита:', e);
        showToast('Ошибка загрузки событий', 'error');
    }
}
3. Обновить функцию renderAuditTable() — добавить иконку источника
Добавить отображение иконки источника в таблице:

javascript
function renderAuditTable(data) {
    // ...
    for (const event of events) {
        const sourceIcon = getEventSourceIcon(event.event_source);
        // ...
        html += `
            <tr onclick="showAuditDetail(${event.id})" style="cursor:pointer;">
                <td>${time}</td>
                <td><span class="event-type-${eventType}">${typeIcon} ${eventType}</span></td>
                <td>${user}</td>
                <td class="file-path-cell" title="${filePath}">${truncatePath(filePath, 50)}</td>
                <td>${sourceIcon} ${event.event_source || '—'}</td>
                <td>${source}</td>
                <td><button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); showAuditDetail(${event.id})">📋</button></td>
            </tr>
        `;
    }
    // ...
}

function getEventSourceIcon(source) {
    const icons = {
        'windows_agent': '🪟',
        'linux_agent': '🐧',
        'scanner': '📡',
        'api': '🔌',
        'agent': '🤖'
    };
    return icons[source] || '📋';
}
4. Обновить функцию resetFilters() (webui/main.py)
Добавить сброс фильтра источника:

javascript
function resetAuditFilters() {
    document.getElementById('audit-days-filter').value = '7';
    document.getElementById('audit-type-filter').value = '';
    document.getElementById('audit-user-filter').value = '';
    document.getElementById('audit-path-filter').value = '';
    document.getElementById('audit-source-filter').value = ''; // 🆕
    auditCurrentPage = 0;
    loadAuditStats();
    loadAuditEvents();
}
5. Обновить API (webui/api/routes.py)
Добавить поддержку фильтра по event_source:

python
@router.get("/api/audit")
def get_audit_events(
    agent_id: Optional[int] = None,
    user: Optional[str] = None,
    event_type: Optional[str] = None,
    event_source: Optional[str] = None,  # 🆕
    file_path: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)

    if agent_id:
        query = query.filter(AuditLog.agent_id == agent_id)
    if user:
        query = query.filter(AuditLog.user.ilike(f"%{user}%"))
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if event_source:  # 🆕
        query = query.filter(AuditLog.event_source == event_source)
    if file_path:
        query = query.filter(AuditLog.file_path.ilike(f"%{file_path}%"))
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(AuditLog.created_at >= since_dt)
        except:
            pass

    total = query.count()
    events = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_source": e.event_source,  # 🆕
                "user": e.user,
                "file_path": e.file_path,
                "old_path": e.old_path,
                "source_host": e.source_host,
                "metadata": e.metadata,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }
6. Обновить статистику (/api/audit/stats)
Добавить статистику по источникам:

python
@router.get("/api/audit/stats")
def get_audit_stats(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)

    from sqlalchemy import func

    total = db.query(AuditLog).filter(AuditLog.created_at >= since).count()

    type_stats = db.query(
        AuditLog.event_type,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .group_by(AuditLog.event_type).all()

    user_stats = db.query(
        AuditLog.user,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .filter(AuditLog.user.isnot(None))\
     .group_by(AuditLog.user)\
     .order_by(func.count(AuditLog.id).desc())\
     .limit(10).all()

    # 🆕 Статистика по источникам
    source_stats = db.query(
        AuditLog.event_source,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .filter(AuditLog.event_source.isnot(None))\
     .group_by(AuditLog.event_source).all()

    return {
        "total": total,
        "days": days,
        "by_type": [{"type": s[0], "count": s[1]} for s in type_stats],
        "top_users": [{"user": s[0], "count": s[1]} for s in user_stats],
        "by_source": [{"source": s[0], "count": s[1]} for s in source_stats]  # 🆕
    }
7. Обновить дашборд — добавить статистику по источникам (опционально)
На дашборде можно добавить краткую статистику:

html
<div class="dashboard-card">
    <div class="card-icon">🪟</div>
    <div class="card-value" id="dashboard-events-windows">0</div>
    <div class="card-label">Windows события</div>
</div>
<div class="dashboard-card">
    <div class="card-icon">🐧</div>
    <div class="card-value" id="dashboard-events-linux">0</div>
    <div class="card-label">Linux события</div>
</div>
✅ КРИТЕРИИ ПРИЕМКИ
□ На странице «Аудит» появился фильтр «Источник»
□ Фильтр содержит: Все, Windows Agent, Linux Agent, Scanner, API
□ При выборе фильтра таблица обновляется
□ В таблице отображается иконка источника
□ API поддерживает фильтрацию по event_source
□ Статистика показывает разбивку по источникам
□ Сброс фильтров работает корректно
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Открыть http://localhost:8001 → Аудит

# 4. Проверить фильтр "Источник"
# - Выбрать "Windows Agent" → должны отображаться только события от windows_agent
# - Выбрать "Linux Agent" → должны отображаться только события от linux_agent
# - Выбрать "Все источники" → должны отображаться все события

# 5. Проверить таблицу
# - В колонке "Источник" должна быть иконка (🪟 / 🐧 / 📡 / 🔌)

# 6. Проверить статистику
# - На дашборде должны быть карточки "Windows события" и "Linux события"
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_26_webui_event_source_filter
git add webui/main.py webui/api/routes.py
git commit -m "feat: День 26 — WebUI фильтр по источнику событий (event_source)"
Разработчик (кодер), приступай! 🚀