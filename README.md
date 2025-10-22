# 🤖 Нейро-бот с Умной Системой Батчей

Интерактивный Telegram бот с AI-генерацией изображений на основе сообщений пользователей.

## ✨ Новые возможности

### 🚀 Умная система батчей
- **Автоматическое деление на батчи**: >= 10 сообщений → 10 пропорциональных батчей, < 10 → по 1 батчу
- **Последовательная обработка**: гарантированный порядок, прозрачность каждого этапа
- **Умное микширование**: объединение сообщений через LLM (до 100 символов)
- **Качественная генерация**: Gemini API, художественный стиль, 1920x1280 изображения
- **Реальное время**: автообновление каждые 5 секунд, полная статистика

### 🎨 AI-генерация изображений
- Автоматическое создание художественных изображений
- Стиль "Пираты Карибского моря"
- Полная HD+ размерность (1920x1280)

### 📊 Админ-панель
- Мониторинг сообщений в реальном времени
- Статистика батчей и процессора
- Управление обработкой
- История всех батчей

## 🚀 Быстрый старт

### 1. Установка
```bash
cd /Users/artembutko/Desktop/neyro_bot
pip install -r requirements.txt
```

### 2. Настройка
Скопируйте `env.example` в `.env` и заполните:
```bash
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
```

### 3. Запуск
```bash
# Запуск Flask приложения (веб-сервер + фоновая обработка)
python app.py

# В отдельном терминале: запуск Telegram бота
python bot.py
```

### 4. Использование
- **Пользователи**: открывают Mini App в боте и пишут сообщения
- **Админы**: открывают http://localhost:8000/admin для мониторинга

## 📚 Документация

- 📖 [SMART_BATCH_SYSTEM.md](SMART_BATCH_SYSTEM.md) - Полная документация системы
- 🚀 [QUICK_START.md](QUICK_START.md) - Быстрый старт и примеры
- 📊 [SYSTEM_FLOW.txt](SYSTEM_FLOW.txt) - Диаграмма потока обработки
- 🗑️ [MESSAGE_CLEANUP_SYSTEM.md](MESSAGE_CLEANUP_SYSTEM.md) - Система очистки сообщений

## 🏗️ Архитектура

### Основные компоненты
- `smart_batch_manager.py` - Менеджер умных батчей
- `sequential_batch_processor.py` - Последовательный процессор
- `app.py` - Flask веб-приложение
- `bot.py` - Telegram бот
- `openai_client.py` - Интеграция с OpenAI
- `gemini_client.py` - Генерация изображений через Gemini

### Новые API эндпоинты
- `GET /api/admin/smart-batches/stats` - Статистика батчей
- `GET /api/admin/smart-batches/list` - Список всех батчей
- `POST /api/admin/smart-batches/create` - Создать батчи
- `POST /api/admin/smart-batches/process-next` - Обработать следующий
- `GET /api/admin/smart-batches/current-mixed-text` - Текущий микс

## 🎮 Команды бота

- `/start` - Запустить бота и открыть Mini App
- `/help` - Показать справку
- `/info` - Информация о боте
- `/app` - Открыть Mini App

## 📊 Примеры использования

### Пример 1: 3 сообщения
```
Пользователь 1: "Море"
Пользователь 2: "Пираты"
Пользователь 3: "Сокровища"

→ 3 батча по 1 сообщению
→ 3 уникальных изображения
→ Время: ~45 секунд
```

### Пример 2: 25 сообщений
```
25 различных сообщений

→ 10 батчей по 2-3 сообщения
→ 10 художественных изображений
→ Время: ~4 минуты
```

## 🔧 Настройки

### SmartBatchManager
```python
TARGET_BATCH_COUNT = 10  # Целевое количество батчей
```

### SequentialBatchProcessor
```python
MAX_MIXED_TEXT_LENGTH = 100  # Макс. длина миксированного текста
IMAGE_SIZE = (1920, 1280)    # Размер изображения
```

## 📝 Структура проекта

```
neyro_bot/
├── smart_batch_manager.py           # NEW: Умный менеджер батчей
├── sequential_batch_processor.py    # NEW: Последовательный процессор
├── app.py                            # UPDATED: Flask приложение
├── bot.py                            # Telegram бот
├── openai_client.py                  # OpenAI интеграция
├── gemini_client.py                  # Gemini API для изображений
├── config.py                         # Конфигурация
├── simple_message_db.py              # БД сообщений
├── content_filter.py                 # Фильтр контента
├── quota_manager.py                  # Управление квотами
├── templates/
│   ├── mini_app.html                # Mini App для пользователей
│   └── admin_mini_app.html          # UPDATED: Админ-панель
├── static/
│   ├── mini_app/                    # Стили и JS для Mini App
│   └── admin_app/                   # UPDATED: Админ-панель стили/JS
├── generated_images/                # Сгенерированные изображения
├── SMART_BATCH_SYSTEM.md            # NEW: Полная документация
├── QUICK_START.md                   # NEW: Быстрый старт
├── SYSTEM_FLOW.txt                  # NEW: Диаграмма потока
└── README.md                        # Этот файл