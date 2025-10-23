#!/usr/bin/env python3
"""
Flask приложение только для админ-панели
Mini App функционал перенесен в enhanced_bot.py
"""

from flask import Flask, render_template, send_from_directory, request, jsonify, session
from flask_cors import CORS
import time
import os
import logging
import asyncio
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import existing handlers
from simple_message_db import message_db
from openai_client import get_openai_response
from gemini_client import generate_image_with_retry, GeminiQuotaError
from content_filter import check_content_safety, sanitize_image_prompt

# OLD: Keep legacy imports for compatibility with old endpoints
from image_queue_manager import queue_manager
from batch_image_generator import batch_generator

# NEW: Import smart batch management system
from smart_batch_manager import smart_batch_manager, BatchStatus
from sequential_batch_processor import sequential_processor
from PIL import Image, ImageOps
from io import BytesIO
import threading
import time
import asyncio
import requests
import base64
from config import BOT_TOKEN, GENERATED_IMAGES_FOLDER, NEW_BOT_TOKEN

# Импортируем менеджер промтов
from prompt_manager import get_current_base_prompt, update_base_prompt, get_prompt_info

def _process_and_compress_image(image_path: str) -> str:
    """
    Обрабатывает и сжимает изображение (как в умной системе батчей)
    
    Args:
        image_path: Путь к исходному изображению
        
    Returns:
        str: Путь к обработанному изображению
    """
    try:
        # Параметры обработки (как в умной системе батчей)
        IMAGE_SIZE = (1920, 1280)
        
        with Image.open(image_path) as img:
            # Конвертируем в RGB если необходимо
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Изменяем размер с сохранением пропорций и обрезкой
            img = ImageOps.fit(img, IMAGE_SIZE, Image.Resampling.LANCZOS)
            
            # Создаем новое имя файла с суффиксом _processed
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            processed_filename = f"{base_name}_processed.png"
            processed_path = os.path.join(GENERATED_IMAGES_FOLDER, processed_filename)
            
            # Сохраняем как PNG с оптимизацией
            img.save(processed_path, 'PNG', optimize=True)
            
            logger.info(f"🖼️ Изображение обработано: {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]} -> {processed_filename}")
            
            # Удаляем оригинальное изображение
            if os.path.exists(image_path) and image_path != processed_path:
                os.remove(image_path)
                logger.info(f"🗑️ Оригинальное изображение удалено: {os.path.basename(image_path)}")
            
            return processed_path
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки изображения: {e}")
        logger.info("💾 Возвращаем оригинальное изображение без обработки")
        return image_path

def auto_generation_worker():
    """
    Новый фоновый процесс для последовательной обработки батчей
    
    Логика:
    1. Проверяет наличие необработанных сообщений
    2. Создает батчи (10 пропорциональных или по 1 сообщению)
    3. Последовательно обрабатывает каждый батч:
       - Создает миксированный текст через LLM
       - Генерирует изображение
       - Сохраняет результат
    4. Повторяет цикл
    """
    logger.info("🔄 Запуск фонового процесса последовательной обработки батчей...")
    
    while True:
        try:
            # Получаем следующий батч для обработки
            next_batch = smart_batch_manager.get_next_batch()
            
            if not next_batch:
                time.sleep(5)  # Ждем 5 секунд, если нет батчей
                continue
            
            logger.info(f"🔄 Обрабатываем батч {next_batch.batch_id} с {next_batch.message_count} сообщениями")
            
            # Обрабатываем батч через sequential_processor
            result = sequential_processor.process_batch(next_batch)
            
            if result:
                logger.info(f"✅ Батч {next_batch.batch_id} успешно обработан")
            else:
                logger.warning(f"⚠️ Батч {next_batch.batch_id} не был обработан")
            
            # Небольшая пауза между циклами
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в фоновом процессе: {e}")
            time.sleep(10)  # Ждем 10 секунд при критической ошибке

# Запускаем фоновый процесс
generation_thread = threading.Thread(target=auto_generation_worker, daemon=True)
generation_thread.start()
logger.info("🚀 Фоновый процесс обработки батчей запущен")

# Создаем Flask приложение
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your-secret-key-here'  # Замените на более безопасный ключ
CORS(app)

# Глобальные переменные для уведомлений
last_admin_message_time = 0
chat_clear_timestamp = None

# Функция для отправки уведомлений в Telegram
def send_telegram_message(user_id, message):
    """Отправляет сообщение пользователю через Telegram Bot API"""
    try:
        url = f"https://api.telegram.org/bot{NEW_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': user_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
                return True
            else:
                logger.error(f"Ошибка Telegram API для пользователя {user_id}: {result.get('description')}")
                return False
        else:
            logger.error(f"HTTP ошибка при отправке сообщения пользователю {user_id}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Исключение при отправке сообщения пользователю {user_id}: {e}")
        return False

def send_telegram_notification_with_button(user_id, notification_text, button_text="🎬 Открыть бота", web_app_url=None):
    """Отправляет уведомление с кнопкой для перехода в бота"""
    try:
        url = f"https://api.telegram.org/bot{NEW_BOT_TOKEN}/sendMessage"
        
        # Если URL не указан, используем дефолтный
        if not web_app_url:
            web_app_url = "https://t.me/neyro_bot"  # Ссылка на бота
        
        data = {
            'chat_id': user_id,
            'text': notification_text,
            'parse_mode': 'Markdown',
            'reply_markup': {
                'inline_keyboard': [[
                    {
                        'text': button_text,
                        'url': web_app_url
                    }
                ]]
            }
        }
        
        response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info(f"Уведомление с кнопкой успешно отправлено пользователю {user_id}")
                return True
            else:
                logger.error(f"Ошибка Telegram API для пользователя {user_id}: {result.get('description')}")
                return False
        else:
            logger.error(f"HTTP ошибка при отправке уведомления пользователю {user_id}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Исключение при отправке уведомления пользователю {user_id}: {e}")
        return False

# Декоратор для проверки аутентификации администратора
def require_admin_auth(f):
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Admin Login Page
@app.route('/admin/login')
def admin_login_page():
    return render_template('admin_login.html')

# Admin App Page
@app.route('/admin')
def admin_app():
    # Проверяем аутентификацию
    if not session.get('admin_authenticated'):
        return render_template('admin_login.html')
    return render_template('admin_mini_app.html')

# Admin API endpoints
@app.route('/api/admin/stats', methods=['GET'])
@require_admin_auth
def admin_stats():
    """Получает статистику системы"""
    message_db.load_messages()
    stats = message_db.get_stats()
    return jsonify(stats)

@app.route('/api/admin/messages', methods=['GET'])
def admin_messages():
    message_db.load_messages()
    all_messages = message_db.messages
    return jsonify(all_messages)

@app.route('/api/admin/export', methods=['GET'])
def admin_export():
    message_db.load_messages()
    all_messages = message_db.messages
    return jsonify(all_messages)

@app.route('/api/admin/reset', methods=['POST'])
def admin_reset():
    message_db.reset_stats()
    return jsonify({'success': True, 'message': 'Stats reset successfully'})

@app.route('/api/admin/mixed-text', methods=['POST'])
def admin_mixed_text():
    # Accept empty request body
    data = request.get_json(force=True) or {}
    
    try:
        # Получаем все сообщения
        message_db.load_messages()
        all_messages = message_db.messages
        
        # Фильтруем только сообщения пользователей (исключаем админские и бот)
        user_messages = [msg for msg in all_messages if msg.get('source') in ['telegram', 'mini_app']]
        
        if not user_messages:
            return jsonify({
                'success': False,
                'error': 'No user messages found',
                'mixed_text': 'Нет сообщений пользователей для обработки'
            })
        
        # Берем последние 10 сообщений
        recent_messages = user_messages[-10:]
        
        # Создаем текст для миксирования
        messages_text = []
        for msg in recent_messages:
            username = msg.get('username', 'Пользователь')
            message_text = msg.get('message', '')
            messages_text.append(f"{username}: {message_text}")
        
        combined_text = "\n".join(messages_text)
        
        # Создаем промпт для миксирования
        mix_prompt = f"""
Создай краткий миксированный текст на основе этих сообщений пользователей:

{combined_text}

Требования:
- Объедини ключевые идеи в один связный текст
- Сохрани эмоциональную окраску
- Сделай текст интересным и креативным
- Максимум 200 символов
- На русском языке
        """
        
        # Получаем миксированный текст от OpenAI
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            mixed_text = loop.run_until_complete(get_openai_response(mix_prompt))
            loop.close()
        except Exception as e:
            logger.error(f"Ошибка получения миксированного текста: {e}")
            mixed_text = "Ошибка генерации миксированного текста"
        
        return jsonify({
            'success': True,
            'mixed_text': mixed_text,
            'source_messages': len(recent_messages)
        })
        
    except Exception as e:
        logger.error(f"Ошибка в admin_mixed_text: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'mixed_text': 'Ошибка обработки сообщений'
        })

# Smart Batch Management API endpoints
@app.route('/api/admin/smart-batches/stats', methods=['GET'])
@require_admin_auth
def smart_batches_stats():
    """Получает статистику умных батчей"""
    try:
        stats = smart_batch_manager.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Ошибка получения статистики батчей: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/smart-batches/list', methods=['GET'])
def smart_batches_list():
    """Получает список всех батчей"""
    try:
        batches = smart_batch_manager.get_all_batches()
        batches_data = []
        for batch in batches:
            batches_data.append({
                'batch_id': batch.batch_id,
                'status': batch.status.value,
                'message_count': batch.message_count,
                'created_at': batch.created_at,
                'completed_at': batch.completed_at,
                'mixed_text': batch.mixed_text,
                'image_path': batch.image_path
            })
        return jsonify({
            'success': True,
            'batches': batches_data
        })
    except Exception as e:
        logger.error(f"Ошибка получения списка батчей: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/smart-batches/create', methods=['POST'])
def smart_batches_create():
    """Принудительно создает батчи из накопленных сообщений"""
    try:
        batches = smart_batch_manager.create_batches()
        return jsonify({
            'success': True,
            'message': f'Создано {len(batches)} батчей',
            'batches_count': len(batches)
        })
    except Exception as e:
        logger.error(f"Ошибка создания батчей: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/smart-batches/process-next', methods=['POST'])
def smart_batches_process_next():
    """Обрабатывает следующий батч"""
    try:
        # Получаем следующий необработанный батч
        pending_batches = smart_batch_manager.get_pending_batches()
        
        if not pending_batches:
            return jsonify({
                'success': False,
                'message': 'Нет необработанных батчей'
            })
        
        # Обрабатываем первый батч
        batch = pending_batches[0]
        result = sequential_processor.process_batch(batch)
        
        if result:
            return jsonify({
                'success': True,
                'message': f'Батч {batch.batch_id} успешно обработан',
                'batch_id': batch.batch_id
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Ошибка обработки батча {batch.batch_id}'
            })
            
    except Exception as e:
        logger.error(f"Ошибка обработки батча: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/smart-batches/current-mixed-text', methods=['GET'])
def smart_batches_current_mixed_text():
    """Получает миксированный текст последнего обработанного батча"""
    try:
        # Получаем последний обработанный батч
        completed_batches = smart_batch_manager.get_completed_batches()
        
        if not completed_batches:
            return jsonify({
                'success': False,
                'message': 'Нет обработанных батчей'
            })
        
        # Берем последний батч
        latest_batch = completed_batches[-1]
        
        return jsonify({
            'success': True,
            'mixed_text': latest_batch.mixed_text or 'Текст не сгенерирован',
            'batch_id': latest_batch.batch_id,
            'completed_at': latest_batch.completed_at
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения миксированного текста: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/smart-batches/images', methods=['GET'])
def smart_batches_images():
    """Получить список сгенерированных изображений"""
    try:
        # Получаем все завершенные батчи с изображениями
        completed_batches = smart_batch_manager.get_completed_batches()
        images_data = []
        
        for batch in completed_batches:
            if batch.image_path and os.path.exists(batch.image_path):
                filename = os.path.basename(batch.image_path)
                image_url = f"/generated_images/{filename}"
                images_data.append({
                    'batch_id': batch.batch_id,
                    'mixed_text': batch.mixed_text or 'Текст не сгенерирован',
                    'image_url': image_url,
                    'image_path': batch.image_path,
                    'completed_at': batch.completed_at * 1000 if batch.completed_at else 0,
                    'processing_time': (batch.completed_at - batch.created_at) if batch.completed_at and batch.created_at else 0,
                    'message_count': batch.message_count
                })
        
        # Сортируем по времени завершения (новые сначала)
        images_data.sort(key=lambda x: x.get('completed_at', 0), reverse=True)
        
        # Если нет изображений из батчей, получаем все изображения из папки
        if not images_data and os.path.exists(GENERATED_IMAGES_FOLDER):
            import glob
            image_files = glob.glob(os.path.join(GENERATED_IMAGES_FOLDER, "*.png"))
            image_files.sort(key=os.path.getmtime, reverse=True)  # Сортируем по времени изменения
            
            for image_file in image_files:
                filename = os.path.basename(image_file)
                image_url = f"/generated_images/{filename}"
                images_data.append({
                    'batch_id': f"file_{filename}",
                    'mixed_text': f"Изображение {filename}",
                    'image_url': image_url,
                    'image_path': image_file,
                    'completed_at': os.path.getmtime(image_file) * 1000,  # Конвертируем в миллисекунды
                    'processing_time': 0,
                    'message_count': 1
                })
        
        return jsonify({
            'success': True,
            'images': images_data,
            'count': len(images_data)
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения изображений: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Admin message management
@app.route('/api/admin/clear-messages', methods=['POST'])
def admin_clear_messages():
    """Очищает все сообщения из базы данных"""
    try:
        message_db.reset_stats()
        return jsonify({
            'success': True,
            'message': 'Все сообщения очищены'
        })
    except Exception as e:
        logger.error(f"Ошибка очистки сообщений: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/clear-all-chats', methods=['POST'])
def admin_clear_all_chats():
    """Очищает всю историю чатов пользователей (сообщения, батчи, изображения)"""
    try:
        # Очищаем базу сообщений
        message_db.reset_stats()
        
        # Очищаем умные батчи
        smart_batch_manager.clear_all_batches()
        
        # Очищаем изображения
        if os.path.exists(GENERATED_IMAGES_FOLDER):
            import shutil
            shutil.rmtree(GENERATED_IMAGES_FOLDER)
            os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)
        
        # Устанавливаем глобальный флаг очистки чатов
        global chat_clear_timestamp
        chat_clear_timestamp = time.time()
        
        # Отправляем уведомления всем пользователям Telegram
        try:
            message_db.load_messages()
            all_messages = message_db.messages
            
            # Получаем уникальных пользователей из Telegram
            telegram_users = set()
            for msg in all_messages:
                if msg.get('source') == 'telegram' and msg.get('user_id') is not None:
                    telegram_users.add(msg['user_id'])
            
            logger.info(f"Найдено {len(telegram_users)} пользователей Telegram для уведомления")
            
            sent_count = 0
            for user_id in telegram_users:
                try:
                    clear_notification_text = "🔄 **История чата была очищена администратором**\n\nНачните новый диалог с ботом!"
                    success = send_telegram_message(user_id, clear_notification_text)
                    if success:
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            
            logger.info(f"Отправлено {sent_count} сообщений об очистке чата из {len(telegram_users)} пользователей")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомлений об очистке: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Вся история чатов очищена',
            'notifications_sent': sent_count if 'sent_count' in locals() else 0
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки всех чатов: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/check-chat-clear-status', methods=['GET'])
def check_chat_clear_status():
    """Проверяет, была ли очищена история чата"""
    global chat_clear_timestamp
    
    # Если есть timestamp очистки, возвращаем его и сбрасываем
    if chat_clear_timestamp is not None:
        timestamp = chat_clear_timestamp
        chat_clear_timestamp = None  # Сбрасываем после получения
        return jsonify({
            "success": True,
            "chat_cleared": True,
            "clear_timestamp": timestamp
        })
    
    return jsonify({
        "success": True,
        "chat_cleared": False,
        "clear_timestamp": None
    })

# Admin concert message system
@app.route('/api/admin/send-concert-message', methods=['POST'])
@require_admin_auth
def admin_send_concert_message():
    """Отправляет сообщение перед треком всем пользователям"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # Сохраняем админское сообщение в БД
        try:
            logger.info(f"💾 Сохраняем админское сообщение в БД: {message[:100]}...")
            message_db.add_message(
                user_id=0,
                username='Admin',
                first_name='Admin',
                message=message,
                source='admin'
            )
            logger.info("✅ Админское сообщение успешно сохранено в БД")
            
            # Устанавливаем флаг для немедленной доставки
            global last_admin_message_time
            last_admin_message_time = time.time()
            logger.info("🚀 Установлен флаг немедленной доставки сообщения")
            
        except Exception as e:
            logger.error(f"❌ Не удалось сохранить админское сообщение: {e}")
        
        # Отправляем сообщение всем пользователям Telegram
        try:
            message_db.load_messages()
            all_messages = message_db.messages
            
            # Получаем уникальных пользователей из Telegram
            telegram_users = set()
            for msg in all_messages:
                if msg.get('source') == 'telegram' and msg.get('user_id') is not None:
                    telegram_users.add(msg['user_id'])
            
            logger.info(f"Найдено {len(telegram_users)} пользователей Telegram для отправки сообщения")
            logger.info(f"ID пользователей: {list(telegram_users)}")
            
            sent_count = 0
            for user_id in telegram_users:
                try:
                    # Отправляем сообщение с кнопкой
                    notification_text = f"🎬 **Новое сообщение от администратора!**\n\n{message}\n\nНажмите кнопку ниже, чтобы открыть бота и ответить."
                    success = send_telegram_notification_with_button(
                        user_id, 
                        notification_text, 
                        "💬 Открыть бота"
                    )
                    if success:
                        sent_count += 1
                        logger.info(f"✅ Сообщение отправлено пользователю {user_id}")
                    else:
                        logger.warning(f"⚠️ Не удалось отправить сообщение пользователю {user_id}")
                        
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
            
            logger.info(f"Отправлено {sent_count} сообщений из {len(telegram_users)} пользователей")
            
            return jsonify({
                'success': True,
                'message': f'Сообщение отправлено {sent_count} пользователям',
                'total_users': len(telegram_users)
            })
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщений пользователям: {e}")
            return jsonify({
                'success': False,
                'error': f'Ошибка отправки: {str(e)}'
            })
            
    except Exception as e:
        logger.error(f"Ошибка в admin_send_concert_message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Base prompt management
@app.route('/api/admin/update-base-prompt', methods=['POST'])
def admin_update_base_prompt():
    """Обновляет базовый промт для AI"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        prompt_content = data.get('prompt', '').strip()
        if not prompt_content:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400
        
        # Обновляем промт через менеджер
        update_base_prompt(prompt_content)
        
        logger.info(f"✅ Базовый промт обновлен: {prompt_content[:100]}...")
        
        return jsonify({
            'success': True,
            'message': 'Базовый промт успешно обновлен',
            'prompt': prompt_content
        })
        
    except Exception as e:
        logger.error(f"Ошибка обновления базового промта: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/generate-film-description', methods=['POST'])
def generate_film_description():
    """Генерировать красивое описание фильма на основе технического промта"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        technical_prompt = data.get('technical_prompt', '').strip()
        if not technical_prompt:
            return jsonify({'success': False, 'error': 'Technical prompt is required'}), 400
        
        # Создаем промпт для генерации описания фильма
        film_prompt = f"""
На основе этого технического описания создай красивое описание фильма:

{technical_prompt}

Требования:
- Создай ОДНО ЗАВЕРШЕННОЕ предложение длиной НЕ БОЛЕЕ 250 символов
- Используй яркие, эмоциональные слова
- Сделай описание захватывающим и интересным
- На русском языке
- Без технических терминов
- Сосредоточься на атмосфере и эмоциях
        """
        
        # Получаем описание от OpenAI
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            film_description = loop.run_until_complete(get_openai_response(film_prompt))
            loop.close()
            
            # Обрезаем до 250 символов на сервере
            if len(film_description) > 250:
                film_description = film_description[:250].rsplit(' ', 1)[0] + '...'
            
            logger.info(f"✅ Описание фильма сгенерировано: {film_description[:100]}...")
            
            return jsonify({
                'success': True,
                'description': film_description,
                'length': len(film_description)
            })
            
        except Exception as e:
            logger.error(f"Ошибка генерации описания фильма: {e}")
            return jsonify({
                'success': False,
                'error': f'Ошибка генерации: {str(e)}'
            })
            
    except Exception as e:
        logger.error(f"Ошибка в generate_film_description: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Authentication endpoints
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Проверка пароля администратора"""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        # Простая проверка пароля (замените на более безопасную)
        if password == 'admin123':  # Замените на ваш пароль
            session['admin_authenticated'] = True
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'error': 'Invalid password'}), 401
            
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Выход администратора"""
    try:
        session.pop('admin_authenticated', None)
        return jsonify({'success': True, 'message': 'Logout successful'})
    except Exception as e:
        logger.error(f"Ошибка выхода: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/check-auth', methods=['GET'])
def check_admin_auth():
    """Проверка аутентификации администратора"""
    try:
        is_authenticated = session.get('admin_authenticated', False)
        return jsonify({
            'success': True,
            'authenticated': is_authenticated
        })
    except Exception as e:
        logger.error(f"Ошибка проверки аутентификации: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Base prompt endpoints
@app.route('/api/admin/get-base-prompt', methods=['GET'])
def get_base_prompt():
    """Получает текущий базовый промт"""
    try:
        prompt_info = get_prompt_info()
        return jsonify({
            'success': True,
            'prompt': prompt_info['prompt'],
            'length': prompt_info['length'],
            'preview': prompt_info['preview']
        })
    except Exception as e:
        logger.error(f"Ошибка получения базового промта: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/generate-custom-image', methods=['POST'])
def generate_custom_image():
    """Генерирует изображение на основе пользовательского промта и базового промта"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        custom_prompt = data.get('custom_prompt', '').strip()
        if not custom_prompt:
            return jsonify({'success': False, 'error': 'Custom prompt is required'}), 400
        
        # Получаем базовый промт
        base_prompt = get_current_base_prompt()
        
        # Объединяем промты
        full_prompt = f"{custom_prompt} {base_prompt}"
        
        logger.info(f"🎨 Генерируем изображение с промтом: {full_prompt[:100]}...")
        
        # Генерируем изображение
        try:
            # Создаем папку если не существует
            os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)
            
            # Генерируем изображение
            image_path = generate_image_with_retry(full_prompt)
            
            if image_path and os.path.exists(image_path):
                # Обрабатываем изображение с помощью PIL (как в умной системе батчей)
                processed_image_path = _process_and_compress_image(image_path)
                
                filename = os.path.basename(processed_image_path)
                image_url = f"/generated_images/{filename}"
                
                # Получаем размер обработанного изображения
                try:
                    with Image.open(processed_image_path) as img:
                        image_width, image_height = img.size
                        image_size_info = f"{image_width}x{image_height}"
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить размер изображения: {e}")
                    image_size_info = "Неизвестно"
                
                logger.info(f"✅ Изображение сгенерировано и обработано: {filename} ({image_size_info})")
                
                return jsonify({
                    'success': True,
                    'image_url': image_url,
                    'image_path': processed_image_path,
                    'filename': filename,
                    'prompt': full_prompt,
                    'image_size': image_size_info,
                    'processed': True
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Не удалось сгенерировать изображение'
                })
                
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            return jsonify({
                'success': False,
                'error': f'Ошибка генерации: {str(e)}'
            })
            
    except Exception as e:
        logger.error(f"Ошибка в generate_custom_image: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Serve generated images
@app.route('/generated_images/<filename>')
def serve_generated_image(filename):
    """Отдает сгенерированные изображения"""
    try:
        return send_from_directory(GENERATED_IMAGES_FOLDER, filename)
    except Exception as e:
        logger.error(f"Ошибка отдачи изображения {filename}: {e}")
        return "Image not found", 404

# Global error handlers
@app.errorhandler(UnicodeDecodeError)
def handle_unicode_error(e):
    logger.error(f"UnicodeDecodeError: {e}")
    return jsonify({
        'success': False,
        'error': 'Character encoding error',
        'message': 'Invalid character encoding detected'
    }), 400

@app.errorhandler(UnicodeError)
def handle_unicode_error_general(e):
    logger.error(f"UnicodeError: {e}")
    return jsonify({
        'success': False,
        'error': 'Unicode error',
        'message': 'Text encoding issue detected'
    }), 400

@app.errorhandler(Exception)
def handle_general_error(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

if __name__ == '__main__':
    # Создаем папку для изображений если не существует
    os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)
    
    # Запускаем Flask приложение
    print("🚀 Запуск админ-панели Neuroevent...")
    print("📊 Доступна по адресу: http://localhost:8000/admin")
    print("🔐 Логин: admin123")
    print("🎭 Готов к работе!")
    
    app.run(host='0.0.0.0', port=8000, debug=True)
