// BUG-216 (v3.14.0): перевод ошибок бэкенда на русский.
// Определение errorToRussian — в auth.js (нужен и на /login, где api.js не грузится).

const api = {
    _headers() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof Auth !== 'undefined') Object.assign(headers, Auth.authHeaders());
        return headers;
    },

    _handleErrors(r) {
        if (r.status === 401) {
            if (typeof Auth !== 'undefined') Auth.setToken(null);
            if (window.location.pathname !== '/login') window.location.href = '/login';
        }
        // BUG-213/BUG-256 (v3.14.3): не хватает прав — сообщаем причину и
        // уводим на главную (раньше редирект был молчаливым).
        if (r.status === 403) {
            if (typeof showToast === 'function') {
                showToast('Недостаточно прав', 'error');
            }
            setTimeout(() => {
                if (window.location.pathname !== '/') {
                    window.location.href = '/';
                }
            }, 1000);
        }
        return r;
    },

    async request(method, endpoint, data) {
        const opts = { method, headers: this._headers() };
        if (data !== undefined) opts.body = JSON.stringify(data);
        const r = await fetch(endpoint, opts);
        this._handleErrors(r);
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText || ('HTTP ' + r.status) }));
            throw new Error(errorToRussian(err.detail || ('HTTP ' + r.status)));
        }
        // BUG-150/фронт (53.4c): 204 No Content / пустое тело — не JSON.
        if (r.status === 204) return null;
        const text = await r.text();
        if (!text) return null;
        try { return JSON.parse(text); } catch (e) { return null; }
    },

    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        return this.request('GET', url.toString());
    },

    /** GET с метаданными ответа (X-Total-Count), День 40.4. */
    async getWithMeta(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        const r = await fetch(url.toString(), { headers: this._headers() });
        this._handleErrors(r);
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText || ('HTTP ' + r.status) }));
            throw new Error(errorToRussian(err.detail || ('HTTP ' + r.status)));
        }
        const text = await r.text();
        let data = [];
        try { data = JSON.parse(text); } catch (e) { /* не JSON — вернём пусто */ }
        return { data, total: parseInt(r.headers.get('X-Total-Count') || '0', 10) };
    },
    async post(endpoint, data = {}) {
        return this.request('POST', endpoint, data);
    },
    async put(endpoint, data = {}) {
        return this.request('PUT', endpoint, data);
    },
    async patch(endpoint, data = {}) {
        return this.request('PATCH', endpoint, data);
    },
    async delete(endpoint) {
        return this.request('DELETE', endpoint);
    }
};

function showSuccess(msg) { showToast(msg, 'success'); }
function showError(msg) { showToast(msg, 'error'); }
function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}
