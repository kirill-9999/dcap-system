/**
 * Детали находки: фрагмент, контекст, reveal, смена статуса (День 40.3).
 */
const FINDING_ID = (function () {
  const el = document.getElementById('findingRoot');
  return el ? parseInt(el.dataset.findingId, 10) : NaN;
})();

const FindingDetail = {
  finding: null,

  async init() {
    this.applyBackLink();
    try {
      this.finding = await api.get(`/api/findings/${FINDING_ID}`);
      if (typeof whenSessionReady === 'function') {
        try { await whenSessionReady(); } catch (e) { /* */ }
      }
      this.canAudit = typeof RBAC !== 'undefined' && RBAC.isAuditor();
      this.render();
    } catch (e) {
      document.getElementById('finding-detail').innerHTML =
        `<div class="alert alert-danger">Ошибка: ${escapeHtml(errorToRussian(e.message))}</div>`;
    }
  },

  applyBackLink() {
    const el = document.getElementById('back-link');
    if (!el) return;
    const ref = document.referrer || '';
    let href = '/findings';
    if (ref.includes('/catalog')) href = '/catalog';
    else if (ref.includes('/false-positives')) href = '/false-positives';
    el.setAttribute('href', href);
  },

  render() {
    const f = this.finding;
    const canAudit = this.canAudit;
    const statusRu = this.statusName(f.status);
    const html = `
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h4 class="mb-0">Находка #${f.id}</h4>
          <span class="badge bg-${this.statusColor(f.status)}">${statusRu}</span>
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
            <dd class="col-sm-9">${f.first_seen_at ? formatDate(f.first_seen_at) : '—'}</dd>

            <dt class="col-sm-3">Последнее сканирование</dt>
            <dd class="col-sm-9">${f.last_seen_at ? formatDate(f.last_seen_at) : '—'}</dd>

            <dt class="col-sm-3">Шифрование</dt>
            <dd class="col-sm-9">
              ${f.has_encrypted ? '<span class="text-success">Включено</span>' : '<span class="text-muted">Выключено</span>'}
              ${f.encryption_key_id ? `<span class="text-muted small"> (ключ: ${escapeHtml(f.encryption_key_id)})</span>` : ''}
            </dd>

            <dt class="col-sm-3">Просмотр оригинала</dt>
            <dd class="col-sm-9">${f.can_reveal ? '<span class="text-success">Доступен (Auditor+)</span>' : '<span class="text-muted">Недоступен</span>'}</dd>
          </dl>

          <h5>Фрагмент</h5>
          <div id="fragment">${this.renderFragment(f)}</div>
          <div class="small text-muted mt-1" id="fragment-meta"></div>

          <div class="mt-3">
            ${canAudit && f.can_reveal && f.fragment_type !== 'image_region'
              ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>Показать оригинал</button>`
              : ''}
          </div>
        </div>
        <div class="card-footer">
          <h5>Обработка</h5>
          <div class="mb-2">
            <textarea class="form-control" id="comment" placeholder="Комментарий (опционально)" rows="2">${escapeHtml(f.comment || '')}</textarea>
          </div>
          ${canAudit
            ? `<button class="btn btn-success" id="confirm-btn"><i class="fas fa-check me-1"></i>Подтвердить</button>
               <button class="btn btn-danger" id="fp-btn"><i class="fas fa-times me-1"></i>Ложное срабатывание</button>
               <button class="btn btn-warning" id="dup-btn"><i class="fas fa-clone me-1"></i>Дубликат</button>
               <button class="btn btn-outline-secondary" id="archive-btn"><i class="fas fa-box-archive me-1"></i>В архив</button>`
            : '<span class="text-muted small">Изменение статуса доступно Auditor+</span>'}
        </div>
      </div>
    `;
    document.getElementById('finding-detail').innerHTML = html;
    if (document.getElementById('hex-dump')) this.loadHexFragment();
    this.loadImageFragment();
    if (canAudit) this.bindEvents();
  },

  async loadImageFragment() {
    const img = document.getElementById('fragment-image');
    if (!img) return;
    const meta = document.getElementById('fragment-meta');

    img.addEventListener('error', () => {
      img.style.display = 'none';
      if (!meta) return;
      const div = document.createElement('div');
      div.className = 'alert alert-warning';
      div.textContent = 'Фрагмент недоступен';
      meta.insertAdjacentElement('beforebegin', div);
    }, { once: true });

    try {
      const r = await fetch(`/api/findings/${FINDING_ID}/fragment`,
                            { headers: api._headers() });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const blob = await r.blob();
      img.src = URL.createObjectURL(blob);
      img.style.display = '';
      const mode = r.headers.get('X-Fragment-Mode');
      const hash = r.headers.get('X-Fragment-Hash');
      const parts = [];
      if (mode) parts.push('режим: ' + mode);
      if (hash) parts.push('SHA-256: ' + hash.slice(0, 16) + '…');
      if (meta) meta.textContent = parts.join(' · ');
    } catch (e) {
      img.style.display = 'none';
      if (meta) meta.textContent = 'Фрагмент недоступен: ' + e.message;
    }
  },

  async loadHexFragment() {
    const el = document.getElementById('hex-dump');
    if (!el) return;
    try {
      const r = await fetch(`/api/findings/${FINDING_ID}/fragment?format=hex`,
                            { headers: api._headers() });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      el.textContent = await r.text();
    } catch (e) {
      el.textContent = 'Ошибка загрузки: ' + e.message;
    }
  },

  renderFragment(f) {
    if (f.fragment_type === 'image_region') {
      return f.has_fragment || f.bounding_box
        ? `<img id="fragment-image" class="img-fluid finding-image"
                  style="display:none"
                  alt="Фрагмент находки #${f.id}"
                  data-bbox='${escapeHtml(JSON.stringify(f.bounding_box || {}))}'>`
        : '<span class="text-muted">(изображение без вырезанного фрагмента)</span>';
    }
    if (f.fragment_type === 'byte_range') {
      return f.hex_preview
        ? `<pre class="finding-hex">${escapeHtml(f.hex_preview)}</pre>`
        : (f.has_fragment || f.byte_offset !== null && f.byte_offset !== undefined
            ? `<pre class="finding-hex" id="hex-dump">Загрузка…</pre>`
            : '<span class="text-muted">(hex-фрагмент недоступен)</span>');
    }
    const lines = [];
    if (f.context_before) lines.push(`<span class="text-muted">${escapeHtml(f.context_before)}</span>`);
    if (f.line_text) lines.push(`<mark>${escapeHtml(f.line_text)}</mark>`);
    if (f.context_after) lines.push(`<span class="text-muted">${escapeHtml(f.context_after)}</span>`);
    return lines.join('\n');
  },

  bindEvents() {
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
      let revealed = false;
      let cachedReveal = null;
      const fragmentOriginalHTML = document.getElementById('fragment').innerHTML;

      revealBtn.addEventListener('click', async () => {
        const box = document.getElementById('fragment');
        if (!box) return;

        if (revealed) {
          box.innerHTML = fragmentOriginalHTML;
          revealed = false;
          revealBtn.innerHTML = '<i class="fas fa-eye me-1"></i>Показать оригинал';
          return;
        }

        revealBtn.disabled = true;
        try {
          if (!cachedReveal) {
            cachedReveal = await api.post(`/api/findings/${FINDING_ID}/reveal`);
          }
          const r = cachedReveal;
          const esc = (s) => escapeHtml(s == null ? '' : s);
          const markLine = (line, match) => {
            if (!line) return '';
            const escLine = esc(line);
            if (match && line.includes(match)) {
              return escLine.replace(esc(match), `<mark>${esc(match)}</mark>`);
            }
            return escLine;
          };
          const rows = [];
          if (r.context_before) rows.push(`<span class="text-muted">${esc(r.context_before)}</span>`);
          const lineHtml = markLine(r.line_text || '', r.match_text || '');
          rows.push(lineHtml || (r.match_text ? `<mark>${esc(r.match_text)}</mark>` : '<span class="text-muted">(недоступно)</span>'));
          if (r.context_after) rows.push(`<span class="text-muted">${esc(r.context_after)}</span>`);

          box.innerHTML =
            `<div class="alert alert-warning py-2 small">Оригинал показан (операция записана в аудит${r.revealed_by ? ' · ' + esc(r.revealed_by) : ''})</div>` +
            `<pre class="reveal-block p-2 small mb-1">${rows.join('\n')}</pre>`;

          revealed = true;
          revealBtn.innerHTML = '<i class="fas fa-eye-slash me-1"></i>Скрыть оригинал';
        } catch (e) {
          showError(e.message);
        } finally {
          revealBtn.disabled = false;
        }
      });
    }

    document.getElementById('confirm-btn').addEventListener('click', () => this.update('confirmed'));
    document.getElementById('fp-btn').addEventListener('click', () => this.update('false_positive'));
    document.getElementById('dup-btn')?.addEventListener('click', () => this.update('duplicate'));
    document.getElementById('archive-btn')?.addEventListener('click', () => this.update('archived'));
  },

  async update(status) {
    const comment = document.getElementById('comment').value;
    try {
      await api.patch(`/api/findings/${FINDING_ID}`, { status, comment });
      showSuccess('Сохранено');
      await this.init();
    } catch (e) {
      showError(errorToRussian(e.message));
    }
  },

  statusColor(s) {
    return { new: 'primary', confirmed: 'success', false_positive: 'danger', archived: 'secondary', duplicate: 'warning' }[s] || 'secondary';
  },

  statusName(s) {
    return { new: 'новое', confirmed: 'подтверждено', false_positive: 'ложное', archived: 'архив', duplicate: 'дубликат' }[s] || s;
  },
};

document.addEventListener('DOMContentLoaded', () => FindingDetail.init());