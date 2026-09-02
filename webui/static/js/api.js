const api = {
    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        const headers = (typeof Auth !== 'undefined') ? Auth.authHeaders() : {};
        const r = await fetch(url.toString(), { headers });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    },
    async post(endpoint, data = {}) {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof Auth !== 'undefined') Object.assign(headers, Auth.authHeaders());
        const r = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(data) });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    },
    async put(endpoint, data = {}) {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof Auth !== 'undefined') Object.assign(headers, Auth.authHeaders());
        const r = await fetch(endpoint, { method: 'PUT', headers, body: JSON.stringify(data) });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    },
    async delete(endpoint) {
        const headers = (typeof Auth !== 'undefined') ? Auth.authHeaders() : {};
        const r = await fetch(endpoint, { method: 'DELETE', headers });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    }
};
