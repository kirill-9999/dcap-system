// webui/static/js/auth.js
// Хранение JWT в localStorage и отправка через заголовок Authorization (Bearer).
// Прокси WebUI форвардит этот заголовок в Manager, который валидирует токен.

// BUG-216 (v3.14.0): перевод ошибок бэкенда на русский.
function errorToRussian(detail) {
    if (detail === null || detail === undefined || detail === '') return detail;
    const msg = String(detail);
    const map = {
        'Invalid credentials': 'Неверный логин или пароль',
        'Current password is incorrect': 'Неверный текущий пароль',
        'Passwords do not match': 'Пароли не совпадают',
        'Cannot delete yourself': 'Вы не можете удалить себя',
        'Cannot disable yourself': 'Вы не можете заблокировать себя',
    };
    if (map[msg]) return map[msg];
    if (/^Required roles:/i.test(msg)) return 'Недостаточно прав. Обратитесь к администратору';
    return msg;
}

const Auth = {
    TOKEN_KEY: "dcap_access_token",

    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    setToken(token) {
        if (token) {
            localStorage.setItem(this.TOKEN_KEY, token);
        } else {
            localStorage.removeItem(this.TOKEN_KEY);
        }
    },

    isAuthenticated() {
        return !!this.getToken();
    },

    authHeaders() {
        const token = this.getToken();
        return token ? { "Authorization": `Bearer ${token}` } : {};
    },

    async login(username, password) {
        const r = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            throw new Error(data.detail || "Неверные учётные данные");
        }
        this.setToken(data.access_token);
        return data.user || {};
    },

    async logout() {
        try {
            await fetch("/api/auth/logout", {
                method: "POST",
                headers: this.authHeaders(),
            });
        } catch (e) {
            // игнорируем сетевые ошибки при выходе
        }
        this.setToken(null);
        window.location.href = "/login";
    },

    async me() {
        const r = await fetch("/api/auth/me", { headers: this.authHeaders() });
        if (!r.ok) {
            this.setToken(null);
            return null;
        }
        return r.json();
    },

    // Проверка авторизации для защиты страниц (редирект на /login если 401)
    async check() {
        const r = await fetch("/api/auth/check", { headers: this.authHeaders() });
        if (!r.ok && window.location.pathname !== "/login") {
            window.location.href = "/login";
            return false;
        }
        return true;
    },
};
