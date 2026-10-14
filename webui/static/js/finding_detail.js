/**
 * Р”РµС‚Р°Р»Рё РЅР°С…РѕРґРєРё: С„СЂР°РіРјРµРЅС‚, РєРѕРЅС‚РµРєСЃС‚, reveal, СЃРјРµРЅР° СЃС‚Р°С‚СѓСЃР° (Р”РµРЅСЊ 40.3).
 */
// 53.4e (BUG-126): id РЅР°С…РѕРґРєРё Р±РµСЂС‘Рј РёР· data-Р°С‚СЂРёР±СѓС‚Р° (Р±РµР· inline <script>).
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
        `<div class="alert alert-danger">РћС€РёР±РєР°: ${escapeHtml(errorToRussian(e.message))}</div>`;
    }
  },

  // BACKLOG-112 (v3.14.1): В«Рљ СЃРїРёСЃРєСѓВ» РІРµРґС‘С‚ Рє РёСЃС‚РѕС‡РЅРёРєСѓ РїРµСЂРµС…РѕРґР° вЂ”
  // РєР°С‚Р°Р»РѕРі (/catalog), СЃРїРёСЃРѕРє РЅР°С…РѕРґРѕРє (/findings) РёР»Рё Р›РѕР¶РЅС‹Рµ СЃСЂР°Р±Р°С‚С‹РІР°РЅРёСЏ.
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
          <h4 class="mb-0">РќР°С…РѕРґРєР° #${f.id}</h4>
          <span class="badge bg-${this.statusColor(f.status)}">${statusRu}</span>
        </div>
        <div class="card-body">
          <dl class="row">
            <dt class="col-sm-3">Р¤Р°Р№Р»</dt>
            <dd class="col-sm-9"><code>${escapeHtml(f.file_path || 'вЂ”')}</code></dd>

            <dt class="col-sm-3">РЎС‚СЂРѕРєР°</dt>
            <dd class="col-sm-9">${f.line_number || 'вЂ”'}</dd>

            <dt class="col-sm-3">РўРёРї / РєР°С‚РµРіРѕСЂРёСЏ</dt>
            <dd class="col-sm-9">${escapeHtml(f.finding_type)} / ${escapeHtml(f.category || 'вЂ”')}</dd>

            <dt class="col-sm-3">Severity</dt>
            <dd class="col-sm-9">${escapeHtml(f.severity)}</dd>

            <dt class="col-sm-3">Р”РµС‚РµРєС‚РѕСЂ</dt>
            <dd class="col-sm-9">${escapeHtml(f.detector || 'вЂ”')} (confidence: ${f.confidence || 'вЂ”'})</dd>

            <dt class="col-sm-3">Р РµСЃСѓСЂСЃ / Р·Р°РґР°РЅРёРµ</dt>
            <dd class="col-sm-9">#${f.resource_id || 'вЂ”'} / #${f.task_id || 'вЂ”'}</dd>

            <dt class="col-sm-3">Р’РїРµСЂРІС‹Рµ Р·Р°РјРµС‡РµРЅРѕ</dt>
            <dd class="col-sm-9">${f.first_seen_at ? formatDate(f.first_seen_at) : 'вЂ”'}</dd>

            <dt class="col-sm-3">РџРѕСЃР»РµРґРЅРµРµ СЃРєР°РЅРёСЂРѕРІР°РЅРёРµ</dt>
            <dd class="col-sm-9">${f.last_seen_at ? formatDate(f.last_seen_at) : 'вЂ”'}</dd>

            <dt class="col-sm-3">РЁРёС„СЂРѕРІР°РЅРёРµ</dt>
            <dd class="col-sm-9">
              ${f.has_encrypted ? '<span class="text-success">Р’РєР»СЋС‡РµРЅРѕ</span>' : '<span class="text-muted">Р’С‹РєР»СЋС‡РµРЅРѕ</span>'}
              ${f.encryption_key_id ? `<span class="text-muted small"> (РєР»СЋС‡: ${escapeHtml(f.encryption_key_id)})</span>` : ''}
            </dd>

            <dt class="col-sm-3">РџСЂРѕСЃРјРѕС‚СЂ РѕСЂРёРіРёРЅР°Р»Р°</dt>
            <dd class="col-sm-9">${f.can_reveal ? '<span class="text-success">Р”РѕСЃС‚СѓРїРµРЅ (Auditor+)</span>' : '<span class="text-muted">РќРµРґРѕСЃС‚СѓРїРµРЅ</span>'}</dd>
          </dl>

          <h5>Р¤СЂР°РіРјРµРЅС‚</h5>
          <div id="fragment">${this.renderFragment(f)}</div>
          <div class="small text-muted mt-1" id="fragment-meta"></div>

          <div class="mt-3">
            ${canAudit && f.can_reveal && f.fragment_type !== 'image_region'
              ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>РџРѕРєР°Р·Р°С‚СЊ РѕСЂРёРіРёРЅР°Р»</button>`
              : ''}
          </div>
        </div>
        <div class="card-footer">
          <h5>РћР±СЂР°Р±РѕС‚РєР°</h5>
          <div class="mb-2">
            <textarea class="form-control" id="comment" placeholder="РљРѕРјРјРµРЅС‚Р°СЂРёР№ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)" rows="2">${escapeHtml(f.comment || '')}</textarea>
          </div>
          ${canAudit
            ? `<button class="btn btn-success" id="confirm-btn"><i class="fas fa-check me-1"></i>РџРѕРґС‚РІРµСЂРґРёС‚СЊ</button>
               <button class="btn btn-danger" id="fp-btn"><i class="fas fa-times me-1"></i>Р›РѕР¶РЅРѕРµ СЃСЂР°Р±Р°С‚С‹РІР°РЅРёРµ</button>
               <button class="btn btn-warning" id="dup-btn"><i class="fas fa-clone me-1"></i>Р”СѓР±Р»РёРєР°С‚</button>
               <button class="btn btn-outline-secondary" id="archive-btn"><i class="fas fa-box-archive me-1"></i>Р’ Р°СЂС…РёРІ</button>`
            : '<span class="text-muted small">РР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃР° РґРѕСЃС‚СѓРїРЅРѕ Auditor+</span>'}
        </div>
      </div>
    `;
    document.getElementById('finding-detail').innerHTML = html;
    if (document.getElementById('hex-dump')) this.loadHexFragment();
    this.loadImageFragment();
    if (canAudit) this.bindEvents();
  },

  /**
   * BUG-088 (TASK-055, v3.13.22): С„СЂР°РіРјРµРЅС‚ РіСЂСѓР·РёРј С‡РµСЂРµР· fetch СЃ Bearer вЂ”
   * <img src="/api/findings/{id}/fragment"> СѓС…РѕРґРёР» Р±РµР· Р·Р°РіРѕР»РѕРІРєР° Authorization
   * (JWT Р»РµР¶РёС‚ РІ localStorage, Р° Set-Cookie Manager'Р° РїСЂРѕРєСЃРё РЅРµ РїСЂРѕР±СЂР°СЃС‹РІР°РµС‚)
   * Рё РїРѕР»СѓС‡Р°Р» 401: РІСЃС‚СЂРѕРµРЅРЅС‹Рµ С„СЂР°РіРјРµРЅС‚С‹ BACKLOG-086 Р±С‹Р»Рё РЅРµ РІРёРґРЅС‹.
   * Blob-URL СЃРЅРёРјР°РµС‚ РїСЂРѕР±Р»РµРјСѓ Рё РґР»СЏ image/png, Рё РґР»СЏ hex-РґР°РјРїР°.
   */
  async loadImageFragment() {
    const img = document.getElementById('fragment-image');
    if (!img) return;
    const meta = document.getElementById('fragment-meta');

    // BUG-138: РѕР±СЂР°Р±РѕС‚РєР° РѕС€РёР±РєРё С‡РµСЂРµР· DOM API (addEventListener),
    // РЅРµ С‡РµСЂРµР· onerror-Р°С‚СЂРёР±СѓС‚ СЃ HTML РІРЅСѓС‚СЂРё.
    img.addEventListener('error', () => {
      img.style.display = 'none';
      if (!meta) return;
      const div = document.createElement('div');
      div.className = 'alert alert-warning';
      div.textContent = 'Р¤СЂР°РіРјРµРЅС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ';
      meta.insertAdjacentElement('beforebegin', div);
    }, { once: true });

    try {
      const r = await fetch(`/api/findings/${FINDING_ID}/fragment`,
                            { headers: api._headers() });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const blob = await r.blob();
      img.src = URL.createObjectURL(blob);
      img.style.display = '';
      // BUG-087 (TASK-054): Р·Р°РіРѕР»РѕРІРєРё X-Fragment-Mode/X-Fragment-Hash С‚РµРїРµСЂСЊ
      // РґРѕС…РѕРґСЏС‚ РґРѕ Р±СЂР°СѓР·РµСЂР° С‡РµСЂРµР· РїСЂРѕРєСЃРё WebUI.
      const mode = r.headers.get('X-Fragment-Mode');
      const hash = r.headers.get('X-Fragment-Hash');
      const parts = [];
      if (mode) parts.push('СЂРµР¶РёРј: ' + mode);
      if (hash) parts.push('SHA-256: ' + hash.slice(0, 16) + 'вЂ¦');
      if (meta) meta.textContent = parts.join(' В· ');
    } catch (e) {
      img.style.display = 'none';
      if (meta) meta.textContent = 'Р¤СЂР°РіРјРµРЅС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ: ' + e.message;
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
      el.textContent = 'РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё: ' + e.message;
    }
  },

  renderFragment(f) {
    if (f.fragment_type === 'image_region') {
      return f.has_fragment || f.bounding_box
        ? `<img id="fragment-image" class="img-fluid finding-image"
                  style="display:none"
                  alt="Р¤СЂР°РіРјРµРЅС‚ РЅР°С…РѕРґРєРё #${f.id}"
                  data-bbox='${escapeHtml(JSON.stringify(f.bounding_box || {}))}'>`
        : '<span class="text-muted">(РёР·РѕР±СЂР°Р¶РµРЅРёРµ Р±РµР· РІС‹СЂРµР·Р°РЅРЅРѕРіРѕ С„СЂР°РіРјРµРЅС‚Р°)</span>';
    }
    if (f.fragment_type === 'byte_range') {
      return f.hex_preview
        ? `<pre class="finding-hex">${escapeHtml(f.hex_preview)}</pre>`
        : (f.has_fragment || f.byte_offset !== null && f.byte_offset !== undefined
            ? `<pre class="finding-hex" id="hex-dump">Р—Р°РіСЂСѓР·РєР°вЂ¦</pre>`
            : '<span class="text-muted">(hex-С„СЂР°РіРјРµРЅС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ)</span>');
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
      // BUG-140: toggle + РєСЌС€, С‡С‚РѕР±С‹ РЅРµ СЃРїР°РјРёС‚СЊ Р°СѓРґРёС‚.
      // РћСЂРёРіРёРЅР°Р»СЊРЅРѕРµ СЃРѕРґРµСЂР¶РёРјРѕРµ #fragment СЃРѕС…СЂР°РЅСЏРµРј Рё РІРѕСЃСЃС‚Р°РЅР°РІР»РёРІР°РµРј.
      let revealed = false;
      let cachedReveal = null;
      const fragmentOriginalHTML = document.getElementById('fragment').innerHTML;

      revealBtn.addEventListener('click', async () => {
        const box = document.getElementById('fragment');
        if (!box) return;

        if (revealed) {
          // Р’РѕР·РІСЂР°С‚ Рє РјР°СЃРєРёСЂРѕРІР°РЅРЅРѕРјСѓ РІРёРґСѓ вЂ” Р±РµР· POST, РёР· РєСЌС€Р° HTML.
          box.innerHTML = fragmentOriginalHTML;
          revealed = false;
          revealBtn.innerHTML = '<i class="fas fa-eye me-1"></i>РџРѕРєР°Р·Р°С‚СЊ РѕСЂРёРіРёРЅР°Р»';
          return;
        }

        revealBtn.disabled = true;
        try {
          if (!cachedReveal) {
            cachedReveal = await api.post(`/api/findings/${FINDING_ID}/reveal`);
          }
          const r = cachedReveal;

          // BACKLOG-110 (v3.14.1): reveal Р±РѕР»СЊС€Рµ РЅРµ С‚РµСЂСЏРµС‚ РєРѕРЅС‚РµРєСЃС‚ вЂ”
          // СЃС‚СЂРѕРєР° СЃ РїРѕРґСЃРІРµС‚РєРѕР№ РїРѕРєР°Р·С‹РІР°РµС‚СЃСЏ РІРјРµСЃС‚Рµ СЃ context_before/after
          // (РєРѕРЅС‚РµРєСЃС‚ РѕС‚РґР°С‘С‚СЃСЏ Manager'РѕРј РІ masked-РІРёРґРµ).
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
          rows.push(lineHtml || (r.match_text ? `<mark>${esc(r.match_text)}</mark>` : '<span class="text-muted">(РЅРµРґРѕСЃС‚СѓРїРЅРѕ)</span>'));
          if (r.context_after) rows.push(`<span class="text-muted">${esc(r.context_after)}</span>`);

          box.innerHTML =
            `<div class="alert alert-warning py-2 small">РћСЂРёРіРёРЅР°Р» РїРѕРєР°Р·Р°РЅ (РѕРїРµСЂР°С†РёСЏ Р·Р°РїРёСЃР°РЅР° РІ Р°СѓРґРёС‚${r.revealed_by ? ' В· ' + esc(r.revealed_by) : ''})</div>` +
            `<pre class="reveal-block p-2 small mb-1">${rows.join('\n')}</pre>`;

          revealed = true;
          revealBtn.innerHTML = '<i class="fas fa-eye-slash me-1"></i>РЎРєСЂС‹С‚СЊ РѕСЂРёРіРёРЅР°Р»';
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
      showSuccess('РЎРѕС…СЂР°РЅРµРЅРѕ');
      await this.init();
    } catch (e) {
      showError(errorToRussian(e.message));
    }
  },

  statusColor(s) {
    return { new: 'primary', confirmed: 'success', false_positive: 'danger', archived: 'secondary', duplicate: 'warning' }[s] || 'secondary';
  },

  // BUG-207 (v3.14.0): СЃС‚Р°С‚СѓСЃ РЅР°С…РѕРґРєРё РЅР° СЂСѓСЃСЃРєРѕРј.
  statusName(s) {
    return { new: 'РЅРѕРІРѕРµ', confirmed: 'РїРѕРґС‚РІРµСЂР¶РґРµРЅРѕ', false_positive: 'Р»РѕР¶РЅРѕРµ', archived: 'Р°СЂС…РёРІ', duplicate: 'РґСѓР±Р»РёРєР°С‚' }[s] || s;
  },
};

document.addEventListener('DOMContentLoaded', () => FindingDetail.init());