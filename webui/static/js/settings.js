// webui/static/js/settings.js
// 53.4d: режим аутентификации — только просмотр (BUG-187), счётчики данных
// (BUG-199), пароль в <form> с подтверждением (BUG-194/195/196), пояснения
// архивации (BUG-189/190/191), единые тосты (BUG-198).

const MODE_LABELS = {
    local: 'local — локальные учётные записи',
    hybrid: 'hybrid — локальные + Windows Integrated',
    windows_integrated: 'windows_integrated — только Windows Integrated',
};

async function loadAuthMode() {
    const el = document.getElementById('authModeValue');
    try {
        const r = await api.get('/api/auth/mode');
        const mode = (r && r.mode) || 'local';
        el.textContent = MODE_LABELS[mode] || mode;
    } catch (e) {
        el.textContent = 'недоступно';
    }
}

async function loadSettingsInfo() {
    const el = document.getElementById('settingsInfo');
    try {
        const me = await Auth.me();
        if (!me) { el.textContent = 'Нет данных'; return; }
        const type = me.auth_source === 'ad' ? 'AD' : 'Локальная';
        el.innerHTML =
            '<div>Пользователь: <b>' + escapeHtml(me.full_name || me.username) + '</b></div>' +
            '<div>Логин: <b>' + escapeHtml(me.username) + '</b></div>' +
            '<div>Тип учётной записи: <b>' + escapeHtml(type) + '</b></div>' +
            '<div>Роли: <b>' + escapeHtml((me.roles || []).join(', ') || '—') + '</b></div>';
    } catch (e) {
        el.textContent = 'Нет данных';
    }
}

async function loadRetentionCounters() {
    try {
        const s = await api.get('/api/retention/stats');
        document.getElementById('statAuditCount').textContent = s.audit_events ?? 0;
        document.getElementById('statArchiveCount').textContent = s.archived_events ?? 0;
        document.getElementById('statFindingsCount').textContent = s.findings ?? 0;
        document.getElementById('statTasksCount').textContent = s.completed_tasks ?? 0;
    } catch (e) {
        // Счётчики недоступны — оставляем нули, статус укажет причину.
    }
}

async function loadRetention() {
    try {
        const r = await api.get('/api/retention/policies');
        const p = r.policies || {};
        const aud = p.audit_events || {};
        document.getElementById('retAuditTtl').textContent = aud.ttl_days ?? '—';
        document.getElementById('retAuditArchiveTtl').textContent = aud.archive_ttl_days ?? '—';
        document.getElementById('retAuditArchiveOn').textContent =
            aud.archive_enabled === false ? 'выключена' : 'включена';
        const fin = p.findings || {};
        document.getElementById('retFindingsTtl').textContent = fin.ttl_days ?? '—';
        const tasks = p.tasks || {};
        document.getElementById('retTasksTtl').textContent = tasks.ttl_days ?? '—';
        const exp = p.export || {};
        document.getElementById('retExportFormat').textContent = exp.format || 'JSON / CSV';
        document.getElementById('retExportPath').textContent = exp.path || 'директория Manager (exports)';
    } catch (e) {
        document.getElementById('retentionStatus').textContent = 'Политики недоступны: ' + errorToRussian(e.message);
    }
    try {
        const r = await api.get('/api/retention/status');
        const last = r.last_run ? formatDate(r.last_run) : '—';
        document.getElementById('retentionStatus').textContent =
            'Интервал: ' + (r.interval_hours != null ? r.interval_hours : '—') + ' ч · Последний запуск: ' + last +
            (r.running ? ' · Выполняется…' : '');
    } catch (e) {
        document.getElementById('retentionStatus').textContent = 'Статус недоступен: ' + errorToRussian(e.message);
    }
    await loadRetentionCounters();
}

async function runRetention(dryRun) {
    if (!dryRun && !confirm('Запустить архивацию и очистку по политикам хранения? Данные будут перенесены в архив и/или удалены.')) return;
    try {
        const r = await api.post('/api/retention/run' + (dryRun ? '?dry_run=true' : ''));
        const res = r.result || {};
        const parts = [];
        const aud = res.archived_audit || {}; if (aud.archived) parts.push('архив аудита: ' + aud.archived);
        const fin = res.archived_findings || {}; if (fin.archived) parts.push('архив находок: ' + fin.archived);
        const ca = res.cleaned_archive || {}; let caSum = 0;
        Object.values(ca).forEach(v => { if (v && v.deleted) caSum += v.deleted; });
        if (caSum) parts.push('очистка архива: ' + caSum);
        const ct = res.cleaned_tasks || {}; if (ct.deleted) parts.push('очистка задач: ' + ct.deleted);
        const ex = res.exported || {}; if (ex.exported) parts.push('экспорт: ' + ex.exported);
        showToast('Архивация завершена' + (dryRun ? ' (dry-run)' : '') + (parts.length ? ': ' + parts.join(', ') : ''), 'success');
        loadRetention();
    } catch (e) {
        showToast('Ошибка архивации: ' + errorToRussian(e.message), 'error');
    }
}

async function exportArchive(dataType) {
    try {
        const r = await api.post('/api/retention/export', { data_type: dataType, limit: 10000 });
        showToast('Экспорт (' + dataType + '): ' + (r.exported ?? r.count ?? 0) + ' записей', 'success');
    } catch (e) {
        showToast('Ошибка экспорта: ' + errorToRussian(e.message), 'error');
    }
}

async function changePassword() {
    const cur = document.getElementById('curPassword').value;
    const nw = document.getElementById('newPassword').value;
    const nw2 = document.getElementById('newPassword2').value;
    if (!nw || nw.length < 6) { showToast('Новый пароль: минимум 6 символов', 'warning'); return; }
    if (nw !== nw2) { showToast('Пароли не совпадают', 'warning'); return; }
    try {
        await api.post('/api/auth/change-password', {
            old_password: cur,
            new_password: nw,
            confirm_password: nw2,  // BUG-196: подтверждение проверяет и backend.
        });
        showToast('Пароль изменён', 'success');
        closeModal('passwordModal');
        ['curPassword', 'newPassword', 'newPassword2'].forEach(id => { document.getElementById(id).value = ''; });
    } catch (e) {
        showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    loadAuthMode();
    loadSettingsInfo();
    loadRetention();
});
