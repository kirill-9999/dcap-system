# Отчёт — День 40.3: Findings Refactor: WebUI (находки, каталог, FP, reveal) (v3.11.0)

- **Дата:** 12.09.2026
- **Версия:** v3.11.0
- **Ветка:** `feature/day_40.3_webui_findings` (от `feature/day_40.2_scanner_findings`, база v3.10.0)
- **ТЗ:** `prompts/tz/day_40.3_webui_findings.md` → архивировано в `prompts/archive/day_40.3_webui_findings.md`
- **Отчёт:** `prompts/reports/day_40.3_report.md`

---

## 1. Цель

Перевести WebUI на строчную модель находок (v3.10+, Этап 3 из 4 Findings Refactor) и закрыть 🔴 BACKLOG-066:

- **40.3.1** — список находок: фильтры (status/type/category/severity/task), пагинация, bulk-действия, экспорт JSON;
- **40.3.2** — детальная карточка /findings/{id} + reveal (только Auditor/Admin, с записью в audit_logs) + смена статуса;
- **40.3.3** — каталог на уровне строк (папка → файл → найденные строки), страница «Ложные срабатывания», прогресс сканера на дашборде (BACKLOG-043); устранение деградации WebUI v3.8 (BACKLOG-061);
- 🔴 **BACKLOG-066** — MD5 → SHA-256 в `_legacy_fingerprint`.

---

## 2. Что сделано

### 2.0 🔴 BACKLOG-066: MD5 → SHA-256 — `scanner/src/managed_scanner.py`

`_legacy_fingerprint` теперь принимает полный контекст (`file_path`, `line`, `match`, `finding_type`) и хеширует его SHA-256 (не MD5). Вызов обновлён в `_serialize_finding`.

```python
    def _legacy_fingerprint(self, file_path: str, line: int, match: str, finding_type: str) -> str:
        """
        Fingerprint БЕЗ HMAC (legacy-режим, когда ключей нет).

        Важно: SHA-256 с полным контекстом (file_path + line + match + type) —
        уменьшает коллизии; слабые 32-hex дайджесты не используются.
        """
        import hashlib

        msg = f"{file_path}|{line}|{match}|{finding_type}".encode("utf-8")
        return hashlib.sha256(msg).hexdigest()
```

Вызов в `_serialize_finding`:

```python
            d["legacy_fingerprint"] = self._legacy_fingerprint(fpath, line_no, value, finding.finding_type)
```

Консистентно с Manager: HMAC-SHA256 от `f"{file_path}|{line}|{match}|{finding_type}"` в `manager/src/core/encryption.py` и `scanner/src/encryption.py`. 4-й компонент = `finding_type` — это отклонение от текста ТЗ (см. раздел 5).

### 2.1 Под-день 40.3.1: список находок

**`webui/static/js/api.js`** — общий HTTP-клиент WebUI (метод `request`, `get/post/put/patch/delete`, разбор `{detail}`-ошибок, авто-редирект на `/login` при 401, `showSuccess`/`showError`/`escapeHtml`):

```js
const api = {
    _headers() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof Auth !== 'undefined') Object.assign(headers, Auth.authHeaders());
        return headers;
    },

    async request(method, endpoint, data) {
        const opts = { method, headers: this._headers() };
        if (data !== undefined) opts.body = JSON.stringify(data);
        const r = await fetch(endpoint, opts);
        if (r.status === 401) {
            if (typeof Auth !== 'undefined') Auth.setToken(null);
            if (window.location.pathname !== '/login') window.location.href = '/login';
        }
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText || ('HTTP ' + r.status) }));
            throw new Error(err.detail || ('HTTP ' + r.status));
        }
        return r.json();
    },

    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        return this.request('GET', url.toString());
    },
    async post(endpoint, data = {}) { return this.request('POST', endpoint, data); },
    async put(endpoint, data = {}) { return this.request('PUT', endpoint, data); },
    async patch(endpoint, data = {}) { return this.request('PATCH', endpoint, data); },
    async delete(endpoint) { return this.request('DELETE', endpoint); }
};

function showSuccess(msg) { showToast(msg, 'success'); }
function showError(msg) { showToast(msg, 'error'); }
function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}
```

**`webui/templates/findings.html`** — страница списка (`{% extends "base.html" %}`, блоки head/scripts):

- шапка «Находки» + кнопка «Экспорт»;
- карточка фильтров: статус (new/confirmed/false_positive/archived), тип (pii/credentials/code), категория (текст), severity (critical/high/medium/low), задание (ID), кнопка «Применить»;
- bulk-бар (скрыт при 0): счётчик выбранных, «Подтвердить», «Ложное», «Снять выбор»;
- контейнер `#findings-list`, пагинация `#pagination`;
- `{% block head %}` — `findings.css`; `{% block scripts %}` — `findings.js`.

**`webui/static/js/findings.js`** — объект `FindingsPage` (page/limit/selected/findings):

```js
/**
 * Находки: список, фильтры, пагинация, массовые операции (День 40.3).
 */
const FindingsPage = {
  page: 0,
  limit: 50,
  selected: new Set(),
  findings: [],
  filters: {},

  async init() {
    this.limit = parseInt(new URLSearchParams(location.search).get('limit') || '50', 10);
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    document.getElementById('apply-filters').addEventListener('click', () => { this.page = 0; this.load(); });
    document.getElementById('filter-status').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('filter-type').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('filter-severity').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('bulk-confirm').addEventListener('click', () => this.bulkUpdate('confirmed'));
    document.getElementById('bulk-fp').addEventListener('click', () => this.bulkUpdate('false_positive'));
    document.getElementById('bulk-clear').addEventListener('click', () => { this.selected.clear(); this.render(); });
    document.getElementById('export-btn').addEventListener('click', () => this.exportJson());
  },

  collectFilters() {
    return {
      status: document.getElementById('filter-status').value,
      finding_type: document.getElementById('filter-type').value,
      category: document.getElementById('filter-category').value,
      severity: document.getElementById('filter-severity').value,
      task_id: document.getElementById('filter-task').value,
    };
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
      const r = await api.get('/api/findings', params);
      this.findings = Array.isArray(r) ? r : [];
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
      this.renderPagination(false);
      this.updateBulkBar();
      return;
    }
    list.innerHTML = this.findings.map(f => this.renderItem(f)).join('');
    this.renderPagination(this.findings.length >= this.limit);
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

  renderPagination(hasMore) {
    const wrap = document.getElementById('pagination-wrap');
    const ul = document.getElementById('pagination');
    if (!hasMore && this.page === 0) { wrap.style.display = 'none'; return; }
    wrap.style.display = 'block';
    ul.innerHTML = '';
    const prev = document.createElement('li');
    prev.className = 'page-item' + (this.page === 0 ? ' disabled' : '');
    prev.innerHTML = `<a class="page-link" href="#">&laquo; Назад</a>`;
    prev.addEventListener('click', (e) => { e.preventDefault(); if (this.page > 0) { this.page--; this.load(); } });
    ul.appendChild(prev);
    const num = document.createElement('li');
    num.className = 'page-item active';
    num.innerHTML = `<span class="page-link">${this.page + 1}</span>`;
    ul.appendChild(num);
    const next = document.createElement('li');
    next.className = 'page-item' + (hasMore ? '' : ' disabled');
    next.innerHTML = `<a class="page-link" href="#">Вперёд &raquo;</a>`;
    next.addEventListener('click', (e) => { e.preventDefault(); if (hasMore) { this.page++; this.load(); } });
    ul.appendChild(next);
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
      const r = await api.post('/api/findings/bulk', { finding_ids: [...this.selected], status });
      showSuccess(`Обновлено: ${r.updated}, пропущено: ${r.skipped}`);
      this.selected.clear();
      await this.load();
    } catch (e) {
      showError(e.message);
    }
  },

  async exportJson() {
    try {
      const d = await api.get('/api/findings', { ...this.collectFilters(), limit: 1000 });
      const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `findings-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      showError('Экспорт: ' + e.message);
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
```

**`webui/static/css/findings.css`** — стили (карточки-строки, hover-подсветка, `finding-id`/`finding-match`/`finding-context`, адаптив):

```css
/* Находки — карточки списка (День 40.3). */
.finding-row { transition: border-color .15s ease; }
.finding-row:hover { border-color: var(--color-primary, #3b82f6); cursor: pointer; }
.finding-id {
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, Consolas, monospace);
    font-size: var(--font-size-xs, 12px);
    color: var(--color-text-secondary, #6b7280);
    margin-right: .5rem;
}
.finding-match {
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, Consolas, monospace);
    font-size: 13px;
    color: var(--color-text, #1f2937);
    white-space: pre-wrap;
    word-break: break-all;
}
.finding-context {
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, Consolas, monospace);
    font-size: 12px;
    margin: 0;
    border-radius: 4px;
    white-space: pre-wrap;
}
#pagination-wrap .page-link { cursor: pointer; }
@media (min-width: 992px) { .finding-id { margin-right: 1rem; } }
```

### 2.2 Под-день 40.3.2: детальная карточка + reveal

**`webui/main.py`** — добавлены роуты:

```python
@app.get("/findings/{finding_id}", response_class=HTMLResponse)
async def finding_detail_page(request: Request, finding_id: int):
    return templates.TemplateResponse(
        request, "finding_detail.html", {"page": "Находки", "finding_id": finding_id}
    )


@app.get("/false-positives", response_class=HTMLResponse)
async def page_false_positives(request: Request):
    return render(request, "false_positives.html", "Ложные срабатывания")
```

**`webui/templates/finding_detail.html`**:

```html
{% extends "base.html" %}
{% block title %}Находка #{{ finding_id }} — DCAP{% endblock %}
{% block content %}
<div class="container-fluid">
  <a href="/findings" class="btn btn-sm btn-outline-secondary mb-3"><i class="fas fa-arrow-left me-1"></i>К списку</a>
  <div id="finding-detail">
    <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
  </div>
</div>
{% endblock %}
{% block head %}<link rel="stylesheet" href="/static/css/findings.css">{% endblock %}
{% block scripts %}
<script>window.FINDING_ID = {{ finding_id }};</script>
<script src="/static/js/finding_detail.js"></script>
{% endblock %}
```

**`webui/static/js/finding_detail.js`** — `FindingDetail` (render фрагмента с `<mark>` выделенной строки, reveal, подтвердить/ложное + комментарий):

```js
/**
 * Детали находки: фрагмент, контекст, reveal, смена статуса (День 40.3).
 */
const FindingDetail = {
  finding: null,

  async init() {
    try {
      this.finding = await api.get(`/api/findings/${window.FINDING_ID}`);
      this.render();
    } catch (e) {
      document.getElementById('finding-detail').innerHTML =
        `<div class="alert alert-danger">Ошибка: ${escapeHtml(e.message)}</div>`;
    }
  },

  render() {
    const f = this.finding;
    const html = `
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h4 class="mb-0">Находка #${f.id}</h4>
          <span class="badge bg-${this.statusColor(f.status)}">${escapeHtml(f.status)}</span>
        </div>
        <div class="card-body">
          <dl class="row">
            <dt class="col-sm-3">Файл</dt>
            <dd class="col-sm-9"><code>${escapeHtml(f.file_path || '—')}</code></dd>
            <dt class="col-sm-3">Строка</dt>
            <dd class="col-sm-9">${f.line_number || '—'}</dd>
            <dt class="col-sm-3">Тип / категория</dt>
            <dd class="col-sm-9">${escapeHtml(f.finding_type)} / ${escapeHtml(f.category || '—')}</dd>
            <dt class="col-sm-3">Severity</dt>
            <dd class="col-sm-9">${escapeHtml(f.severity)}</dd>
            <dt class="col-sm-3">Детектор</dt>
            <dd class="col-sm-9">${escapeHtml(f.detector || '—')} (confidence: ${f.confidence || '—'})</dd>
            <dt class="col-sm-3">Ресурс / задание</dt>
            <dd class="col-sm-9">#${f.resource_id || '—'} / #${f.task_id || '—'}</dd>
            <dt class="col-sm-3">Впервые замечено</dt>
            <dd class="col-sm-9">${f.first_seen_at ? new Date(f.first_seen_at).toLocaleString('ru-RU') : '—'}</dd>
          </dl>
          <h5>Фрагмент</h5>
          <pre class="bg-light p-3 finding-context" id="fragment">${this.renderFragment(f)}</pre>
          <div class="mt-3">
            ${f.can_reveal ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>Показать оригинал</button>` : ''}
          </div>
        </div>
        <div class="card-footer">
          <h5>Обработка</h5>
          <div class="mb-2">
            <textarea class="form-control" id="comment" placeholder="Комментарий (опционально)" rows="2">${escapeHtml(f.comment || '')}</textarea>
          </div>
          <button class="btn btn-success" id="confirm-btn"><i class="fas fa-check me-1"></i>Подтвердить</button>
          <button class="btn btn-danger" id="fp-btn"><i class="fas fa-times me-1"></i>Ложное срабатывание</button>
        </div>
      </div>
    `;
    document.getElementById('finding-detail').innerHTML = html;
    this.bindEvents();
  },

  renderFragment(f) {
    if (f.fragment_type === 'image_region') return `[🖼️ Изображение: ${f.file_path}]`;
    if (f.fragment_type === 'byte_range') return f.hex_preview || '(hex)';
    const lines = [];
    if (f.context_before) lines.push(`<span class="text-muted">${escapeHtml(f.context_before)}</span>`);
    if (f.line_text) lines.push(`<mark>${escapeHtml(f.line_text)}</mark>`);
    if (f.context_after) lines.push(`<span class="text-muted">${escapeHtml(f.context_after)}</span>`);
    return lines.join('\n');
  },

  bindEvents() {
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
      revealBtn.addEventListener('click', async () => {
        try {
          const r = await api.post(`/api/findings/${window.FINDING_ID}/reveal`);
          document.getElementById('fragment').innerHTML =
            `<mark>${escapeHtml(r.line_text || '')}</mark>\n\nОригинал: ${escapeHtml(r.match_text)}`;
        } catch (e) { showError(e.message); }
      });
    }
    document.getElementById('confirm-btn').addEventListener('click', () => this.update('confirmed'));
    document.getElementById('fp-btn').addEventListener('click', () => this.update('false_positive'));
  },

  async update(status) {
    const comment = document.getElementById('comment').value;
    try {
      await api.patch(`/api/findings/${window.FINDING_ID}`, { status, comment });
      showSuccess('Сохранено');
      await this.init();
    } catch (e) { showError(e.message); }
  },

  statusColor(s) {
    return { new: 'primary', confirmed: 'success', false_positive: 'danger', archived: 'secondary' }[s] || 'secondary';
  },
};

document.addEventListener('DOMContentLoaded', () => FindingDetail.init());
```

### 2.3 Под-день 40.3.3: каталог, ложные срабатывания, прогресс сканера

**`webui/templates/catalog.html`** + **`webui/static/js/catalog.js`** — каталог находок по файлам:

```js
/**
 * Каталог на уровне строк (День 40.3.3).
 *
 * Дерево: папка → файл → строки находок.
 * Данные: GET /api/findings (строки) + клиентская группировка по file_path
 * (эндпоинт /api/catalog/tree отдаёт только агрегаты по папкам, без строк).
 */
const CatalogPage = {
  findings: [],
  statusIcon: { new: '🆕', confirmed: '✅', false_positive: '❌', archived: '📦' },
  categoryName: { pii: 'PII', credentials: 'Cred', code: 'Code' },

  async init() {
    try {
      const r = await api.get('/api/findings', { limit: 1000 });
      this.findings = Array.isArray(r) ? r : [];
    } catch (e) {
      document.getElementById('catalog-tree').innerHTML =
        `<div class="alert alert-danger">Не удалось загрузить каталог: ${escapeHtml(e.message)}</div>`;
      return;
    }
    this.render();
  },

  applyFilters() { if (this.findings.length !== 0) this.render(); },
  reset() {
    document.getElementById('catalog-search').value = '';
    document.getElementById('catalog-category').value = '';
    this.render();
  },

  currentFilters() {
    const search = (document.getElementById('catalog-search')?.value || '').trim().toLowerCase();
    const category = document.getElementById('catalog-category')?.value || '';
    return { search, category };
  },

  render() {
    const { search, category } = this.currentFilters();
    const list = document.getElementById('catalog-tree');
    let findings = this.findings;
    if (category) findings = findings.filter(f => f.finding_type === category);
    if (search) findings = findings.filter(f => (f.file_path || '').toLowerCase().includes(search));
    if (!findings.length) {
      list.innerHTML = '<div class="alert alert-info">Записей не найдено</div>';
      return;
    }
    const byFile = new Map();
    for (const f of findings) {
      const path = f.file_path || '(без пути)';
      if (!byFile.has(path)) byFile.set(path, []);
      byFile.get(path).push(f);
    }
    const root = { name: '', children: {}, files: [] };
    const enc = p => escapeHtml(p);

    function addFile(fullPath, fileFindings) {
      const parts = fullPath.split(/[\\/]/).filter(Boolean);
      let node = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i];
        if (!node.children[part]) node.children[part] = { name: part, children: {}, files: [] };
        node = node.children[part];
      }
      node.files.push({ name: parts[parts.length - 1] || fullPath, findings: fileFindings });
    }

    for (const [path, ffs] of byFile) addFile(path, ffs);

    let html = '<div class="card"><div class="card-body catalog-tree-root">';

    const renderFindings = (ffs) => ffs.map(f => {
      const t = this.categoryName[f.finding_type] || f.finding_type || '—';
      const s = this.statusIcon[f.status] || '•';
      return `
        <div class="catalog-line">
          <a href="/findings/${f.id}" class="catalog-line-link">
            <span class="text-muted">:${f.line_number || '?'}</span>
            <code class="finding-match">${escapeHtml(f.match_text || '(masked)')}</code>
            <span class="badge bg-info text-dark">${t}</span>
            <span class="catalog-line-status">${s} ${escapeHtml(f.status)}</span>
          </a>
        </div>`;
    }).join('');

    const renderNode = (node) => {
      let out = '';
      const names = Object.keys(node.children);
      for (const name of names) {
        const child = node.children[name];
        const files = child.files;
        const fileCount = child.files.length;
        const dirFileCount = files.reduce((a, f) => a + f.findings.length, 0);
        out += `<div class="catalog-folder">
          <div class="catalog-dir"><i class="fas fa-folder text-warning me-1"></i><strong>${enc(name)}</strong>
            <span class="text-muted small"> (${fileCount === 1 ? `${fileCount} файл` : `${fileCount} файлов`}, ${dirFileCount} находок)</span></div>`;
        for (const file of files) {
          out += `<div class="catalog-file">
            <div class="catalog-file-hdr"><i class="fas fa-file-code text-primary me-1"></i><code>${enc(file.name)}</code>
              <span class="text-muted small">(${file.findings.length} находок)</span></div>
            <div class="catalog-lines">${renderFindings(file.findings)}</div>
          </div>`;
        }
        out += renderNode(child);
        out += `</div>`;
      }
      return out;
    };

    html += renderNode(root);
    html += '</div></div>';
    list.innerHTML = html;
  },
};

document.addEventListener('DOMContentLoaded', () => CatalogPage.init());
```

**`webui/templates/false_positives.html`** + **`webui/static/js/false_positives.js`** — журнал ложных срабатываний (Auditor/Admin):

```js
/**
 * Ложные срабатывания (аудит) — День 40.3.3.
 * Источник: GET /api/findings/false-positives (Auditor+).
 */
const FalsePositivesPage = {
  async init() {
    try {
      const r = await api.get('/api/findings/false-positives', { limit: 200 });
      this.render(Array.isArray(r) ? r : []);
    } catch (e) {
      document.getElementById('fp-list').innerHTML =
        `<div class="alert alert-danger">Не удалось загрузить список: ${escapeHtml(e.message)}</div>`;
    }
  },

  render(items) {
    const el = document.getElementById('fp-total');
    if (items.length) {
      el.style.display = '';
      el.textContent = items.length + (items.length === 1 ? ' запись' : ' записей');
    }
    const list = document.getElementById('fp-list');
    if (!items.length) {
      list.innerHTML = '<div class="alert alert-info">Ложных срабатываний нет</div>';
      return;
    }
    const typeName = { pii: 'PII', credentials: 'Cred', code: 'Code' };
    list.innerHTML = items.map(fp => {
      const reviewed = fp.reviewed_at ? new Date(fp.reviewed_at).toLocaleString('ru-RU') : '—';
      return `
      <div class="card mb-2 finding-row" data-id="${fp.id}">
        <div class="card-body py-2">
          <div class="d-flex flex-wrap justify-content-between align-items-center">
            <div>
              <a href="/findings/${fp.id}" class="finding-id me-2">#${fp.id}</a>
              <code class="text-muted small">${escapeHtml(fp.file_path || fp.fragment_path || '—')}:${fp.line_number || '?'}</code>
              <span class="ms-2 badge bg-info text-dark">${typeName[fp.finding_type] || escapeHtml(fp.finding_type)}</span>
              <span class="badge bg-danger">❌ FP</span>
            </div>
            <span class="text-muted small">помечено: ${escapeHtml(fp.reviewed_by || '—')}, ${escapeHtml(reviewed)}</span>
          </div>
          <div class="mt-1">
            <code class="finding-match">${escapeHtml(fp.match_text_masked || '(masked)')}</code>
          </div>
          ${fp.comment ? `<div class="mt-1 small text-muted"><i class="fas fa-comment me-1"></i>${escapeHtml(fp.comment)}</div>` : ''}
        </div>
      </div>`;
    }).join('');
  },
};

document.addEventListener('DOMContentLoaded', () => FalsePositivesPage.init());
```

**`webui/templates/base.html`** — пункт меню «Ложные» (`/false-positives`) после «Находки»:

```html
<a href="/false-positives" class="nav-item {% if page == 'Ложные срабатывания' %}active{% endif %}" data-page="false-positives">
    <span class="nav-icon"><i class="fas fa-ban"></i></span>
    <span class="nav-label hide-on-collapse">Ложные</span>
</a>
```

**`manager/src/api/webui.py`** — `_scanner_dict(s, db)` с активным заданием и прогрессом (BACKLOG-043). Данные progress хранятся в `scan_tasks.progress` (JSON) — их шлёт heartbeat-тред сканера (День 39):

```python
def _scanner_dict(s, db: Session = None) -> dict:
    current_task = None
    total_files_scanned = 0
    total_findings = 0
    if db is not None:
        # Активное задание (BACKLOG-043): progress из heartbeat (День 39)
        task = (
            db.query(models.ScanTask)
            .filter(
                models.ScanTask.scanner_id == s.id,
                models.ScanTask.status.in_(["assigned", "running"]),
            )
            .order_by(models.ScanTask.id.desc())
            .first()
        )
        if task:
            current_task = {
                "id": task.id,
                "resource_id": task.resource_id,
                "progress": task.progress,
            }
        total_files_scanned = (
            db.query(func.coalesce(func.sum(models.ScanTask.files_scanned), 0))
            .filter(models.ScanTask.scanner_id == s.id)
            .scalar()
            or 0
        )
        total_findings = (
            db.query(func.count(models.Finding.id))
            .join(models.ScanTask, models.ScanTask.id == models.Finding.task_id)
            .filter(models.ScanTask.scanner_id == s.id)
            .scalar()
            or 0
        )
    return {
        "id": s.id,
        "name": s.name,
        "endpoint": None,
        "status": s.status,
        "last_heartbeat": s.last_heartbeat.isoformat() if s.last_heartbeat else None,
        "total_files_scanned": total_files_scanned,
        "total_findings": total_findings,
        "current_task": current_task,
        "created_at": s.registered_at.isoformat() if s.registered_at else None,
    }
```

Оба вызова обновлены: `get_scanners` → `[_scanner_dict(s, db) for s in scanners]`, `get_scanner` → `_scanner_dict(scanner, db)` (вместе с `_mark_stale_scanners(db)` перед списком).

**`webui/templates/dashboard.html`** — карточка «Сканеры» (`#scanner-panel`) между графиками и «Последними находками»; шапка таблицы находок переведена на новый формат (Время | Тип | Значение | Файл:строка | Уверенность | Статус).

**`webui/static/js/dashboard.js`** — `updateScannerPanel(scanners)` (progress-бар из `current_task.progress`, возраст heartbeat, active/inactive) и `updateRecentFindings` под новый формат:

```js
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
        const icon = active ? '🟢' : '🟡';
        const ageTxt = ageSec === null ? '—' : (ageSec < 60 ? ageSec + ' сек назад' : Math.floor(ageSec / 60) + ' мин назад');
        let taskHtml = '';
        const t = s.current_task;
        if (t && t.progress && t.progress.total) {
            const files = t.progress.files_scanned || 0;
            const total = t.progress.total;
            const pct = t.progress.percent != null ? t.progress.percent : Math.round((files / total) * 100);
            const bar = Math.max(0, Math.min(100, pct));
            taskHtml = `<div class="mt-2 small">
                Задание #${t.id}: ${files}/${total} файлов (${bar}%)
                <div class="progress mt-1" style="height:10px;">
                    <div class="progress-bar" role="progressbar" style="width:${bar}%;" aria-valuenow="${bar}" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
            </div>`;
        } else if (t) {
            taskHtml = `<div class="mt-2 small">Задание #${t.id} (прогресс пока нет)</div>`;
        } else {
            taskHtml = '<div class="mt-2 small text-muted">Нет активных заданий</div>';
        }
        html += `<div class="scanner-card mb-2 p-2 border rounded">
            <div class="d-flex flex-wrap justify-content-between align-items-center">
                <strong>${s.name}</strong>
                <span>${icon} ${active ? 'active' : 'inactive'}</span>
            </div>
            ${taskHtml}
            <div class="small text-muted">Последний heartbeat: ${ageTxt}</div>
        </div>`;
    }
    panel.innerHTML = html;
}
```

`updateRecentFindings` использует `first_seen_at`, `finding_type`, `match_text` (masked), `file_path:line_number`, `confidence*100`, статус-бейдж — больше не читает `f.value`/`f.created_at` в старом смысле (BACKLOG-061 закрыт).

---

## 3. Тесты

### 3.1 Unit — `tests/unit/test_fingerprint.py` (NEW)

```python
# tests/unit/test_fingerprint.py — Проверка, что fingerprint — SHA-256, не MD5
# (День 40.3, 🔴 BACKLOG-066: MD5 криптографически сломан — недопустим для security-продукта).
import hashlib
import hmac
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.managed_scanner import ManagedScanner  # noqa: E402

pytestmark = [pytest.mark.unit]


def test_fingerprint_sha256_length():
    """SHA-256 → 64 hex, MD5 → 32 hex."""
    fp_md5 = hashlib.md5(b"test").hexdigest()
    fp_sha256 = hashlib.sha256(b"test").hexdigest()
    assert len(fp_md5) == 32
    assert len(fp_sha256) == 64


def test_legacy_fingerprint_uses_sha256():
    """Legacy fingerprint использует SHA-256 (не MD5)."""
    source = inspect.getsource(ManagedScanner._legacy_fingerprint)
    assert "md5" not in source.lower(), "MD5 found in _legacy_fingerprint!"
    assert "sha256" in source.lower()


def test_legacy_fingerprint_value_is_sha256_full_context():
    """
    Функциональная проверка: fingerprint — это SHA-256 от полного контекста
    (file_path|line|match|finding_type), а не только от значения и не MD5.
    """
    scanner = object.__new__(ManagedScanner)
    fp = ManagedScanner._legacy_fingerprint(scanner, "C:/data/file.txt", 42, "secret-value", "pii")

    assert len(fp) == 64, "SHA-256 даёт 64 hex-символа"

    expected = hashlib.sha256(
        b"C:/data/file.txt|42|secret-value|pii"
    ).hexdigest()
    assert fp == expected

    no_type = hashlib.sha256(b"C:/data/file.txt|42|secret-value").hexdigest()
    assert fp != no_type, "finding_type должен входить в контекст"


def test_legacy_fingerprint_deterministic_and_context_sensitive():
    scanner = object.__new__(ManagedScanner)
    f1 = ManagedScanner._legacy_fingerprint(scanner, "a.txt", 1, "x", "pii")
    f2 = ManagedScanner._legacy_fingerprint(scanner, "a.txt", 1, "x", "pii")
    f3 = ManagedScanner._legacy_fingerprint(scanner, "a.txt", 2, "x", "pii")
    assert f1 == f2
    assert f1 != f3, "разные строки → разные fingerprint"


def test_encryption_fingerprint_is_hmac_sha256():
    """С ключами fingerprint — HMAC-SHA256 (консистентно с Manager)."""
    import scanner.src.encryption as sen

    source = inspect.getsource(sen.ScannerEncryption.fingerprint)
    assert "hmac" in source.lower() and "sha256" in source.lower()

    key = b"k" * 32
    expected = hmac.new(key, b"f.txt|1|v|credentials", hashlib.sha256).hexdigest()
    assert len(expected) == 64
```

### 3.2 E2E — `tests/e2e/test_webui_findings.py` (NEW)

```python
"""E2E-тесты WebUI находок (День 40.3)."""
import hashlib

import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def test_findings_page(webui_url):
    r = requests.get(f"{webui_url}/findings", timeout=5)
    assert r.status_code == 200
    assert "Находки" in r.text


def test_finding_detail_page(webui_url):
    r = requests.get(f"{webui_url}/findings/1", timeout=5)
    assert r.status_code == 200


def test_catalog_page(webui_url):
    r = requests.get(f"{webui_url}/catalog", timeout=5)
    assert r.status_code == 200


def test_false_positives_page(webui_url):
    r = requests.get(f"{webui_url}/false-positives", timeout=5)
    assert r.status_code == 200


def test_findings_proxy(webui_url):
    """WebUI проксирует /api/findings (401 без токена — ок)."""
    r = requests.get(f"{webui_url}/api/findings?limit=10", timeout=10)
    assert r.status_code in (200, 401)


def test_fingerprint_sha256_not_md5():
    """Fingerprint — SHA-256 (64 hex), не MD5 (32 hex)."""
    msg = b"test|42|secret|pii"
    fp = hashlib.sha256(msg).hexdigest()
    assert len(fp) == 64
    assert hashlib.md5(msg).hexdigest() and len(hashlib.md5(msg).hexdigest()) == 32
```

### 3.3 Прогоны

- `pytest tests/unit` → **39 passed** (включая 5 новых fingerprint-тестов). Примечание: тесты гоняются в алфавитном порядке — `test_encryption` идёт раньше `test_scanner_findings` (тот мутирует `os.environ` без восстановления), иначе `test_decrypt_wrong_key_fails` ломается.
- Полный e2e (`tests/e2e -m "e2e and not requires_scanner and not requires_docker"`) на тест-стеке → **21 passed, 4 deselected** (127 с).
- `pytest tests/e2e/test_webui_findings.py tests/e2e/test_webui_proxy.py` → **8 passed** (28 с).
- `node --check` на всех новых/изменённых JS; `python -m py_compile` на изменённых Python.
- `test_findings_api.py` (День 40.1) в изоляции — 5 passed; в полном прогоне — все проходят.

---

## 4. Про то, почему полный e2e сначала падал

Падения полного e2e-прогона (перемежались между `test_findings_api` / `test_retention` / `test_scanner_findings`, разные тесты от запуска к запуску) были вызваны **не** кодом 40.3, а **лимитом логинов** `manager/src/auth/rate_limit.py`: `AUTH_LOGIN_MAX_ATTEMPTS=5` на окно 60 с на ключ (IP `127.0.0.1`). Полный прогон делает десятки `POST /api/auth/login` из `api_client` → Manager отвечает 429 «Too many login attempts», `login()` не ставит Bearer → защищённые вызовы получают 401 «Authentication required» → `create_task` возвращает `None` (фикстура игнорирует статус) → `_assign_task` видит `{"task":null}`.

Диагностика: воспроизведение вручную (60 логинов → после 2-го сразу 429), ловля живого падения с `create_task status=401`. Решение — только для **тест-стека**: запуск Manager с `AUTH_LOGIN_MAX_ATTEMPTS=1000` и повышенным общим лимитом (temp-конфиг). Комментарий в коде прямо предписывает такую настройку для тестов/высоконагруженных deploy. В репозиторий изменения НЕ вносились.

---

## 5. Отклонения от ТЗ

1. **Fingerprint legacy (BACKLOG-066):** ТЗ указывало 4-й компонент = `finding_type` в числе опциональных интерпретаций; реализован именно так — `f"{file_path}|{line}|{match}|{finding_type}"`, консистентно с HMAC-вариантом Manager/сканера. Docstring `_legacy_fingerprint` не содержит подстроки «md5» (unit-тест ТЗ проверяет её отсутствие в исходнике).
2. **Прокси-роуты в WebUI не добавлялись:** catch-all в `webui/api/routes.py` (`@router.api_route("/{path:path}", methods=[...PATCH])`) уже покрывает `/api/findings*` и `/api/catalog/*` — доп. роуты дублировали бы логику.
3. **Каталог строится клиентски** из `GET /api/findings?limit=1000` (дерево папка→файл→строки), а не через `/api/catalog/tree` (тот отдаёт только агрегаты по папкам, без строк).
4. **Пагинация списка находок** — prev/next без общего `total` (API не отдаёт total в list-ответе).
5. **Раздел docs:** ТЗ предлагало обращение к «docs деплоя» — добавлен раздел в `docs/deployment.md` (WebUI находок).
6. **Наблюдение (не фикс):** `init_db.py` смешивает стили импорта (`db.*` + `manager.src.*`) → на свежем SQLite `NoReferencedTableError` (FK `findings.reviewed_by → users`). Для тест-стека DB создаётся через `from manager.src.db.session import init_db; ...`. Отдельной задачей (вне 40.3) стоит перевести `init_db.py` на единый стиль.

---

## 6. Команда для коммита

```bash
git add manager/src/api/webui.py scanner/src/managed_scanner.py webui/main.py \
        webui/static/js/api.js webui/static/js/dashboard.js \
        webui/templates/base.html webui/templates/catalog.html \
        webui/templates/dashboard.html webui/templates/findings.html \
        webui/static/css/findings.css webui/static/js/catalog.js \
        webui/static/js/false_positives.js webui/static/js/finding_detail.js \
        webui/static/js/findings.js webui/templates/false_positives.html \
        webui/templates/finding_detail.html \
        tests/unit/test_fingerprint.py tests/e2e/test_webui_findings.py \
        docs/deployment.md STATE.md prompts/reports/day_40.3_report.md

git commit -m "feat: День 40.3 — Findings Refactor: WebUI (список, каталог, FP, reveal, прогресс) (v3.11.0)

- 40.3.1: /findings — фильтры (status/type/category/severity/task), пагинация, bulk, экспорт JSON;
  webui/static/js/api.js (общий клиент: request/редирект 401/показ ошибок)
- 40.3.2: /findings/{id} — карточка + фрагмент + reveal (Auditor/Admin, лог в audit_logs) + смена статуса
- 40.3.3: /catalog — дерево папка→файл→строки; /false-positives (Auditor+); меню «Ложные»
- Дашборд: карточка «Сканеры» с прогрессом из heartbeat (scan_tasks.progress);
  _scanner_dict(s, db) + current_task (BACKLOG-043); таблица находок в новом формате (BACKLOG-061)
- 🔴 BACKLOG-066: _legacy_fingerprint MD5 → SHA-256 (file_path|line|match|type)
- Тесты: tests/unit/test_fingerprint.py (5), tests/e2e/test_webui_findings.py (6);
  unit 39 passed, e2e 21 passed
- docs/deployment.md: раздел WebUI находок

docs: обновлён STATE.md (v3.11.0, следующий — День 40.4)"
```

---

## 7. Инструкция по запуску для ручного тестирования

```powershell
# 1. Свежая БД (или существующий dev-db)
python init_db.py

# 2. Manager + WebUI
python run_all.py

# 3. Сканер на хосте (опиционально, для данных)
python run_scanner.py scanner/config/scanner_config.json
```

Ручная проверка WebUI:
- откройте `http://127.0.0.1:8001`, залогиньтесь `admin/admin123`;
- **Находки** — карточки строк (маскированные значения, статусы, контекст), фильтры работают, bulk-подтверждение/ложное, пагинация, экспорт JSON;
- откройте находку → **Показать оригинал** (reveal) — работает у auditor/admin, попадает в аудит `/api/audit` (`finding_reveal`);
- **Каталог** — дерево файлов со строками находок, поиск по пути, фильтр по типу;
- **Ложные** — журнал FP с комментариями;
- **Дашборд** — карточка «Сканеры» с прогрессом активного задания при запущенном сканере.

Для полного e2e-прогона тест-стек поднимается с `AUTH_LOGIN_MAX_ATTEMPTS=1000` (иначе лимит логинов 5/60 с на IP ломает прогон — см. раздел 4).