import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "8394487624:AAEUTsqaRtXsCBW2B3mqeu8HaC1zpE2ocow")

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")

# Message Collection Settings
MESSAGE_COLLECTION_INTERVAL = 15  # секунд
MAX_MESSAGES_PER_BATCH = 100

# Настройки бота
BOT_USERNAME = "neyro_bot"
ADMIN_IDS = []  # Добавьте ID администраторов

# Настройки базы данных (если понадобится)
DATABASE_URL = "sqlite:///bot.db"

# Gemini API для генерации изображений
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_MODEL = "gemini-2.5-flash-image"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Папка для сохранения сгенерированных изображений
GENERATED_IMAGES_FOLDER = "generated_images"

# Включение постоянной генерации изображений
ENABLE_IMAGE_GENERATION = True
IMAGE_GENERATION_MESSAGE = "🎨 Генерация изображений активна! Ваши идеи превращаются в визуальные образы."

