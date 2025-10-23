#!/bin/bash

echo "🚀 Запуск новой системы Neuroevent Bot..."
echo "=========================================="

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python3 и попробуйте снова."
    exit 1
fi

# Проверяем наличие зависимостей
echo "🔍 Проверяем зависимости..."
if ! python3 -c "import telegram, flask, openai" &> /dev/null; then
    echo "⚠️ Не все зависимости установлены. Устанавливаем..."
    pip3 install -r requirements.txt
fi

# Проверяем конфигурацию
echo "🔧 Проверяем конфигурацию..."
if [ ! -f ".env" ]; then
    echo "⚠️ Файл .env не найден. Копируем из примера..."
    cp env.example .env
    echo "📝 Отредактируйте файл .env с вашими настройками"
fi

# Создаем папки если не существуют
mkdir -p generated_images
mkdir -p static/admin_app
mkdir -p templates

echo "✅ Система готова к запуску!"
echo ""
echo "🎯 Доступные команды:"
echo "1. python3 run_system.py     - Запуск всей системы"
echo "2. python3 enhanced_bot.py   - Только бот"
echo "3. python3 app_admin_only.py - Только админ-панель"
echo ""
echo "📊 Админ-панель: http://localhost:8000/admin"
echo "🔐 Логин: admin123"
echo ""
echo "🤖 Бот готов к работе!"
echo "🎭 Система Neuroevent Bot запущена!"
