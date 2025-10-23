import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN
from openai_client import get_openai_response, test_openai_connection
from message_collector import message_collector
from simple_message_db import message_db  # Добавляем для сохранения в файл
from question_system import question_system

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    
    # Создаем кнопку для Mini App
    mini_app_button = InlineKeyboardButton(
        "Начать", 
        web_app=WebAppInfo(url="https://neuroevent.ru/")  # Production URL
    )
    
    keyboard = [[mini_app_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Добро пожаловать! Выберите действие:",
        reply_markup=reply_markup
    )

# Обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справку по командам"""
    help_text = """
🤖 Доступные команды:

/start - Запустить бота и открыть Mini App
/app - Открыть Mini App приложение
/web - Показать прямые ссылки на Mini App
/help - Показать эту справку
/info - Информация о боте
/echo <текст> - Повторить ваш текст
/questions - Показать статус вопросов
/reset_questions - Сбросить счетчик вопросов

📱 Mini App включает:
• Интерактивную статистику
• Настройки уведомлений
• Быстрые действия
• Отправку сообщений

❓ Система вопросов:
• Бот задает 3 вопроса каждые 3 минуты
• Вопросы о музыкальных ассоциациях
• Счетчик сбрасывается каждый день

💡 Просто отправьте мне любое сообщение, и я отвечу!
    """
    await update.message.reply_text(help_text)

# Обработчик команды /app
async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывает Mini App приложение"""
    mini_app_button = InlineKeyboardButton(
        "Начать", 
        web_app=WebAppInfo(url="https://neuroevent.ru/")  # Production URL
    )
    reply_markup = InlineKeyboardMarkup([[mini_app_button]])
    
    await update.message.reply_text(
        "Откройте Mini App:",
        reply_markup=reply_markup
    )

# Обработчик команды /web
async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает прямую ссылку на Mini App"""
    web_text = """
🌐 Прямой доступ к Mini App:

🔗 Production URL: https://neuroevent.ru/
🔗 Локальный: http://localhost:8000

📱 Для использования:
1. Откройте ссылку выше в браузере
2. Mini App загрузится и будет работать
3. Или используйте кнопку "Открыть Mini App" в боте

✅ Production сервер обеспечивает HTTPS соединение для Telegram Mini App
    """
    await update.message.reply_text(web_text)

# Обработчик команды /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет информацию о боте"""
    info_text = """
🤖 Информация о боте:

• Название: Нейро-бот
• Версия: 2.0 (с Mini App)
• Разработчик: AI Assistant
• Статус: Активен ✅

🔧 Возможности:
• Обработка текстовых сообщений
• Интерактивные кнопки
• Mini App приложение
• Команды управления
• Логирование действий

📱 Mini App функции:
• Интерактивная статистика
• Настройки уведомлений
• Быстрые действия
• Отправка сообщений
    """
    await update.message.reply_text(info_text)

# Обработчик команды /echo
async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Повторяет текст после команды /echo"""
    if context.args:
        text = ' '.join(context.args)
        await update.message.reply_text(f"Вы сказали: {text}")
    else:
        await update.message.reply_text("Использование: /echo <ваш текст>")

# Обработчик команды /questions
async def questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статус вопросов"""
    user = update.effective_user
    status = question_system.get_question_status(user.id)
    await update.message.reply_text(f"📊 Статус вопросов:\n\n{status}")

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
    
    # 1. Выводим сообщение пользователя в консоль
    print(f"📨 Получено сообщение от {user.first_name} (ID: {user.id}): {user_message}")
    
    # 2. Добавляем сообщение в коллектор для админ бота (в память)
    message_collector.add_message(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        message=user_message,
        source='telegram'
    )
    
    # 2.1. ВАЖНО: Также сохраняем в файловую БД для админ-панели
    message_db.add_message(
        user_id=user.id,
        username=user.username or f"user_{user.id}",
        first_name=user.first_name,
        message=user_message,
        source='telegram'
    )
    
    # Показываем индикатор печати
    await update.message.chat.send_action("typing")
    
    try:
        # 3. Отправляем в LLM с промптом "Уменьшить размер до 1 предложения"
        summarization_prompt = f"Уменьшить размер до 1 предложения: {user_message}"
        summarized_message = await get_openai_response(summarization_prompt)
        
        # 4. Выводим результат в консоль
        print(f"📝 Сокращенное сообщение: {summarized_message}")
        
        # 5. Получаем обычный ответ от OpenAI для пользователя
        ai_response = await get_openai_response(user_message)
        
        # Отправляем ответ пользователю
        await update.message.reply_text(ai_response)
        
        # 6. Сохраняем ответ бота в БД (с source='bot' чтобы не попадал в микс)
        message_db.add_message(
            user_id=0,  # ID бота = 0
            username="neyro_bot",
            first_name="Нейро-бот",
            message=ai_response,
            source='bot'
        )
        
        # 7. Проверяем, нужно ли задать вопрос
        next_question = question_system.get_next_question(user.id)
        if next_question:
            # Ждем 2 секунды перед вопросом
            await asyncio.sleep(2)
            await update.message.reply_text(next_question)
            
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
        from mock_responses import get_friendly_response
        fallback_response = f"Привет, {user.first_name}! 👋\n\n{get_friendly_response()}"
        await update.message.reply_text(fallback_response)

# Обработчик нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'stats':
        await query.edit_message_text("📊 Статистика бота:\n\n• Пользователей: 1\n• Сообщений: 1\n• Время работы: Активен")
    elif query.data == 'settings':
        await query.edit_message_text("⚙️ Настройки:\n\n• Уведомления: Включены\n• Язык: Русский\n• Режим: Стандартный")
    elif query.data == 'help':
        await help_command(update, context)

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки"""
    logger.warning(f'Update {update} caused error {context.error}')

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
    application.add_handler(CommandHandler("app", app_command))
    application.add_handler(CommandHandler("web", web_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("echo", echo_command))
    application.add_handler(CommandHandler("questions", questions_command))
    application.add_handler(CommandHandler("reset_questions", reset_questions_command))
    
    # Добавляем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Добавляем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("🤖 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
