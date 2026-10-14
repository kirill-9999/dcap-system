/**
 * Каталог на уровне строк (День 40.3.3; редизайн 53.4c).
 *
 * Дерево: папка → файл → строки находок.
 * Данные: GET /api/findings (строки) + клиентская группировка по file_path.
 *
 * v3.14.1 (53.4c):
 *   - BUG-210 — пагинация («Показать ещё», X-Total-Count);
 *   - BACKLOG-111 — папки свёрнуты, состояние в URL (#open=…);
 *   - BACKLOG-113 — единый бейдж статуса (statusBadge), без «NEW + new»;
 *   - BACKLOG-115 — ложные срабатывания скрыты по умолчанию;
 *   - BACKLOG-116 — granular-фильтр по типу находки.
 */
const CatalogPage = {
  findings: [],
  total: 0,
  PAGE: 200,
  expanded: null,
  typeOptions: null,

  categoryName: {
    pii: 'PII', credentials: 'Cred', code: 'Code',
  },

  init() {
    this.expanded = new Set();
    this.typeOptions = new Set();
    this.readState();
    this.bind();
    return this.reload();
  },

  bind() {
    const search = document.getElementById('catalog-search');
    search.addEventListener('keyup', (e) => {
      clearTimeout(this._t);
      this._t = setTimeout(() => this.reload(), 350);
    });
    ['catalog-category', 'catalog-status', 'catalog-show-fp'].forEach((id) => {
      document.getElementById(id).addEventListener('change', () => this.reload());
    });
  },

  /* ---------- состояние в URL (BACKLOG-111) ---------- */
  readState() {
    const h = new URLSearchParams((location.hash || '').replace(/^#/, ''));
    document.getElementById('catalog-search').value = h.get('q') || '';
    const cat = h.get('cat') || '';
    document.getElementById('catalog-status').value = h.get('st') || '';
    document.getElementById('catalog-show-fp').checked = h.get('fp') === '1';
    this._pendingCat = cat;
    (h.get('open') || '').split('|').filter(Boolean).forEach((p) => this.expanded.add(p));
  },

  writeState() {
    const p = new URLSearchParams();
    const q = document.getElementById('catalog-search').value.trim();
    const cat = document.getElementById('catalog-category').value;
    const st = document.getElementById('catalog-status').value;
    if (q) p.set('q', q);
    if (cat) p.set('cat', cat);
    if (st) p.set('st', st);
    if (document.getElementById('catalog-show-fp').checked) p.set('fp', '1');
    if (this.expanded.size) p.set('open', Array.from(this.expanded).join('|'));
    const hash = p.toString();
    history.replaceState(null, '', location.pathname + location.search + (hash ? '#' + hash : ''));
  },

  /* ---------- загрузка ---------- */
  params(offset) {
    const p = {
      limit: this.PAGE,
      offset: offset,
      order_by: 'id',
      order: 'asc',
    };
    const q = document.getElementById('catalog-search').value.trim();
    const cat = document.getElementById('catalog-category').value;
    const st = document.getElementById('catalog-status').value;
    if (q) p.search = q;
    if (cat) p.finding_type = cat;
    if (st) p.status = st;
    return p;
  },

  async reload() {
    this.findings = [];
    this.offset = 0;
    const list = document.getElementById('catalog-tree');
    list.innerHTML = '<div class="text-center py-5"><div class="spinner-border"></div></div>';
    await this.loadMore();
  },

  async loadMore() {
    const more = document.getElementById('catalog-more');
    if (more) more.disabled = true;
    try {
      const r = await api.getWithMeta('/api/findings', this.params(this.offset));
      const chunk = Array.isArray(r.data) ? r.data : [];
      this.total = r.total || chunk.length;
      this.offset += chunk.length;
      for (const f of chunk) {
        this.findings.push(f);
        if (f.finding_type) this.typeOptions.add(f.finding_type);
      }
    } catch (e) {
      document.getElementById('catalog-tree').innerHTML =
        `<div class="alert alert-danger">Не удалось загрузить каталог: ${escapeHtml(errorToRussian(e.message))}</div>`;
      return;
    }
    this.buildCategoryOptions();
    this.render();
    if (more) {
      more.style.display = this.findings.length < this.total ? '' : 'none';
      more.disabled = false;
    }
  },

  buildCategoryOptions() {
    const sel = document.getElementById('catalog-category');
    const want = this._pendingCat || '';
    const values = Array.from(this.typeOptions).sort();
    sel.innerHTML = '<option value="">Все</option>' +
      values.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(this.categoryName[v] || v)}</option>`).join('');
    sel.value = values.includes(want) ? want : '';
    this._pendingCat = '';
  },

  /* ---------- фильтрация (клиентская поверх загруженного) ---------- */
  currentFindings() {
    const showFP = document.getElementById('catalog-show-fp').checked;
    const cat = document.getElementById('catalog-category').value;
    const st = document.getElementById('catalog-status').value;
    return this.findings.filter((f) => {
      if (!showFP && f.status === 'false_positive') return false;
      if (cat && f.finding_type !== cat) return false;
      if (st && f.status !== st) return false;
      return true;
    });
  },

  reset() {
    document.getElementById('catalog-search').value = '';
    document.getElementById('catalog-category').value = '';
    document.getElementById('catalog-status').value = '';
    document.getElementById('catalog-show-fp').checked = false;
    this.expanded.clear();
    this.reload();
  },

  expandAll() {
    this.currentFindings().forEach((f) => { for (const p of this._paths(f.file_path)) this.expanded.add(p); });
    this.render();
  },

  collapseAll() {
    this.expanded.clear();
    this.render();
  },

  toggleFolder(path) {
    if (this.expanded.has(path)) this.expanded.delete(path);
    else this.expanded.add(path);
    this.render();
  },

  _paths(fullPath) {
    const parts = String(fullPath || '').split(/[\\/]/).filter(Boolean);
    const out = [];
    let acc = '';
    for (let i = 0; i < parts.length - 1; i++) {
      acc = acc ? acc + '/' + parts[i] : parts[i];
      out.push(acc);
    }
    return out;
  },

  /* ---------- рендер ---------- */
  render() {
    const list = document.getElementById('catalog-tree');
    const findings = this.currentFindings();
    this.writeState();

    const summary = document.getElementById('catalog-summary');
    if (summary) {
      summary.textContent = `Показано находок: ${findings.length}` +
        (findings.length < this.total ? ` из загруженных ${this.findings.length} (всего ${this.total})` : '');
    }

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
    const enc = (p) => escapeHtml(p);
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

    const renderFindings = (ffs) => ffs.map((f) => {
      const t = this.categoryName[f.finding_type] || f.finding_type || '—';
      return `
        <div class="catalog-line">
          <a href="/findings/${f.id}" class="catalog-line-link">
            <span class="text-muted">:${f.line_number || '?'}</span>
            <code class="finding-match">${escapeHtml(f.match_text || '(masked)')}</code>
            <span class="badge bg-info text-dark">${escapeHtml(t)}</span>
            ${statusBadge(f.status)}
          </a>
        </div>`;
    }).join('');

    const renderNode = (node, prefix) => {
      let out = '';
      for (const name of Object.keys(node.children)) {
        const child = node.children[name];
        const path = prefix ? prefix + '/' + name : name;
        const open = this.expanded.has(path);
        const dirFindings = child.files.reduce((a, f) => a + f.findings.length, 0);
        out += `<div class="catalog-folder">
          <div class="catalog-dir" role="button" onclick="CatalogPage.toggleFolder('${escapeHtml(path).replace(/'/g, "\\'")}')">
            <i class="fas fa-chevron-${open ? 'down' : 'right'} me-1"></i>
            <i class="fas fa-folder${open ? '-open' : ''} text-warning me-1"></i><strong>${enc(name)}</strong>
            <span class="text-muted small"> (${child.files.length} файл., ${dirFindings} находок)</span></div>
          <div class="catalog-folder-children" style="display:${open ? '' : 'none'}">`;
        for (const file of child.files) {
          out += `<div class="catalog-file">
            <div class="catalog-file-hdr"><i class="fas fa-file-code text-primary me-1"></i><code>${enc(file.name)}</code>
              <span class="text-muted small">(${file.findings.length} находок)</span></div>
            <div class="catalog-lines">${renderFindings(file.findings)}</div>
          </div>`;
        }
        out += renderNode(child, path);
        out += '</div></div>';
      }
      return out;
    };

    list.innerHTML = `<div class="card"><div class="card-body catalog-tree-root">${renderNode(root, '')}</div></div>`;
  },
};

document.addEventListener('DOMContentLoaded', async () => {
  if (typeof whenSessionReady === 'function') {
    try { await whenSessionReady(); } catch (e) { /* */ }
  }
  CatalogPage.init();
});
