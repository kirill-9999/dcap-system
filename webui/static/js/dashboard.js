let auditChartInstance = null;
let findingsChartInstance = null;

async function loadDashboard() {
    try {
        const stats = await api.get('/api/audit/stats', {days: 7});
        updateKPIs(stats);
        updateCharts(stats);
    } catch(e) { console.error('Dashboard stats error:', e); }
    try {
        const data = await api.get('/api/audit', {limit: 10});
        updateRecentEvents(data.events || []);
    } catch(e) { console.error('Dashboard events error:', e); }
    try {
        const findings = await api.get('/api/findings', {limit: 10});
        updateRecentFindings(Array.isArray(findings) ? findings : []);
    } catch(e) { console.error('Dashboard findings error:', e); }
}

function updateKPIs(s) {
    const el = id => document.getElementById(id);
    if (el('kpiResources')) el('kpiResources').textContent = s.total_resources || 0;
    if (el('kpiFindings')) el('kpiFindings').textContent = s.total || 0;
    if (el('kpiAgents')) el('kpiAgents').textContent = s.agents_online || 0;
    if (el('kpiAgentsChange')) el('kpiAgentsChange').textContent = 'из ' + (s.agents_total || 0);
}

function updateCharts(s) {
    const byType = s.by_type || [];
    const labels = byType.map(t => t.type);
    const values = byType.map(t => t.count);
    const cs = getComputedStyle(document.documentElement);
    const primary = cs.getPropertyValue('--color-primary').trim();
    const danger = cs.getPropertyValue('--color-danger').trim();
    const warning = cs.getPropertyValue('--color-warning').trim();
    const info = cs.getPropertyValue('--color-info').trim();
    const success = cs.getPropertyValue('--color-success').trim();

    const ctx1 = document.getElementById('auditChart');
    if (ctx1) {
        if (auditChartInstance) auditChartInstance.destroy();
        auditChartInstance = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{ label: 'События', data: values, backgroundColor: [primary, success, danger, warning, info] }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    }

    const bySource = s.by_source || [];
    const ctx2 = document.getElementById('findingsChart');
    if (ctx2) {
        if (findingsChartInstance) findingsChartInstance.destroy();
        findingsChartInstance = new Chart(ctx2, {
            type: 'doughnut',
            data: {
                labels: bySource.map(x => x.source),
                datasets: [{ data: bySource.map(x => x.count), backgroundColor: [primary, success, warning, info, danger] }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        });
    }
}

function updateRecentEvents(events) {
    const tbody = document.getElementById('recentEvents');
    if (!tbody) return;
    if (!events.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет событий</td></tr>'; return; }
    const icons = {windows_agent:'🖥️',linux_agent:'🐧',scanner:'📡',api:'🔌'};
    const ticons = {read:'📖',write:'✏️',delete:'🗑️',move:'📦'};
    let html = '';
    for (const e of events) {
        const t = new Date(e.created_at).toLocaleString('ru-RU');
        html += '<tr><td>' + t + '</td><td>' + (e.user||'—') + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (e.file_path||'—') + '</td><td><span class="badge badge-primary">' + (ticons[e.event_type]||'') + ' ' + (e.event_type||'') + '</span></td><td>' + (icons[e.event_source]||'📋') + ' ' + (e.event_source||'—') + '</td></tr>';
    }
    tbody.innerHTML = html;
}

function updateRecentFindings(findings) {
    const tbody = document.getElementById('recentFindings');
    if (!tbody) return;
    if (!findings.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет находок</td></tr>'; return; }
    let html = '';
    for (const f of findings) {
        const t = new Date(f.created_at).toLocaleString('ru-RU');
        const bc = f.category === 'credentials' ? 'badge-warning' : 'badge-primary';
        const val = (f.value || '').length > 40 ? f.value.substring(0, 40) + '…' : (f.value || '—');
        const fp = (f.file_path || '').length > 40 ? '…' + f.file_path.substring(f.file_path.length - 35) : (f.file_path || '—');
        html += '<tr><td>' + t + '</td><td><span class="badge ' + bc + '">' + (f.category||'') + '</span></td><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + val + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + fp + '</td><td>' + ((f.confidence||0)).toFixed(0) + '%</td></tr>';
    }
    tbody.innerHTML = html;
}
