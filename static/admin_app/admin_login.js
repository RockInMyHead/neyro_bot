// Admin Login JavaScript

// DOM элементы
const loginForm = document.getElementById('login-form');
const passwordInput = document.getElementById('password');
const loginBtn = document.getElementById('login-btn');
const btnText = loginBtn.querySelector('.btn-text');
const btnLoading = loginBtn.querySelector('.btn-loading');
const errorMessage = document.getElementById('error-message');

// Состояние формы
let isSubmitting = false;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔐 Страница входа администратора загружена');
    
    // Фокус на поле пароля
    passwordInput.focus();
    
    // Обработчик отправки формы
    loginForm.addEventListener('submit', handleLogin);
    
    // Обработчик нажатия Enter
    passwordInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !isSubmitting) {
            handleLogin(e);
        }
    });
    
    // Очистка ошибки при вводе
    passwordInput.addEventListener('input', clearError);
});

// Обработка входа
async function handleLogin(e) {
    e.preventDefault();
    
    if (isSubmitting) return;
    
    const password = passwordInput.value.trim();
    
    if (!password) {
        showError('Введите пароль');
        return;
    }
    
    isSubmitting = true;
    setLoadingState(true);
    clearError();
    
    try {
        console.log('🔐 Отправка запроса входа...');
        
        const response = await fetch('/api/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                password: password
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('✅ Успешный вход в систему');
            showSuccess('Успешный вход! Перенаправление...');
            
            // Перенаправляем на админ-панель через 1 секунду
            setTimeout(() => {
                window.location.href = '/admin';
            }, 1000);
        } else {
            console.error('❌ Ошибка входа:', data.message);
            showError(data.message || 'Неверный пароль');
        }
        
    } catch (error) {
        console.error('❌ Ошибка сети:', error);
        showError('Ошибка соединения. Попробуйте еще раз.');
    } finally {
        isSubmitting = false;
        setLoadingState(false);
    }
}

// Установка состояния загрузки
function setLoadingState(loading) {
    if (loading) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        loginBtn.disabled = true;
        passwordInput.disabled = true;
    } else {
        btnText.style.display = 'block';
        btnLoading.style.display = 'none';
        loginBtn.disabled = false;
        passwordInput.disabled = false;
    }
}

// Показать ошибку
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    
    // Добавляем анимацию
    errorMessage.style.opacity = '0';
    errorMessage.style.transform = 'translateY(-10px)';
    
    setTimeout(() => {
        errorMessage.style.opacity = '1';
        errorMessage.style.transform = 'translateY(0)';
    }, 10);
}

// Показать успех
function showSuccess(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    errorMessage.style.background = 'rgba(40, 167, 69, 0.1)';
    errorMessage.style.borderColor = 'rgba(40, 167, 69, 0.3)';
    errorMessage.style.color = '#28a745';
}

// Очистить ошибку
function clearError() {
    errorMessage.style.display = 'none';
    errorMessage.style.background = 'rgba(220, 53, 69, 0.1)';
    errorMessage.style.borderColor = 'rgba(220, 53, 69, 0.3)';
    errorMessage.style.color = '#dc3545';
}

// Переключение видимости пароля
function togglePasswordVisibility() {
    const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
    passwordInput.setAttribute('type', type);
    
    // Обновляем иконку
    const eyeIcon = document.querySelector('.eye-icon');
    if (type === 'text') {
        // Показать иконку "скрыть"
        eyeIcon.innerHTML = `
            <path d="M3 3l14 14M10 6.5a3.5 3.5 0 0 1 3.5 3.5M10 6.5a3.5 3.5 0 0 0-3.5 3.5M10 6.5V3M10 6.5v7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        `;
    } else {
        // Показать иконку "показать"
        eyeIcon.innerHTML = `
            <path d="M10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 3c-3.5 0-6.5 2.5-8 6 1.5 3.5 4.5 6 8 6s6.5-2.5 8-6c-1.5-3.5-4.5-6-8-6Z" stroke="currentColor" stroke-width="1.5"/>
        `;
    }
}

// Экспорт функций для использования в HTML
window.togglePasswordVisibility = togglePasswordVisibility;
