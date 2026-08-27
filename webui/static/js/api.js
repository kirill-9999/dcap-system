const api = {
    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        const r = await fetch(url.toString());
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    },
    async post(endpoint, data = {}) {
        const r = await fetch(endpoint, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    },
    async delete(endpoint) {
        const r = await fetch(endpoint, { method: 'DELETE' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    }
};
