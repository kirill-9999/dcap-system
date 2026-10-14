// BUG-208 (v3.14.0): heartbeat — локальное время (datetime.js).
// BUG-209 (v3.14.1): «Заданий» → «Файлов просканировано» (значение — total_files_scanned).
// BACKLOG-155 (v3.14.1): массовое удаление неактивных сканеров (admin).
var SCANNER_STATUS_RU = { active: 'активен', ACTIVE: 'активен', inactive: 'неактивен', INACTIVE: 'неактивен', busy: 'занят', assigned: 'занято' };
var AGENT_STATUS_RU = { online: 'онлайн', offline: 'офлайн', inactive: 'неактивен' };
var _scanners = [];
var _canDeleteScanners = false;

function badge(cls, text) { return '<span class="status-badge '+cls+'">'+text+'</span>'; }

async function loadScannersPage() {
    var scanners = await api.get('/api/scanners');
    _scanners = scanners || [];
    var c = document.getElementById('scanners-table');
    if (!scanners.length) { c.innerHTML = '<div class="text-center p-4 text-muted">Нет сканеров</div>'; }
    else {
        var html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>'
            + (_canDeleteScanners ? '<th></th>' : '')
            + '<th>ID</th><th>Имя</th><th>Статус</th><th>Heartbeat</th><th>Файлов просканировано</th></tr></thead><tbody>';
        for (var i = 0; i < scanners.length; i++) {
            var s = scanners[i];
            var st = SCANNER_STATUS_RU[s.status] || s.status;
            var online = /active|busy|assigned/i.test(s.status || '');
            var hb = s.last_heartbeat ? formatDate(s.last_heartbeat) : '—';
            var task = s.current_task ? ('<span class="text-muted small">задание #' + s.current_task.id + '</span>') : '';
            html += '<tr>'
                + (_canDeleteScanners ? '<td>' + (online ? '' : '<input type="checkbox" class="form-check-input scanner-chk" value="'+s.id+'">') + '</td>' : '')
                + '<td>#'+s.id+'</td><td>'+escapeHtml(s.name || '')+' '+task+'</td>'
                + '<td>'+badge(online?'online':'offline', st)+'</td>'
                + '<td>'+hb+'</td><td>'+((s.total_files_scanned||0))+'</td></tr>';        }
        c.innerHTML = html + '</tbody></table></div>';
    }
    updateInactiveCount();

    var agentsResp = await api.get('/api/audit/agents');
    var agents = agentsResp.agents || [];
    var c2 = document.getElementById('agents-table');
    if (!agents.length) { c2.innerHTML = '<div class="text-center p-4 text-muted">Нет агентов</div>'; return; }
    var html2 = '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>ID</th><th>Имя</th><th>Хост</th><th>Статус</th><th>Событий</th><th>Heartbeat</th></tr></thead><tbody>';
    for (var i = 0; i < agents.length; i++) {
        var a = agents[i];
        var on = a.status === 'online';
        var hb = a.last_heartbeat ? formatDate(a.last_heartbeat) : '—';
        html2 += '<tr><td>#'+a.id+'</td><td><strong>'+escapeHtml(a.name||'')+'</strong></td><td>'+escapeHtml(a.hostname||'')+'</td>'
            + '<td>'+badge(on?'online':'offline', AGENT_STATUS_RU[a.status] || a.status)+'</td>'
            + '<td>'+(a.events_sent||0)+'</td><td>'+hb+'</td></tr>';
    }
    c2.innerHTML = html2 + '</tbody></table></div>';
}

function updateInactiveCount() {
    var n = _scanners.filter(function (s) { return !/active|busy|assigned/i.test(s.status || ''); }).length;
    var el = document.getElementById('inactive-count');
    if (el) el.textContent = n;
}

async function deleteInactiveScanners() {
    var ids = Array.from(document.querySelectorAll('.scanner-chk:checked')).map(function (cb) { return parseInt(cb.value, 10); });
    if (!ids.length) { showToast('Отметьте неактивные сканеры для удаления', 'warning'); return; }
    if (!confirm('Удалить выбранные сканеры (' + ids.length + ')? Действие необратимо.')) return;
    var ok = 0, fail = 0;
    for (var i = 0; i < ids.length; i++) {
        try { await api.delete('/api/scanners/' + ids[i] + '?force=true'); ok++; }
        catch (e) { fail++; }
    }
    showToast('Удалено: ' + ok + (fail ? ', ошибок: ' + fail : ''), fail ? 'warning' : 'success');
    loadScannersPage();
}

document.addEventListener('DOMContentLoaded', async function () {
    if (typeof whenSessionReady === 'function') { try { await whenSessionReady(); } catch (e) {} }
    _canDeleteScanners = typeof RBAC !== 'undefined' && RBAC.isAdmin();
    var btn = document.getElementById('delete-inactive-btn');
    if (btn && _canDeleteScanners) btn.style.display = '';
    loadScannersPage();
});
