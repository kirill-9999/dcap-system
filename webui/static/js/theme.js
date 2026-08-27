function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme') || 'light';
    const next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    localStorage.setItem('dcap-theme', next);
    const icon = document.getElementById('themeIcon');
    if (icon) icon.className = next === 'light' ? 'fas fa-moon' : 'fas fa-sun';
}
function initTheme() {
    const saved = localStorage.getItem('dcap-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    const icon = document.getElementById('themeIcon');
    if (icon) icon.className = saved === 'light' ? 'fas fa-moon' : 'fas fa-sun';
}
document.addEventListener('DOMContentLoaded', initTheme);
