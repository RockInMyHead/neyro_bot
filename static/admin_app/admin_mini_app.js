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
        await refreshMessages();
        await generateMixedText();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
    }
}

function startAutoUpdate() {
    updateInterval = setInterval(async () => {
        try {
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
                promptText.textContent = basePrompts[selectedValue] || basePrompts.default;
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
    const promptSelect = document.getElementById('base-prompt');
    const customPromptText = document.getElementById('custom-prompt-text');
    
    if (!promptSelect) {
        showNotification('Ошибка: элемент выбора промта не найден', 'error');
        return;
    }
    
    const selectedType = promptSelect.value;
    let promptContent;
    
    if (selectedType === 'custom') {
        if (!customPromptText || !customPromptText.value.trim()) {
            showNotification('Пожалуйста, введите пользовательский промт', 'warning');
            return;
        }
        promptContent = customPromptText.value.trim();
    } else {
        promptContent = basePrompts[selectedType] || basePrompts.default;
    }
    
    try {
        const response = await fetch('/api/admin/update-base-prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt_type: selectedType,
                prompt_content: promptContent
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Базовый промт "${selectedType}" успешно обновлен!`, 'success');
        } else {
            showNotification(data.message || 'Ошибка обновления промта', 'error');
        }
    } catch (error) {
        console.error('Ошибка обновления базового промта:', error);
        showNotification('Ошибка обновления промта', 'error');
    }
}

// Функции для редактирования промтов
function loadPromptList() {
    const promptList = document.getElementById('prompt-list');
    if (!promptList) return;
    
    promptList.innerHTML = '';
    
    Object.entries(basePrompts).forEach(([key, content], index) => {
        const promptItem = createPromptItem(key, content, index);
        promptList.appendChild(promptItem);
    });
}

function createPromptItem(key, content, index) {
    const item = document.createElement('div');
    item.className = 'prompt-item';
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
                <button class="prompt-item-btn edit" onclick="editPrompt('${key}', ${index})">✏️</button>
                <button class="prompt-item-btn delete" onclick="deletePrompt('${key}', ${index})">🗑️</button>
            </div>
        </div>
        <div class="prompt-item-content" onclick="togglePromptContent(this)">
            ${description}
        </div>
        <div class="prompt-edit-form" id="edit-form-${key}">
            <input type="text" id="edit-title-${key}" value="${title}" placeholder="Название промта">
            <textarea id="edit-content-${key}" placeholder="Содержимое промта">${content}</textarea>
            <div class="prompt-edit-actions">
                <button class="save" onclick="savePrompt('${key}', ${index})">💾 Сохранить</button>
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

function editPrompt(key, index) {
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

function savePrompt(key, index) {
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

function deletePrompt(key, index) {
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
    const select = document.getElementById('base-prompt');
    if (!select) return;
    
    // Сохраняем текущее значение
    const currentValue = select.value;
    
    // Очищаем опции (кроме custom)
    select.innerHTML = '<option value="custom">Пользовательский</option>';
    
    // Добавляем все промты
    Object.entries(basePrompts).forEach(([key, content]) => {
        const lines = content.split('\n');
        const title = lines[0];
        const option = document.createElement('option');
        option.value = key;
        option.textContent = title;
        select.appendChild(option);
    });
    
    // Восстанавливаем значение
    if (currentValue && basePrompts[currentValue]) {
        select.value = currentValue;
    }
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
        const dropIndex = parseInt(this.dataset.index);
        
        // Перемещаем элементы в массиве
        const promptEntries = Object.entries(basePrompts);
        const draggedItem = promptEntries[draggedIndex];
        promptEntries.splice(draggedIndex, 1);
        promptEntries.splice(dropIndex, 0, draggedItem);
        
        // Обновляем объект промтов
        Object.keys(basePrompts).forEach(key => delete basePrompts[key]);
        promptEntries.forEach(([key, value]) => {
            basePrompts[key] = value;
        });
        
        // Перезагружаем список
        loadPromptList();
        updatePromptSelect();
        
        showNotification('Порядок промтов обновлен!', 'success');
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

// ===== ФУНКЦИИ УПРАВЛЕНИЯ КОНЦЕРТОМ =====

async function sendTrackMessage() {
    console.log('sendTrackMessage вызвана');
    
    const movieTitle = document.getElementById('movie-title');
    const movieDescription = document.getElementById('movie-description');
    const movieActors = document.getElementById('movie-actors');
    
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
    
    const titleValue = movieTitle.value.trim();
    const descriptionValue = movieDescription.value.trim();
    const actorsValue = movieActors.value.trim();
    
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

Какие образы или пейзажи возникают у вас, когда вы думаете об этой истории? 

Пожалуйста, ответьте 1–5 словами. Можно написать сейчас или во время исполнения, но только один раз в рамках этого произведения.`;
    
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
    const message = `Спасибо, что были с нами — Main Strings Orchestra × Neuroevent.
Оставьте короткий отзыв — это помогает нам становиться лучше!
P.S. Ответы анонимны.`;
    
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
window.generateMixedText = generateMixedText;
window.resetStats = resetStats;
window.exportData = exportData;
window.generateImageFromMix = generateImageFromMix;
window.downloadGeneratedImage = downloadGeneratedImage;
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
