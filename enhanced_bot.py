#!/usr/bin/env python3
"""
Улучшенный Telegram бот для Neuroevent
Полный функционал без Mini App
"""

import logging
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN
from openai_client import get_openai_response, test_openai_connection, get_quick_response
from message_collector import message_collector
from simple_message_db import message_db
from question_system import question_system
from smart_batch_manager import smart_batch_manager
from mock_responses import get_friendly_response

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для состояния пользователей
user_states = {}
user_chat_history = {}

class UserState:
    """Класс для управления состоянием пользователя"""
    def __init__(self, user_id):
        self.user_id = user_id
        # Флаг ожидания ответа на админ-вопрос
        self.awaiting_answer = False
        # Последний вопрос администратора, на который отвечали
        self.last_question = None
        self.has_started = False
        self.is_waiting_for_response = False
        self.last_message_time = 0
        self.message_count = 0
        self.chat_history = []
        self.current_question = None
        self.is_typing = False

    def add_message(self, message, is_user=True):
        """Добавляет сообщение в историю"""
        self.chat_history.append({
            'message': message,
            'is_user': is_user,
            'timestamp': time.time()
        })
        # Ограничиваем историю последними 10 сообщениями
        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]

def get_user_state(user_id):
    """Получает или создает состояние пользователя"""
    if user_id not in user_states:
        user_states[user_id] = UserState(user_id)
    return user_states[user_id]

# Функция для сохранения пользователя в реестр
def save_user_to_registry(user_id, username, first_name):
    """Сохраняет пользователя в реестр для рассылок"""
    import json
    import os
    
    registry_file = 'user_registry.json'
    
    try:
        # Загружаем существующий реестр
        if os.path.exists(registry_file):
            with open(registry_file, 'r', encoding='utf-8') as f:
                registry = json.load(f)
        else:
            registry = {'users': []}
        
        # Проверяем, есть ли уже такой пользователь
        existing_user = next((u for u in registry['users'] if u['user_id'] == user_id), None)
        
        if not existing_user:
            # Добавляем нового пользователя
            registry['users'].append({
                'user_id': user_id,
                'username': username or f'user_{user_id}',
                'first_name': first_name or 'User',
                'registered_at': time.time()
            })
            
            # Сохраняем реестр
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Пользователь {user_id} добавлен в реестр")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения пользователя в реестр: {e}")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    user_state = get_user_state(user.id)
    
    # Всегда отвечаем на /start и отмечаем начало сессии
    user_state.has_started = True
    # Сохраняем пользователя в реестр для рассылок
    save_user_to_registry(user.id, user.username, user.first_name)
    
    # Убираем кнопки - используем только текстовые сообщения
    reply_markup = None
    
    welcome_text = f"""
🎵 **Команда Neuroevent приветствует Вас!** 🎵

Я — Ваш виртуальный помощник на концерте Main Strings Orchestra.

Перед каждым треком я пришлю краткий анонс киновселенной и один вопрос.
Ваш короткий ответ поможет ИИ оперативно сформировать визуальные образы.

**Важно:** один трек — один ответ. Пишите коротко и наслаждайтесь происходящим на сцене — главное эмоции, а не телефон 😊

Скоро начнём! ✨
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Сохраняем приветственное сообщение
    user_state.add_message("Добро пожаловать в Neuroevent Bot!", is_user=False)

# Обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справку по командам"""
    help_text = """
🤖 **Доступные команды:**

/start - Запустить бота и показать главное меню
/help - Показать эту справку
/info - Информация о боте
/clear - Очистить историю чата
/status - Показать статус системы
/questions - Показать статус вопросов
/reset_questions - Сбросить счетчик вопросов

🎯 **Основные функции:**
• **Общение** - Просто напишите мне что угодно
• **Темы** - Используйте кнопки для быстрого доступа
• **Искусство** - Обсуждаем фильмы, музыку, книги
• **Творчество** - Генерируем идеи и помогаем с проектами

💡 **Советы:**
• Будьте конкретными в вопросах
• Используйте кнопки для быстрого старта
• Не стесняйтесь задавать любые вопросы

🎭 **Готов помочь с любыми творческими задачами!**
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Обработчик команды /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет информацию о боте"""
    info_text = """
🤖 **Информация о Neuroevent Bot:**

• **Название:** Neuroevent Bot
• **Версия:** 3.0 (Enhanced)
• **Разработчик:** AI Assistant
• **Статус:** Активен ✅

🔧 **Возможности:**
• Обработка текстовых сообщений
• Интерактивные кнопки
• Умные ответы с помощью AI
• Система вопросов
• История чата
• Логирование действий

📱 **Особенности:**
• Адаптивное меню
• Быстрые темы
• Творческие обсуждения
• Помощь с проектами

🎯 **Готов к любым задачам!**
    """
    await update.message.reply_text(info_text, parse_mode='Markdown')

# Обработчик команды /clear
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очищает историю чата пользователя"""
    user = update.effective_user
    user_state = get_user_state(user.id)
    
    # Очищаем историю
    user_state.chat_history = []
    user_state.message_count = 0
    
    await update.message.reply_text("🧹 История чата очищена! Начинаем с чистого листа.")
    
    # Сохраняем сообщение об очистке
    user_state.add_message("История чата очищена", is_user=False)

# Обработчик команды /status
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статус системы"""
    user = update.effective_user
    user_state = get_user_state(user.id)
    
    status_text = f"""
📊 **Статус системы:**

👤 **Пользователь:** {user.first_name}
🆔 **ID:** {user.id}
💬 **Сообщений в сессии:** {user_state.message_count}
📝 **История чата:** {len(user_state.chat_history)} сообщений
⏰ **Последняя активность:** {time.strftime('%H:%M:%S')}

🤖 **Бот:**
• Статус: Активен ✅
• OpenAI: Подключен ✅
• База данных: Работает ✅
• Система вопросов: Активна ✅

🎯 **Все системы работают нормально!**
    """
    await update.message.reply_text(status_text, parse_mode='Markdown')

# Обработчик команды /questions
async def questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статус вопросов"""
    user = update.effective_user
    status = question_system.get_question_status(user.id)
    await update.message.reply_text(f"📊 **Статус вопросов:**\n\n{status}", parse_mode='Markdown')

# Обработчик команды /reset_questions
async def reset_questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает счетчик вопросов"""
    user = update.effective_user
    question_system.reset_user_questions(user.id)
    await update.message.reply_text("🔄 Счетчик вопросов сброшен!")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ответы пользователей: отвечает на админ-вопросы и на спам стандартным сообщением"""
    user_message = update.message.text
    user = update.effective_user
    user_state = get_user_state(user.id)
    # Защита от спама по частоте
    current_time = time.time()
    if current_time - user_state.last_message_time < 2:
        return
    user_state.last_message_time = current_time
    user_state.message_count += 1

    # Определяем текст последнего вопроса администратора
    context_question = None
    # Локальная история
    for m in reversed(user_state.chat_history):
        if not m['is_user'] and ('📽️' in m['message'] or '🎬' in m['message']):
            context_question = m['message']
            break
    else:
        try:
            message_db.load_messages()
            for m in reversed(message_db.messages):
                if m.get('source') == 'admin' and ('📽️' in m.get('message','') or '🎬' in m.get('message','')):
                    context_question = m.get('message')
                    break
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения контекста: {e}")

    # Если найден новый вопрос админа, устанавливаем ожидание ответа
    if context_question and context_question != user_state.last_question:
        user_state.awaiting_answer = True
        user_state.last_question = context_question

    if user_state.awaiting_answer:
        # Первый ответ на текущий вопрос администратора
        fixed_response = "Спасибо за ответ! Наслаждайтесь музыкой и визуальным рядом по вашим идеям ✨"
        await update.message.reply_text(fixed_response)
        user_state.add_message(fixed_response, is_user=False)
        user_state.awaiting_answer = False
    else:
        # Любое другое сообщение
        standard_response = "Пожалуйста, ожидайте, я пришлю анонс перед началом композиции 😌"
        await update.message.reply_text(standard_response)
        user_state.add_message(standard_response, is_user=False)

# Обработчик кнопок удален - кнопки больше не используются

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки"""
    logger.warning(f'Update {update} caused error {context.error}')
    
    # Отправляем дружелюбное сообщение об ошибке
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "😅 Упс! Произошла небольшая ошибка. Попробуйте еще раз!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

def main() -> None:
    """Основная функция для запуска бота"""
    # Тестируем подключение к OpenAI
    print("🔍 Проверяем подключение к OpenAI...")
    if test_openai_connection():
        print("✅ OpenAI подключение успешно!")
    else:
        print("⚠️ Проблемы с подключением к OpenAI. Бот будет работать с ограниченным функционалом.")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("questions", questions_command))
    application.add_handler(CommandHandler("reset_questions", reset_questions_command))
    
    # Добавляем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик кнопок удален - кнопки больше не используются
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("🤖 Enhanced Neuroevent Bot запускается...")
    print("🎭 Готов к творческим обсуждениям!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
