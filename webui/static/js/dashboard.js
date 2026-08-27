let auditChartInstance = null;
let findingsChartInstance = null;

async function loadDashboard() {
    try {
        const stats = await api.get('/api/audit/stats', {days: 7});
        updateKPIs(stats);
        updateCharts(stats);
        updateRecentEvents(stats);
    } catch(e) { console.error('Dashboard error:', e); }
}

function updateKPIs(s) {
    const el = id => document.getElementById(id);
    if (el('kpiResources')) el('kpiResources').textContent = s.total_resources || 0;
    if (el('kpiFindings')) el('kpiFindings').textContent = s.total || 0;
    if (el('kpiAgents')) el('kpiAgents').textContent = s.agents_online || 0;
    if (el('kpiAgentsChange')) el('kpiAgentsChange').textContent = '\u0438\u0437 ' + (s.agents_total || 0);
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
                datasets: [{ label: '\u0421\u043e\u0431\u044b\u0442\u0438\u044f', data: values, backgroundColor: [primary, success, danger, warning, info] }]
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

function updateRecentEvents(s) {
    const tbody = document.getElementById('recentEvents');
    if (!tbody) return;
    const events = s.recent || [];
    if (!events.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">\u041d\u0435\u0442 \u0441\u043e\u0431\u044b\u0442\u0438\u0439</td></tr>'; return; }
    const icons = {windows_agent:'\ud83e\udea7',linux_agent:'\ud83d\udc27',scanner:'\ud83d\udce1',api:'\ud83d\udd0c'};
    const ticons = {read:'\ud83d\udcd6',write:'\u270f\ufe0f',delete:'\ud83d\uddd1\ufe0f',move:'\ud83d\udce6'};
    let html = '';
    for (const e of events) {
        const t = new Date(e.created_at).toLocaleString('ru-RU');
        html += '<tr><td>' + t + '</td><td>' + (e.user||'\u2014') + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (e.file_path||'\u2014') + '</td><td><span class="badge badge-primary">' + (ticons[e.event_type]||'') + ' ' + (e.event_type||'') + '</span></td><td>' + (icons[e.event_source]||'\ud83d\udccb') + ' ' + (e.event_source||'\u2014') + '</td></tr>';
    }
    tbody.innerHTML = html;
}
