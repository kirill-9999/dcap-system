const usernameEl = document.getElementById('username');
const passwordEl = document.getElementById('password');
const errorBox = document.getElementById('errorBox');
const loginBtn = document.getElementById('loginBtn');

// Режим аутентификации (для подсказки)
// BACKLOG-119 (v3.13.41): badge показываем только для windows_integrated;
// для local/hybrid — скрываем («Гибридный режим» избыточен).
fetch('/api/auth/mode')
    .then(r => r.json())
    .then(d => {
        const b = document.getElementById('modeBadge');
        if (d.mode === 'windows_integrated') {
            b.textContent = 'Windows Authentication';
            b.style.display = '';
        } else {
            b.style.display = 'none';
        }
    })
    .catch(() => {});

// Если уже авторизованы — на главную
if (Auth.isAuthenticated()) {
    window.location.href = '/';
}

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    errorBox.classList.add('d-none');
    loginBtn.disabled = true;
    try {
        await Auth.login(usernameEl.value.trim(), passwordEl.value);
        window.location.href = '/';
    } catch (err) {
        // BUG-216 (v3.14.0): ошибка API — на русском.
        errorBox.textContent = (typeof errorToRussian === 'function' ? errorToRussian(err.message) : err.message) || 'Ошибка входа';
        errorBox.classList.remove('d-none');
        loginBtn.disabled = false;
    }
});
