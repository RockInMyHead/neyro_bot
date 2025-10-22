// Mini App JavaScript для Telegram бота

// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;

// Инициализация приложения
function initApp() {
    // Расширяем приложение на весь экран
    tg.expand();
    
    // Устанавливаем цветовую схему (проверяем поддержку версии)
    if (tg.setHeaderColor) {
        tg.setHeaderColor('#007bff');
    }
    
    // Устанавливаем цвет фона только если поддерживается
    if (tg.setBackgroundColor) {
        tg.setBackgroundColor('#ffffff');
    }
    
    // Включаем кнопку закрытия только если поддерживается
    if (tg.enableClosingConfirmation) {
        tg.enableClosingConfirmation();
    }
    
    // Получаем данные пользователя
    const user = tg.initDataUnsafe?.user;
    console.log('initApp - Telegram WebApp user data:', user);
    console.log('initApp - tg.initDataUnsafe:', tg.initDataUnsafe);
    console.log('initApp - tg.initData:', tg.initData);
    
    if (user) {
        console.log('Пользователь найден в tg.initDataUnsafe:', user);
        updateUserInfo(user);
    } else {
        console.log('Пользователь не найден в tg.initDataUnsafe, пробуем initData');
        try {
            const initData = tg.initData;
            if (initData) {
                const urlParams = new URLSearchParams(initData);
                const userParam = urlParams.get('user');
                if (userParam) {
                    const userData = JSON.parse(decodeURIComponent(userParam));
                    console.log('Пользователь найден в initData:', userData);
                    updateUserInfo(userData);
                } else {
                    console.log('Пользователь не найден в initData');
                }
            }
        } catch (e) {
            console.log('Ошибка парсинга initData:', e);
        }
        
        // Если все еще нет пользователя, создаем тестового для локальной разработки
        if (!user) {
            const testUser = {
                id: Math.floor(Math.random() * 1000000) + 100000,
                username: 'test_user',
                first_name: 'Test User'
            };
            console.log('Создаем тестового пользователя для локальной разработки:', testUser);
            updateUserInfo(testUser);
        }
    }
    
    
    // Инициализируем чат
    initChat();
    
    // Обработчики событий
    setupEventListeners();
    
    console.log('Mini App инициализирован');
}

// Обновление информации о пользователе
function updateUserInfo(user) {
    console.log('updateUserInfo called with:', user);
    const header = document.querySelector('.header p');
    if (header && user.first_name) {
        header.textContent = `с ВАС идеи — с НАС воплощение`;
    }
}


// Настройка обработчиков событий
function setupEventListeners() {
    // Обработчики событий для чата
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendChatMessage();
            }
        });
    }
}

// Отправка сообщения боту
function sendMessage(message) {
    if (tg && tg.sendData) {
        // Отправляем данные боту
        tg.sendData(JSON.stringify({
            action: 'send_message',
            message: message,
            timestamp: Date.now()
        }));
        
        
        // Показываем уведомление
        showNotification('Сообщение отправлено!');
        
        console.log('Отправлено сообщение:', message);
    } else {
        console.error('Telegram WebApp API недоступен');
        showNotification('Ошибка: не удалось отправить сообщение');
    }
}



// Показ уведомления
function showNotification(message) {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--tg-theme-button-color, #007bff);
        color: var(--tg-theme-button-text-color, #ffffff);
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 14px;
        z-index: 1000;
        animation: slideDown 0.3s ease-out;
    `;
    
    // Добавляем стили анимации
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateX(-50%) translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }
        }
    `;
    document.head.appendChild(style);
    
    // Добавляем уведомление на страницу
    document.body.appendChild(notification);
    
    // Удаляем через 3 секунды
    setTimeout(() => {
        notification.style.animation = 'slideDown 0.3s ease-out reverse';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Обработка данных от бота
function handleBotData(data) {
    try {
        const parsedData = JSON.parse(data);
        console.log('Получены данные от бота:', parsedData);
        
        switch (parsedData.action) {
            case 'show_message':
                showNotification(parsedData.message);
                // Re-enable chat input for user response
                const chatInput = document.getElementById('chat-input');
                const sendBtn = document.querySelector('.chat-send-btn');
                if (chatInput) chatInput.disabled = false;
                if (sendBtn) sendBtn.disabled = false;
                break;
            default:
                console.log('Неизвестное действие:', parsedData.action);
        }
    } catch (error) {
        console.error('Ошибка обработки данных:', error);
    }
}

// Обработчик события закрытия приложения
function onCloseApp() {
    console.log('Приложение закрывается');
    // Можно сохранить данные или выполнить очистку
}

// Обработчик события изменения размера окна
function onViewportChanged() {
    console.log('Размер окна изменен:', tg.viewportHeight, tg.viewportStableHeight);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, что мы в Telegram WebApp
    if (typeof Telegram !== 'undefined' && Telegram.WebApp) {
        initApp();
        
        // Настраиваем обработчики событий Telegram
        tg.onEvent('close', onCloseApp);
        tg.onEvent('viewportChanged', onViewportChanged);
        
        // Обработчик данных от бота
        tg.onEvent('mainButtonClicked', function() {
            console.log('Нажата главная кнопка');
        });
        
    } else {
        console.warn('Telegram WebApp API недоступен. Запуск в режиме разработки.');
        // Режим разработки - инициализируем без Telegram API
        initApp();
    }
});

// Чат функциональность
let chatHistory = [];

// Добавление сообщения в чат
function addMessageToChat(message, isUser = false, timestamp = null) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const time = timestamp || new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    messageDiv.innerHTML = `
        <div class="message-content">${message}</div>
        <div class="message-time">${time}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Сохраняем в историю
    chatHistory.push({
        message: message,
        isUser: isUser,
        timestamp: time
    });
    
    // Ограничиваем историю последними 50 сообщениями
    if (chatHistory.length > 50) {
        chatHistory = chatHistory.slice(-50);
    }
}

// Отправка сообщения в чат
async function sendChatMessage() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.querySelector('.chat-send-btn');
    
    // Disable input until next admin message
    if (chatInput) chatInput.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    
    // Existing logic to add user message and send to API
    const message = chatInput.value.trim();
    
    if (!message) return;
    
    addMessageToChat(message, true);
    chatInput.value = '';
    
    // Показываем индикатор печати
    showTypingIndicator();
    
    // Отправляем сообщение боту
    sendMessageToBot(message);
}

// Показать индикатор печати
function showTypingIndicator() {
    const chatMessages = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.innerHTML = `
        <div class="message-content">
            <span class="typing-dots">
                <span>.</span><span>.</span><span>.</span>
            </span>
        </div>
    `;
    
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return typingDiv;
}

// Убрать индикатор печати
function removeTypingIndicator() {
    const typingIndicator = document.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Отправка сообщения боту через OpenAI API
async function sendMessageToBot(message) {
    try {
        // Получаем данные пользователя из Telegram WebApp
        const user = tg.initDataUnsafe?.user;
        console.log('Telegram WebApp user data:', user);
        console.log('tg.initDataUnsafe:', tg.initDataUnsafe);
        console.log('tg.initData:', tg.initData);
        
        // Попробуем альтернативные способы получения данных пользователя
        let user_id = 0;
        let username = '';
        let first_name = 'MiniApp';
        
        if (user) {
            user_id = user.id || 0;
            username = user.username || '';
            first_name = user.first_name || 'MiniApp';
        } else {
            // Если данные пользователя недоступны, попробуем получить их из initData
            try {
                const initData = tg.initData;
                console.log('Raw initData:', initData);
                if (initData) {
                    // Парсим initData для извлечения user_id
                    const urlParams = new URLSearchParams(initData);
                    const userParam = urlParams.get('user');
                    if (userParam) {
                        const userData = JSON.parse(decodeURIComponent(userParam));
                        console.log('Parsed user data from initData:', userData);
                        user_id = userData.id || 0;
                        username = userData.username || '';
                        first_name = userData.first_name || 'MiniApp';
                    }
                }
            } catch (e) {
                console.log('Error parsing initData:', e);
            }
            
            // Если все еще нет user_id, используем случайный для локальной разработки
            if (user_id === 0) {
                // Генерируем случайный user_id для локальной разработки
                user_id = Math.floor(Math.random() * 1000000) + 100000;
                username = 'test_user_' + user_id;
                first_name = 'Test User';
                console.log('Using generated user_id for local development:', user_id);
            }
        }
        
        console.log('Final user data:', { user_id, username, first_name });
        
        // Отправляем запрос к API
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                history: chatHistory.slice(-10), // Отправляем последние 10 сообщений как контекст
                user_id: user_id,
                username: username,
                first_name: first_name
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            removeTypingIndicator();
            addMessageToChat(data.response, false);
        } else {
            throw new Error('API returned error');
        }
        
    } catch (error) {
        removeTypingIndicator();
        console.error('Ошибка отправки сообщения:', error);
        
        // Fallback на локальную генерацию ответа
        const botResponse = generateBotResponse(message);
        addMessageToChat(botResponse, false);
    }
}

// Генерация ответа бота
function generateBotResponse(userMessage) {
    const message = userMessage.toLowerCase();
    
    // Простые ответы на основе ключевых слов
    if (message.includes('привет') || message.includes('hello') || message.includes('hi')) {
        return 'Привет! 👋 Рад тебя видеть! Чем могу помочь?';
    }
    
    if (message.includes('как дела') || message.includes('как ты')) {
        return 'У меня всё отлично! 🤖 Работаю, отвечаю на сообщения. А у тебя как дела?';
    }
    
    if (message.includes('спасибо') || message.includes('thanks')) {
        return 'Пожалуйста! 😊 Всегда рад помочь!';
    }
    
    if (message.includes('погода')) {
        return 'К сожалению, я не могу проверить погоду прямо сейчас. Но надеюсь, что у тебя хорошая погода! ☀️';
    }
    
    if (message.includes('время') || message.includes('который час')) {
        const now = new Date();
        return `Сейчас ${now.toLocaleTimeString('ru-RU')} ⏰`;
    }
    
    if (message.includes('помощь') || message.includes('help')) {
        return 'Я могу помочь с различными вопросами! Попробуй спросить о времени, поздороваться или просто поболтать со мной! 😊';
    }
    
    if (message.includes('бот') || message.includes('robot')) {
        return 'Да, я бот! 🤖 Но я стараюсь быть полезным и дружелюбным. Есть что-то, с чем я могу помочь?';
    }
    
    if (message.includes('что умеешь') || message.includes('функции')) {
        return 'Я умею:\n• Отвечать на сообщения\n• Показывать статистику\n• Помогать с настройками\n• Просто общаться! 😊';
    }
    
    // Случайные ответы
    const randomResponses = [
        'Интересно! Расскажи больше! 🤔',
        'Понял тебя! 👍',
        'Это звучит здорово! 😊',
        'Спасибо за сообщение! 😄',
        'Я слушаю! 👂',
        'Отличная мысль! 💭',
        'Продолжай! 📝',
        'Очень интересно! 🎯'
    ];
    
    return randomResponses[Math.floor(Math.random() * randomResponses.length)];
}

// Обработчик нажатия Enter в чате
function handleChatKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

// Инициализация чата
function initChat() {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', handleChatKeyPress);
        
        // Автофокус на поле ввода
        chatInput.focus();
    }
    
    // Первое сообщение уже есть в HTML, не добавляем дублирующее
}

// Экспорт функций для использования в HTML
window.sendMessage = sendMessage;
window.sendChatMessage = sendChatMessage;
window.handleBotData = handleBotData;
