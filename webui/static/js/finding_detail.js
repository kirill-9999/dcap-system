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

            <dt class="col-sm-3">Последнее сканирование</dt>
            <dd class="col-sm-9">${f.last_seen_at ? new Date(f.last_seen_at).toLocaleString('ru-RU') : '—'}</dd>

            <dt class="col-sm-3">Шифрование</dt>
            <dd class="col-sm-9">
              ${f.has_encrypted ? '<span class="text-success">Включено</span>' : '<span class="text-muted">Выключено</span>'}
              ${f.encryption_key_id ? `<span class="text-muted small"> (ключ: ${escapeHtml(f.encryption_key_id)})</span>` : ''}
            </dd>

            <dt class="col-sm-3">Просмотр оригинала</dt>
            <dd class="col-sm-9">${f.can_reveal ? '<span class="text-success">Доступен (Auditor+)</span>' : '<span class="text-muted">Недоступен</span>'}</dd>
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
    if (document.getElementById('hex-dump')) this.loadHexFragment();
    this.bindEvents();
  },

  async loadHexFragment() {
    const el = document.getElementById('hex-dump');
    if (!el) return;
    try {
      const r = await fetch(`/api/findings/${window.FINDING_ID}/fragment?format=hex`,
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
        ? `<img src="/api/findings/${f.id}/fragment"
                 class="img-fluid finding-image"
                 alt="Фрагмент находки #${f.id}"
                 data-bbox='${JSON.stringify(f.bounding_box || {})}'
                 onerror="this.style.display='none'; this.insertAdjacentHTML('afterend','<div class=\'alert alert-warning\'>Фрагмент недоступен</div>')">`
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
      revealBtn.addEventListener('click', async () => {
        try {
          const r = await api.post(`/api/findings/${window.FINDING_ID}/reveal`);
          document.getElementById('fragment').innerHTML =
            `<mark>${escapeHtml(r.line_text || '')}</mark>\n\nОригинал: ${escapeHtml(r.match_text)}`;
        } catch (e) {
          showError(e.message);
        }
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
    } catch (e) {
      showError(e.message);
    }
  },

  statusColor(s) {
    return { new: 'primary', confirmed: 'success', false_positive: 'danger', archived: 'secondary' }[s] || 'secondary';
  },
};

document.addEventListener('DOMContentLoaded', () => FindingDetail.init());