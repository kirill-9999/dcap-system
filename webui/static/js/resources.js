/**
 * Ресурсы (53.4c): список с пагинацией, статусы, создание, удаление.
 *
 * BUG-147 — пагинация через skip/limit (раньше видели только 100 из 127).
 * BUG-211 — статус «Активен/Отключён» вместо непонятного ✔.
 * BUG-226 — модалка создания доведена до рабочего вида.
 * BACKLOG-122 — убран тип S3 (AWS) и поле Region.
 * BACKLOG-124 — убрано поле «Расширения» (не отправлялось).
 * BACKLOG-125 — значения не капсом (Filesystem / MinIO).
 * BACKLOG-128 — кнопка удаления ресурса (DELETE /api/resources/{id}).
 */
const ResourcesPage = {
  PAGE: 100,
  offset: 0,
  resources: [],
  canScan: false,
  canDelete: false,

  RES_TYPE_RU: { filesystem: 'Filesystem', s3: 'S3', minio: 'MinIO' },
  RES_TYPE_CLS: { filesystem: 'badge-secondary', s3: 'badge-info', minio: 'badge-primary' },

  async init() {
    if (typeof whenSessionReady === 'function') {
      try { await whenSessionReady(); } catch (e) { /* */ }
    }
    this.canScan = typeof RBAC !== 'undefined' && RBAC.isScanner();
    this.canDelete = typeof RBAC !== 'undefined' && RBAC.isAdmin();
    if (typeof RBAC !== 'undefined' && !RBAC.isAdmin()) {
      const addBtn = document.getElementById('add-resource-btn');
      if (addBtn) addBtn.style.display = 'none';
    }
    await this.load(true);

    // BACKLOG-123 (частично): подсказка существующих путей в datalist.
    const dl = document.getElementById('resource-path-list');
    if (dl) {
      const paths = Array.from(new Set(this.resources.map(r => r.path))).slice(0, 50);
      dl.innerHTML = paths.map(p => `<option value="${escapeHtml(p)}"></option>`).join('');
    }
  },

  async load(reset) {
    if (reset) { this.offset = 0; this.resources = []; }
    let batch = [];
    try {
      batch = await api.get('/api/resources', { limit: this.PAGE, offset: this.offset });
    } catch (e) {
      document.getElementById('resources-table').innerHTML =
        `<div class="alert alert-danger">${escapeHtml(errorToRussian(e.message))}</div>`;
      return;
    }
    this.resources = this.resources.concat(batch);
    this.offset += batch.length;
    this.render();
    const more = document.getElementById('resources-more');
    if (more) more.style.display = batch.length >= this.PAGE ? '' : 'none';
  },

  async loadMore() { await this.load(false); },

  render() {
    const c = document.getElementById('resources-table');
    document.getElementById('resources-count').textContent = `Загружено: ${this.resources.length}`;
    if (!this.resources.length) { c.innerHTML = '<div class="text-center p-4 text-muted">Нет ресурсов</div>'; return; }
    let html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>'
      + '<th>ID</th><th>Тип</th><th>Путь</th><th>Статус</th><th>Последнее сканирование</th><th>Создан</th><th></th></tr></thead><tbody>';
    for (const r of this.resources) {
      const st = r.enabled
        ? '<span class="badge badge-success">Активен</span>'
        : '<span class="badge badge-secondary">Отключён</span>';
      const scanBtn = (r.enabled && this.canScan)
        ? `<button class="btn btn-sm btn-outline-primary" onclick="ResourcesPage.rescan(${r.id})" title="Запустить сканирование"><i class="fas fa-play"></i></button>` : '';
      const delBtn = this.canDelete
        ? `<button class="btn btn-sm btn-outline-danger" onclick="ResourcesPage.remove(${r.id})" title="Удалить ресурс"><i class="fas fa-trash"></i></button>` : '';
      html += '<tr><td>#' + r.id + '</td>'
        + '<td><span class="badge ' + (this.RES_TYPE_CLS[r.type] || 'badge-secondary') + '">' + escapeHtml(this.RES_TYPE_RU[r.type] || r.type || '') + '</span></td>'
        + '<td><code>' + escapeHtml(r.path || '') + '</code></td>'
        + '<td>' + st + '</td>'
        + '<td>' + (r.last_scanned_at ? formatDate(r.last_scanned_at) : '—') + '</td>'
        + '<td>' + (r.created_at ? formatDate(r.created_at) : '—') + '</td>'
        + '<td class="text-end" style="white-space:nowrap;">' + scanBtn + ' ' + delBtn + '</td></tr>';
    }
    c.innerHTML = html + '</tbody></table></div>';
  },

  showCreate() {
    document.getElementById('resource-path').value = '';
    document.getElementById('resource-endpoint').value = '';
    document.getElementById('resource-secure').checked = false;
    document.getElementById('resource-path-style').checked = true;
    document.getElementById('resource-type').value = 'filesystem';
    this.onTypeChange();
    openModal('create-resource-modal');
  },

  onTypeChange() {
    const t = document.getElementById('resource-type').value;
    const s3 = document.getElementById('s3-fields');
    const hint = document.getElementById('resource-path-hint');
    const path = document.getElementById('resource-path');
    if (t === 'minio') {
      s3.style.display = '';
      hint.innerHTML = 'Формат: <code>s3://bucket[/prefix]</code>';
      path.placeholder = 's3://bucket/prefix';
    } else {
      s3.style.display = 'none';
      hint.innerHTML = 'Локальный путь или UNC (<code>\\\\server\\share</code>). Выбор каталога на сервере — в v3.1.0.';
      path.placeholder = 'D:\\data или /home/user/data';
    }
  },

  async create() {
    const path = document.getElementById('resource-path')?.value?.trim();
    if (!path) { showToast('Укажите путь', 'warning'); return; }
    const type = document.getElementById('resource-type')?.value || 'filesystem';
    const params = new URLSearchParams({ path, type });
    if (type === 'minio') {
      const endpoint = document.getElementById('resource-endpoint')?.value?.trim();
      if (endpoint) params.append('endpoint', endpoint);
      params.append('secure', document.getElementById('resource-secure')?.checked ? 'true' : 'false');
      params.append('use_path_style', document.getElementById('resource-path-style')?.checked ? 'true' : 'false');
    }
    const btn = document.getElementById('resource-save-btn');
    if (btn) btn.disabled = true;
    try {
      const r = await fetch('/api/resources?' + params.toString(), { method: 'POST', headers: api._headers() });
      if (r.status === 401) { Auth.setToken(null); window.location.href = '/login'; return; }
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        showToast(errorToRussian(err.detail || ('HTTP ' + r.status)), 'error');
        return;
      }
      closeModal('create-resource-modal');
      showToast('Ресурс создан', 'success');
      await this.load(true);
    } catch (e) {
      showToast('Ошибка: ' + errorToRussian(e.message), 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  async rescan(id) {
    if (!confirm('Запустить сканирование ресурса #' + id + '?')) return;
    try {
      const res = await api.post('/api/resources/' + id + '/scan');
      if (res.success) showToast('Задание #' + res.task_id + ' создано', 'success');
      else showToast(res.detail || 'Ошибка', 'error');
    } catch (e) {
      showToast(errorToRussian(e.message), 'error');
    }
  },

  async remove(id) {
    const r = this.resources.find(x => x.id === id);
    if (!confirm('Удалить ресурс #' + id + (r ? ' (' + r.path + ')' : '') + '?\nСвязанные находки, права и история останутся, но отвязаться от ресурса.')) return;
    try {
      await api.delete('/api/resources/' + id);
      showToast('Ресурс удалён', 'success');
      await this.load(true);
    } catch (e) {
      showToast(errorToRussian(e.message), 'error');
    }
  },
};

document.addEventListener('DOMContentLoaded', () => ResourcesPage.init());
