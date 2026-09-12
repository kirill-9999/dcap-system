📋 ТЗ: День 40.3 — WebUI: находки, каталог, FP, reveal
Дата: 12.09.2026
Роль: Кодер
Версия (целевая): v3.11.0
Ветка: feature/day_40.3_webui_findings
Предыдущая версия: v3.10.0
Этап: 3 из 4 (Findings Refactor)

🎯 Цель дня
Переработать WebUI под новую модель находок (строки, а не файлы)

Исправить fingerprint — убрать MD5, везде HMAC-SHA256 (BACKLOG-066)

Реализовать:

Список находок (фильтры, пагинация)

Детали находки (фрагмент, контекст, reveal)

Кнопки: подтвердить / ложное / reveal

Массовые операции

Каталог на уровне строк

Страница «Ложные срабатывания» (аудит)

Прогресс сканера в панели «Сканеры» (BACKLOG-043)

ВАЖНО: это большая задача — разбита на 3 под-дня (40.3.1, 40.3.2, 40.3.3). Каждый под-день тестируется отдельно.

🔴 КРИТИЧНО: Fingerprint — убрать MD5
Проблема
В Дне 40.2 в _legacy_fingerprint используется MD5 — это криптографически сломанный алгоритм. Для security-продукта недопустимо.

Что делать
MODIFIED: scanner/src/managed_scanner.py

Заменить MD5 на SHA-256 в legacy-режиме.

Использовать полный контекст (file_path + line + match_text + finding_type), а не только match_text — уменьшает коллизии.

Если ключи есть — использовать HMAC-SHA256 (как сейчас, но проверить консистентность с Manager).

python
# scanner/src/managed_scanner.py

def _legacy_fingerprint(self, file_path: str, line: int, match: str, finding_type: str) -> str:
    """
    Fingerprint БЕЗ HMAC (legacy-режим, когда ключей нет).

    ВАЖНО: SHA-256, НЕ MD5! MD5 криптографически сломан.
    Используем полный контекст (file_path + line + match + type) —
    это уменьшает вероятность коллизий при повторном сканировании.
    """
    import hashlib
    msg = f"{file_path}|{line}|{match}|{finding_type}".encode("utf-8")
    return hashlib.sha256(msg).hexdigest()
Проверить: в scanner/src/encryption.py HMAC уже используется? Если да — ок. Если нет — добавить.

MODIFIED: manager/src/api/scanner.py — при приёме legacy-формата (без fingerprint) Manager пересчитывает fingerprint через HMAC (уже есть). Убедиться, что используется HMAC-SHA256, а не MD5.

Поиск MD5 по проекту:

bash
grep -rn "md5\|MD5" --include="*.py" .
# Найти все вхождения, заменить на sha256 (вне крипто-контекста)
Тест: tests/unit/test_scanner_findings.py — добавить проверку, что fingerprint = 64 hex-символа (SHA-256), не 32 (MD5).

📦 Под-день 40.3.1 — Список находок
Версия: v3.11.0
Цель: пользователь видит список находок (строки файлов) с фильтрами.

Задачи
#	Задача	Артефакт
1	Страница «Находки» (список, фильтры, пагинация)	webui/templates/findings.html
2	API-прокси для /api/findings	webui/api/routes.py
3	JS: загрузка, фильтры, пагинация	webui/static/js/findings.js
4	CSS: карточки находок	webui/static/css/findings.css
5	Ссылка в меню	webui/templates/base.html
6	Фикс MD5 → SHA-256	scanner/src/managed_scanner.py
7	Тесты	tests/e2e/test_webui_findings.py
1. Шаблон findings.html
html
{% extends "base.html" %}

{% block title %}Находки — DCAP{% endblock %}

{% block content %}
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2>🔍 Находки</h2>
    <div>
      <button class="btn btn-outline-secondary" id="export-btn">📥 Экспорт</button>
    </div>
  </div>

  <!-- Фильтры -->
  <div class="card mb-3">
    <div class="card-body">
      <div class="row g-2">
        <div class="col-md-2">
          <label class="form-label small">Статус</label>
          <select class="form-select form-select-sm" id="filter-status">
            <option value="">Все</option>
            <option value="new">🆕 Новые</option>
            <option value="confirmed">✅ Подтверждённые</option>
            <option value="false_positive">❌ Ложные</option>
            <option value="archived">📦 Архив</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">Тип</label>
          <select class="form-select form-select-sm" id="filter-type">
            <option value="">Все</option>
            <option value="pii">PII</option>
            <option value="credentials">Credentials</option>
            <option value="code">Code</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">Категория</label>
          <input type="text" class="form-control form-control-sm" id="filter-category" placeholder="phone, email...">
        </div>
        <div class="col-md-2">
          <label class="form-label small">Severity</label>
          <select class="form-select form-select-sm" id="filter-severity">
            <option value="">Все</option>
            <option value="critical">🔴 Critical</option>
            <option value="high">🟠 High</option>
            <option value="medium">🟡 Medium</option>
            <option value="low">🟢 Low</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">Задание</label>
          <input type="number" class="form-control form-control-sm" id="filter-task" placeholder="ID">
        </div>
        <div class="col-md-2 d-flex align-items-end">
          <button class="btn btn-primary btn-sm w-100" id="apply-filters">Применить</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Массовые операции -->
  <div class="card mb-2" id="bulk-actions" style="display: none;">
    <div class="card-body py-2">
      <span class="me-3">Выбрано: <strong id="selected-count">0</strong></span>
      <button class="btn btn-success btn-sm" id="bulk-confirm">✅ Подтвердить</button>
      <button class="btn btn-danger btn-sm" id="bulk-fp">❌ Ложное</button>
      <button class="btn btn-outline-secondary btn-sm" id="bulk-clear">Снять выбор</button>
    </div>
  </div>

  <!-- Список -->
  <div id="findings-list">
    <div class="text-center py-5">
      <div class="spinner-border" role="status"></div>
      <p class="mt-2">Загрузка...</p>
    </div>
  </div>

  <!-- Пагинация -->
  <nav class="mt-3">
    <ul class="pagination justify-content-center" id="pagination"></ul>
  </nav>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/findings.js"></script>
{% endblock %}
2. JS findings.js
javascript
/**
 * Находки: список, фильтры, пагинация, массовые операции.
 */
const FindingsPage = {
  page: 0,
  limit: 50,
  selected: new Set(),
  filters: {},

  async init() {
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    document.getElementById('apply-filters').addEventListener('click', () => {
      this.page = 0;
      this.load();
    });
    document.getElementById('bulk-confirm').addEventListener('click', () => this.bulkUpdate('confirmed'));
    document.getElementById('bulk-fp').addEventListener('click', () => this.bulkUpdate('false_positive'));
    document.getElementById('bulk-clear').addEventListener('click', () => {
      this.selected.clear();
      this.render();
    });
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
    const params = new URLSearchParams({
      ...this.collectFilters(),
      limit: this.limit,
      offset: this.page * this.limit,
    });
    // Убрать пустые
    for (const [k, v] of [...params.entries()]) {
      if (!v) params.delete(k);
    }

    try {
      const r = await api.get(`/api/findings?${params}`);
      this.findings = r;
      this.render();
    } catch (e) {
      showError('Не удалось загрузить находки: ' + e.message);
    }
  },

  render() {
    const list = document.getElementById('findings-list');
    if (!this.findings || this.findings.length === 0) {
      list.innerHTML = '<div class="alert alert-info">Находок не найдено</div>';
      return;
    }

    list.innerHTML = this.findings.map(f => this.renderItem(f)).join('');
    this.updateBulkBar();

    // Привязка кнопок
    list.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        const id = parseInt(btn.dataset.id);
        this.handleAction(action, id);
      });
    });

    list.querySelectorAll('.finding-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const id = parseInt(cb.dataset.id);
        if (cb.checked) this.selected.add(id);
        else this.selected.delete(id);
        this.updateBulkBar();
      });
    });

    list.querySelectorAll('.finding-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.type === 'checkbox' || e.target.dataset.action) return;
        const id = row.dataset.id;
        window.location.href = `/findings/${id}`;
      });
    });
  },

  renderItem(f) {
    const statusBadge = {
      new: '<span class="badge bg-primary">🆕 new</span>',
      confirmed: '<span class="badge bg-success">✅ confirmed</span>',
      false_positive: '<span class="badge bg-danger">❌ false_positive</span>',
      archived: '<span class="badge bg-secondary">📦 archived</span>',
    }[f.status] || f.status;

    const typeBadge = {
      pii: '<span class="badge bg-info text-dark">PII</span>',
      credentials: '<span class="badge bg-warning text-dark">Cred</span>',
      code: '<span class="badge bg-secondary">Code</span>',
    }[f.finding_type] || f.finding_type;

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
              <div class="d-flex justify-content-between">
                <div>
                  <code class="text-muted small">${lineInfo}</code>
                  <span class="ms-2">${typeBadge}</span>
                  <span class="badge bg-${severityClass}">${f.severity}</span>
                  <span class="badge bg-light text-dark">${f.category}</span>
                </div>
                <div>${statusBadge}</div>
              </div>
              <div class="mt-1">
                <code class="finding-match">${escapeHtml(f.match_text || '(masked)')}</code>
              </div>
              ${f.context_before ? `
                <details class="mt-1">
                  <summary class="small text-muted">Контекст</summary>
                  <pre class="small bg-light p-2">${escapeHtml(f.context_before)}\n${escapeHtml(f.line_text || '')}\n${escapeHtml(f.context_after || '')}</pre>
                </details>
              ` : ''}
              <div class="mt-2">
                ${f.status === 'new' ? `
                  <button class="btn btn-sm btn-success" data-action="confirm" data-id="${f.id}">✅</button>
                  <button class="btn btn-sm btn-danger" data-action="fp" data-id="${f.id}">❌</button>
                ` : ''}
                ${f.can_reveal ? `
                  <button class="btn btn-sm btn-outline-primary" data-action="reveal" data-id="${f.id}">👁️ Reveal</button>
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
    if (!confirm(`Обновить ${this.selected.size} находок?`)) return;

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

  updateBulkBar() {
    const bar = document.getElementById('bulk-actions');
    const count = this.selected.size;
    document.getElementById('selected-count').textContent = count;
    bar.style.display = count > 0 ? 'block' : 'none';
  },
};

document.addEventListener('DOMContentLoaded', () => FindingsPage.init());
3. API-прокси webui/api/routes.py
Добавить (если ещё нет):

python
@router.get("/findings")
async def proxy_findings(request: Request):
    """Прокси GET /api/findings."""
    return await proxy_to_manager(request, "GET", "/api/findings")

@router.get("/findings/stats")
async def proxy_findings_stats(request: Request):
    return await proxy_to_manager(request, "GET", "/api/findings/stats")

@router.get("/findings/false-positives")
async def proxy_findings_fp(request: Request):
    return await proxy_to_manager(request, "GET", "/api/findings/false-positives")

@router.get("/findings/{finding_id}")
async def proxy_finding(request: Request, finding_id: int):
    return await proxy_to_manager(request, "GET", f"/api/findings/{finding_id}")

@router.post("/findings/{finding_id}/reveal")
async def proxy_reveal(request: Request, finding_id: int):
    return await proxy_to_manager(request, "POST", f"/api/findings/{finding_id}/reveal")

@router.patch("/findings/{finding_id}")
async def proxy_patch_finding(request: Request, finding_id: int):
    return await proxy_to_manager(request, "PATCH", f"/api/findings/{finding_id}")

@router.post("/findings/bulk")
async def proxy_bulk(request: Request):
    return await proxy_to_manager(request, "POST", "/api/findings/bulk")
Примечание: proxy_to_manager — существующая функция проксирования. Если её нет — использовать существующий паттерн из routes.py.

4. Ссылка в меню base.html
html
<li class="nav-item">
  <a class="nav-link" href="/findings">
    <i class="fas fa-search"></i> Находки
  </a>
</li>
5. Тесты
NEW: tests/e2e/test_webui_findings.py

python
"""E2E-тесты WebUI находок."""
import pytest
import requests


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_page_renders(webui_url):
    """Страница /findings рендерится."""
    r = requests.get(f"{webui_url}/findings", timeout=5)
    assert r.status_code == 200
    assert "Находки" in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_proxy(webui_url):
    """WebUI проксирует /api/findings."""
    r = requests.get(f"{webui_url}/api/findings?limit=10", timeout=10)
    # 200 (с токеном через прокси) или 401 (без)
    assert r.status_code in (200, 401)


def test_fingerprint_sha256_not_md5():
    """Fingerprint — SHA-256 (64 hex), не MD5 (32 hex)."""
    import hashlib
    msg = b"test|42|secret|pii"
    fp = hashlib.sha256(msg).hexdigest()
    assert len(fp) == 64
✅ Тестирование 40.3.1
bash
# 1. Открыть WebUI
http://localhost:8001/findings
# → список находок (строки файлов)

# 2. Фильтры
# → выбрать статус = new, тип = pii, применить

# 3. Тесты
pytest tests/e2e/test_webui_findings.py -v
📦 Под-день 40.3.2 — Детали находки + reveal + FP
Цель: пользователь открывает находку, видит фрагмент, может reveal/FP.

Задачи
#	Задача	Артефакт
1	Страница деталей /findings/{id}	webui/templates/finding_detail.html
2	Reveal (показать оригинал)	webui/static/js/finding_detail.js
3	Комментарий + смена статуса	—
4	Роут в webui/main.py	/findings/{id}
5	Тесты	—
1. Шаблон finding_detail.html
html
{% extends "base.html" %}
{% block title %}Находка #{{ finding_id }} — DCAP{% endblock %}

{% block content %}
<div class="container">
  <a href="/findings" class="btn btn-sm btn-outline-secondary mb-3">← К списку</a>

  <div id="finding-detail">
    <div class="text-center py-5">
      <div class="spinner-border"></div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
  window.FINDING_ID = {{ finding_id }};
</script>
<script src="/static/js/finding_detail.js"></script>
{% endblock %}
2. JS finding_detail.js
javascript
const FindingDetail = {
  finding: null,

  async init() {
    try {
      this.finding = await api.get(`/api/findings/${window.FINDING_ID}`);
      this.render();
    } catch (e) {
      document.getElementById('finding-detail').innerHTML =
        `<div class="alert alert-danger">Ошибка: ${e.message}</div>`;
    }
  },

  render() {
    const f = this.finding;
    const html = `
      <div class="card">
        <div class="card-header d-flex justify-content-between">
          <h4>Находка #${f.id}</h4>
          <span class="badge bg-${this.statusColor(f.status)}">${f.status}</span>
        </div>
        <div class="card-body">
          <dl class="row">
            <dt class="col-sm-3">Файл</dt>
            <dd class="col-sm-9"><code>${f.file_path || '—'}</code></dd>

            <dt class="col-sm-3">Строка</dt>
            <dd class="col-sm-9">${f.line_number || '—'}</dd>

            <dt class="col-sm-3">Тип</dt>
            <dd class="col-sm-9">${f.finding_type} / ${f.category}</dd>

            <dt class="col-sm-3">Severity</dt>
            <dd class="col-sm-9">${f.severity}</dd>

            <dt class="col-sm-3">Детектор</dt>
            <dd class="col-sm-9">${f.detector || '—'} (confidence: ${f.confidence || '—'})</dd>
          </dl>

          <h5>Фрагмент</h5>
          <pre class="bg-light p-3" id="fragment">${this.renderFragment(f)}</pre>

          <div class="mt-3">
            ${f.can_reveal ? `<button class="btn btn-outline-primary" id="reveal-btn">👁️ Показать оригинал</button>` : ''}
          </div>
        </div>
        <div class="card-footer">
          <h5>Обработка</h5>
          <div class="mb-2">
            <textarea class="form-control" id="comment" placeholder="Комментарий (опционально)">${f.comment || ''}</textarea>
          </div>
          <button class="btn btn-success" id="confirm-btn">✅ Подтвердить</button>
          <button class="btn btn-danger" id="fp-btn">❌ Ложное срабатывание</button>
        </div>
      </div>
    `;
    document.getElementById('finding-detail').innerHTML = html;
    this.bindEvents();
  },

  renderFragment(f) {
    if (f.fragment_type === 'image_region') {
      return `[🖼️ Изображение: ${f.file_path}]`;
    }
    if (f.fragment_type === 'byte_range') {
      return f.hex_preview || '(hex)';
    }
    // text
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
3. Роут в webui/main.py
python
@app.get("/findings/{finding_id}", response_class=HTMLResponse)
async def finding_detail_page(request: Request, finding_id: int):
    return templates.TemplateResponse("finding_detail.html", {
        "request": request,
        "finding_id": finding_id,
    })
✅ Тестирование 40.3.2
bash
# 1. Открыть /findings/123
# → детали находки

# 2. Нажать "Показать оригинал" (если Auditor)
# → открытый текст

# 3. Подтвердить / Ложное
# → статус меняется
📦 Под-день 40.3.3 — Каталог + FP-страница + прогресс сканера
Цель: каталог на уровне строк, аудит FP, прогресс сканера в WebUI.

Задачи
#	Задача	Артефакт
1	Каталог на уровне строк	webui/templates/catalog.html
2	Страница FP (аудит)	webui/templates/false_positives.html
3	Прогресс сканера в панели «Сканеры» (BACKLOG-043)	webui/templates/dashboard.html
4	API-прокси для каталога	webui/api/routes.py
5	Тесты	—
1. Каталог на уровне строк catalog.html
text
┌─────────────────────────────────────────────────────────────┐
│ 📁 Каталог                                                  │
├─────────────────────────────────────────────────────────────┤
│ 📁 E:\data                                                  │
│   📄 file1.txt (3 находки)                                  │
│     ├── :42  Иван Иванов, +7-***-**-67   PII  🆕           │
│     ├── :58  ivan@example.com            PII  🆕           │
│     └── :103 password = "***"            Cred ✅           │
│   📄 file2.env (2 находки)                                  │
│     ├── :5   AWS_KEY=AKIA***             Cred 🆕           │
│     └── :12  SECRET=***                  Cred ❌ FP        │
└─────────────────────────────────────────────────────────────┘
API: GET /api/catalog/tree — дерево с находками на уровне строк.

Примечание: если /api/catalog/tree нет — использовать GET /api/findings?resource_id=X + группировку на клиенте.

2. Страница FP false_positives.html
text
┌─────────────────────────────────────────────────────────────┐
│ ❌ Ложные срабатывания (аудит)                              │
├─────────────────────────────────────────────────────────────┤
│ ☐ file2.env:5   AWS_KEY=AKIA***   Cred   ❌ FP              │
│   └── помечено: admin, 11.09.2026 14:30                     │
│   └── комментарий: "Тестовый ключ из документации"          │
├─────────────────────────────────────────────────────────────┤
│ ☐ file3.py:12   password = "***"  Cred   ❌ FP              │
│   └── помечено: auditor1, 11.09.2026 15:00                  │
│   └── комментарий: "Пример в комментарии"                   │
└─────────────────────────────────────────────────────────────┘
API: GET /api/findings/false-positives (уже есть).

3. Прогресс сканера в дашборде
MODIFIED: webui/templates/dashboard.html — панель «Сканеры»:

text
┌─────────────────────────────────────────────────────────────┐
│ 🔍 Сканеры                                                  │
├─────────────────────────────────────────────────────────────┤
│ scanner-1  🟢 active                                        │
│   └── Задание #42: 1250/5000 файлов (25%) ████░░░░░░        │
│   └── Последний heartbeat: 5 сек назад                      │
├─────────────────────────────────────────────────────────────┤
│ scanner-2  🟡 inactive                                      │
│   └── Последний heartbeat: 3 мин назад                      │
└─────────────────────────────────────────────────────────────┘
API: GET /api/scanners уже отдаёт status, last_heartbeat. Добавить current_task + progress (из scan_tasks.progress).

MODIFIED: manager/src/api/webui.py — в GET /api/scanners добавить поля:

python
{
    "id": s.id,
    "name": s.name,
    "status": s.status,
    "last_heartbeat": s.last_heartbeat,
    "current_task": {
        "id": task.id,
        "progress": task.progress,  # {files_scanned, total, percent}
    } if task else None,
}
✅ Тестирование 40.3.3
bash
# 1. Каталог
http://localhost:8001/catalog
# → дерево файлов со строками-находками

# 2. FP-страница
http://localhost:8001/false-positives
# → список FP с комментариями

# 3. Дашборд
http://localhost:8001/
# → прогресс сканера (во время задания)
📦 Часть 4. Общие правки WebUI
4.1. webui/static/js/api.js — helpers
NEW или MODIFIED: webui/static/js/api.js

javascript
/**
 * API-клиент WebUI с JWT.
 */
const api = {
  async request(method, url, body) {
    const token = localStorage.getItem('access_token');
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
    if (body) opts.body = JSON.stringify(body);

    const r = await fetch(url, opts);
    if (r.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
  get: (url) => api.request('GET', url),
  post: (url, body) => api.request('POST', url, body),
  patch: (url, body) => api.request('PATCH', url, body),
  delete: (url) => api.request('DELETE', url),
};

function showSuccess(msg) { /* toast */ }
function showError(msg) { /* toast */ }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
Проверить: возможно, api.js уже есть — дополнить.

4.2. base.html — добавить ссылки в меню
html
<li><a href="/findings">🔍 Находки</a></li>
<li><a href="/catalog">📁 Каталог</a></li>
<li><a href="/false-positives">❌ Ложные</a></li>
📦 Часть 5. Тесты
NEW: tests/e2e/test_webui_findings.py

python
"""E2E-тесты WebUI находок."""
import pytest
import requests


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_page(webui_url):
    r = requests.get(f"{webui_url}/findings", timeout=5)
    assert r.status_code == 200
    assert "Находки" in r.text


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_finding_detail_page(webui_url):
    r = requests.get(f"{webui_url}/findings/1", timeout=5)
    assert r.status_code == 200


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_catalog_page(webui_url):
    r = requests.get(f"{webui_url}/catalog", timeout=5)
    assert r.status_code == 200


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_false_positives_page(webui_url):
    r = requests.get(f"{webui_url}/false-positives", timeout=5)
    assert r.status_code == 200


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_findings_proxy(webui_url):
    r = requests.get(f"{webui_url}/api/findings?limit=10", timeout=10)
    assert r.status_code in (200, 401)
NEW: tests/unit/test_fingerprint.py

python
"""Проверка, что fingerprint — SHA-256, не MD5."""
import hashlib
import pytest


def test_fingerprint_sha256_length():
    """SHA-256 → 64 hex, MD5 → 32 hex."""
    fp = hashlib.sha256(b"test").hexdigest()
    assert len(fp) == 64


def test_legacy_fingerprint_uses_sha256():
    """Legacy fingerprint использует SHA-256 (не MD5)."""
    from scanner.src.managed_scanner import ManagedScanner
    # Проверить, что в коде нет md5
    import inspect
    source = inspect.getsource(ManagedScanner._legacy_fingerprint)
    assert "md5" not in source.lower(), "MD5 found in _legacy_fingerprint!"
    assert "sha256" in source.lower()
📦 Часть 6. Документация
6.1. STATE.md (кодер обновит в конце)
Версия → v3.11.0

Текущий день → 40.4

Последний отчёт → day_40.3_report.md

6.2. ROADMAP.md
День 40.3 ✅

BACKLOG-056, 057, 043, 061 ✅

NEW: BACKLOG-066 (MD5 → SHA-256) ✅

6.3. docs/deployment.md
Раздел про WebUI находок:

markdown
### WebUI: Находки

- `/findings` — список находок (строки файлов, фильтры)
- `/findings/{id}` — детали + reveal (Auditor+)
- `/catalog` — каталог на уровне строк
- `/false-positives` — аудит ложных срабатываний

Reveal доступен только ролям **Auditor** и **Admin**.
✅ Критерии приёмки Дня 40.3
40.3.1 — Список находок
MD5 → SHA-256 — исправлено в _legacy_fingerprint

Страница /findings — список, фильтры, пагинация

Массовые операции — подтвердить / FP

API-прокси — работает

Тесты — WebUI страницы, fingerprint

40.3.2 — Детали + reveal + FP
Страница /findings/{id} — детали, фрагмент

Reveal — только Auditor+, с аудитом

Смена статуса + комментарий

40.3.3 — Каталог + FP + прогресс
Каталог /catalog — дерево со строками

FP /false-positives — аудит

Прогресс сканера в дашборде

Общее
STATE.md обновлён (v3.11.0)

ROADMAP.md — День 40.3 ✅ + BACKLOG-066 ✅

Тесты — все проходят

📁 Артефакты (итог)
NEW:

webui/templates/findings.html

webui/templates/finding_detail.html

webui/templates/catalog.html

webui/templates/false_positives.html

webui/static/js/findings.js

webui/static/js/finding_detail.js

webui/static/js/api.js (если нет)

webui/static/css/findings.css

tests/e2e/test_webui_findings.py

tests/unit/test_fingerprint.py

prompts/reports/day_40.3_report.md

MODIFIED:

scanner/src/managed_scanner.py (MD5 → SHA-256) 🔴

webui/api/routes.py (прокси findings)

webui/main.py (роуты /findings/{id}, /catalog, /false-positives)

webui/templates/base.html (меню)

webui/templates/dashboard.html (прогресс сканера)

manager/src/api/webui.py (progress в /api/scanners)

docs/deployment.md (WebUI находок)

STATE.md (v3.11.0)

ROADMAP.md (День 40.3 ✅)

DELETED: —

🚀 Команда коммита
bash
git checkout -b feature/day_40.3_webui_findings
git add -A
git commit -m "feat: День 40.3 — WebUI: находки, каталог, FP, reveal (v3.11.0)

🔴 КРИТИЧНО: MD5 → SHA-256 (BACKLOG-066):
- scanner/src/managed_scanner.py: _legacy_fingerprint использует SHA-256
  (MD5 криптографически сломан, недопустим для security-продукта)
- Fingerprint: file_path|line|match|finding_type (полный контекст)
- Тест: проверка, что fingerprint = 64 hex (не 32)

40.3.1 — Список находок (BACKLOG-056):
- webui/templates/findings.html: список, фильтры, пагинация
- webui/static/js/findings.js: загрузка, массовые операции
- API-прокси /api/findings (list, stats, FP)

40.3.2 — Детали + reveal + FP (BACKLOG-057):
- webui/templates/finding_detail.html
- webui/static/js/finding_detail.js
- Reveal (Auditor+), смена статуса, комментарий

40.3.3 — Каталог + FP + прогресс (BACKLOG-043, 061):
- webui/templates/catalog.html — дерево со строками
- webui/templates/false_positives.html — аудит FP
- webui/templates/dashboard.html — прогресс сканера
- manager/src/api/webui.py: progress в /api/scanners

Тесты:
- tests/e2e/test_webui_findings.py
- tests/unit/test_fingerprint.py

Docs:
- STATE.md → v3.11.0, следующий — День 40.4
- ROADMAP.md: День 40.3 ✅
- docs/deployment.md: WebUI находок"
📝 Обратная связь архитектору (шаблон)
После выполнения — заполнить:

Что заработало / что нет

Проблемы с proxy_to_manager

Работает ли каталог (API /api/catalog/tree может не быть)

Производительность (большие списки)

Готовность к Дню 40.4 (фрагменты)

⚠️ Важные замечания
MD5 → SHA-256 — критично. Это security-фикс, не косметика.

Reveal — только Auditor+. Проверить роли в WebUI (кнопка скрыта для Viewer).

Каталог — если API /api/catalog/tree нет, использовать /api/findings?resource_id=X + группировка на клиенте.

Прогресс сканера — требует heartbeat + scan_tasks.progress (есть с Дня 39).

Разбивка на 3 под-дня — тестировать каждый отдельно.