// webui/static/js/datetime.js
// BUG-141 (v3.14.0): бэкенд отдаёт UTC-строки без временной зоны и без 'Z'
// (например "2026-10-13T10:20:30"). Браузерный new Date(...) трактует такие
// строки как ЛОКАЛЬНОЕ время — события/находки «уезжали» на несколько часов.
// parseUtc/formatDate принудительно трактуют строку как UTC и локализуют
// вывод в timezone браузера (ru-RU).

function parseUtc(isoStr) {
    if (!isoStr) return NaN;
    let s = String(isoStr).trim();
    if (s && !/[Zz]$|[+-]\d{2}:\d{2}$/.test(s)) s += 'Z';
    const t = new Date(s).getTime();
    return isNaN(t) ? NaN : t;
}

function formatDate(isoStr) {
    if (isoStr === null || isoStr === undefined || isoStr === '') return '—';
    const t = parseUtc(isoStr);
    if (isNaN(t)) return String(isoStr);
    return new Date(t).toLocaleString('ru-RU');
}

function formatDateShort(isoStr) {
    if (isoStr === null || isoStr === undefined || isoStr === '') return '—';
    const t = parseUtc(isoStr);
    if (isNaN(t)) return String(isoStr);
    return new Date(t).toLocaleDateString('ru-RU');
}