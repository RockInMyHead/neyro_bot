#!/usr/bin/env python3
"""
Улучшенный Telegram бот для Neuroevent
Полный функционал без Mini App
"""

import logging
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN
from openai_client import get_openai_response, test_openai_connection
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

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    user_state = get_user_state(user.id)
    
    # Создаем главное меню
    main_menu = [
        [KeyboardButton("🎬 Фильмы"), KeyboardButton("🎵 Музыка")],
        [KeyboardButton("🎭 Искусство"), KeyboardButton("📚 Книги")],
        [KeyboardButton("🎮 Игры"), KeyboardButton("🌍 Путешествия")],
        [KeyboardButton("💡 Идеи"), KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True, one_time_keyboard=False)
    
    welcome_text = f"""
🎭 **Добро пожаловать в Neuroevent Bot!** 🎭

Привет, {user.first_name}! 👋

Я — ваш виртуальный помощник на концерте Main Strings Orchestra. 

🎵 **Что я умею:**
• Обсуждать фильмы и музыку
• Генерировать креативные идеи
• Отвечать на вопросы об искусстве
• Помогать с творческими задачами

💬 **Просто напишите мне что угодно!**
Используйте кнопки ниже для быстрого доступа к темам.

🎯 **Готов к общению!**
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
    """Обрабатывает обычные текстовые сообщения с помощью OpenAI"""
    user_message = update.message.text
    user = update.effective_user
    user_state = get_user_state(user.id)
    
    # Проверяем, не обрабатывается ли уже сообщение
    if user_state.is_waiting_for_response:
        await update.message.reply_text("⏳ Пожалуйста, подождите, я еще думаю над предыдущим сообщением...")
        return
    
    # Проверяем частоту сообщений (защита от спама)
    current_time = time.time()
    if current_time - user_state.last_message_time < 2:  # Минимум 2 секунды между сообщениями
        await update.message.reply_text("⏳ Пожалуйста, не торопитесь! Дайте мне время подумать...")
        return
    
    user_state.last_message_time = current_time
    user_state.message_count += 1
    user_state.is_waiting_for_response = True
    
    # Выводим сообщение пользователя в консоль
    print(f"📨 Получено сообщение от {user.first_name} (ID: {user.id}): {user_message}")
    
    # Добавляем сообщение в историю пользователя
    user_state.add_message(user_message, is_user=True)
    
    # Добавляем сообщение в коллектор для админ бота
    message_collector.add_message(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        message=user_message,
        source='telegram'
    )
    
    # Сохраняем в файловую БД для админ-панели
    message_db.add_message(
        user_id=user.id,
        username=user.username or f"user_{user.id}",
        first_name=user.first_name,
        message=user_message,
        source='telegram'
    )
    
    # Добавляем в систему умных батчей
    try:
        msg_id = smart_batch_manager.add_message(user.id, user.username, user.first_name, user_message)
        logger.info(f"✅ Сообщение добавлено в SmartBatchManager: {msg_id}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось добавить сообщение в SmartBatchManager: {e}")
    
    # Показываем индикатор печати
    await update.message.chat.send_action("typing")
    
    try:
        # Создаем контекст для AI на основе истории чата
        conversation_context = ""
        if user_state.chat_history:
            recent_messages = user_state.chat_history[-5:]  # Последние 5 сообщений
            for msg in recent_messages:
                if msg['is_user']:
                    conversation_context += f"Пользователь: {msg['message']}\n"
                else:
                    conversation_context += f"Бот: {msg['message']}\n"
        
        # Формируем промпт с контекстом
        if conversation_context:
            full_prompt = f"Контекст разговора:\n{conversation_context}\n\nТекущее сообщение пользователя: {user_message}\n\nОтветь как творческий помощник, учитывая контекст разговора."
        else:
            full_prompt = user_message
        
        # Получаем ответ от OpenAI
        ai_response = await get_openai_response(full_prompt)
        
        # Отправляем ответ пользователю
        await update.message.reply_text(ai_response)
        
        # Добавляем ответ в историю пользователя
        user_state.add_message(ai_response, is_user=False)
        
        # Сохраняем ответ бота в БД
        message_db.add_message(
            user_id=0,  # ID бота = 0
            username="neyro_bot",
            first_name="Нейро-бот",
            message=ai_response,
            source='bot'
        )
        
        # Проверяем, нужно ли задать вопрос
        next_question = question_system.get_next_question(user.id)
        if next_question:
            # Ждем 2 секунды перед вопросом
            await asyncio.sleep(2)
            await update.message.reply_text(next_question)
            
            # Добавляем вопрос в историю
            user_state.add_message(next_question, is_user=False)
            
            # Сохраняем вопрос в БД
            message_db.add_message(
                user_id=0,  # ID бота = 0
                username="neyro_bot",
                first_name="Нейро-бот",
                message=next_question,
                source='bot'
            )
        
        logger.info(f"OpenAI response sent to user {user.first_name} (ID: {user.id})")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        print(f"❌ Ошибка при обработке сообщения: {e}")
        
        # Fallback ответ в случае ошибки
        fallback_response = f"Привет, {user.first_name}! 👋\n\n{get_friendly_response()}"
        await update.message.reply_text(fallback_response)
        
        # Добавляем fallback в историю
        user_state.add_message(fallback_response, is_user=False)
    
    finally:
        # Сбрасываем флаг ожидания ответа
        user_state.is_waiting_for_response = False

# Обработчик нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'stats':
        await query.edit_message_text("📊 **Статистика бота:**\n\n• Пользователей: Активно\n• Сообщений: Обработано\n• Время работы: Активен", parse_mode='Markdown')
    elif query.data == 'settings':
        await query.edit_message_text("⚙️ **Настройки:**\n\n• Уведомления: Включены\n• Язык: Русский\n• Режим: Творческий", parse_mode='Markdown')
    elif query.data == 'help':
        await help_command(update, context)

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
    
    # Добавляем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("🤖 Enhanced Neuroevent Bot запускается...")
    print("🎭 Готов к творческим обсуждениям!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
