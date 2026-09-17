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
        // W-42: kpiFindings считает НАХОДКИ через /api/findings/count,
        // а не события аудита (s.total из /api/audit/stats).
        const cnt = await api.get('/api/findings/count');
        const el = document.getElementById('kpiFindings');
        if (el) el.textContent = cnt && cnt.count != null ? cnt.count : 0;
    } catch(e) { console.error('Dashboard findings count error:', e); }
    try {
        const findings = await api.get('/api/findings', {limit: 500});
        renderFindingsCharts(Array.isArray(findings) ? findings : []);
        updateRecentFindings(Array.isArray(findings) ? findings.slice(0, 10) : []);
    } catch(e) { console.error('Dashboard findings error:', e); }
    try {
        const scanners = await api.get('/api/scanners');
        updateScannerPanel(Array.isArray(scanners) ? scanners : []);
    } catch(e) { console.error('Dashboard scanners error:', e); }
    try {
        const data = await api.get('/api/audit', {limit: 10});
        updateRecentEvents(data.events || []);
    } catch(e) { console.error('Dashboard events error:', e); }
}

function updateScannerPanel(scanners) {
    const panel = document.getElementById('scanner-panel');
    if (!panel) return;
    if (!scanners.length) {
        panel.innerHTML = '<div class="text-center text-muted">Сканеры не зарегистрированы</div>';
        return;
    }
    let html = '';
    const now = Date.now();
    for (const s of scanners) {
        const hb = s.last_heartbeat ? new Date(s.last_heartbeat).getTime() : 0;
        const ageSec = hb ? Math.max(0, Math.round((now - hb) / 1000)) : null;
        const active = s.status === 'active' || s.status === 'ACTIVE' || (ageSec !== null && ageSec < 120);
        const icon = active ? '\ud83d\udfe2' : '\ud83d\udfe1';
        const ageTxt = ageSec === null ? '\u2014' : (ageSec < 60 ? ageSec + ' \u0441\u0435\u043a \u043d\u0430\u0437\u0430\u0434' : Math.floor(ageSec / 60) + ' \u043c\u0438\u043d \u043d\u0430\u0437\u0430\u0434');

        let taskHtml = '';
        const t = s.current_task;
        if (t && t.progress && t.progress.total) {
            const files = t.progress.files_scanned || 0;
            const total = t.progress.total;
            const pct = t.progress.percent != null ? t.progress.percent : Math.round((files / total) * 100);
            const bar = Math.max(0, Math.min(100, pct));
            const blocks = Math.round(bar / 10);
            let speedTxt = '';
            const speed = t.progress.speed_files_per_sec;
            const eta = t.progress.eta_seconds;
            if (speed != null) {
                speedTxt = speed < 1
                    ? ' \u00b7 ' + (speed * 60).toFixed(1) + ' \u0444/\u043c\u0438\u043d'
                    : ' \u00b7 ' + speed.toFixed(1) + ' \u0444/\u0441';
            }
            if (eta != null && eta > 0) {
                const h = Math.floor(eta / 3600);
                const m = Math.floor((eta % 3600) / 60);
                speedTxt += ' \u00b7 ETA ' + (h > 0 ? h + '\u0447 ' + m + '\u043c' : m + '\u043c');
            }
            taskHtml = `<div class="mt-2 small">
                \u0417\u0430\u0434\u0430\u043d\u0438\u0435 #${t.id}: ${files}/${total} \u0444\u0430\u0439\u043b\u043e\u0432 (${bar}%)${speedTxt}
                <div class="progress mt-1" style="height:10px;">
                    <div class="progress-bar" role="progressbar" style="width:${bar}%;" aria-valuenow="${bar}" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
            </div>`;
        } else if (t) {
            taskHtml = `<div class="mt-2 small">\u0417\u0430\u0434\u0430\u043d\u0438\u0435 #${t.id} (\u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442)</div>`;
        } else {
            taskHtml = '<div class="mt-2 small text-muted">\u041d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0437\u0430\u0434\u0430\u043d\u0438\u0439</div>';
        }

        html += `<div class="scanner-card mb-2 p-2 border rounded">
            <div class="d-flex flex-wrap justify-content-between align-items-center">
                <strong>${s.name}</strong>
                <span>${icon} ${active ? 'active' : 'inactive'}</span>
            </div>
            ${taskHtml}
            <div class="small text-muted">\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0439 heartbeat: ${ageTxt}</div>
        </div>`;
    }
    panel.innerHTML = html;
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
    if (!findings.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">\u041d\u0435\u0442 \u043d\u0430\u0445\u043e\u0434\u043e\u043a</td></tr>'; return; }
    const statusBadge = {
        new: 'badge-primary', confirmed: 'badge-success', false_positive: 'badge-danger', archived: 'badge-secondary',
    };
    let html = '';
    for (const f of findings) {
        const t = new Date(f.first_seen_at || f.created_at || Date.now()).toLocaleString('ru-RU');
        const loc = (f.file_path || '') + (f.line_number ? ':' + f.line_number : '');
        const val = (f.match_text || f.value || '').length > 40 ? (f.match_text || f.value || '').substring(0, 40) + '\u2026' : (f.match_text || f.value || '\u2014');
        const fl = loc.length > 45 ? '\u2026' + loc.substring(loc.length - 40) : (loc || '\u2014');
        html += '<tr><td>' + t + '</td><td><span class="badge ' + (f.finding_type === 'credentials' ? 'badge-warning' : 'badge-primary') + '">' + (f.finding_type||'') + '</span></td><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + val + '</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><code>' + fl + '</code></td><td>' + ((f.confidence||0) * 100).toFixed(0) + '%</td><td><span class="badge ' + (statusBadge[f.status] || 'badge-primary') + '">' + (f.status||'') + '</span></td></tr>';
    }
    tbody.innerHTML = html;
}
