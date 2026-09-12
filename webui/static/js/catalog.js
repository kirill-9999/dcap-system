/**
 * Каталог на уровне строк (День 40.3.3).
 *
 * Дерево: папка → файл → строки находок.
 * Данные: GET /api/findings (строки) + клиентская группировка по file_path
 * (эндпоинт /api/catalog/tree отдаёт только агрегаты по папкам, без строк).
 */
const CatalogPage = {
  findings: [],

  statusIcon: {
    new: '🆕', confirmed: '✅', false_positive: '❌', archived: '📦',
  },

  categoryName: {
    pii: 'PII', credentials: 'Cred', code: 'Code',
  },

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

  applyFilters() {
    if (this.findings.length === 0) return;
    this.render();
  },

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

    // Группировка по файлам
    const byFile = new Map();
    for (const f of findings) {
      const path = f.file_path || '(без пути)';
      if (!byFile.has(path)) byFile.set(path, []);
      byFile.get(path).push(f);
    }

    // Строим дерево папок
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