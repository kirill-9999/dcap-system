/**
 * Находки: список, фильтры, пагинация, массовые операции (День 40.3).
 */
const FindingsPage = {
  page: 0,
  limit: 50,
  total: 0,
  selected: new Set(),
  findings: [],
  filters: {},

  async init() {
    this.limit = parseInt(new URLSearchParams(location.search).get('limit') || '50', 10);
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    document.getElementById('apply-filters').addEventListener('click', () => {
      this.page = 0;
      this.load();
    });

    const resetBtn = document.getElementById('reset-filters');
    if (resetBtn) resetBtn.addEventListener('click', () => this.resetFilters());

    const search = document.getElementById('filter-search');
    if (search) {
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); this.page = 0; this.load(); }
      });
    }

    document.getElementById('filter-status').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('filter-type').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('filter-severity').addEventListener('change', () => { this.page = 0; this.load(); });

    document.getElementById('bulk-confirm').addEventListener('click', () => this.bulkUpdate('confirmed'));
    document.getElementById('bulk-fp').addEventListener('click', () => this.bulkUpdate('false_positive'));
    document.getElementById('bulk-clear').addEventListener('click', () => {
      this.selected.clear();
      this.render();
    });

    document.getElementById('export-btn').addEventListener('click', () => this.showExportDialog());
  },

  collectFilters() {
    return {
      status: document.getElementById('filter-status').value,
      finding_type: document.getElementById('filter-type').value,
      category: document.getElementById('filter-category').value,
      severity: document.getElementById('filter-severity').value,
      task_id: document.getElementById('filter-task').value,
      detector: document.getElementById('filter-detector')?.value || '',
      fragment_type: document.getElementById('filter-fragment')?.value || '',
      search: document.getElementById('filter-search')?.value || '',
    };
  },

  resetFilters() {
    ['filter-status', 'filter-type', 'filter-category', 'filter-severity', 'filter-task',
     'filter-detector', 'filter-fragment', 'filter-search'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    this.page = 0;
    this.load();
  },

  async load() {
    const params = {
      ...this.collectFilters(),
      limit: this.limit,
      offset: this.page * this.limit,
      order_by: 'first_seen_at',
      order: 'desc',
    };

    try {
      const r = await api.getWithMeta('/api/findings', params);
      this.findings = Array.isArray(r.data) ? r.data : [];
      this.total = r.total || 0;
      this.render();
    } catch (e) {
      document.getElementById('findings-list').innerHTML =
        `<div class="alert alert-danger">Не удалось загрузить находки: ${escapeHtml(e.message)}</div>`;
    }
  },

  render() {
    const list = document.getElementById('findings-list');
    if (!this.findings || this.findings.length === 0) {
      list.innerHTML = '<div class="alert alert-info">Находок не найдено</div>';
      this.renderPagination(false, 0);
      this.updateBulkBar();
      return;
    }

    list.innerHTML = this.findings.map(f => this.renderItem(f)).join('');
    this.renderPagination(this.findings.length >= this.limit, this.total);
    this.updateBulkBar();

    list.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        const id = parseInt(btn.dataset.id, 10);
        this.handleAction(action, id);
      });
    });

    list.querySelectorAll('.finding-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const id = parseInt(cb.dataset.id, 10);
        if (cb.checked) this.selected.add(id);
        else this.selected.delete(id);
        this.updateBulkBar();
      });
    });

    list.querySelectorAll('.finding-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.type === 'checkbox' || e.target.dataset.action) return;
        window.location.href = `/findings/${row.dataset.id}`;
      });
    });
  },

  renderPagination(hasMore, total) {
    const wrap = document.getElementById('pagination-wrap');
    const ul = document.getElementById('pagination');
    const totalPages = Math.max(1, Math.ceil((total || 0) / this.limit));
    if (this.page === 0 && !hasMore && totalPages <= 1) { wrap.style.display = 'none'; return; }
    wrap.style.display = 'block';
    ul.innerHTML = '';

    const mkItem = (label, pageIdx, active, disabled, onClick) => {
      const li = document.createElement('li');
      li.className = 'page-item' + (active ? ' active' : '') + (disabled ? ' disabled' : '');
      if (active) li.innerHTML = `<span class="page-link">${label}</span>`;
      else {
        li.innerHTML = `<a class="page-link" href="#">${label}</a>`;
        li.addEventListener('click', (e) => { e.preventDefault(); if (!disabled) onClick(pageIdx); });
      }
      ul.appendChild(li);
    };

    mkItem('« Назад', this.page - 1, false, this.page === 0, (p) => { this.page = p; this.load(); });

    // Окно из номеров страниц (максимум 7)
    const win = 7;
    let start = Math.max(0, this.page - Math.floor(win / 2));
    let end = Math.min(totalPages - 1, start + win - 1);
    start = Math.max(0, end - win + 1);
    for (let p = start; p <= end; p++) {
      mkItem(String(p + 1), p, p === this.page, false, (idx) => { this.page = idx; this.load(); });
    }

    mkItem('Вперёд »', this.page + 1, false, this.page >= totalPages - 1, (p) => { this.page = p; this.load(); });

    const count = document.getElementById('pagination-count');
    if (count) count.textContent = `Всего: ${total}`;
  },

  renderItem(f) {
    const statusBadge = {
      new: '<span class="badge bg-primary">🆕 new</span>',
      confirmed: '<span class="badge bg-success">✅ confirmed</span>',
      false_positive: '<span class="badge bg-danger">❌ false_positive</span>',
      archived: '<span class="badge bg-secondary">📦 archived</span>',
    }[f.status] || escapeHtml(f.status);

    const typeBadge = {
      pii: '<span class="badge bg-info text-dark">PII</span>',
      credentials: '<span class="badge bg-warning text-dark">Cred</span>',
      code: '<span class="badge bg-secondary">Code</span>',
    }[f.finding_type] || escapeHtml(f.finding_type);

    const severityClass = {
      critical: 'danger', high: 'warning', medium: 'info', low: 'secondary',
    }[f.severity] || 'secondary';

    const lineInfo = f.line_number
      ? `${f.file_path || 'файл'}:${f.line_number}`
      : (f.file_path || '—');

    return `
      <div class="card mb-2 finding-row" data-id="${f.id}">
        <div class="card-body py-2">
          <div class="d-flex align-items-start">
            <input type="checkbox" class="form-check-input me-2 finding-checkbox"
                   data-id="${f.id}" ${this.selected.has(f.id) ? 'checked' : ''}>
            <div class="flex-grow-1">
              <div class="d-flex flex-wrap justify-content-between align-items-center">
                <div>
                  <span class="finding-id">#${f.id}</span>
                  <code class="text-muted small">${escapeHtml(lineInfo)}</code>
                  <span class="ms-2">${typeBadge}</span>
                  <span class="badge bg-${severityClass}">${escapeHtml(f.severity)}</span>
                  <span class="badge bg-light text-dark">${escapeHtml(f.category)}</span>
                </div>
                <div>${statusBadge}</div>
              </div>
              <div class="mt-1">
                <code class="finding-match">${escapeHtml(f.match_text || '(masked)')}</code>
              </div>
              ${f.context_before ? `
                <details class="mt-1">
                  <summary class="small text-muted">Контекст</summary>
                  <pre class="small bg-light p-2 finding-context">${escapeHtml(f.context_before)}\n${escapeHtml(f.line_text || '')}\n${escapeHtml(f.context_after || '')}</pre>
                </details>
              ` : ''}
              <div class="mt-2">
                ${f.status === 'new' ? `
                  <button class="btn btn-sm btn-success" data-action="confirm" data-id="${f.id}" title="Подтвердить">✅</button>
                  <button class="btn btn-sm btn-danger" data-action="fp" data-id="${f.id}" title="Ложное">❌</button>
                ` : ''}
                ${f.can_reveal ? `
                  <button class="btn btn-sm btn-outline-primary" data-action="reveal" data-id="${f.id}" title="Показать оригинал">👁️ Reveal</button>
                ` : ''}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  async handleAction(action, id) {
    try {
      if (action === 'confirm') {
        await api.patch(`/api/findings/${id}`, { status: 'confirmed' });
        showSuccess('Подтверждено');
      } else if (action === 'fp') {
        await api.patch(`/api/findings/${id}`, { status: 'false_positive' });
        showSuccess('Помечено как ложное');
      } else if (action === 'reveal') {
        const r = await api.post(`/api/findings/${id}/reveal`);
        alert(`Оригинал:\n${r.match_text}\n\nСтрока:\n${r.line_text || '(нет)'}`);
      }
      await this.load();
    } catch (e) {
      showError(e.message);
    }
  },

  async bulkUpdate(status) {
    if (this.selected.size === 0) return;
    if (!confirm(`Обновить ${this.selected.size} находок на статус "${status}"?`)) return;

    try {
      const r = await api.post('/api/findings/bulk', {
        finding_ids: [...this.selected],
        status,
      });
      showSuccess(`Обновлено: ${r.updated}, пропущено: ${r.skipped}`);
      this.selected.clear();
      await this.load();
    } catch (e) {
      showError(e.message);
    }
  },

  /**
   * BUG-093 (TASK-059, v3.13.22): экспорт выполнялся через
   * window.location.href = '/api/findings/export' — браузер уходил без
   * заголовка Authorization (JWT в localStorage, cookie через прокси не
   * доходят) и получал 401. Качаем ответ через fetch и сохраняем blob.
   */
  async showExportDialog() {
    const fmt = prompt('Формат экспорта (csv/json):', 'csv');
    if (!fmt || !['csv', 'json'].includes(fmt)) return;

    const reveal = confirm('Показать оригиналы (только Auditor+)?\n\nOK = reveal, Отмена = masked');

    const params = new URLSearchParams({
      ...this.collectFilters(),
      format: fmt,
      reveal: reveal ? 'true' : 'false',
    });
    // Убрать пустые
    for (const [k, v] of [...params.entries()]) {
      if (!v || v === 'false') params.delete(k);
    }

    try {
      const r = await fetch(`/api/findings/export?${params.toString()}`, {
        headers: api._headers(),
      });
      if (r.status === 401) {
        if (typeof Auth !== 'undefined') Auth.setToken(null);
        window.location.href = '/login';
        return;
      }
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || ('HTTP ' + r.status));
      }
      const blob = await r.blob();
      const cd = r.headers.get('Content-Disposition') || '';
      const m = /filename="?([^"]+)"?/.exec(cd);
      const name = m ? m[1] : `findings.${fmt}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      showSuccess(`Экспорт: ${name}`);
    } catch (e) {
      showError('Ошибка экспорта: ' + e.message);
    }
  },

  updateBulkBar() {
    const bar = document.getElementById('bulk-actions');
    const count = this.selected.size;
    document.getElementById('selected-count').textContent = count;
    bar.style.display = count > 0 ? 'block' : 'none';
  },
};

document.addEventListener('DOMContentLoaded', () => FindingsPage.init());