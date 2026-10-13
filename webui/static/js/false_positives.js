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
      const reviewed = fp.reviewed_at ? formatDate(fp.reviewed_at) : '—';
      const reviewedBy = fp.reviewed_by_username || fp.reviewed_by || '—';
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
            <div class="d-flex align-items-center gap-2">
              <span class="text-muted small">помечено: ${escapeHtml(reviewedBy)}, ${escapeHtml(reviewed)}</span>
              <button class="btn btn-sm btn-outline-success restore-fp" data-id="${fp.id}"><i class="fas fa-undo me-1"></i>Восстановить</button>
            </div>
          </div>
          <div class="mt-1">
            <code class="finding-match">${escapeHtml(fp.match_text_masked || '(masked)')}</code>
          </div>
          ${fp.comment ? `<div class="mt-1 small text-muted"><i class="fas fa-comment me-1"></i>${escapeHtml(fp.comment)}</div>` : ''}
        </div>
      </div>`;
    }).join('');
    document.querySelectorAll('.restore-fp').forEach(btn =>
      btn.addEventListener('click', () => this.restore(parseInt(btn.dataset.id, 10))));
  },

  async restore(id) {
    try {
      await api.patch(`/api/findings/${id}`, { status: 'new', comment: 'Возвращено из ложных срабатываний' });
      showSuccess('Находка возвращена в /findings');
      await this.init();
    } catch (e) {
      showError(e.message);
    }
  },
};

document.addEventListener('DOMContentLoaded', () => FalsePositivesPage.init());