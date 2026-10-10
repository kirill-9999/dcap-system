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
          <div id="fragment">${this.renderFragment(f)}</div>
          <div class="small text-muted mt-1" id="fragment-meta"></div>

          <div class="mt-3">
            ${f.can_reveal && f.fragment_type !== 'image_region'
              ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>Показать оригинал</button>`
              : ''}
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
    this.loadImageFragment();
    this.bindEvents();
  },

  /**
   * BUG-088 (TASK-055, v3.13.22): фрагмент грузим через fetch с Bearer —
   * <img src="/api/findings/{id}/fragment"> уходил без заголовка Authorization
   * (JWT лежит в localStorage, а Set-Cookie Manager'а прокси не пробрасывает)
   * и получал 401: встроенные фрагменты BACKLOG-086 были не видны.
   * Blob-URL снимает проблему и для image/png, и для hex-дампа.
   */
  async loadImageFragment() {
    const img = document.getElementById('fragment-image');
    if (!img) return;
    const meta = document.getElementById('fragment-meta');

    // BUG-138: обработка ошибки через DOM API (addEventListener),
    // не через onerror-атрибут с HTML внутри.
    img.addEventListener('error', () => {
      img.style.display = 'none';
      if (!meta) return;
      const div = document.createElement('div');
      div.className = 'alert alert-warning';
      div.textContent = 'Фрагмент недоступен';
      meta.insertAdjacentElement('beforebegin', div);
    }, { once: true });

    try {
      const r = await fetch(`/api/findings/${window.FINDING_ID}/fragment`,
                            { headers: api._headers() });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const blob = await r.blob();
      img.src = URL.createObjectURL(blob);
      img.style.display = '';
      // BUG-087 (TASK-054): заголовки X-Fragment-Mode/X-Fragment-Hash теперь
      // доходят до браузера через прокси WebUI.
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
      // BUG-140: toggle + кэш, чтобы не спамить аудит.
      // Оригинальное содержимое #fragment сохраняем и восстанавливаем.
      let revealed = false;
      let cachedReveal = null;
      const fragmentOriginalHTML = document.getElementById('fragment').innerHTML;

      revealBtn.addEventListener('click', async () => {
        const box = document.getElementById('fragment');
        if (!box) return;

        if (revealed) {
          // Возврат к маскированному виду — без POST, из кэша HTML.
          box.innerHTML = fragmentOriginalHTML;
          revealed = false;
          revealBtn.innerHTML = '<i class="fas fa-eye me-1"></i>Показать оригинал';
          return;
        }

        revealBtn.disabled = true;
        try {
          if (!cachedReveal) {
            cachedReveal = await api.post(`/api/findings/${window.FINDING_ID}/reveal`);
          }
          const r = cachedReveal;

          // Убираем дублирование line_text / match_text:
          // если match входит в line — подсвечиваем match внутри line.
          let blockHtml;
          const line = r.line_text || '';
          const match = r.match_text || '';
          if (line && match && line.includes(match)) {
            const escaped = escapeHtml(line);
            const escapedMatch = escapeHtml(match);
            const highlighted = escaped.replace(
              escapedMatch,
              `<mark>${escapedMatch}</mark>`
            );
            blockHtml = `<pre class="reveal-block p-2 small mb-1">${highlighted}</pre>`;
          } else if (line) {
            blockHtml = `<pre class="reveal-block p-2 small mb-1">${escapeHtml(line)}</pre>`;
          } else if (match) {
            blockHtml = `<div><code>${escapeHtml(match)}</code></div>`;
          } else {
            blockHtml = `<div class="text-muted">(недоступно)</div>`;
          }

          box.innerHTML =
            `<div class="alert alert-warning py-2 small">Оригинал показан (операция записана в аудит)</div>` +
            blockHtml;

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