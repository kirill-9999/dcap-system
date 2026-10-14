// BUG-152 (v3.14.1): страница «Доступ» больше не заглушка — ресурсы+права+алерты.
// BUG-153 (v3.14.1): тип ресурса отображается по-человечески (не FILESYSTEM uppercase).
// BACKLOG-118 (v3.14.1): действие возврата алерта в работу переименовано в «Вернуть в работу» + подсказка.
var RES_TYPE_RU = { filesystem: 'Файловая система', s3: 'S3', minio: 'MinIO' };
var PERM_RU = { read: 'чтение', write: 'запись', delete: 'удаление', modify: 'изменение', full_control: 'полный доступ' };
var PRINCIPAL_RU = { user: 'пользователь', group: 'группа', local_user: 'локальный', local_group: 'локальная группа', ad_user: 'AD-пользователь', ad_group: 'AD-группа', system: 'система' };
var ALERT_STATUS_RU = { open: 'открыт', acknowledged: 'принят', resolved: 'решён', ignored: 'игнорируется' };
var SEVERITY_RU = { critical: 'критично', warning: 'предупреждение', info: 'инфо' };
var ALERT_TYPE_RU = { excessive_permissions: 'избыточные права', inherited_risk: 'опасное наследование', orphaned: 'бесхозный объект', sensitive_access: 'доступ к чувствительному' };
var SEVERITY_CLS = { critical: 'badge-danger', warning: 'badge-warning', info: 'badge-info' };
var RES_TYPE_CLS = { filesystem: 'badge-secondary', s3: 'badge-primary', minio: 'badge-info' };

async function loadAccess() {
    try {
        var d = await api.get('/api/access/resources');
        var resources = d.resources || [];
        document.getElementById('ac-resources').textContent = d.total != null ? d.total : resources.length;
        var openAlerts = resources.reduce(function (a, r) { return a + (r.open_alerts_count || 0); }, 0);
        document.getElementById('ac-open-alerts').textContent = openAlerts;
        renderResources(resources);
    } catch (e) {
        document.getElementById('access-resources-table').innerHTML = '<div class="alert alert-danger">' + escapeHtml(errorToRussian(e.message)) + '</div>';
    }
    loadAlerts();
}

function renderResources(resources) {
    var c = document.getElementById('access-resources-table');
    if (!resources.length) { c.innerHTML = '<div class="text-center p-4 text-muted">Нет ресурсов</div>'; return; }
    var html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>'
        + '<th>ID</th><th>Тип</th><th>Путь</th><th>Владелец</th><th>Записей прав</th><th>Открытых алертов</th><th></th></tr></thead><tbody>';
    resources.forEach(function (r) {
        html += '<tr><td>#' + r.id + '</td>'
            + '<td><span class="badge ' + (RES_TYPE_CLS[r.type] || 'badge-secondary') + '">' + escapeHtml(RES_TYPE_RU[r.type] || r.type || '') + '</span></td>'
            + '<td><code>' + escapeHtml(r.path || '') + '</code>' + (r.is_sensitive ? ' <span class="badge badge-danger" title="Чувствительный ресурс">!</span>' : '') + '</td>'
            + '<td>' + escapeHtml(r.owner || '—') + '</td>'
            + '<td>' + (r.entries_count || 0) + '</td>'
            + '<td>' + ((r.open_alerts_count || 0) ? '<span class="badge badge-danger">' + r.open_alerts_count + '</span>' : '0') + '</td>'
            + '<td class="text-end"><button class="btn btn-sm btn-outline-primary" onclick="showEntries(' + r.id + ', \'' + escapeHtml((r.path || '').replace(/'/g, "\\'")) + '\')"><i class="fas fa-users-viewfinder"></i> Права</button></td>'
            + '</tr>';
    });
    c.innerHTML = html + '</tbody></table></div>';
}

async function showEntries(resourceId, path) {
    var panel = document.getElementById('entries-panel');
    document.getElementById('entries-resource-path').textContent = path;
    document.getElementById('entries-body').innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';
    panel.style.display = '';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    try {
        var d = await api.get('/api/access/resources/' + resourceId + '/entries', { limit: 500 });
        var entries = d.entries || [];
        if (!entries.length) { document.getElementById('entries-body').innerHTML = '<div class="text-muted">Записей прав нет</div>'; return; }
        var html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>'
            + '<th>Субъект</th><th>Тип</th><th>Право</th><th>Источник</th><th>Унаследовано</th><th>Проверено</th></tr></thead><tbody>';
        entries.forEach(function (e) {
            html += '<tr><td><code>' + escapeHtml(e.principal_name || '') + '</code></td>'
                + '<td>' + escapeHtml(PRINCIPAL_RU[e.principal_type] || e.principal_type || '') + '</td>'
                + '<td><span class="badge badge-primary">' + escapeHtml(PERM_RU[e.permission_type] || e.permission_type || '') + '</span></td>'
                + '<td>' + escapeHtml(e.permission_source || '') + '</td>'
                + '<td>' + (e.is_inherited ? ('да <span class="text-muted small">(' + escapeHtml(e.inherited_from || '') + ')</span>') : 'нет') + '</td>'
                + '<td>' + (e.last_verified_at ? formatDate(e.last_verified_at) : '—') + '</td>'
                + '</tr>';
        });
        document.getElementById('entries-body').innerHTML = html + '</tbody></table></div>' + '<div class="text-muted small mt-1">Всего: ' + (d.total != null ? d.total : entries.length) + '</div>';
    } catch (e) {
        document.getElementById('entries-body').innerHTML = '<div class="alert alert-danger">' + escapeHtml(errorToRussian(e.message)) + '</div>';
    }
}

function closeEntries() { document.getElementById('entries-panel').style.display = 'none'; }

async function loadAlerts() {
    var sev = document.getElementById('al-severity').value;
    var st = document.getElementById('al-status').value;
    try {
        var params = { limit: 200 };
        if (sev) params.severity = sev;
        if (st) params.status = st;
        var d = await api.get('/api/access/alerts', params);
        var alerts = d.alerts || [];
        if (sev === 'critical' || st === 'open') { /* фильтр по открытым */ }
        if (st === 'open' || !st) {
            var crit = alerts.filter(function (a) { return a.severity === 'critical' && a.status === 'open'; }).length;
            document.getElementById('ac-critical').textContent = crit;
        }
        renderAlerts(alerts);
    } catch (e) {
        document.getElementById('access-alerts-table').innerHTML = '<div class="alert alert-danger">' + escapeHtml(errorToRussian(e.message)) + '</div>';
    }
}

function renderAlerts(alerts) {
    var c = document.getElementById('access-alerts-table');
    if (!alerts.length) { c.innerHTML = '<div class="text-center p-4 text-muted">Алертов нет</div>'; return; }
    var canAct = typeof RBAC !== 'undefined' && RBAC.isAuditor();
    var html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>'
        + '<th>Важность</th><th>Тип</th><th>Ресурс</th><th>Субъект</th><th>Описание</th><th>Статус</th><th></th></tr></thead><tbody>';
    alerts.forEach(function (a) {
        var actions = '';
        if (canAct) {
            if (a.status === 'open') {
                actions = '<button class="btn btn-sm btn-outline-secondary" onclick="setAlertStatus(' + a.id + ',\'acknowledged\')" title="Принять к рассмотрению">Принять</button> '
                    + '<button class="btn btn-sm btn-outline-success" onclick="setAlertStatus(' + a.id + ',\'resolved\')" title="Отметить как решённый">Решён</button> '
                    + '<button class="btn btn-sm btn-outline-secondary" onclick="setAlertStatus(' + a.id + ',\'ignored\')" title="Скрыть без действий">Игнор</button>';
            } else {
                actions = '<button class="btn btn-sm btn-outline-primary" onclick="setAlertStatus(' + a.id + ',\'open\')" title="Вернуть алерт в список открытых для повторного рассмотрения"><i class="fas fa-rotate-left"></i> Вернуть в работу</button>';
            }
        }
        html += '<tr>'
            + '<td><span class="badge ' + (SEVERITY_CLS[a.severity] || 'badge-secondary') + '">' + escapeHtml(SEVERITY_RU[a.severity] || a.severity || '') + '</span></td>'
            + '<td>' + escapeHtml(ALERT_TYPE_RU[a.alert_type] || a.alert_type || '') + '</td>'
            + '<td><code>' + escapeHtml(a.resource_path || ('#' + (a.resource_id || '—'))) + '</code></td>'
            + '<td>' + escapeHtml(a.principal_name || '—') + '</td>'
            + '<td>' + escapeHtml(a.description || '') + (a.recommendation ? '<div class="text-muted small">Рекомендация: ' + escapeHtml(a.recommendation) + '</div>' : '') + '</td>'
            + '<td>' + escapeHtml(ALERT_STATUS_RU[a.status] || a.status || '') + '</td>'
            + '<td class="text-end" style="white-space:nowrap;">' + actions + '</td></tr>';
    });
    c.innerHTML = html + '</tbody></table></div>';
}

async function setAlertStatus(id, status) {
    try {
        await api.put('/api/access/alerts/' + id, { status: status });
        showToast('Статус алерта обновлён: ' + (ALERT_STATUS_RU[status] || status), 'success');
        loadAlerts();
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

function resetAlerts() {
    document.getElementById('al-severity').value = '';
    document.getElementById('al-status').value = '';
    loadAlerts();
}

document.addEventListener('DOMContentLoaded', async function () {
    if (typeof whenSessionReady === 'function') { try { await whenSessionReady(); } catch (e) {} }
    loadAccess();
});
