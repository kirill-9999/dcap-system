let charts = {};

function makeChart(id, config) {
    const ctx = document.getElementById(id);
    if (!ctx) return null;
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart(ctx, config);
    return charts[id];
}

function getColors() {
    const cs = getComputedStyle(document.documentElement);
    return {
        primary: cs.getPropertyValue('--color-primary').trim(),
        danger: cs.getPropertyValue('--color-danger').trim(),
        warning: cs.getPropertyValue('--color-warning').trim(),
        info: cs.getPropertyValue('--color-info').trim(),
        success: cs.getPropertyValue('--color-success').trim(),
        textSecondary: cs.getPropertyValue('--color-text-secondary').trim(),
    };
}

async function loadDashboard() {
    try {
        const stats = await api.get('/api/audit/stats', {days: 7});
        updateKPIs(stats);
        renderAuditCharts(stats);
    } catch(e) { console.error('Dashboard stats error:', e); }
    try {
        const findings = await api.get('/api/findings', {limit: 500});
        renderFindingsCharts(Array.isArray(findings) ? findings : []);
        updateRecentFindings(Array.isArray(findings) ? findings.slice(0, 10) : []);
    } catch(e) { console.error('Dashboard findings error:', e); }
    try {
        const data = await api.get('/api/audit', {limit: 10});
        updateRecentEvents(data.events || []);
    } catch(e) { console.error('Dashboard events error:', e); }
}

function updateKPIs(s) {
    const el = id => document.getElementById(id);
    if (el('kpiResources')) el('kpiResources').textContent = s.total_resources || 0;
    if (el('kpiFindings')) el('kpiFindings').textContent = s.total || 0;
    if (el('kpiAgents')) el('kpiAgents').textContent = s.agents_online || 0;
    if (el('kpiAgentsChange')) el('kpiAgentsChange').textContent = '\u0438\u0437 ' + (s.agents_total || 0);
}

function renderFindingsCharts(findings) {
    const c = getColors();
    const palette = [c.primary, c.danger, c.warning, c.info, c.success];

    const catMap = {};
    for (const f of findings) {
        const cat = f.category || 'other';
        catMap[cat] = (catMap[cat] || 0) + 1;
    }
    const catLabels = Object.keys(catMap);
    const catValues = Object.values(catMap);
    makeChart('findingsByCategoryChart', {
        type: 'doughnut',
        data: {
            labels: catLabels,
            datasets: [{ data: catValues, backgroundColor: palette.slice(0, catLabels.length) }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });

    const resMap = {};
    for (const f of findings) {
        const fp = f.file_path || 'unknown';
        const short = fp.split(/[/\\]/).pop() || fp;
        resMap[short] = (resMap[short] || 0) + 1;
    }
    const sorted = Object.entries(resMap).sort((a, b) => b[1] - a[1]).slice(0, 10);
    makeChart('findingsByResourceChart', {
        type: 'bar',
        data: {
            labels: sorted.map(s => s[0]),
            datasets: [{ label: '\u041d\u0430\u0445\u043e\u0434\u043a\u0438', data: sorted.map(s => s[1]), backgroundColor: palette[0] }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true } }
        }
    });
}

function renderAuditCharts(s) {
    const c = getColors();
    const palette = [c.primary, c.success, c.danger, c.warning, c.info];

    const byType = s.by_type || [];
    makeChart('auditChart', {
        type: 'bar',
        data: {
            labels: byType.map(t => t.type),
            datasets: [{ label: '\u0421\u043e\u0431\u044b\u0442\u0438\u044f', data: byType.map(t => t.count), backgroundColor: palette.slice(0, byType.length) }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });

    const bySource = s.by_source || [];
    makeChart('auditBySourceChart', {
        type: 'doughnut',
        data: {
            labels: bySource.map(x => x.source),
            datasets: [{ data: bySource.map(x => x.count), backgroundColor: palette.slice(0, bySource.length) }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });
}

function updateRecentEvents(events) {
    const tbody = document.getElementById('recentEvents');
    if (!tbody) return;
    if (!events.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">\u041d\u0435\u0442 \u0441\u043e\u0431\u044b\u0442\u0438\u0439</td></tr>'; return; }
    const icons = {windows_agent:'\ud83e\udea3',linux_agent:'\ud83d\udc27',scanner:'\ud83d\udce1',api:'\ud83d\udd0c'};
    const ticons = {read:'\ud83d\udcd6',write:'\u270f\ufe0f',delete:'\ud83d\uddd1\ufe0f',move:'\ud83d\udce6'};
    let html = '';
    for (const e of events) {
        const t = new Date(e.created_at).toLocaleString('ru-RU');
        html += '<tr><td>' + t + '</td><td>' + (e.user||'\u2014') + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (e.file_path||'\u2014') + '</td><td><span class="badge badge-primary">' + (ticons[e.event_type]||'') + ' ' + (e.event_type||'') + '</span></td><td>' + (icons[e.event_source]||'\ud83d\udccb') + ' ' + (e.event_source||'\u2014') + '</td></tr>';
    }
    tbody.innerHTML = html;
}

function updateRecentFindings(findings) {
    const tbody = document.getElementById('recentFindings');
    if (!tbody) return;
    if (!findings.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">\u041d\u0435\u0442 \u043d\u0430\u0445\u043e\u0434\u043e\u043a</td></tr>'; return; }
    let html = '';
    for (const f of findings) {
        const t = new Date(f.created_at).toLocaleString('ru-RU');
        const bc = f.category === 'credentials' ? 'badge-warning' : 'badge-primary';
        const val = (f.value || '').length > 40 ? f.value.substring(0, 40) + '\u2026' : (f.value || '\u2014');
        const fp = (f.file_path || '').length > 40 ? '\u2026' + f.file_path.substring(f.file_path.length - 35) : (f.file_path || '\u2014');
        html += '<tr><td>' + t + '</td><td><span class="badge ' + bc + '">' + (f.category||'') + '</span></td><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + val + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + fp + '</td><td>' + ((f.confidence||0)).toFixed(0) + '%</td></tr>';
    }
    tbody.innerHTML = html;
}
