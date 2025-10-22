// Админ Mini App JavaScript
let tg = null;
let updateInterval = null;

// Инициализация приложения
document.addEventListener('DOMContentLoaded', function() {
    if (Telegram.WebApp) {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
        
        tg = Telegram.WebApp;
        
        // Настройка темы
        document.body.setAttribute('data-theme', tg.colorScheme);
        document.body.style.backgroundColor = tg.backgroundColor || '#ffffff';
        document.body.style.color = tg.textColor || '#000000';
        
        console.log('🔧 Админ Mini App инициализирован');
        
        // Запускаем автообновление
        startAutoUpdate();
        
        // Загружаем начальные данные
        loadInitialData();
        
    } else {
        console.error('Telegram WebApp API не инициализирован');
        // Для тестирования в браузере
        startAutoUpdate();
        loadInitialData();
    }
});

// Загрузка начальных данных
async function loadInitialData() {
    try {
        await refreshStats();
        await refreshMessages();
        await generateMixedText();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
    }
}

function startAutoUpdate() {
    updateInterval = setInterval(async () => {
        try {
            await refreshStats();
            await refreshMessages();
            await generateMixedText();
        } catch (error) {
            console.error('Ошибка автообновления:', error);
        }
    }, 15000); // 15 секунд
    
    console.log('🔄 Автообновление запущено (каждые 15 секунд)');
}

// Остановка автообновления
function stopAutoUpdate() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
        console.log('⏹️ Автообновление остановлено');
    }
}

// Обновление статистики
async function refreshStats() {
    try {
        const response = await fetch('/api/admin/stats');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            updateStatsDisplay(data.stats);
        } else {
            throw new Error(data.error || 'Ошибка получения статистики');
        }
        
    } catch (error) {
        console.error('Ошибка обновления статистики:', error);
        showNotification('Ошибка загрузки статистики', 'error');
    }
}

// Обновление отображения статистики
function updateStatsDisplay(stats) {
    document.getElementById('total-messages').textContent = stats.total_messages || 0;
    document.getElementById('unique-users').textContent = stats.unique_users_count || 0;
    document.getElementById('recent-messages').textContent = stats.recent_messages_count || 0;
    document.getElementById('uptime').textContent = `${(stats.uptime_hours || 0).toFixed(1)}ч`;
}

// Обновление сообщений
async function refreshMessages() {
    try {
        const response = await fetch('/api/admin/messages');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            updateMessagesDisplay(data.messages);
        } else {
            throw new Error(data.error || 'Ошибка получения сообщений');
        }
        
    } catch (error) {
        console.error('Ошибка обновления сообщений:', error);
        showNotification('Ошибка загрузки сообщений', 'error');
    }
}

// Обновление отображения сообщений
function updateMessagesDisplay(messages) {
    const container = document.getElementById('messages-container');
    
    if (!messages || messages.length === 0) {
        container.innerHTML = '<div class="no-messages">Нет сообщений</div>';
        return;
    }
    
    container.innerHTML = messages.map(msg => `
        <div class="message-item">
            <div class="message-header">
                <span class="message-user">${msg.first_name}</span>
                <span class="message-time">${formatTime(msg.timestamp)}</span>
            </div>
            <div class="message-text">${msg.message}</div>
            <div class="message-source">Источник: ${msg.source}</div>
        </div>
    `).join('');
}

// Генерация миксированного текста
async function generateMixedText() {
    try {
        const response = await fetch('/api/admin/mixed-text', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            updateMixedTextDisplay(data.mixed_text);
        } else {
            throw new Error(data.error || 'Ошибка генерации миксированного текста');
        }
        
    } catch (error) {
        console.error('Ошибка генерации миксированного текста:', error);
        showNotification('Ошибка генерации миксированного текста', 'error');
    }
}

// Обновление отображения миксированного текста
function updateMixedTextDisplay(mixedText) {
    document.getElementById('mixed-text').textContent = mixedText;
    document.getElementById('mixed-text-time').textContent = 
        `Последнее обновление: ${new Date().toLocaleTimeString()}`;
}

// Сброс статистики
async function resetStats() {
    if (!confirm('Вы уверены, что хотите сбросить всю статистику?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/admin/reset', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Статистика сброшена', 'success');
            await refreshStats();
            await refreshMessages();
        } else {
            throw new Error(data.error || 'Ошибка сброса статистики');
        }
        
    } catch (error) {
        console.error('Ошибка сброса статистики:', error);
        showNotification('Ошибка сброса статистики', 'error');
    }
}

// Экспорт данных
async function exportData() {
    try {
        const response = await fetch('/api/admin/export');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Создаем и скачиваем файл
            const blob = new Blob([JSON.stringify(data.data, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `admin_data_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showNotification('Данные экспортированы', 'success');
        } else {
            throw new Error(data.error || 'Ошибка экспорта данных');
        }
        
    } catch (error) {
        console.error('Ошибка экспорта данных:', error);
        showNotification('Ошибка экспорта данных', 'error');
    }
}

// Форматирование времени
function formatTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Показ уведомлений
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Добавляем стили
    const style = document.createElement('style');
    style.innerHTML = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }
        .notification-success { background: #28a745; }
        .notification-error { background: #dc3545; }
        .notification-info { background: #17a2b8; }
        .notification-warning { background: #ffc107; color: #212529; }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
    
    // Добавляем уведомление
    document.body.appendChild(notification);
    
    // Удаляем через 3 секунды
    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Обработка закрытия приложения
if (Telegram.WebApp) {
    Telegram.WebApp.onEvent('viewport_changed', function() {
        console.log('Viewport changed');
    });
    
    Telegram.WebApp.onEvent('theme_changed', function() {
        document.body.setAttribute('data-theme', Telegram.WebApp.colorScheme);
    });
}

// Генерация изображения из микса
let currentImageData = null;

async function generateImageFromMix() {
    const btn = document.getElementById('generateImageBtn');
    const loading = document.getElementById('imageLoading');
    const result = document.getElementById('generatedImageResult');
    
    try {
        // Показываем загрузку
        btn.disabled = true;
        loading.style.display = 'block';
        result.style.display = 'none';
        
        const startTime = Date.now();
        
        const response = await fetch('/api/admin/generate-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            const generationTime = ((Date.now() - startTime) / 1000).toFixed(1);
            
            // Сохраняем данные для скачивания
            currentImageData = data;
            
            // Отображаем изображение по пути
            const img = document.getElementById('generatedImage');
            img.src = data.filepath;
            
            // Отображаем детали
            document.getElementById('imagePrompt').textContent = data.prompt;
            document.getElementById('imageSize').textContent = formatFileSize(data.file_size);
            document.getElementById('imageTime').textContent = `${generationTime}с`;
            
            // Показываем результат
            result.style.display = 'block';
            
            showNotification('Изображение успешно сгенерировано!', 'success');
        } else {
            throw new Error(data.error || 'Ошибка генерации изображения');
        }
        
    } catch (error) {
        console.error('Ошибка генерации изображения:', error);
        showNotification(`Ошибка: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        loading.style.display = 'none';
    }
}

// Скачивание сгенерированного изображения
function downloadGeneratedImage() {
    if (!currentImageData) {
        showNotification('Нет изображения для скачивания', 'error');
        return;
    }
    
    try {
        // Создаем ссылку для скачивания
        const link = document.createElement('a');
        link.href = currentImageData.filepath;
        link.download = currentImageData.filename || `generated_${Date.now()}.png`;
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showNotification('Изображение скачано', 'success');
    } catch (error) {
        console.error('Ошибка скачивания:', error);
        showNotification('Ошибка скачивания изображения', 'error');
    }
}

// Форматирование размера файла
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// Экспорт функций для использования в HTML






window.refreshStats = refreshStats;
window.refreshMessages = refreshMessages;
window.generateMixedText = generateMixedText;
window.resetStats = resetStats;
window.exportData = exportData;
window.generateImageFromMix = generateImageFromMix;
window.downloadGeneratedImage = downloadGeneratedImage;
