/**
 * DCAP WebUI - Основной JavaScript файл
 * Версия: 3.0.0
 */

// Глобальные переменные
let refreshInterval = null;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Показываем время обновления при загрузке
    updateTime();
    
    // Автообновление
    if (typeof AUTO_REFRESH === 'undefined' || AUTO_REFRESH) {
        startAutoRefresh();
    }
    
    // Обработка ошибок fetch
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        return originalFetch.apply(this, args)
            .catch(error => {
                console.error('Network error:', error);
                showNotification('Ошибка сети', 'error');
                throw error;
            });
    };
});

/**
 * Обновление времени последнего обновления
 */
function updateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    const el = document.getElementById('update-time');
    if (el) {
        el.textContent = '🔄 ' + timeStr;
    }
}

/**
 * Старт автообновления
 */
function startAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    
    refreshInterval = setInterval(() => {
        updateTime();
        // Страницы сами обновляют данные через свои функции
        if (typeof refreshData === 'function') {
            refreshData();
        }
    }, 30000); // 30 секунд
}

/**
 * Остановка автообновления
 */
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

/**
 * Уведомления
 */
function showNotification(message, type = 'info') {
    const colors = {
        info: '#4299e1',
        success: '#48bb78',
        warning: '#ed8936',
        error: '#fc8181'
    };
    
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 24px;
        background: ${colors[type] || colors.info};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
        max-width: 400px;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Добавляем CSS для анимаций
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

/**
 * Форматирование размера файла
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Обрезка строки
 */
function truncateString(str, maxLength = 50) {
    if (str.length <= maxLength) return str;
    return str.slice(0, maxLength) + '...';
}

/**
 * Получение цвета для категории
 */
function getCategoryColor(category) {
    const colors = {
        'PII_PER': '#fc8181',
        'PII_LOC': '#f6ad55',
        'PII_DATE': '#f6e05e',
        'PII_EMAIL': '#68d391',
        'PII_PHONE': '#63b3ed',
        'API_KEY': '#9f7aea',
        'AWS_ACCESS_KEY': '#ed64a6',
        'JWT_TOKEN': '#fc8181',
        'PASSWORD': '#f56565',
        'CRED_HIGH_ENTROPY': '#ed8936',
        'default': '#a0aec0'
    };
    return colors[category] || colors.default;
}

// Экспорт для использования в других файлах
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        updateTime,
        startAutoRefresh,
        stopAutoRefresh,
        showNotification,
        formatFileSize,
        truncateString,
        getCategoryColor
    };
}