function toggleSidebar() {
    const s = document.getElementById('sidebar');
    const m = document.getElementById('mainContent');
    s.classList.toggle('collapsed');
    m.classList.toggle('expanded');
    localStorage.setItem('dcap-sidebar', s.classList.contains('collapsed') ? '1' : '0');
}
function initSidebar() {
    if (localStorage.getItem('dcap-sidebar') === '1') {
        document.getElementById('sidebar')?.classList.add('collapsed');
        document.getElementById('mainContent')?.classList.add('expanded');
    }
}
function updateFooterTime() {
    const el = document.getElementById('footerTime');
    if (el) el.textContent = new Date().toLocaleString('ru-RU');
}
document.addEventListener('DOMContentLoaded', function() {
    initSidebar();
    updateFooterTime();
    setInterval(updateFooterTime, 10000);
});
