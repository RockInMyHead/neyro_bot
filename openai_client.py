#!/usr/bin/env python3
"""
Модуль для работы с OpenAI API
"""

import openai
from config import OPENAI_API_KEY
import logging
import httpx

# Настройка логирования
logger = logging.getLogger(__name__)

# Настройка прокси
PROXY_HOST = "185.68.186.35"
PROXY_PORT = 8000
PROXY_USERNAME = "uTGXAk"
PROXY_PASSWORD = "oYDLdR"

# Создаем HTTP клиент с прокси
http_client = httpx.Client(
    proxies={
        "http://": f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}",
        "https://": f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
    }
)

# Инициализация OpenAI клиента с прокси
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=http_client
)

# Системный промпт для бота
SYSTEM_PROMPT = """Ты — виртуальный ассистент на концерте Main Strings Orchestra. 

Твоя задача:
1. Когда администратор отправляет анонс фильма с вопросом - просто подтверди получение
2. Когда пользователь отвечает на вопрос - поблагодари его за ответ коротко и вежливо
3. НЕ задавай дополнительные вопросы
4. НЕ говори о музыке
5. Отвечай кратко и по делу

Примеры ответов:
- На анонс: "Понял, жду ответов от зрителей!"
- На ответ пользователя: "Спасибо за ваш ответ! ✨" или "Отлично, спасибо! 🎬"
- На любой другой текст: "Спасибо за сообщение!"
"""

async def get_openai_response(user_message: str, conversation_history: list = None) -> str:
    """
    Получает ответ от OpenAI на основе сообщения пользователя
    
    Args:
        user_message (str): Сообщение пользователя
        conversation_history (list): История разговора (опционально)
    
    Returns:
        str: Ответ от OpenAI
    """
    try:
        # Формируем сообщения для API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Добавляем историю разговора, если есть
        if conversation_history:
            for msg in conversation_history[-10:]:  # Ограничиваем историю последними 10 сообщениями
                # Преобразуем формат из Mini App в формат OpenAI
                role = "user" if msg.get('isUser', False) else "assistant"
                messages.append({
                    "role": role,
                    "content": msg.get('message', '')
                })
        
        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})
        
        # Отправляем запрос к OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        # Извлекаем ответ
        ai_response = response.choices[0].message.content.strip()
        
        logger.info(f"OpenAI response generated for message: {user_message[:50]}...")
        return ai_response
        
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return "Извините, произошла ошибка при обращении к AI. Попробуйте позже. 😔"
    
    except openai.RateLimitError as e:
        logger.error(f"OpenAI rate limit error: {e}")
        return "Слишком много запросов. Подождите немного и попробуйте снова. ⏰"
    
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI connection error: {e}")
        return "Проблемы с подключением к AI. Проверьте интернет-соединение. 🌐"
    
    except Exception as e:
        logger.error(f"Unexpected error in OpenAI client: {e}")
        return "Произошла неожиданная ошибка. Попробуйте позже. 🔧"

def test_openai_connection() -> bool:
    """
    Тестирует подключение к OpenAI API
    
    Returns:
        bool: True если подключение успешно, False иначе
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Привет! Это тест подключения."}],
            max_tokens=10
        )
        logger.info("OpenAI connection test successful")
        return True
    except Exception as e:
        logger.error(f"OpenAI connection test failed: {e}")
        return False

# Функция для получения краткого ответа (для быстрых ответов)
async def get_quick_response(user_message: str) -> str:
    """
    Получает краткий ответ от OpenAI
    
    Args:
        user_message (str): Сообщение пользователя
    
    Returns:
        str: Краткий ответ от OpenAI
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - дружелюбный AI-ассистент. Отвечай кратко и по делу на русском языке. Используй эмодзи."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error in quick response: {e}")
        return "Извините, не могу ответить сейчас. 😔"
