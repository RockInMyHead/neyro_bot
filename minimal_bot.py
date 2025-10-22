#!/usr/bin/env python3
"""
Упрощенный Telegram бот для Mini App
Только кнопка "Начать" без лишнего текста
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN
from openai_client import get_openai_response, test_openai_connection
from message_collector import message_collector
from simple_message_db import message_db
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
        web_app=WebAppInfo(url="https://neuroevent.ru/")
    )
    
    keyboard = [[mini_app_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀",  # Эмодзи ракеты как минимальный текст
        reply_markup=reply_markup
    )

# Обработчик команды /app
async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывает Mini App приложение"""
    mini_app_button = InlineKeyboardButton(
        "Начать", 
        web_app=WebAppInfo(url="https://neuroevent.ru/")
    )
    reply_markup = InlineKeyboardMarkup([[mini_app_button]])
    
    await update.message.reply_text(
        "🚀",  # Эмодзи ракеты как минимальный текст
        reply_markup=reply_markup
    )

# Обработчик для автоматического показа Mini App
async def show_mini_app_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает кнопку Mini App при любом взаимодействии"""
    # Создаем кнопку для Mini App
    mini_app_button = InlineKeyboardButton(
        "Начать", 
        web_app=WebAppInfo(url="https://neuroevent.ru/")
    )
    
    keyboard = [[mini_app_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀",  # Эмодзи ракеты как минимальный текст
        reply_markup=reply_markup
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает обычные текстовые сообщения с помощью OpenAI"""
    user_message = update.message.text
    user = update.effective_user
    
    # Логируем сообщение
    print(f"📨 Получено сообщение от {user.first_name} (ID: {user.id}): {user_message}")
    
    # Добавляем сообщение в коллектор
    message_collector.add_message(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        message=user_message,
        source='telegram'
    )
    
    # Сохраняем в файловую БД
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
        # Получаем ответ от OpenAI
        ai_response = await get_openai_response(user_message)
        
        # Отправляем ответ пользователю
        await update.message.reply_text(ai_response)
        
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
        fallback_response = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я получил ваше сообщение, но сейчас у меня технические проблемы. "
            "Попробуйте написать мне позже! 😊"
        )
        await update.message.reply_text(fallback_response)

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
    
    # Добавляем обработчик для всех текстовых сообщений (показывает кнопку Mini App)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, show_mini_app_button))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("🤖 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
