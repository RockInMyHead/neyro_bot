// Админ Mini App JavaScript
let tg = null;
let updateInterval = null;

// Переменные для системы очереди промтов
let legacyPromptIndex = 0;
let promptQueue = [];
let isEditing = false;

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
        await refreshMessages();
        initializePromptQueue();
        
        // NEW: Запускаем автообновление умной системы батчей
        startSmartBatchAutoUpdate();
        
        // Инициализируем промты
        initializePrompts();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
    }
}

// Инициализация очереди промтов
function initializePromptQueue() {
    // Создаем очередь из всех доступных промтов
    promptQueue = Object.keys(basePrompts).filter(key => key !== 'custom');
    legacyPromptIndex = 0;
    
    // Загружаем список промтов
    loadPromptList();
    
    // Генерируем концертный контент для текущего промта
    generateConcertContent();
}

function startAutoUpdate() {
    updateInterval = setInterval(async () => {
        try {
            await refreshMessages();
        } catch (error) {
            console.error('Ошибка автообновления:', error);
        }
    }, 15000); // 15 секунд
    
}

// Остановка автообновления
function stopAutoUpdate() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
        console.log('⏹️ Автообновление остановлено');
    }
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

// ===== ФУНКЦИИ УПРАВЛЕНИЯ БАЗОВЫМИ ПРОМТАМИ =====

// Базовые промты фильмов
const basePrompts = {
    pirates: "Пираты Карибского моря\nМрачный кинематографичный реализм во вселенной Пиратов карибского моря; деревянные корабли с парусами и пушками; пираты; морская дымка, контраст, рим-свет; палитра: сталь/свинец воды, изумруд/бирюза, мох, мокрое дерево, патина бронзы, янтарные блики; фактуры: соль на канатах, камень, рваная парусина, брызги; широкий план, масштаб, без крупных лиц.",
    got: "Игра престолов\nМрачный кинематографичный реализм по вселенной сериала Игра престолов; замок, дракон; суровая атмосфера, мягкая дымка; палитра: сланцевый серый, сталь, холодный синий, охра/терракота, выцветшие ткани, тёмное дерево, тёплые свечи/факелы; фактуры: камень/шифер, шерсть/мех, кожа, кованое железо; широкий план, масштаб, без крупных лиц.",
    sherlock: "Шерлок Холмс\nКинематографичный реализм BBC Sherlock: дождливый Лондон, мокрый асфальт, кирпич/стекло; палитра холодный синий/циан + тёплые фонари; без крупных лиц; боковой/контровый свет, отражения и блики, мелкое боке, малая ГРИП; диагональные ракурсы, лёгкое плёночное зерно.",
    ghostbusters: "Охотники за приведениями\nКинореализм паранормального '80s в духе фильмов Охотники за приведениями: туман, объёмный свет, неон-зелёные эктопары, тёплые фонари, lens flare, призраки, ловушка для призраков, из оружия охотников красные с желтым как молнии лучи.",
    interstellar: "Интерстеллар\nКинематографичный hard-sci-fi реализм по фильму Интерстеллар: чистая оптика, высокий контраст, мягкая дымка; палитра холодный синий/сталь, угольный чёрный, пыльная охра, янтарное солнце, белые скафандры; звёздные поля, лёгкое гравитационное линзирование, тонкий lens flare, объёмный свет/пыль, широкие планы, масштаб и время.",
    leon: "Леон\nНео-нуар '90s по фильму Леон, Нью-Йорк: тёплый вольфрам, холодный флуоресцент, высокий контраст, узкая ГРИП, низкие ракурсы, полосы света от жалюзи; мокрый асфальт, отражения, дым/пыль в лучах, мягкое боке, плёночное зерно; палитра оливковый/хаки, чёрный, серый бетон, латунь; без читаемых надписей.",
    batman: "Бэтмен\nКинореализм нео-нуар «Бэтмен (Нолана)»: дождливый ночной мегаполис, контраст тёплых натриевых фонарей и холодного циана; объёмный свет/дым, неоновые отражения на мокром асфальте, длинные тени, дальний план, лёгкое плёночное зерно.",
    rocky: "Рокки\nГритти-драма по фильму «Рокки»: натриевые фонари, сырые спортзалы, пот и мел; тренировки; палитра кирпич, сталь, выцветший индиго; контраст холода улицы и тёплого лампового света; плёночное зерно, дальний план.",
    gladiator: "Гладиатор\nИсторический эпик по фильму «Гладиатор»: арена в пыли, лучи солнца, кожа/сталь/лён, гул толпы, контровый свет; палитра охра, песок, ржавое золото и холодная сталь, дальний план.",
    mission: "Миссия: невыполнима\nТехно-шпионский триллер по фильму «Миссия: невыполнима»: стекло и сталь, циановые рефлексы, тросы, блики; ритм тикает, чистые силуэты гаджетов, дальний план.",
    professionnel: "Le Professionnel (1981)\nФранцузский нео-нуар по фильму «Le Professionnel» (1981): парижский камень после дождя, дым в лучах, тренч и тень шляпы; палитра сепия, олива, графит, латунь; мягкая виньетка, дальний план",
    starwars: "Звёздные войны\nКосмическая опера по «Звёздным войнам»: «истёртая техника», гигантские корабли, гиперпролёты, двойные солнца; лазерные мечи, дроиды, туман объёма; палитра пустынных охр и холодного космоса, дальний план",
    killbill: "Убить Билла\nГрафичный гриндхаус по фильму «Убить Билла»: жёсткий боковой и контровый свет, резкие тени; палитра жёлтый+чёрный, алый, тёмное дерево, сталь; кожа, шёлк, брызги, плёночное зерно, дальний план",
    love: "Мы. Верим в любовь\nИнди-ромдрама по фильму «Мы. Верим в любовь»: натуральный свет, мягкое боке; пастель и тёплый янтарь против прохладного серо-голубого; шорох ткани, дальний план",
    intouchables: "1+1\nТёплая драмеди по фильму «1+1»: янтарные интерьеры и прохладные экстерьеры, движение в кадре, палитра слоновая кость, тёмное дерево, графит; мягкий контраст, дальний план",
    bond: "Агент 007\nГлянцевый шпионаж по франшизе «Агент 007»: смокинги, казино, пентхаусы, автомобили, экзотические локации; циан и золото, анаморфные блики, точный ключевой свет; дальний план",
    pulp: "Криминальное чтиво\nНео-нуар '90s по фильму «Криминальное чтиво»: ретро автомобили, винил, ироничный пафос; палитра горчица, вишня, чёрный; плёночное зерно, дальний план",
    soviet: "Свой среди чужих, чужой среди своих\nСоветский остерн по фильму «Свой среди чужих, чужой среди своих»: степь, мираж, пыльный эшелон, лошади и кожанки; широкие панорамы; палитра охра, пепел, выгоревшая синь, дальний план",
    swan: "Лебединое озеро\nБалет «Лебединое озеро»: сцена у лунного озера, туман и зеркальные отражения; выразительные линии рук и па, тюлевые пачки, перья, пуанты. Палитра холодный синий и серебро + мягкий тёплый свет рампы; контровый «лунный» рим-свет, лёгкая дымка, деликатное размытие движения, бархат и дерево декора, дальний план"
};

// Переменные для drag & drop
let draggedElement = null;
let draggedIndex = -1;

// Инициализация промтов при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const promptSelect = document.getElementById('base-prompt');
    const customPromptGroup = document.getElementById('custom-prompt-group');
    const promptText = document.getElementById('prompt-text');
    
    if (promptSelect && customPromptGroup && promptText) {
        // Обновляем предварительный просмотр при изменении выбора
        promptSelect.addEventListener('change', function() {
            const selectedValue = this.value;
            
            if (selectedValue === 'custom') {
                customPromptGroup.style.display = 'block';
                promptText.textContent = 'Введите ваш пользовательский промт...';
            } else {
                customPromptGroup.style.display = 'none';
                promptText.textContent = basePrompts[selectedValue] || basePrompts.pirates;
            }
        });
        
        // Обновляем предварительный просмотр при вводе пользовательского промта
        const customPromptText = document.getElementById('custom-prompt-text');
        if (customPromptText) {
            customPromptText.addEventListener('input', function() {
                if (promptSelect.value === 'custom') {
                    promptText.textContent = this.value || 'Введите ваш пользовательский промт...';
                }
            });
        }
    }
});

async function updateBasePrompt() {
    // Используем текущий промт из очереди
    if (promptQueue.length === 0) {
        showNotification('Ошибка: очередь промтов пуста', 'error');
        return;
    }
    
    const currentPromptKey = promptQueue[legacyPromptIndex];
    const promptContent = basePrompts[currentPromptKey];
    
    if (!promptContent) {
        showNotification('Ошибка: промт не найден', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/admin/update-base-prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt_type: currentPromptKey,
                prompt_content: promptContent
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Базовый промт "${currentPromptKey}" успешно обновлен!`, 'success');
        } else {
            showNotification(data.message || 'Ошибка обновления промта', 'error');
        }
    } catch (error) {
        console.error('Ошибка обновления базового промта:', error);
        showNotification('Ошибка обновления промта', 'error');
    }
}

// Функция для перехода к следующему промту
function nextPrompt() {
    if (promptQueue.length === 0) {
        showNotification('Очередь промтов пуста', 'warning');
        return;
    }
    
    // Перемещаем текущий промт в конец очереди
    const currentPrompt = promptQueue[legacyPromptIndex];
    promptQueue.splice(legacyPromptIndex, 1);
    promptQueue.push(currentPrompt);
    
    // Обновляем индекс (остается 0, так как следующий промт теперь первый)
    legacyPromptIndex = 0;
    
    // Обновляем отображение
    loadPromptList();
    updatePromptPreview();
    
    showNotification(`Переход к следующему промту: ${basePrompts[promptQueue[0]]?.split('\n')[0] || 'Неизвестный промт'}`, 'success');
    
    // Автоматически генерируем концертный контент для нового промта
    generateConcertContent();
}

// Функция для обновления предварительного просмотра промта
function updatePromptPreview() {
    const promptText = document.getElementById('prompt-text');
    
    if (promptText && promptQueue.length > 0) {
        const currentPromptKey = promptQueue[legacyPromptIndex];
        const currentPromptContent = basePrompts[currentPromptKey];
        
        if (currentPromptContent) {
            promptText.innerHTML = currentPromptContent.replace(/\n/g, '<br>');
        }
    }
}

// Функции для редактирования промтов
function loadPromptList() {
    const promptList = document.getElementById('prompt-list');
    if (!promptList) return;
    
    promptList.innerHTML = '';
    
    // Создаем элементы для каждого промта в порядке очереди
    promptQueue.forEach((key, index) => {
        const promptItem = createPromptItem(key, basePrompts[key], index === legacyPromptIndex, index);
        promptList.appendChild(promptItem);
    });
}

function createPromptItem(key, content, isCurrent = false, index) {
    const item = document.createElement('div');
    item.className = 'prompt-item';
    if (isCurrent) {
        item.classList.add('current');
    }
    item.draggable = true;
    item.dataset.index = index;
    item.dataset.key = key;
    
    const lines = content.split('\n');
    const title = lines[0];
    const description = lines.slice(1).join(' ');
    
    item.innerHTML = `
        <div class="prompt-item-header">
            <div class="prompt-item-title">${title}</div>
            <div class="prompt-item-actions">
                <button class="prompt-item-btn edit" onclick="editPrompt('${key}')">✏️</button>
                <button class="prompt-item-btn delete" onclick="deletePrompt('${key}')">🗑️</button>
            </div>
            </div>
        <div class="prompt-item-content" onclick="togglePromptContent(this)">
            ${description}
            </div>
        <div class="prompt-edit-form" id="edit-form-${key}">
            <input type="text" id="edit-title-${key}" value="${title}" placeholder="Название промта">
            <textarea id="edit-content-${key}" placeholder="Содержимое промта">${content}</textarea>
            <div class="prompt-edit-actions">
                <button class="save" onclick="savePrompt('${key}')">💾 Сохранить</button>
                <button class="cancel" onclick="cancelEdit('${key}')">❌ Отмена</button>
            </div>
        </div>
    `;
    
    // Добавляем обработчики drag & drop
    item.addEventListener('dragstart', handleDragStart);
    item.addEventListener('dragend', handleDragEnd);
    item.addEventListener('dragover', handleDragOver);
    item.addEventListener('drop', handleDrop);
    
    return item;
}

function togglePromptContent(element) {
    element.classList.toggle('expanded');
}

function editPrompt(key) {
    const form = document.getElementById(`edit-form-${key}`);
    if (form) {
        form.classList.add('active');
    }
}

function cancelEdit(key) {
    const form = document.getElementById(`edit-form-${key}`);
    if (form) {
        form.classList.remove('active');
    }
}

function savePrompt(key) {
    const titleInput = document.getElementById(`edit-title-${key}`);
    const contentInput = document.getElementById(`edit-content-${key}`);
    
    if (!titleInput || !contentInput) return;
    
    const newTitle = titleInput.value.trim();
    const newContent = contentInput.value.trim();
    
    if (!newTitle || !newContent) {
        showNotification('Пожалуйста, заполните все поля', 'warning');
        return;
    }
    
    // Обновляем промт
    basePrompts[key] = newContent;
    
    // Перезагружаем список
    loadPromptList();
    
    // Обновляем селект
    updatePromptSelect();
    
    showNotification(`Промт "${newTitle}" успешно обновлен!`, 'success');
}

function deletePrompt(key) {
    if (confirm('Вы уверены, что хотите удалить этот промт?')) {
        delete basePrompts[key];
        loadPromptList();
        updatePromptSelect();
        showNotification('Промт удален!', 'success');
    }
}

function addNewPrompt() {
    const key = 'custom_' + Date.now();
    const title = prompt('Введите название нового промта:');
    
    if (!title) return;
    
    const content = prompt('Введите содержимое промта:');
    if (!content) return;
    
    basePrompts[key] = content;
    loadPromptList();
    updatePromptSelect();
    showNotification(`Новый промт "${title}" добавлен!`, 'success');
}

function updatePromptSelect() {
    // Функция больше не нужна, так как селект удален
    // Оставляем пустой для совместимости
}

// Drag & Drop функции
function handleDragStart(e) {
    draggedElement = this;
    draggedIndex = parseInt(this.dataset.index);
    this.classList.add('dragging');
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    draggedElement = null;
    draggedIndex = -1;
}

function handleDragOver(e) {
    e.preventDefault();
    this.classList.add('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    
    if (draggedElement && draggedElement !== this) {
        const draggedKey = draggedElement.dataset.key;
        const dropKey = this.dataset.key;
        
        if (draggedKey === dropKey) return;
        
        // Находим индексы в очереди
        const draggedIndex = promptQueue.indexOf(draggedKey);
        const dropIndex = promptQueue.indexOf(dropKey);
        
        if (draggedIndex === -1 || dropIndex === -1) return;
        
        // Перемещаем элементы в очереди
        promptQueue.splice(draggedIndex, 1);
        promptQueue.splice(dropIndex, 0, draggedKey);
        
        // Обновляем индекс текущего промта
        if (draggedIndex === legacyPromptIndex) {
            legacyPromptIndex = dropIndex;
        } else if (dropIndex === legacyPromptIndex) {
            legacyPromptIndex = draggedIndex;
        }
        
        // Перезагружаем список
        loadPromptList();
        updatePromptPreview();
        
        showNotification('Порядок промтов в очереди обновлен!', 'success');
    }
}

// Инициализация промтов при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const promptSelect = document.getElementById('base-prompt');
    const customPromptGroup = document.getElementById('custom-prompt-group');
    const promptText = document.getElementById('prompt-text');
    
    if (promptSelect && customPromptGroup && promptText) {
        // Обновляем предварительный просмотр при изменении выбора
        promptSelect.addEventListener('change', function() {
            const selectedValue = this.value;
            
            if (selectedValue === 'custom') {
                customPromptGroup.style.display = 'block';
                promptText.textContent = 'Введите ваш пользовательский промт...';
            } else {
                customPromptGroup.style.display = 'none';
                promptText.textContent = basePrompts[selectedValue] || basePrompts.pirates;
            }
        });
        
        // Обновляем предварительный просмотр при вводе пользовательского промта
        const customPromptText = document.getElementById('custom-prompt-text');
        if (customPromptText) {
            customPromptText.addEventListener('input', function() {
                if (promptSelect.value === 'custom') {
                    promptText.textContent = this.value || 'Введите ваш пользовательский промт...';
                }
            });
        }
    }
    
    // Загружаем список промтов для редактирования
    loadPromptList();
});

// ===== ФУНКЦИИ РЕДАКТИРОВАНИЯ КОНЦЕРТНОГО КОНТЕНТА =====

// Функция для переключения между режимами просмотра и редактирования
function toggleEdit(fieldId) {
    const displayElement = document.getElementById(fieldId);
    const editElement = document.getElementById(fieldId + '-edit');
    const editBtn = displayElement.parentElement.querySelector('.edit-btn');
    
    if (!displayElement || !editElement || !editBtn) {
        console.error('Элементы для редактирования не найдены:', fieldId);
        return;
    }
    
    const isEditing = editElement.style.display !== 'none';
    
    if (isEditing) {
        // Сохраняем изменения и переключаемся в режим просмотра
        const newValue = editElement.value.trim();
        if (newValue) {
            displayElement.textContent = newValue;
            console.log(`✅ Сохранено изменение для ${fieldId}:`, newValue);
        }
        
        editElement.style.display = 'none';
        displayElement.style.display = 'flex';
        editBtn.textContent = '✏️';
        editBtn.classList.remove('editing');
        
    } else {
        // Переключаемся в режим редактирования
        editElement.value = displayElement.textContent;
        editElement.style.display = 'block';
        displayElement.style.display = 'none';
        editBtn.textContent = '💾';
        editBtn.classList.add('editing');
        
        // Фокусируемся на поле редактирования
        setTimeout(() => {
            editElement.focus();
            editElement.select();
        }, 100);
    }
}

// Функция для сохранения всех изменений
function saveAllEdits() {
    const editableFields = ['current-prompt-title', 'generated-movie-description', 'generated-movie-actors', 'concert-end-message'];
    
    editableFields.forEach(fieldId => {
        const displayElement = document.getElementById(fieldId);
        const editElement = document.getElementById(fieldId + '-edit');
        
        if (editElement && editElement.style.display !== 'none') {
            const newValue = editElement.value.trim();
            if (newValue) {
                displayElement.textContent = newValue;
                editElement.style.display = 'none';
                displayElement.style.display = 'flex';
                
                const editBtn = displayElement.parentElement.querySelector('.edit-btn');
                if (editBtn) {
                    editBtn.textContent = '✏️';
                    editBtn.classList.remove('editing');
                }
            }
        }
    });
    
    console.log('💾 Все изменения сохранены');
}

// Функция для отмены всех изменений
function cancelAllEdits() {
    const editableFields = ['current-prompt-title', 'generated-movie-description', 'generated-movie-actors', 'concert-end-message'];
    
    editableFields.forEach(fieldId => {
        const displayElement = document.getElementById(fieldId);
        const editElement = document.getElementById(fieldId + '-edit');
        
        if (editElement && editElement.style.display !== 'none') {
            editElement.value = displayElement.textContent; // Восстанавливаем исходное значение
            editElement.style.display = 'none';
            displayElement.style.display = 'flex';
            
            const editBtn = displayElement.parentElement.querySelector('.edit-btn');
            if (editBtn) {
                editBtn.textContent = '✏️';
                editBtn.classList.remove('editing');
            }
        }
    });
    
    console.log('❌ Все изменения отменены');
}

// ===== ФУНКЦИИ АВТОМАТИЧЕСКОЙ ГЕНЕРАЦИИ КОНЦЕРТНОГО КОНТЕНТА =====

// Функция для автоматической генерации концертного контента
async function generateConcertContent() {
    console.log('🎬 Начинаем генерацию концертного контента...');
    
    if (promptQueue.length === 0) {
        console.error('❌ Очередь промтов пуста');
        updateConcertDisplay('Ошибка: очередь промтов пуста', 'Ошибка: очередь промтов пуста', 'Ошибка: очередь промтов пуста');
        return;
    }
    
    const currentPromptKey = promptQueue[legacyPromptIndex];
    const currentPromptContent = basePrompts[currentPromptKey];
    
    console.log('📝 Текущий промт:', currentPromptKey, currentPromptContent?.substring(0, 100));
    
    if (!currentPromptContent) {
        console.error('❌ Промт не найден');
        updateConcertDisplay('Ошибка: промт не найден', 'Ошибка: промт не найден', 'Ошибка: промт не найден');
        return;
    }
    
    // Показываем название промта (первая строка)
    const promptTitle = currentPromptContent.split('\n')[0];
    updatePromptTitle(promptTitle);
    console.log('🏷️ Название промта:', promptTitle);
    
    // Показываем индикатор загрузки для остальных полей
    updateConcertDisplay('', 'Генерация...', 'Генерация...');
    
    try {
        console.log('🔄 Генерируем описание и актёров...');
        // Генерируем только описание и актёров параллельно
        const [descriptionResult, actorsResult] = await Promise.all([
            generateContentByType('movie_description', currentPromptContent),
            generateContentByType('movie_actors', currentPromptContent)
        ]);
        
        console.log('✅ Генерация завершена:', { descriptionResult, actorsResult });
        updateConcertDisplay('', descriptionResult, actorsResult);
        
    } catch (error) {
        console.error('❌ Ошибка генерации концертного контента:', error);
        updateConcertDisplay('', 'Ошибка генерации', 'Ошибка генерации');
    }
}

// Вспомогательная функция для генерации контента по типу
async function generateContentByType(type, promptContent) {
    let prompt = '';
    
    switch (type) {
        case 'movie_description':
            prompt = `На основе этого кинематографического стиля: "${promptContent}"\n\nНапиши короткое описание фильма (2-3 предложения) о чем он, какие вопросы поднимает. Стиль должен соответствовать кинематографическому направлению.`;
            break;
        case 'movie_actors':
            prompt = `На основе этого кинематографического стиля: "${promptContent}"\n\nПеречисли актёров/персонажей в главных ролях (3-5 имен), которые подходят к этому стилю фильма. Ответь в формате: "Имя актёра (роль), Имя актёра (роль)"`;
            break;
        default:
            return 'Неизвестный тип';
    }
    
    try {
        console.log(`📤 Отправляем запрос для ${type}:`, prompt.substring(0, 100));
        
        const response = await fetch('/api/admin/generate-content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                type: type
            })
        });
        
        console.log(`📥 Получен ответ для ${type}:`, response.status);
        
        const data = await response.json();
        console.log(`✅ Данные для ${type}:`, data);
        
        if (data.success) {
            return data.content;
        } else {
            console.error(`❌ Ошибка в ответе для ${type}:`, data);
            return 'Ошибка генерации';
        }
    } catch (error) {
        console.error(`❌ Ошибка запроса для ${type}:`, error);
        return 'Ошибка генерации';
    }
}

// Функция для обновления названия промта
function updatePromptTitle(title) {
    const titleElement = document.getElementById('current-prompt-title');
    if (titleElement) {
        titleElement.textContent = title;
    }
}

// Функция для обновления отображения концертного контента
function updateConcertDisplay(title, description, actors) {
    const descriptionElement = document.getElementById('generated-movie-description');
    const actorsElement = document.getElementById('generated-movie-actors');
    
    if (descriptionElement) descriptionElement.textContent = description;
    if (actorsElement) actorsElement.textContent = actors;
}

// ===== ФУНКЦИИ ГЕНЕРАЦИИ КОНЦЕРТНОГО КОНТЕНТА =====

async function generateMovieTitle() {
    if (promptQueue.length === 0) {
        showNotification('Ошибка: очередь промтов пуста', 'error');
        return;
    }
    
    const currentPromptKey = promptQueue[legacyPromptIndex];
    const currentPromptContent = basePrompts[currentPromptKey];
    
    if (!currentPromptContent) {
        showNotification('Ошибка: промт не найден', 'error');
        return;
    }
    
    const prompt = `На основе этого кинематографического стиля: "${currentPromptContent}"\n\nСгенерируй название фильма в этом стиле. Ответь только названием фильма, без дополнительных объяснений.`;
    
    try {
        const response = await fetch('/api/admin/generate-content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                type: 'movie_title'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('movie-title').value = data.content;
            showNotification('Название фильма сгенерировано!', 'success');
        } else {
            showNotification(data.message || 'Ошибка генерации', 'error');
        }
    } catch (error) {
        console.error('Ошибка генерации названия фильма:', error);
        showNotification('Ошибка генерации названия фильма', 'error');
    }
}

async function generateMovieDescription() {
    if (promptQueue.length === 0) {
        showNotification('Ошибка: очередь промтов пуста', 'error');
        return;
    }
    
    const currentPromptKey = promptQueue[legacyPromptIndex];
    const currentPromptContent = basePrompts[currentPromptKey];
    const movieTitle = document.getElementById('movie-title').value;
    
    if (!currentPromptContent) {
        showNotification('Ошибка: промт не найден', 'error');
        return;
    }
    
    const prompt = `На основе этого кинематографического стиля: "${currentPromptContent}"\n\nФильм: "${movieTitle || 'фильм в этом стиле'}"\n\nНапиши короткое описание фильма (2-3 предложения) о чем он, какие вопросы поднимает. Стиль должен соответствовать кинематографическому направлению.`;
    
    try {
        const response = await fetch('/api/admin/generate-content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                type: 'movie_description'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('movie-description').value = data.content;
            showNotification('Описание фильма сгенерировано!', 'success');
        } else {
            showNotification(data.message || 'Ошибка генерации', 'error');
        }
    } catch (error) {
        console.error('Ошибка генерации описания фильма:', error);
        showNotification('Ошибка генерации описания фильма', 'error');
    }
}

async function generateMovieActors() {
    if (promptQueue.length === 0) {
        showNotification('Ошибка: очередь промтов пуста', 'error');
        return;
    }
    
    const currentPromptKey = promptQueue[legacyPromptIndex];
    const currentPromptContent = basePrompts[currentPromptKey];
    const movieTitle = document.getElementById('movie-title').value;
    
    if (!currentPromptContent) {
        showNotification('Ошибка: промт не найден', 'error');
        return;
    }
    
    const prompt = `На основе этого кинематографического стиля: "${currentPromptContent}"\n\nФильм: "${movieTitle || 'фильм в этом стиле'}"\n\nПеречисли актёров/персонажей в главных ролях (3-5 имен), которые подходят к этому стилю фильма. Ответь в формате: "Имя актёра (роль), Имя актёра (роль)"`;
    
    try {
        const response = await fetch('/api/admin/generate-content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                type: 'movie_actors'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('movie-actors').value = data.content;
            showNotification('Актёры/персонажи сгенерированы!', 'success');
        } else {
            showNotification(data.message || 'Ошибка генерации', 'error');
        }
    } catch (error) {
        console.error('Ошибка генерации актёров:', error);
        showNotification('Ошибка генерации актёров', 'error');
    }
}

async function generateAIComment() {
    if (promptQueue.length === 0) {
        showNotification('Ошибка: очередь промтов пуста', 'error');
        return;
    }
    
    const currentPromptKey = promptQueue[legacyPromptIndex];
    const currentPromptContent = basePrompts[currentPromptKey];
    
    if (!currentPromptContent) {
        showNotification('Ошибка: промт не найден', 'error');
        return;
    }
    
    const prompt = `На основе этого кинематографического стиля: "${currentPromptContent}"\n\nНапиши краткий умный комментарий от нейронки для зрителей концерта. Комментарий должен быть связан с киновселенной и стилем фильма, но адаптирован для музыкального концерта. Длина: 1-2 предложения.`;
    
    try {
        const response = await fetch('/api/admin/generate-content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                type: 'ai_comment'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('ai-comment').value = data.content;
            showNotification('Комментарий от нейронки сгенерирован!', 'success');
        } else {
            showNotification(data.message || 'Ошибка генерации', 'error');
        }
    } catch (error) {
        console.error('Ошибка генерации комментария:', error);
        showNotification('Ошибка генерации комментария', 'error');
    }
}

// ===== ФУНКЦИИ УПРАВЛЕНИЯ КОНЦЕРТОМ =====

async function sendTrackMessage() {
    console.log('sendTrackMessage вызвана');
    
    const movieTitle = document.getElementById('current-prompt-title');
    const movieDescription = document.getElementById('generated-movie-description');
    const movieActors = document.getElementById('generated-movie-actors');
    
    console.log('Элементы найдены:', {
        title: movieTitle,
        description: movieDescription,
        actors: movieActors
    });
    
    if (!movieTitle || !movieDescription || !movieActors) {
        console.error('Не все элементы найдены');
        showNotification('Ошибка: не все поля найдены', 'error');
        return;
    }
    
    const titleValue = movieTitle.textContent.trim();
    const descriptionValue = movieDescription.textContent.trim();
    const actorsValue = movieActors.textContent.trim();
    
    console.log('Значения полей:', {
        title: titleValue,
        description: descriptionValue,
        actors: actorsValue
    });
    
    if (!titleValue || !descriptionValue || !actorsValue) {
        showNotification('Пожалуйста, заполните все поля', 'warning');
        return;
    }
    
    const message = `📽️ **${titleValue}**

${descriptionValue}

**Актёры/персонажи:** ${actorsValue}

---

Какие образы или пейзажи возникают у вас, когда вы думаете об этой истории?`;
    
    try {
        const response = await fetch('/api/admin/send-concert-message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'track_message',
                content: message
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Сообщение перед треком отправлено!', 'success');
            // Очищаем поля
            movieTitle.value = '';
            movieDescription.value = '';
            movieActors.value = '';
        } else {
            showNotification(data.message || 'Ошибка отправки сообщения', 'error');
        }
    } catch (error) {
        console.error('Ошибка отправки сообщения перед треком:', error);
        showNotification('Ошибка отправки сообщения', 'error');
    }
}

async function sendAudienceResponse() {
    const aiComment = document.getElementById('ai-comment').value.trim();
    
    if (!aiComment) {
        showNotification('Пожалуйста, введите комментарий от нейронки', 'warning');
        return;
    }
    
    const message = `${aiComment}

Спасибо, что поделились своими идеями, мы обязательно постараемся их учесть. 
Продолжайте наслаждаться музыкой и визуальными образами на сцене!`;
    
    try {
        const response = await fetch('/api/admin/send-concert-message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'audience_response',
                content: message
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Ответ зрителям отправлен!', 'success');
            // Очищаем поле
            document.getElementById('ai-comment').value = '';
        } else {
            showNotification(data.message || 'Ошибка отправки ответа', 'error');
        }
    } catch (error) {
        console.error('Ошибка отправки ответа зрителям:', error);
        showNotification('Ошибка отправки ответа', 'error');
    }
}

async function sendConcertEnd() {
    // Получаем сообщение из редактируемого поля
    const messageElement = document.getElementById('concert-end-message');
    if (!messageElement) {
        console.error('Элемент concert-end-message не найден');
        showNotification('Ошибка: поле сообщения не найдено', 'error');
        return;
    }
    
    const message = messageElement.textContent.trim();
    
    if (!message) {
        showNotification('Пожалуйста, заполните финальное сообщение', 'warning');
        return;
    }
    
    console.log('Отправляем финальное сообщение:', message);
    
    try {
        const response = await fetch('/api/admin/send-concert-message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'concert_end',
                content: message
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Финальное сообщение отправлено!', 'success');
        } else {
            showNotification(data.message || 'Ошибка отправки финального сообщения', 'error');
        }
    } catch (error) {
        console.error('Ошибка отправки финального сообщения:', error);
        showNotification('Ошибка отправки финального сообщения', 'error');
    }
}

// Экспорт функций для использования в HTML






window.refreshMessages = refreshMessages;
window.resetStats = resetStats;
window.exportData = exportData;
window.updateBasePrompt = updateBasePrompt;
window.loadPromptList = loadPromptList;
window.editPrompt = editPrompt;
window.deletePrompt = deletePrompt;
window.addNewPrompt = addNewPrompt;
window.togglePromptContent = togglePromptContent;
window.savePrompt = savePrompt;
window.cancelEdit = cancelEdit;
window.sendTrackMessage = sendTrackMessage;
window.sendAudienceResponse = sendAudienceResponse;
window.sendConcertEnd = sendConcertEnd;
window.nextPrompt = nextPrompt;
window.generateMovieTitle = generateMovieTitle;
window.generateMovieDescription = generateMovieDescription;
window.generateMovieActors = generateMovieActors;
window.generateAIComment = generateAIComment;
window.generateConcertContent = generateConcertContent;
window.generateContentByType = generateContentByType;
window.updateConcertDisplay = updateConcertDisplay;
window.updatePromptTitle = updatePromptTitle;
window.toggleEdit = toggleEdit;
window.saveAllEdits = saveAllEdits;
window.cancelAllEdits = cancelAllEdits;

// ============================================================================
// NEW: Smart Batch System Functions
// ============================================================================

// Загрузка статистики умных батчей
async function loadSmartBatchStats() {
    try {
        const response = await fetch('/api/admin/smart-batches/stats');
        const data = await response.json();
        
        if (data.success) {
            updateSmartBatchStatsDisplay(data.batch_stats, data.processor_stats);
        }
    } catch (error) {
        console.error('Ошибка загрузки статистики батчей:', error);
    }
}

// Переменные для управления выпадающим списком статистики
let isStatsDropdownOpen = false;

// Переключение выпадающего списка статистики
function toggleStatsDropdown() {
    const dropdown = document.getElementById('stats-dropdown');
    const header = document.querySelector('.stats-dropdown-header');
    
    isStatsDropdownOpen = !isStatsDropdownOpen;
    
    if (isStatsDropdownOpen) {
        dropdown.classList.add('active');
        header.classList.add('active');
        
        setTimeout(() => {
            document.addEventListener('click', closeStatsDropdownOnOutsideClick);
        }, 100);
    } else {
        dropdown.classList.remove('active');
        header.classList.remove('active');
        document.removeEventListener('click', closeStatsDropdownOnOutsideClick);
    }
}

// Закрытие выпадающего списка статистики при клике вне его
function closeStatsDropdownOnOutsideClick(event) {
    const dropdown = document.getElementById('stats-dropdown');
    const header = document.querySelector('.stats-dropdown-header');
    
    if (!dropdown.contains(event.target) && !header.contains(event.target)) {
        dropdown.classList.remove('active');
        header.classList.remove('active');
        isStatsDropdownOpen = false;
        document.removeEventListener('click', closeStatsDropdownOnOutsideClick);
    }
}

// Обновление отображения статистики
function updateSmartBatchStatsDisplay(batchStats, processorStats) {
    const statsContainer = document.getElementById('smart-batch-stats');
    const statsSummary = document.getElementById('stats-summary');
    
    if (!statsContainer) return;
    
    // Обновляем заголовок выпадающего списка
    if (statsSummary) {
        statsSummary.textContent = `📊 Сообщений: ${batchStats.total_messages} | Батчей: ${batchStats.total_batches} | Завершено: ${batchStats.completed_batches}`;
    }
    
    const html = `
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">Сообщений в очереди</div>
                <div class="stat-value">${batchStats.total_messages}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Всего батчей</div>
                <div class="stat-value">${batchStats.total_batches}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Ожидают обработки</div>
                <div class="stat-value pending">${batchStats.pending_batches}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">В обработке</div>
                <div class="stat-value processing">${batchStats.processing_batches}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">С миксом</div>
                <div class="stat-value mixed">${batchStats.mixed_batches}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Генерация</div>
                <div class="stat-value generating">${batchStats.generating_batches}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Завершено</div>
                <div class="stat-value completed">${batchStats.completed_batches}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Ошибки</div>
                <div class="stat-value failed">${batchStats.failed_batches}</div>
            </div>
        </div>
        <div class="processor-stats">
            <p>📊 Обработано: ${processorStats.total_processed} | Ошибок: ${processorStats.total_failed}</p>
            <p>🖼️ Изображений сгенерировано: ${processorStats.total_images_generated}</p>
            <p>⏱️ Среднее время обработки: ${processorStats.average_processing_time.toFixed(2)}s</p>
            <p>🔄 Статус: ${processorStats.is_processing ? '🟢 Обрабатывается' : '⚪ Ожидание'}</p>
        </div>
    `;
    
    statsContainer.innerHTML = html;
}

// Загрузка списка батчей
async function loadSmartBatchList() {
    try {
        const response = await fetch('/api/admin/smart-batches/list');
        const data = await response.json();
        
        if (data.success) {
            updateSmartBatchListDisplay(data.batches);
        }
    } catch (error) {
        console.error('Ошибка загрузки списка батчей:', error);
    }
}

// Обновление отображения списка батчей
function updateSmartBatchListDisplay(batches) {
    const listContainer = document.getElementById('smart-batch-list');
    if (!listContainer) return;
    
    if (batches.length === 0) {
        listContainer.innerHTML = '<p class="no-batches">Нет доступных батчей</p>';
        return;
    }
    
    const html = batches.map(batch => `
        <div class="batch-item status-${batch.status}">
            <div class="batch-header">
                <span class="batch-id">Батч ${batch.id.substring(0, 8)}</span>
                <span class="batch-status status-${batch.status}">${getStatusText(batch.status)}</span>
            </div>
            <div class="batch-details">
                <p><strong>Сообщений:</strong> ${batch.message_count}</p>
                ${batch.mixed_text ? `<p><strong>Микс:</strong> ${batch.mixed_text}</p>` : ''}
                ${batch.image_path ? `<p><strong>Изображение:</strong> ${batch.image_path}</p>` : ''}
                ${batch.processing_time ? `<p><strong>Время:</strong> ${batch.processing_time.toFixed(2)}s</p>` : ''}
                ${batch.error_message ? `<p class="error"><strong>Ошибка:</strong> ${batch.error_message}</p>` : ''}
            </div>
        </div>
    `).join('');
    
    listContainer.innerHTML = html;
}

// Получение текста статуса
function getStatusText(status) {
    const statusMap = {
        'pending': '⏳ Ожидает',
        'processing': '⚙️ Обработка',
        'mixed': '🎭 Микс готов',
        'generating': '🎨 Генерация',
        'completed': '✅ Завершено',
        'failed': '❌ Ошибка'
    };
    return statusMap[status] || status;
}

// Принудительное создание батчей
async function forceCreateBatches() {
    try {
        const button = document.getElementById('create-batches-btn');
        if (button) {
            button.disabled = true;
            button.textContent = 'Создание...';
        }
        
        const response = await fetch('/api/admin/smart-batches/create', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Создано ${data.batches_created} батчей`, 'success');
            await loadSmartBatchStats();
            await loadSmartBatchList();
        } else {
            showNotification(data.error || 'Ошибка создания батчей', 'error');
        }
    } catch (error) {
        console.error('Ошибка создания батчей:', error);
        showNotification('Ошибка создания батчей', 'error');
    } finally {
        const button = document.getElementById('create-batches-btn');
        if (button) {
            button.disabled = false;
            button.textContent = '🔄 Создать батчи';
        }
    }
}

// Обработка следующего батча
async function processNextBatch() {
    try {
        const button = document.getElementById('process-next-btn');
        if (button) {
            button.disabled = true;
            button.textContent = 'Обработка...';
        }
        
        const response = await fetch('/api/admin/smart-batches/process-next', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showNotification(data.message, 'success');
            await loadSmartBatchStats();
            await loadSmartBatchList();
            await loadCurrentMixedText();
        } else {
            showNotification(data.message || 'Нет доступных батчей', 'warning');
        }
    } catch (error) {
        console.error('Ошибка обработки батча:', error);
        showNotification('Ошибка обработки батча', 'error');
    } finally {
        const button = document.getElementById('process-next-btn');
        if (button) {
            button.disabled = false;
            button.textContent = '▶️ Обработать следующий';
        }
    }
}

// Загрузка текущего миксированного текста
async function loadCurrentMixedText() {
    try {
        const response = await fetch('/api/admin/smart-batches/current-mixed-text');
        const data = await response.json();
        
        if (data.success) {
            const mixedTextElement = document.getElementById('current-mixed-text');
            if (mixedTextElement) {
                mixedTextElement.textContent = data.mixed_text;
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки миксированного текста:', error);
    }
}

// Автообновление для умных батчей
function startSmartBatchAutoUpdate() {
    // Загружаем данные сразу
    loadSmartBatchStats();
    loadSmartBatchList();
    loadCurrentMixedText();
    loadGeneratedImages();
    
    // Обновляем каждые 5 секунд
    setInterval(async () => {
        await loadSmartBatchStats();
        await loadSmartBatchList();
        await loadCurrentMixedText();
        await loadGeneratedImages();
    }, 5000);
}

// Загрузка сгенерированных изображений
async function loadGeneratedImages() {
    try {
        const response = await fetch('/api/admin/smart-batches/images');
        const data = await response.json();
        
        if (data.success) {
            updateImagesGridDisplay(data.images);
        } else {
            console.error('Ошибка загрузки изображений:', data.error);
        }
    } catch (error) {
        console.error('Ошибка загрузки изображений:', error);
    }
}

// Обновление отображения сетки изображений
function updateImagesGridDisplay(images) {
    const imagesGrid = document.getElementById('images-grid');
    
    if (!images || images.length === 0) {
        imagesGrid.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">Нет сгенерированных изображений</div>';
        return;
    }
    
    imagesGrid.innerHTML = images.map(image => `
        <div class="image-card" onclick="openImageModal('${image.image_url}', '${image.mixed_text}')">
            <img src="${image.image_url}" alt="${image.mixed_text}" loading="lazy">
            <div class="image-card-content">
                <div class="image-card-title">${image.mixed_text}</div>
                <div class="image-card-meta">
                    <div class="image-card-time">${formatTime(image.completed_at)}</div>
                    <div class="image-card-stats">
                        <span class="image-card-stat messages">${image.message_count} сообщ.</span>
                        <span class="image-card-stat time">${image.processing_time.toFixed(1)}с</span>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

// Форматирование времени
function formatTime(timestamp) {
    if (!timestamp) return 'Неизвестно';
    
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    
    if (diffMins < 1) return 'Только что';
    if (diffMins < 60) return `${diffMins}м назад`;
    if (diffHours < 24) return `${diffHours}ч назад`;
    
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Модальное окно для просмотра изображения
function openImageModal(imageUrl, title) {
    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        cursor: pointer;
    `;
    
    modal.innerHTML = `
        <div style="max-width: 90%; max-height: 90%; position: relative;">
            <img src="${imageUrl}" alt="${title}" style="max-width: 100%; max-height: 100%; border-radius: 8px;">
            <div style="position: absolute; top: -40px; left: 0; color: white; font-size: 18px; font-weight: bold;">
                ${title}
            </div>
            <div style="position: absolute; top: -40px; right: 0; color: white; font-size: 24px; cursor: pointer;">
                ✕
            </div>
        </div>
    `;
    
    // Закрытие модального окна
    modal.onclick = () => document.body.removeChild(modal);
    
    document.body.appendChild(modal);
}

// Данные промтов из программы концерта
const concertPrompts = [
    {
        id: 1,
        title: "Рокки",
        description: "Гритти-драма по фильму «Рокки»: натриевые фонари, сырые спортзалы, пот и мел; тренировки; палитра кирпич, сталь, выцветший индиго; контраст холода улицы и тёплого лампового света; плёночное зерно, дальний план.",
        duration: "4:13"
    },
    {
        id: 2,
        title: "Бэтмен",
        description: "Кинореализм нео-нуар «Бэтмен (Нолана)»: дождливый ночной мегаполис, контраст тёплых натриевых фонарей и холодного циана; объёмный свет/дым, неоновые отражения на мокром асфальте, длинные тени, дальний план, лёгкое плёночное зерно.",
        duration: "3:56"
    },
    {
        id: 3,
        title: "Охотники за приведениями",
        description: "Кинореализм паранормального '80s в духе фильмов Охотники за приведениями: туман, объёмный свет, неон-зелёные эктопары, тёплые фонари, lens flare, призраки, ловушка для призраков, из оружия охотников красные с желтым как молнии лучи.",
        duration: "3:09"
    },
    {
        id: 4,
        title: "Гладиатор",
        description: "Исторический эпик по фильму «Гладиатор»: арена в пыли, лучи солнца, кожа/сталь/лён, гул толпы, контровый свет; палитра охра, песок, ржавое золото и холодная сталь, дальний план.",
        duration: "3:22"
    },
    {
        id: 5,
        title: "Шерлок Холмс",
        description: "Кинематографичный реализм BBC Sherlock: дождливый Лондон, мокрый асфальт, кирпич/стекло; палитра холодный синий/циан + тёплые фонари; без крупных лиц; боковой/контровый свет, отражения и блики, мелкое боке, малая ГРИП; диагональные ракурсы, лёгкое плёночное зерно.",
        duration: "4:53"
    },
    {
        id: 6,
        title: "Интерстеллар",
        description: "Кинематографичный hard-sci-fi реализм по фильму Интерстеллар: чистая оптика, высокий контраст, мягкая дымка; палитра холодный синий/сталь, угольный чёрный, пыльная охра, янтарное солнце, белые скафандры; звёздные поля, лёгкое гравитационное линзирование, тонкий lens flare, объёмный свет/пыль, широкие планы, масштаб и время.",
        duration: "5:20"
    },
    {
        id: 7,
        title: "Миссия: невыполнима",
        description: "Техно-шпионский триллер по фильму «Миссия: невыполнима»: стекло и сталь, циановые рефлексы, тросы, блики; ритм тикает, чистые силуэты гаджетов, дальний план.",
        duration: "2:55"
    },
    {
        id: 8,
        title: "Леон",
        description: "Нео-нуар '90s по фильму Леон, Нью-Йорк: тёплый вольфрам, холодный флуоресцент, высокий контраст, узкая ГРИП, низкие ракурсы, полосы света от жалюзи; мокрый асфальт, отражения, дым/пыль в лучах, мягкое боке, плёночное зерно; палитра оливковый/хаки, чёрный, серый бетон, латунь; без читаемых надписей.",
        duration: "4:23"
    },
    {
        id: 9,
        title: "Звёздные войны",
        description: "Космическая опера по «Звёздным войнам»: «истёртая техника», гигантские корабли, гиперпролёты, двойные солнца; лазерные мечи, дроиды, туман объёма; палитра пустынных охр и холодного космоса, дальний план.",
        duration: "3:58"
    },
    {
        id: 10,
        title: "Le Professionnel (1981)",
        description: "Французский нео-нуар по фильму «Le Professionnel» (1981): парижский камень после дождя, дым в лучах, тренч и тень шляпы; палитра сепия, олива, графит, латунь; мягкая виньетка, дальний план.",
        duration: "4:16"
    },
    {
        id: 11,
        title: "Убить Билла",
        description: "Графичный гриндхаус по фильму «Убить Билла»: жёсткий боковой и контровый свет, резкие тени; палитра жёлтый+чёрный, алый, тёмное дерево, сталь; кожа, шёлк, брызги, плёночное зерно, дальний план.",
        duration: "3:34"
    },
    {
        id: 12,
        title: "Игра престолов",
        description: "Мрачный кинематографичный реализм по вселенной сериала Игра престолов; замок, дракон; суровая атмосфера, мягкая дымка; палитра: сланцевый серый, сталь, холодный синий, охра/терракота, выцветшие ткани, тёмное дерево, тёплые свечи/факелы; фактуры: камень/шифер, шерсть/мех, кожа, кованое железо; широкий план, масштаб, без крупных лиц.",
        duration: "4:30"
    },
    {
        id: 13,
        title: "Мы. Верим в любовь",
        description: "Инди-ромдрама по фильму «Мы. Верим в любовь»: натуральный свет, мягкое боке; пастель и тёплый янтарь против прохладного серо-голубого; шорох ткани, дальний план.",
        duration: "4:03"
    },
    {
        id: 14,
        title: "1+1",
        description: "Тёплая драмеди по фильму «1+1»: янтарные интерьеры и прохладные экстерьеры, движение в кадре, палитра слоновая кость, тёмное дерево, графит; мягкий контраст, дальний план.",
        duration: "4:31"
    },
    {
        id: 15,
        title: "Агент 007",
        description: "Глянцевый шпионаж по франшизе «Агент 007»: смокинги, казино, пентхаусы, автомобили, экзотические локации; циан и золото, анаморфные блики, точный ключевой свет; дальний план.",
        duration: "4:32"
    },
    {
        id: 16,
        title: "Криминальное чтиво",
        description: "Нео-нуар '90s по фильму «Криминальное чтиво»: ретро автомобили, винил, ироничный пафос; палитра горчица, вишня, чёрный; плёночное зерно, дальний план.",
        duration: "2:57"
    },
    {
        id: 17,
        title: "Свой среди чужих, чужой среди своих",
        description: "Советский остерн по фильму «Свой среди чужих, чужой среди своих»: степь, мираж, пыльный эшелон, лошади и кожанки; широкие панорамы; палитра охра, пепел, выгоревшая синь, дальний план.",
        duration: "3:03"
    },
    {
        id: 18,
        title: "Пираты Карибского моря",
        description: "Мрачный кинематографичный реализм во вселенной Пиратов карибского моря; деревянные корабли с парусами и пушками; пираты; морская дымка, контраст, рим-свет; палитра: сталь/свинец воды, изумруд/бирюза, мох, мокрое дерево, патина бронзы, янтарные блики; фактуры: соль на канатах, камень, рваная парусина, брызги; широкий план, масштаб, без крупных лиц.",
        duration: "3:13"
    },
    {
        id: 19,
        title: "Лебединое озеро",
        description: "Балет «Лебединое озеро»: сцена у лунного озера, туман и зеркальные отражения; выразительные линии рук и па, тюлевые пачки, перья, пуанты. Палитра холодный синий и серебро + мягкий тёплый свет рампы; контровый «лунный» рим-свет, лёгкая дымка, деликатное размытие движения, бархат и дерево декора, дальний план.",
        duration: "4:42"
    }
];

// Переменные для управления промтами
let currentPromptIndex = 0;
let isDropdownOpen = false;

// Инициализация промтов
function initializePrompts() {
    console.log('🎬 Инициализация промтов...');
    console.log('📊 Количество промтов:', concertPrompts.length);
    
    loadPrompts();
    updatePromptDisplay();
    
    console.log('✅ Промты инициализированы');
    console.log('🔍 Элементы DOM:', {
        dropdown: document.getElementById('prompt-dropdown'),
        header: document.querySelector('.prompt-dropdown-header'),
        list: document.getElementById('prompt-list')
    });
}

// Загрузка промтов
function loadPrompts() {
    const promptList = document.getElementById('prompt-list');
    promptList.innerHTML = '';
    
    concertPrompts.forEach((prompt, index) => {
        const promptItem = createPromptItem(prompt, index);
        promptList.appendChild(promptItem);
    });
}

// Создание элемента промта
function createPromptItem(prompt, index) {
    const item = document.createElement('div');
    item.className = 'prompt-item';
    item.draggable = true;
    item.dataset.index = index;
    
    item.innerHTML = `
        <div class="prompt-drag-handle">⋮⋮</div>
        <div class="prompt-item-content">
            <div class="prompt-item-title">${prompt.title}</div>
            <div class="prompt-item-description">${prompt.description}</div>
            <div class="prompt-item-duration">⏱️ ${prompt.duration}</div>
        </div>
        <div class="prompt-item-actions">
            <button class="prompt-action-btn edit" onclick="editPrompt(${index})" title="Редактировать">✏️</button>
            <button class="prompt-action-btn delete" onclick="deletePrompt(${index})" title="Удалить">🗑️</button>
        </div>
    `;
    
    // Обработчики drag and drop
    item.addEventListener('dragstart', handleDragStart);
    item.addEventListener('dragover', handleDragOver);
    item.addEventListener('drop', handleDrop);
    item.addEventListener('dragend', handleDragEnd);
    
    // Обработчик клика для выбора промта
    item.addEventListener('click', (e) => {
        if (!e.target.closest('.prompt-action-btn')) {
            selectPrompt(index);
        }
    });
    
    return item;
}

// Переключение выпадающего списка
function togglePromptDropdown() {
    console.log('🔄 Переключение выпадающего списка...');
    console.log('📊 Текущее состояние:', isDropdownOpen);
    
    const dropdown = document.getElementById('prompt-dropdown');
    const header = document.querySelector('.prompt-dropdown-header');
    
    console.log('🔍 Элементы DOM:', { dropdown, header });
    
    isDropdownOpen = !isDropdownOpen;
    
    if (isDropdownOpen) {
        dropdown.classList.add('active');
        header.classList.add('active');
        console.log('✅ Выпадающий список открыт');
        
        // Добавляем обработчик клика вне списка для закрытия
        setTimeout(() => {
            document.addEventListener('click', closeDropdownOnOutsideClick);
        }, 100);
    } else {
        dropdown.classList.remove('active');
        header.classList.remove('active');
        console.log('❌ Выпадающий список закрыт');
        document.removeEventListener('click', closeDropdownOnOutsideClick);
    }
}

// Закрытие выпадающего списка при клике вне его
function closeDropdownOnOutsideClick(event) {
    const dropdown = document.getElementById('prompt-dropdown');
    const header = document.querySelector('.prompt-dropdown-header');
    
    if (!dropdown.contains(event.target) && !header.contains(event.target)) {
        dropdown.classList.remove('active');
        header.classList.remove('active');
        isDropdownOpen = false;
        document.removeEventListener('click', closeDropdownOnOutsideClick);
    }
}

// Выбор промта
function selectPrompt(index) {
    currentPromptIndex = index;
    const prompt = concertPrompts[index];
    
    document.getElementById('current-prompt-title').textContent = prompt.title;
    document.getElementById('prompt-text').innerHTML = `
        <strong>${prompt.title}</strong><br>
        <span style="color: #007bff; font-weight: 600;">⏱️ ${prompt.duration}</span><br><br>
        ${prompt.description}
    `;
    
    togglePromptDropdown();
}

// Обновление отображения промта
function updatePromptDisplay() {
    if (concertPrompts.length > 0) {
        selectPrompt(currentPromptIndex);
    }
}

// Drag and Drop обработчики
function handleDragStart(e) {
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.target.outerHTML);
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const dragging = document.querySelector('.dragging');
    const afterElement = getDragAfterElement(e.target.closest('.prompt-list'), e.clientY);
    
    if (afterElement == null) {
        e.target.closest('.prompt-list').appendChild(dragging);
    } else {
        e.target.closest('.prompt-list').insertBefore(dragging, afterElement);
    }
}

function handleDrop(e) {
    e.preventDefault();
    // Обновление порядка промтов будет реализовано позже
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.prompt-item:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// Редактирование промта
function editPrompt(index) {
    const prompt = concertPrompts[index];
    const newTitle = window.prompt('Редактировать название:', prompt.title);
    if (newTitle !== null) {
        prompt.title = newTitle;
        loadPrompts();
        updatePromptDisplay();
    }
}

// Удаление промта
function deletePrompt(index) {
    if (confirm('Удалить этот промт?')) {
        concertPrompts.splice(index, 1);
        if (currentPromptIndex >= concertPrompts.length) {
            currentPromptIndex = Math.max(0, concertPrompts.length - 1);
        }
        loadPrompts();
        updatePromptDisplay();
    }
}

// Добавление нового промта
function addNewPrompt() {
    const title = window.prompt('Название нового промта:');
    if (title) {
        const newPrompt = {
            id: concertPrompts.length + 1,
            title: title,
            description: 'Описание промта...',
            duration: '0:00'
        };
        concertPrompts.push(newPrompt);
        loadPrompts();
        selectPrompt(concertPrompts.length - 1);
    }
}

// Следующий промт
function nextPrompt() {
    if (concertPrompts.length > 0) {
        currentPromptIndex = (currentPromptIndex + 1) % concertPrompts.length;
        selectPrompt(currentPromptIndex);
    }
}

// Обновление базового промта
function updateBasePrompt() {
    if (concertPrompts.length > 0) {
        const prompt = concertPrompts[currentPromptIndex];
        console.log('Обновление базового промта:', prompt.title);
        // Здесь будет логика обновления промта на сервере
    }
}

// Экспорт функций промтов
window.togglePromptDropdown = togglePromptDropdown;
window.selectPrompt = selectPrompt;
window.editPrompt = editPrompt;
window.deletePrompt = deletePrompt;
window.addNewPrompt = addNewPrompt;
window.nextPrompt = nextPrompt;
window.updateBasePrompt = updateBasePrompt;
window.initializePrompts = initializePrompts;

// Функция для очистки всех сообщений
async function clearAllMessages() {
    try {
        // Показываем подтверждение
        const confirmed = confirm('⚠️ ВНИМАНИЕ!\n\nВы уверены, что хотите очистить ВСЕ сообщения?\n\nЭто действие нельзя отменить!\n\nНажмите OK для подтверждения или Отмена для отмены.');
        
        if (!confirmed) {
            console.log('Очистка сообщений отменена пользователем');
            return;
        }
        
        // Показываем индикатор загрузки
        const clearBtn = document.getElementById('clear-messages-btn');
        const originalText = clearBtn.textContent;
        clearBtn.disabled = true;
        clearBtn.textContent = '🔄 Очистка...';
        
        // Отправляем запрос на очистку
        const response = await fetch('/api/admin/clear-messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Показываем уведомление об успехе
            alert('✅ Все сообщения успешно очищены!');
            
            // Обновляем статистику и список батчей
            await loadSmartBatchStats();
            await loadSmartBatchList();
            
            console.log('Сообщения успешно очищены');
        } else {
            // Показываем ошибку
            alert(`❌ Ошибка очистки сообщений: ${data.message}`);
            console.error('Ошибка очистки сообщений:', data.message);
        }
        
    } catch (error) {
        console.error('Ошибка при очистке сообщений:', error);
        alert('❌ Произошла ошибка при очистке сообщений. Проверьте консоль для подробностей.');
    } finally {
        // Восстанавливаем кнопку
        const clearBtn = document.getElementById('clear-messages-btn');
        clearBtn.disabled = false;
        clearBtn.textContent = '🗑️ Очистить сообщения';
    }
}

// Экспортируем новые функции
window.loadSmartBatchStats = loadSmartBatchStats;
window.loadSmartBatchList = loadSmartBatchList;
window.forceCreateBatches = forceCreateBatches;
window.processNextBatch = processNextBatch;
window.loadCurrentMixedText = loadCurrentMixedText;
window.loadGeneratedImages = loadGeneratedImages;
window.startSmartBatchAutoUpdate = startSmartBatchAutoUpdate;
window.openImageModal = openImageModal;
window.toggleStatsDropdown = toggleStatsDropdown;
window.clearAllMessages = clearAllMessages;
