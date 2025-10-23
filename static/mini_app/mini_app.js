// Mini App JavaScript для Telegram бота

// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;

// Глобальные переменные для отслеживания сообщений
let lastAddedMessageHash = null;

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
        header.textContent = ``;
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

// Функции для сохранения и загрузки чата
function saveChatToStorage() {
    try {
        const chatData = {
            history: chatHistory,
            timestamp: Date.now(),
            user_id: getUserId()
        };
        localStorage.setItem('neuroevent_chat', JSON.stringify(chatData));
        console.log('💾 Чат сохранен в localStorage:', chatHistory.length, 'сообщений');
    } catch (error) {
        console.error('Ошибка сохранения чата:', error);
    }
}

function loadChatFromStorage() {
    try {
        const savedData = localStorage.getItem('neuroevent_chat');
        if (savedData) {
            const chatData = JSON.parse(savedData);
            const currentUserId = getUserId();
            
            // Проверяем, что чат принадлежит текущему пользователю
            if (chatData.user_id === currentUserId) {
                chatHistory = chatData.history || [];
                console.log('📂 Чат загружен из localStorage:', chatHistory.length, 'сообщений');
                return true;
            } else {
                console.log('🔄 Чат принадлежит другому пользователю, очищаем');
                localStorage.removeItem('neuroevent_chat');
                chatHistory = [];
                return false;
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки чата:', error);
        chatHistory = [];
    }
    return false;
}

function getUserId() {
    // Получаем ID пользователя из Telegram WebApp или используем fallback
    const user = tg.initDataUnsafe?.user;
    return user?.id || 'anonymous';
}

// Восстановление чата из истории
function restoreChatFromHistory() {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    // Очищаем текущие сообщения (кроме первого приветственного)
    const existingMessages = chatMessages.querySelectorAll('.message');
    for (let i = 1; i < existingMessages.length; i++) {
        existingMessages[i].remove();
    }
    
    // Восстанавливаем сообщения из истории
    chatHistory.forEach(chatItem => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${chatItem.isUser ? 'user-message' : 'bot-message'}`;
        
        messageDiv.innerHTML = `
            <div class="message-content">${markdownToHtml(chatItem.message)}</div>
            <div class="message-time">${chatItem.timestamp}</div>
        `;
        
        chatMessages.appendChild(messageDiv);
    });
    
    // Прокручиваем к последнему сообщению
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
    
    console.log('🔄 Чат восстановлен из истории:', chatHistory.length, 'сообщений');
}

// Включение блока ввода сообщений
function enableChatInput() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.querySelector('.chat-send-btn');
    
    if (chatInput) {
        chatInput.disabled = false;
        chatInput.placeholder = 'Напишите сообщение...';
        chatInput.style.opacity = '1';
        chatInput.style.cursor = 'text';
        // Не устанавливаем фокус автоматически, чтобы не мешать пользователю
    }
    
    if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.style.opacity = '1';
        sendBtn.style.cursor = 'pointer';
    }
    
    console.log('✅ Поле ввода включено');
}

// Отключение блока ввода сообщений
function disableChatInput() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.querySelector('.chat-send-btn');
    
    if (chatInput) {
        chatInput.disabled = true;
        chatInput.placeholder = '';
        chatInput.style.opacity = '0.5';
        chatInput.style.cursor = 'not-allowed';
    }
    
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.style.opacity = '0.5';
        sendBtn.style.cursor = 'not-allowed';
    }
    
    console.log('❌ Поле ввода отключено');
}

// Добавление сообщения в чат
// Функция для преобразования Markdown в HTML
function markdownToHtml(text) {
    if (!text) return '';
    
    return text
        // Преобразуем **текст** в <strong>текст</strong>
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Преобразуем --- в горизонтальную линию
        .replace(/^---$/gm, '<hr>')
        // Преобразуем переносы строк в <br>
        .replace(/\n/g, '<br>');
}

function addMessageToChat(message, isUser = false, timestamp = null) {
    const chatMessages = document.getElementById('chat-messages');
    
    // Проверяем, является ли это сообщением об очистке чата
    if (!isUser && (message.includes('История чата была очищена администратором') || 
                   message.includes('История чатов успешно очищена'))) {
        console.log('🔄 Получено сообщение об очистке чата, очищаем localStorage');
        
        // Используем улучшенную функцию очистки
        clearLocalChat();
        
        // Показываем уведомление
        showNotification('🔄 История чата была очищена администратором');
        
        // Обновляем страницу через 2 секунды
        setTimeout(() => {
            window.location.reload();
        }, 2000);
        return;
    }
    
    // Проверяем, есть ли уже такое сообщение в чате (только для бот-сообщений)
    if (!isUser) {
        // Создаем хеш сообщения для более надежной проверки
        const messageHash = btoa(message.trim()).substring(0, 20);
        
        // Проверяем, не добавляли ли мы это сообщение недавно
        if (lastAddedMessageHash === messageHash) {
            console.log('🔄 Сообщение уже было добавлено недавно, пропускаем дублирование');
            console.log('🔍 Хеш сообщения:', messageHash);
            return;
        }
        
        // Проверяем существующие сообщения в DOM
        const existingMessages = chatMessages.querySelectorAll('.message.bot-message');
        for (let existingMsg of existingMessages) {
            const existingContent = existingMsg.querySelector('.message-content');
            if (existingContent) {
                const existingText = existingContent.textContent.trim();
                const newText = message.trim();
                
                // Проверяем совпадение по первым 50 символам для надежности
                if (existingText.substring(0, 50) === newText.substring(0, 50)) {
                    console.log('🔄 Сообщение уже существует в чате, пропускаем дублирование');
                    console.log('🔍 Существующий текст:', existingText.substring(0, 30) + '...');
                    console.log('🔍 Новый текст:', newText.substring(0, 30) + '...');
                    return;
                }
            }
        }
        
        // Сохраняем хеш последнего добавленного сообщения
        lastAddedMessageHash = messageHash;
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    // Отладочная информация
    console.log('Добавление сообщения:', {
        message: message.substring(0, 50) + '...',
        isUser: isUser,
        className: messageDiv.className
    });
    
    const time = timestamp || new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    messageDiv.innerHTML = `
        <div class="message-content">${markdownToHtml(message)}</div>
        <div class="message-time">${time}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    
    // Плавная прокрутка к последнему сообщению
    setTimeout(() => {
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });
        
        // Проверяем, нужно ли показать кнопку прокрутки
        toggleScrollButton();
    }, 100);
    
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
    
    // Сохраняем чат в localStorage
    saveChatToStorage();
    
    // НЕ включаем блок ввода автоматически при добавлении сообщения от бота
    // Поле ввода должно включаться только после получения сообщения от администратора
    // через getLatestMessage()
    console.log('📝 Сообщение добавлено в чат:', isUser ? 'пользователь' : 'бот');
}

// Отправка сообщения в чат
async function sendChatMessage() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.querySelector('.chat-send-btn');
    
    // Проверяем, не отключено ли уже поле ввода
    if (chatInput && chatInput.disabled) {
        console.log('⚠️ Поле ввода уже отключено, игнорируем отправку');
        return;
    }
    
    // Отключаем блок ввода до получения ответа
    console.log('🔒 Отключаем поле ввода перед отправкой сообщения');
    disableChatInput();
    
    // Existing logic to add user message and send to API
    const message = chatInput.value.trim();
    
    if (!message) {
        // Если сообщение пустое, включаем поле ввода обратно
        enableChatInput();
        return;
    }
    
    console.log('📤 Отправляем сообщение пользователя:', message);
    addMessageToChat(message, true);
    chatInput.value = '';
    
    // Устанавливаем флаг ожидания сообщения от администратора
    isWaitingForAdminMessage = true;
    console.log('⏳ Установлен флаг ожидания сообщения от администратора');
    
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
    
    // Плавная прокрутка к индикатору печати
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
    
    return typingDiv;
}

// Убрать индикатор печати
function removeTypingIndicator() {
    const typingIndicator = document.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
    
    // НЕ включаем блок ввода, если ждем сообщение от администратора
    // Поле ввода должно оставаться отключенным до получения нового сообщения от админа
    if (!isWaitingForAdminMessage) {
        console.log('🔓 Включаем поле ввода после удаления индикатора печати');
        enableChatInput();
    } else {
        console.log('⏳ Поле ввода остается отключенным - ждем сообщение от администратора');
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
        
        // НЕ сбрасываем флаг isWaitingForAdminMessage при ошибке
        // Поле ввода должно оставаться отключенным до получения сообщения от администратора
        console.log('⚠️ Ошибка отправки, но поле ввода остается отключенным');
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
        
        const chatInput = document.getElementById('chat-input');
        if (chatInput && chatInput.disabled) {
            console.log('⚠️ Поле ввода отключено, игнорируем нажатие Enter');
            return;
        }
        
        sendChatMessage();
    }
}

// Переменные для отслеживания сообщений
let lastMessageTimestamp = 0;
let isInitialized = false;
let isWaitingForAdminMessage = false; // Флаг ожидания сообщения от администратора

// Функция для получения последнего сообщения от админа
async function getLatestMessage() {
    try {
        console.log('🔍 Запрашиваем последнее сообщение от админа...');
        const response = await fetch('/api/mini-app/latest-message');
        const data = await response.json();
        
        console.log('📨 Ответ от сервера:', {
            success: data.success,
            hasMessage: !!data.message,
            messageLength: data.message ? data.message.length : 0,
            timestamp: data.timestamp,
            isInitialized: isInitialized,
            lastMessageTimestamp: lastMessageTimestamp,
            isRecent: data.is_recent,
            lastAdminTime: data.last_admin_time
        });
        
        if (data.success && data.message && data.timestamp) {
            // При первой инициализации показываем сообщение сразу, если оно есть
            if (!isInitialized) {
                lastMessageTimestamp = data.timestamp;
                isInitialized = true;
                console.log('Инициализирован timestamp последнего сообщения:', lastMessageTimestamp);
                
                // Если есть сообщение, показываем его сразу
                if (data.message.trim()) {
                    console.log('📨 Показываем сообщение при инициализации:', data.message.substring(0, 50) + '...');
                    addMessageToChat(data.message, false);
                    enableChatInput();
                }
                return;
            }
            
            // Проверяем, не получали ли мы уже это сообщение
            if (data.timestamp > lastMessageTimestamp) {
                console.log('📨 Получено новое сообщение от администратора');
                console.log('📨 Содержимое сообщения:', data.message.substring(0, 100) + '...');
                
                // Добавляем сообщение в чат
                addMessageToChat(data.message, false);
                
                // Сбрасываем флаг ожидания сообщения от администратора
                isWaitingForAdminMessage = false;
                console.log('🔄 Сброшен флаг ожидания сообщения от администратора');
                
                // Активируем блок ввода после получения сообщения от админа
                console.log('🔓 Включаем поле ввода после сообщения от администратора');
                enableChatInput();
                
                // Обновляем timestamp последнего сообщения
                lastMessageTimestamp = data.timestamp;
                
                console.log('✅ Сообщение от администратора обработано:', data.message.substring(0, 50) + '...');
            } else if (data.is_recent && data.timestamp === lastMessageTimestamp) {
                // Если сообщение недавнее, но timestamp тот же, проверяем дублирование
                console.log('🔄 Обнаружено недавнее сообщение с тем же timestamp, проверяем дублирование...');
                
                // Проверяем, есть ли уже это сообщение в чате
                const chatMessages = document.getElementById('chat-messages');
                const existingMessages = chatMessages.querySelectorAll('.message.bot-message');
                let messageExists = false;
                
                for (let existingMsg of existingMessages) {
                    const existingContent = existingMsg.querySelector('.message-content');
                    if (existingContent) {
                        // Сравниваем исходный текст сообщения, а не HTML
                        const existingText = existingContent.textContent.trim();
                        const newText = data.message.trim();
                        
                        // Проверяем совпадение по первым 50 символам для надежности
                        if (existingText.substring(0, 50) === newText.substring(0, 50)) {
                            messageExists = true;
                            console.log('🔍 Найдено дублирующееся сообщение:', existingText.substring(0, 30) + '...');
                            break;
                        }
                    }
                }
                
                if (!messageExists) {
                    console.log('📨 Показываем недавнее сообщение, которого нет в чате');
                    addMessageToChat(data.message, false);
                    enableChatInput();
                } else {
                    console.log('🔍 Сообщение уже существует в чате, пропускаем дублирование');
                }
            } else {
                console.log('🔍 Сообщение уже было получено ранее или timestamp не изменился');
            }
        } else {
            console.log('❌ Нет сообщений от админа или ошибка в ответе');
        }
    } catch (error) {
        console.error('Ошибка получения последнего сообщения:', error);
    }
}

// Функция для периодической проверки новых сообщений
function startMessagePolling() {
    // Проверяем каждые 2 секунды для более быстрого отклика
    setInterval(getLatestMessage, 2000);
}

// Инициализация чата
function initChat() {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', handleChatKeyPress);
        
        // Изначально отключаем блок ввода до первого ответа от бота
        disableChatInput();
        
        // Сначала проверяем статус очистки чата
        initClearCheck();
        
        // Загружаем историю чата из localStorage
        const chatLoaded = loadChatFromStorage();
        if (chatLoaded && chatHistory.length > 0) {
            // Восстанавливаем чат из истории
            restoreChatFromHistory();
        }
        
        // Запускаем проверку новых сообщений от админа
        startMessagePolling();
        
        // Немедленная проверка сообщений при инициализации
        getLatestMessage();
        
        // Инициализируем обработчик прокрутки
        initScrollHandler();
        
        // Инициализируем проверку очистки чата
        initClearCheck();
        
        // Запускаем мониторинг очистки чата
        startChatClearMonitoring();
    }
    
    // Первое сообщение уже есть в HTML, не добавляем дублирующее
}

// Функция для плавной прокрутки к последнему сообщению
function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    const scrollBtn = document.getElementById('scroll-to-bottom-btn');
    
    if (chatMessages) {
        // Плавная прокрутка к самому низу
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });
        
        // Скрываем кнопку после прокрутки
        setTimeout(() => {
            if (scrollBtn) {
                scrollBtn.classList.remove('show');
            }
        }, 500);
    }
}

// Функция для показа/скрытия кнопки прокрутки
function toggleScrollButton() {
    const chatMessages = document.getElementById('chat-messages');
    const scrollBtn = document.getElementById('scroll-to-bottom-btn');
    
    if (chatMessages && scrollBtn) {
        const isAtBottom = chatMessages.scrollTop + chatMessages.clientHeight >= chatMessages.scrollHeight - 20;
        
        if (isAtBottom) {
            scrollBtn.classList.remove('show');
            scrollBtn.style.display = 'none';
        } else {
            scrollBtn.classList.add('show');
            scrollBtn.style.display = 'flex';
        }
    }
}

// Инициализация обработчика прокрутки
function initScrollHandler() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.addEventListener('scroll', toggleScrollButton);
    }
}

// Проверка статуса очистки чата
let lastClearCheck = 0;

// Инициализация lastClearCheck при загрузке страницы
function initClearCheck() {
    // Получаем текущий timestamp при загрузке страницы
    fetch('/api/check-chat-clear-status')
        .then(response => response.json())
        .then(data => {
            console.log('🔍 Инициализация проверки очистки:', data);
            if (data.success && data.clear_timestamp) {
                lastClearCheck = data.clear_timestamp;
                console.log('🔍 Инициализирован lastClearCheck:', lastClearCheck);
                
                // Если чат был очищен недавно (в течение последних 10 минут), 
                // принудительно очищаем локальный чат
                const now = Date.now();
                const tenMinutesAgo = now - (10 * 60 * 1000);
                
                if (data.clear_timestamp > tenMinutesAgo) {
                    console.log('🔄 Обнаружена недавняя очистка чата, принудительно очищаем локальный чат');
                    clearLocalChat();
                    
                    // Показываем уведомление пользователю
                    showNotification('🔄 История чата была очищена администратором');
                }
            }
        })
        .catch(error => {
            console.error('Ошибка инициализации lastClearCheck:', error);
        });
}

// Функция для очистки локального чата
function clearLocalChat() {
    console.log('🔄 Очистка локального чата');
    
    // Очищаем все возможные ключи localStorage
    localStorage.removeItem('neuroevent_chat');
    localStorage.removeItem('mini_app_chat_history');
    localStorage.removeItem('mini_app_user_data');
    localStorage.removeItem('chat_history');
    localStorage.removeItem('user_data');
    
    // Очищаем текущий чат
    chatHistory = [];
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        // Оставляем только первое приветственное сообщение
        const welcomeMessage = chatMessages.querySelector('.message:first-child');
        chatMessages.innerHTML = '';
        if (welcomeMessage) {
            chatMessages.appendChild(welcomeMessage);
        }
    }
    
    // Сбрасываем флаги состояния
    isWaitingForAdminMessage = false;
    lastMessageTimestamp = 0;
    
    console.log('✅ Локальный чат полностью очищен');
}
async function checkChatClearStatus() {
    try {
        const response = await fetch('/api/check-chat-clear-status');
        const data = await response.json();
        
        console.log('🔍 Проверка статуса очистки чата:', data);
        console.log('🔍 lastClearCheck:', lastClearCheck);
        
        if (data.success && data.chat_cleared && data.clear_timestamp) {
            // Проверяем, что это новая очистка (timestamp больше предыдущего)
            if (data.clear_timestamp > lastClearCheck) {
                console.log('🔄 Обнаружена новая очистка чата администратором');
                lastClearCheck = data.clear_timestamp;
                
                // Очищаем локальный чат
                clearLocalChat();
                
                // Показываем уведомление
                showNotification('🔄 История чата была очищена администратором');
                
                // Не перезагружаем страницу сразу, даем пользователю время прочитать уведомление
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                console.log('🔍 Очистка чата уже была обработана ранее');
            }
        }
    } catch (error) {
        console.error('Ошибка проверки статуса очистки чата:', error);
    }
}

// Запуск периодической проверки статуса очистки чата
function startChatClearMonitoring() {
    // Проверяем каждые 3 секунды для более быстрого отклика
    setInterval(checkChatClearStatus, 3000);
}

// Экспорт функций для использования в HTML
window.sendMessage = sendMessage;
window.sendChatMessage = sendChatMessage;
window.handleBotData = handleBotData;
window.enableChatInput = enableChatInput;
window.disableChatInput = disableChatInput;
window.scrollToBottom = scrollToBottom;
