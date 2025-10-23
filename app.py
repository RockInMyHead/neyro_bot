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
    logger.info("🚀 Новая система последовательной обработки батчей запущена")
    
    while True:
        try:
            # Проверяем, есть ли необработанные сообщения
            stats = smart_batch_manager.get_statistics()
            
            if stats['total_messages'] > 0:
                logger.info(f"📝 Обнаружено {stats['total_messages']} сообщений, создаем батчи...")
                
                # Создаем батчи из накопленных сообщений
                created_batches = smart_batch_manager.create_batches()
                
                if created_batches:
                    logger.info(f"✅ Создано {len(created_batches)} батчей")
                    
                    # Последовательно обрабатываем все батчи
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        result = loop.run_until_complete(sequential_processor.process_all_batches())
                        logger.info(f"🎉 Обработка завершена: {result['processed']} успешно, {result['failed']} ошибок")
                    finally:
                        loop.close()
            
            # Очищаем старые завершенные батчи (старше 1 часа)
            smart_batch_manager.clear_completed_batches(older_than_hours=1)
            
            # Проверяем очередь каждые 5 секунд
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в фоновом процессе: {e}", exc_info=True)
            time.sleep(10)  # При ошибке увеличиваем интервал

def send_telegram_message(user_id, message):
    """Отправляет сообщение пользователю через Telegram Bot API"""
    try:
        url = f"https://api.telegram.org/bot{NEW_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': user_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, data=data, timeout=10)
        
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

def send_telegram_notification_with_button(user_id, notification_text, button_text="🎬 Открыть Mini App", web_app_url=None):
    """Отправляет уведомление с кнопкой для перехода в Mini App"""
    try:
        url = f"https://api.telegram.org/bot{NEW_BOT_TOKEN}/sendMessage"
        
        # Если URL не указан, используем дефолтный
        if not web_app_url:
            web_app_url = "https://t.me/neyro_bot/app"  # Замените на ваш реальный URL Mini App
        
        data = {
            'chat_id': user_id,
            'text': notification_text,
            'parse_mode': 'Markdown',
            'reply_markup': {
                'inline_keyboard': [[
                    {
                        'text': button_text,
                        'web_app': {'url': web_app_url}
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

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'neuroevent_admin_secret_key_2024')

# Enable CORS for API routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Глобальная обработка ошибок UnicodeDecodeError
@app.errorhandler(UnicodeDecodeError)
def handle_unicode_error(e):
    logger.error(f"UnicodeDecodeError: {e}")
    return jsonify({
        'success': False, 
        'error': 'Character encoding error',
        'message': 'Invalid character encoding detected'
    }), 400

# Глобальная обработка ошибок кодировки
@app.errorhandler(UnicodeError)
def handle_unicode_error_general(e):
    logger.error(f"UnicodeError: {e}")
    return jsonify({
        'success': False, 
        'error': 'Unicode error',
        'message': 'Text encoding issue detected'
    }), 400

# Обработка общих ошибок
@app.errorhandler(Exception)
def handle_general_error(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({
        'success': False, 
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

# Декоратор для проверки аутентификации администратора
def require_admin_auth(f):
    def decorated_function(*args, **kwargs):
        is_authenticated = session.get('admin_authenticated', False)
        login_time = session.get('admin_login_time', 0)
        
        # Проверяем, не истекла ли сессия (24 часа)
        if is_authenticated and time.time() - login_time > 86400:
            session.pop('admin_authenticated', None)
            session.pop('admin_login_time', None)
            is_authenticated = False
        
        if not is_authenticated:
            return jsonify({"success": False, "message": "Требуется аутентификация"}), 401
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Serve Mini App
@app.route('/')
def mini_app():
    return render_template('mini_app.html')

# Admin Login Page
@app.route('/admin/login')
def admin_login_page():
    return render_template('admin_login.html')

# Admin Panel (Protected)
@app.route('/admin')
def admin_app():
    # Проверяем аутентификацию
    is_authenticated = session.get('admin_authenticated', False)
    login_time = session.get('admin_login_time', 0)
    
    # Проверяем, не истекла ли сессия (24 часа)
    if is_authenticated and time.time() - login_time > 86400:
        session.pop('admin_authenticated', None)
        session.pop('admin_login_time', None)
        is_authenticated = False
    
    if not is_authenticated:
        return render_template('admin_login.html')
    
    return render_template('admin_mini_app.html')

# Mini App API endpoint
@app.route('/api/message', methods=['POST', 'OPTIONS'])
def api_message():
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response
    # Безопасная обработка JSON данных
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
    except Exception as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return jsonify({'success': False, 'error': 'Invalid JSON format'}), 400
    
    # Безопасная обработка данных с проверкой кодировки
    try:
        message = data.get('message', '').strip()
        # Проверяем и исправляем кодировку сообщения
        if isinstance(message, str):
            # Удаляем недопустимые символы Unicode
            message = message.encode('utf-8', errors='ignore').decode('utf-8')
        
        user_id = data.get('user_id', 0)
        username = data.get('username', 'MiniApp')
        first_name = data.get('first_name', 'MiniApp')
        
        # Безопасная обработка строковых полей
        if isinstance(username, str):
            username = username.encode('utf-8', errors='ignore').decode('utf-8')
        if isinstance(first_name, str):
            first_name = first_name.encode('utf-8', errors='ignore').decode('utf-8')
            
    except UnicodeDecodeError as e:
        logger.error(f"UnicodeDecodeError в api_message: {e}")
        return jsonify({'success': False, 'error': 'Invalid character encoding'}), 400
    except Exception as e:
        logger.error(f"Ошибка обработки данных в api_message: {e}")
        return jsonify({'success': False, 'error': 'Data processing error'}), 400
    
    # Сохраняем сообщение Mini App в базу
    try:
        message_db.add_message(
            user_id=user_id,
            username=username,
            first_name=first_name,
            message=message,
            source='mini_app'
        )
        logger.info(f"Сообщение Mini App сохранено: user_id={user_id}, username={username}")
        
        # NEW: Добавляем сообщение в систему умных батчей
        try:
            msg_id = smart_batch_manager.add_message(user_id, username, first_name, message)
            logger.info(f"✅ Сообщение добавлено в SmartBatchManager: {msg_id}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось добавить сообщение в SmartBatchManager: {e}")
            
    except Exception as e:
        logger.warning(f"Не удалось сохранить сообщение Mini App: {e}")
    conversation_history = data.get('history', [])
    
    if not message:
        return jsonify(success=False, error="Message is required"), 400
    
    # Безопасный вызов async функции
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ai_response = loop.run_until_complete(get_openai_response(message, conversation_history))
        loop.close()
    except RuntimeError as e:
        logger.error(f"Ошибка event loop в api_message: {e}")
        from mock_responses import get_friendly_response
        ai_response = get_friendly_response()
    
    response_data = {
        'success': True,
        'response': ai_response,
        'timestamp': int(time.time() * 1000)
    }
    
    response = jsonify(response_data)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Alias endpoint for compatibility
@app.route('/api/chat', methods=['GET', 'POST', 'OPTIONS'])
def api_chat():
    """Alias for /api/message - supports both GET and POST"""
    if request.method == 'GET':
        # GET request - return chat history or status
        user_id = request.args.get('user_id', 0)
        try:
            # Return basic chat status
            return jsonify({
                'success': True,
                'user_id': user_id,
                'message': 'Chat endpoint active',
                'timestamp': int(time.time() * 1000)
            })
        except Exception as e:
            logger.error(f"Error in GET /api/chat: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        # POST request - process message
        return api_message()

# Admin stats endpoint
@app.route('/api/admin/stats', methods=['GET'])
@require_admin_auth
def admin_stats():
    message_db.load_messages()
    stats = message_db.get_stats()
    response = jsonify(success=True, stats=stats, timestamp=int(time.time()*1000))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Admin messages endpoint
@app.route('/api/admin/messages', methods=['GET'])
def admin_messages():
    message_db.load_messages()
    # Показываем только сообщения от Mini App (исключаем админские и бот)
    all_user_msgs = message_db.get_user_messages_only(200)  # Увеличиваем лимит до 200 сообщений
    msgs = [msg for msg in all_user_msgs if msg.get('source') == 'mini_app'][-50:]  # Показываем последние 50 сообщений
    response = jsonify(success=True, messages=msgs, count=len(msgs), timestamp=int(time.time()*1000))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Admin export endpoint
@app.route('/api/admin/export', methods=['GET'])
def admin_export():
    message_db.load_messages()
    stats = message_db.get_stats()
    recent = message_db.get_messages(60)
    export_data = {'export_info':{'timestamp':int(time.time()*1000),'export_time': time.strftime('%Y-%m-%d %H:%M:%S'),'total_messages': len(message_db.messages)}, 'statistics': stats, 'recent_messages': recent}
    response = jsonify(success=True, data=export_data, timestamp=int(time.time()*1000))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Admin reset endpoint
@app.route('/api/admin/reset', methods=['POST'])
def admin_reset():
    message_db.reset_stats()
    response = jsonify(success=True, message='Статистика сброшена', timestamp=int(time.time()*1000))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Admin mixed-text endpoint
@app.route('/api/admin/mixed-text', methods=['POST'])
def admin_mixed_text():
    # Accept empty request body
    content = request.get_json(silent=True) or {}
    message_db.load_messages()
    recent = message_db.get_user_messages_only(15)
    texts = [m['message'] for m in recent]
    if not texts:
        mixed = 'Нет сообщений пользователей для генерации миксированного текста.'
    else:
        # Фильтруем сообщения перед обработкой
        filtered_texts = []
        for text in texts:
            is_safe, _ = check_content_safety(text)
            if is_safe:
                filtered_texts.append(text)
            else:
                logger.warning(f"Отфильтровано сообщение: {text[:50]}...")
        
        if not filtered_texts:
            mixed = 'Все сообщения содержат нежелательный контент и были отфильтрованы.'
        else:
            # Создаем краткий усредненный промпт (до 100 символов)
            if len(filtered_texts) == 1:
                # Если только одно сообщение, используем его напрямую
                single_text = filtered_texts[0]
                mixed = single_text[:97] + "..." if len(single_text) > 100 else single_text
            else:
                # Для множественных сообщений создаем краткий усредненный промпт
                prompt = f"""Создай краткий усредненный промпт (максимум 100 символов) из этих сообщений пользователей:

Сообщения: {'; '.join(filtered_texts)}

ТРЕБОВАНИЯ:
- Максимум 100 символов
- Объедини ключевые слова и образы
- Используй только самые важные элементы
- Пиши на русском языке
- Создай единый краткий образ

Пример: "Море, шторм, корабль, приключения" """
                
                # Используем синхронный подход для вызова async функции
                try:
                    # Создаем новый event loop для этого вызова
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    mixed = loop.run_until_complete(get_openai_response(prompt))
                    loop.close()
                    
                    # Принудительно ограничиваем до 100 символов
                    if len(mixed) > 100:
                        mixed = mixed[:97] + "..."
                        
                except RuntimeError as e:
                    logger.error(f"Ошибка event loop: {e}")
                    # Fallback: простое объединение ключевых слов
                    mixed = " ".join(filtered_texts[:3])  # Берем первые 3 сообщения
                    if len(mixed) > 100:
                        mixed = mixed[:97] + "..."
    
    response = jsonify(success=True, mixed_text=mixed, timestamp=int(time.time()*1000))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Admin add to queue endpoint
@app.route('/api/admin/queue/add', methods=['POST'])
def admin_queue_add():
    data = request.get_json(force=True)
    try:
        req_id = queue_manager.add_request(
            data.get('user_id'), data.get('username'), data.get('first_name'), data.get('message')
        )
        resp = jsonify(success=True, request_id=req_id, message='Запрос добавлен в очередь', timestamp=int(time.time()*1000))
    except Exception as e:
        resp = jsonify(success=False, error=str(e), timestamp=int(time.time()*1000))
        resp.status_code = 500
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

# Admin queue stats endpoint
@app.route('/api/admin/queue/stats', methods=['GET'])
def admin_queue_stats():
    stats = queue_manager.get_queue_stats()
    resp = jsonify(success=True, stats=stats, timestamp=int(time.time()*1000))
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

# Admin process batch endpoint
@app.route('/api/admin/queue/process', methods=['POST'])
def admin_queue_process():
    try:
        success = batch_generator.process_next_batch()
        resp = jsonify(success=success, message='Батч обработан' if success else 'Нет готовых батчей', timestamp=int(time.time()*1000))
    except Exception as e:
        resp = jsonify(success=False, error=str(e), timestamp=int(time.time()*1000))
        resp.status_code = 500
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

# Admin batch status endpoint
@app.route('/api/admin/queue/batch-status', methods=['GET'])
def admin_batch_status():
    batch_id = request.args.get('batch_id')
    try:
        if batch_id:
            status = batch_generator.get_batch_status(batch_id)
            if not status:
                raise Exception('Батч не найден')
        else:
            current = queue_manager.get_current_batch()
            status = batch_generator.get_batch_status(current.id) if current else None
        resp = jsonify(success=True, batch_status=status, timestamp=int(time.time()*1000))
    except Exception as e:
        resp = jsonify(success=False, error=str(e), timestamp=int(time.time()*1000))
        resp.status_code = 500
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

# ============================================================================
# NEW: Smart Batch System Endpoints
# ============================================================================

@app.route('/api/admin/smart-batches/stats', methods=['GET'])
@require_admin_auth
def smart_batches_stats():
    """Получает статистику умной системы батчей"""
    try:
        batch_stats = smart_batch_manager.get_statistics()
        processor_stats = sequential_processor.get_stats()
        
        response = jsonify(
            success=True,
            batch_stats=batch_stats,
            processor_stats=processor_stats,
            timestamp=int(time.time() * 1000)
        )
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        logger.error(f"Ошибка получения статистики батчей: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/admin/smart-batches/list', methods=['GET'])
def smart_batches_list():
    """Получает список всех батчей"""
    try:
        batches = smart_batch_manager.get_all_batches_info()
        
        response = jsonify(
            success=True,
            batches=batches,
            count=len(batches),
            timestamp=int(time.time() * 1000)
        )
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        logger.error(f"Ошибка получения списка батчей: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/admin/smart-batches/create', methods=['POST'])
def smart_batches_create():
    """Принудительно создает батчи из накопленных сообщений"""
    try:
        created_batches = smart_batch_manager.create_batches()
        
        response = jsonify(
            success=True,
            message=f'Создано {len(created_batches)} батчей',
            batches_created=len(created_batches),
            timestamp=int(time.time() * 1000)
        )
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        logger.error(f"Ошибка создания батчей: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/admin/smart-batches/process-next', methods=['POST'])
def smart_batches_process_next():
    """Обрабатывает следующий батч"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success = loop.run_until_complete(sequential_processor.process_next_batch())
            
            response = jsonify(
                success=success,
                message='Батч обработан успешно' if success else 'Нет доступных батчей',
                timestamp=int(time.time() * 1000)
            )
        finally:
            loop.close()
        
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        logger.error(f"Ошибка обработки батча: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/admin/smart-batches/current-mixed-text', methods=['GET'])
def smart_batches_current_mixed_text():
    """Получает миксированный текст последнего обработанного батча"""
    try:
        batches = smart_batch_manager.get_all_batches_info()
        
        # Ищем последний батч с миксированным текстом
        mixed_text = None
        for batch in reversed(batches):
            if batch.get('mixed_text'):
                mixed_text = batch['mixed_text']
                break
        
        if not mixed_text:
            mixed_text = 'Нет миксированного текста'
        
        response = jsonify(
            success=True,
            mixed_text=mixed_text,
            timestamp=int(time.time() * 1000)
        )
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        logger.error(f"Ошибка получения миксированного текста: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/admin/smart-batches/images', methods=['GET'])
def smart_batches_images():
    """Получить список сгенерированных изображений"""
    try:
        batches = smart_batch_manager.get_all_batches_info()
        completed_batches = [b for b in batches if b['status'] == 'completed' and b.get('image_path')]
        
        # Сортируем по времени завершения (новые сначала)
        # Защищаемся от None значений в completed_at
        completed_batches.sort(key=lambda x: x.get('completed_at') or 0, reverse=True)
        
        images_data = []
        for batch in completed_batches:
            image_path = batch.get('image_path')
            if image_path and os.path.exists(image_path):
                # Создаем URL для изображения
                image_url = f"/static/generated_images/{os.path.basename(image_path)}"
                images_data.append({
                    'batch_id': batch['id'],
                    'mixed_text': batch.get('mixed_text', ''),
                    'image_url': image_url,
                    'image_path': image_path,
                    'completed_at': batch.get('completed_at') or 0,
                    'processing_time': batch.get('processing_time') or 0,
                    'message_count': batch.get('message_count') or 0
                })
        
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
        
        response = jsonify({
            'success': True,
            'images': images_data,
            'count': len(images_data),
            'timestamp': int(time.time() * 1000)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        logger.error(f"Ошибка получения изображений: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time() * 1000)
        }), 500

# ============================================================================

@app.route('/static/generated_images/<filename>')
def serve_generated_image(filename):
    """Служит сгенерированные изображения"""
    try:
        return send_from_directory(GENERATED_IMAGES_FOLDER, filename)
    except Exception as e:
        logger.error(f"Ошибка загрузки изображения {filename}: {e}")
        return "Image not found", 404

@app.route('/api/admin/latest-track', methods=['GET'])
def admin_latest_track():
    """Возвращает последний трек-сообщение"""
    try:
        message_db.load_messages()
        # Фильтруем только админские сообщения треков
        admin_msgs = [m for m in message_db.messages if m.get('source')=='admin']
        if not admin_msgs:
            return jsonify(success=True, message='', timestamp=int(time.time()*1000))
        last = admin_msgs[-1]['message']
        resp = jsonify(success=True, message=last, timestamp=int(time.time()*1000))
        resp.headers.add('Access-Control-Allow-Origin', '*')
        return resp
    except Exception as e:
        logger.exception("Ошибка получения последнего трека")
        return jsonify(success=False, message=str(e)), 500

# Admin generate image endpoint
@app.route('/api/admin/generate-image', methods=['POST'])
def admin_generate_image():
    data = request.get_json(force=True) or {}
    prompt = data.get('prompt')
    if not prompt:
        # derive prompt from mixed text
        recent = message_db.get_user_messages_only(15)
        msgs = [m['message'] for m in recent]
        if not msgs:
            return jsonify(success=False, error='Нет сообщений для генерации', timestamp=int(time.time()*1000)), 400
        prompt = ' '.join(msgs)
    
    # Проверяем безопасность контента
    is_safe, reason = check_content_safety(prompt)
    if not is_safe:
        logger.warning(f"Заблокирован небезопасный контент: {reason}")
        resp = jsonify(success=False, error=f'Контент заблокирован: {reason}', timestamp=int(time.time()*1000))
        resp.status_code = 400
        resp.headers.add('Access-Control-Allow-Origin', '*')
        return resp
    
    # Очищаем промпт от нежелательного контента
    clean_prompt = sanitize_image_prompt(prompt)
    
    try:
        # Используем безопасный вызов async функции
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            image_b64 = loop.run_until_complete(generate_image_with_retry(clean_prompt))
            loop.close()
        except RuntimeError as e:
            logger.error(f"Ошибка event loop в генерации изображения: {e}")
            raise Exception(f"Ошибка генерации: {e}")
            
        img_data = base64.b64decode(image_b64)
        filename = f"image_{int(time.time())}.png"
        folder = os.getenv('GENERATED_IMAGES_FOLDER','generated_images')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        with Image.open(BytesIO(img_data)) as img:
            img = ImageOps.fit(img, (1920,1280), Image.Resampling.LANCZOS)
            img.save(path)
        resp = jsonify(success=True, filename=filename, filepath=f'/generated_images/{filename}', original_prompt=prompt, clean_prompt=clean_prompt, timestamp=int(time.time()*1000))
    except GeminiQuotaError as e:
        resp = jsonify(success=False, error=f'Квота истекла: {e}', timestamp=int(time.time()*1000))
        resp.status_code = 429
    except Exception as e:
        resp = jsonify(success=False, error=str(e), timestamp=int(time.time()*1000))
        resp.status_code = 500
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

# Serve generated images
@app.route('/generated_images/<path:filename>')
def generated_images(filename):
    return send_from_directory(os.getenv('GENERATED_IMAGES_FOLDER','generated_images'), filename)

# Telegram Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    """Обрабатывает webhook от Telegram"""
    try:
        # Получаем данные от Telegram
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("Получен пустой webhook от Telegram")
            return jsonify({"status": "error", "message": "Empty data"}), 400
        
        logger.info(f"Получен webhook: {json.dumps(update_data, ensure_ascii=False)}")
        
        # Здесь можно добавить обработку обновлений от Telegram
        # Пока просто логируем и отвечаем OK
        if 'message' in update_data:
            message = update_data['message']
            logger.info(f"Получено сообщение от пользователя {message.get('from', {}).get('id')}: {message.get('text')}")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/generate-content', methods=['POST'])
def admin_generate_content():
    """Генерирует контент для концертных сообщений с помощью ChatGPT"""
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400
        
        prompt = data['prompt']
        content_type = data.get('type', 'general')
        
        # Используем OpenAI для генерации контента
        import asyncio
        from openai_client import get_openai_response
        
        # Выполняем асинхронную генерацию безопасно
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            generated_content = loop.run_until_complete(get_openai_response(prompt))
            loop.close()
        except RuntimeError as e:
            logger.error(f"Ошибка event loop в генерации контента: {e}")
            generated_content = f"Ошибка генерации контента: {e}"
        
        if generated_content:
            logger.info(f"Контент сгенерирован ({content_type}): {generated_content[:100]}...")
            return jsonify({
                "success": True,
                "content": generated_content,
                "type": content_type
            })
        else:
            return jsonify({"success": False, "message": "Ошибка генерации контента"}), 500
            
    except Exception as e:
        logger.error(f"Ошибка генерации контента: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/clear-messages', methods=['POST'])
def admin_clear_messages():
    """Очищает все сообщения из базы данных"""
    try:
        logger.info("Запрос на очистку всех сообщений")
        
        # Очищаем все сообщения
        message_db.clear_all_messages()
        
        logger.info("Все сообщения успешно очищены")
        
        return jsonify({
            "success": True,
            "message": "Все сообщения успешно очищены",
            "timestamp": int(time.time() * 1000)
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки сообщений: {e}")
        return jsonify({
            "success": False,
            "message": f"Ошибка очистки сообщений: {str(e)}",
            "timestamp": int(time.time() * 1000)
        }), 500

@app.route('/api/admin/clear-all-chats', methods=['POST'])
def admin_clear_all_chats():
    """Очищает всю историю чатов пользователей (сообщения, батчи, изображения)"""
    try:
        logger.info("Запрос на очистку всей истории чатов")
        
        # ВАЖНО: Получаем список пользователей ДО очистки базы данных
        message_db.load_messages()
        mini_app_users = set()
        all_messages = message_db.messages
        
        for msg in all_messages:
            if msg.get('source') == 'mini_app' and msg.get('user_id') is not None:
                mini_app_users.add(msg['user_id'])
        
        logger.info(f"Найдено {len(mini_app_users)} пользователей Mini App для уведомления: {list(mini_app_users)}")
        
        # Теперь очищаем все сообщения
        message_db.clear_all_messages()
        
        # Очищаем все батчи
        smart_batch_manager.clear_all_batches()
        
        # Очищаем все изображения (удаляем файлы)
        import os
        import shutil
        if os.path.exists(GENERATED_IMAGES_FOLDER):
            for filename in os.listdir(GENERATED_IMAGES_FOLDER):
                file_path = os.path.join(GENERATED_IMAGES_FOLDER, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"Удален файл изображения: {filename}")
        
        logger.info("Вся история чатов успешно очищена")
        
        # Устанавливаем timestamp очистки чата
        global chat_clear_timestamp
        chat_clear_timestamp = int(time.time() * 1000)
        
        # Отправляем специальное сообщение всем пользователям для очистки их чата
        try:
            clear_chat_message = "🔄 История чата была очищена администратором. Ваш чат будет автоматически обновлен."
            
            # Отправляем сообщение каждому пользователю через Telegram Bot
            sent_count = 0
            for user_id in mini_app_users:
                try:
                    # Если user_id = 0, это локальная разработка - пропускаем отправку через Telegram
                    if user_id == 0:
                        logger.info(f"Пропускаем отправку через Telegram для user_id = 0 (локальная разработка)")
                        sent_count += 1  # Считаем как успешную отправку
                        continue
                    
                    # Отправляем уведомление с кнопкой вместо полного сообщения
                    clear_notification_text = "🔄 **История чата была очищена администратором**\n\nНажмите кнопку ниже, чтобы открыть Mini App с чистым чатом."
                    success = send_telegram_notification_with_button(user_id, clear_notification_text, "🔄 Открыть Mini App")
                    if success:
                        sent_count += 1
                        logger.info(f"✅ Уведомление об очистке отправлено пользователю {user_id}")
                    else:
                        logger.warning(f"⚠️ Не удалось отправить уведомление об очистке пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения очистки пользователю {user_id}: {e}")
            
            logger.info(f"Отправлено {sent_count} сообщений об очистке чата из {len(mini_app_users)} пользователей")
            
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщения об очистке чата: {e}")
        
        return jsonify({
            "success": True,
            "message": "Вся история чатов успешно очищена",
            "timestamp": int(time.time() * 1000)
        })
        
    except Exception as e:
        logger.error(f"Ошибка при очистке истории чатов: {e}")
        return jsonify({
            "success": False,
            "message": f"Ошибка при очистке истории чатов: {str(e)}",
            "timestamp": int(time.time() * 1000)
        }), 500

@app.route('/api/mini-app/latest-message', methods=['GET'])
def get_latest_message():
    """Получает последнее сообщение для отображения в mini_app"""
    try:
        # Получаем последнее сообщение от админа
        message_db.load_messages()
        admin_messages = [msg for msg in message_db.messages if msg.get('source') == 'admin']
        
        # Автоматически очищаем старые админские сообщения (старше 5 минут)
        current_time = time.time()
        old_admin_messages = [msg for msg in admin_messages if current_time - msg.get('timestamp', 0) > 300]
        
        if old_admin_messages:
            logger.info(f"🧹 Автоматически очищаем {len(old_admin_messages)} старых админских сообщений")
            message_db.messages = [msg for msg in message_db.messages if not (msg.get('source') == 'admin' and current_time - msg.get('timestamp', 0) > 300)]
            message_db.save_messages()
            # Перезагружаем сообщения после очистки
            message_db.load_messages()
            admin_messages = [msg for msg in message_db.messages if msg.get('source') == 'admin']
        
        logger.info(f"🔍 Поиск сообщений от админа: найдено {len(admin_messages)} сообщений")
        logger.info(f"🔍 Все сообщения в БД: {len(message_db.messages)}")
        
        # Логируем все источники сообщений для отладки
        sources = [msg.get('source', 'unknown') for msg in message_db.messages]
        logger.info(f"🔍 Источники сообщений: {set(sources)}")
        
        if admin_messages:
            # Сортируем сообщения по времени и берем самое новое
            latest_message = max(admin_messages, key=lambda x: x.get('timestamp', 0))
            logger.info(f"✅ Найдено последнее сообщение от админа: {latest_message.get('message', '')[:50]}...")
            
            # Проверяем, не было ли недавно отправлено новое сообщение
            global last_admin_message_time
            message_time = latest_message.get('timestamp', 0)
            is_recent = (time.time() - message_time) < 30  # Сообщение отправлено менее 30 секунд назад
            
            # Дополнительная проверка: если есть несколько одинаковых сообщений, берем только одно
            message_content = latest_message.get('message', '').strip()
            if message_content:
                # Проверяем, есть ли дублирующиеся сообщения с тем же содержимым
                duplicate_messages = [
                    msg for msg in admin_messages 
                    if msg.get('message', '').strip() == message_content and msg.get('timestamp', 0) != message_time
                ]
                
                if duplicate_messages:
                    logger.info(f"🔍 Найдено {len(duplicate_messages)} дублирующихся сообщений с тем же содержимым")
                    # Очищаем дублирующиеся сообщения
                    message_db.messages = [msg for msg in message_db.messages if not (
                        msg.get('source') == 'admin' and 
                        msg.get('message', '').strip() == message_content and 
                        msg.get('timestamp', 0) != message_time
                    )]
                    message_db.save_messages()
                    logger.info("🧹 Дублирующиеся админские сообщения очищены")
            
            return jsonify({
                "success": True,
                "message": latest_message.get('message', ''),
                "timestamp": latest_message.get('timestamp', 0),
                "is_recent": is_recent,
                "last_admin_time": last_admin_message_time
            })
        else:
            logger.info("❌ Сообщения от админа не найдены")
            return jsonify({
                "success": True,
                "message": "",
                "timestamp": 0,
                "is_recent": False,
                "last_admin_time": last_admin_message_time
            })
    except Exception as e:
        logger.error(f"Ошибка получения последнего сообщения: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def clear_old_admin_messages():
    """Очищает старые админские сообщения из БД"""
    try:
        message_db.load_messages()
        admin_messages = [msg for msg in message_db.messages if msg.get('source') == 'admin']
        
        if len(admin_messages) > 0:
            logger.info(f"🧹 Очищаем {len(admin_messages)} старых админских сообщений")
            
            # Удаляем все админские сообщения
            message_db.messages = [msg for msg in message_db.messages if msg.get('source') != 'admin']
            message_db.save_messages()
            
            logger.info("✅ Старые админские сообщения очищены")
    except Exception as e:
        logger.error(f"❌ Ошибка очистки старых админских сообщений: {e}")

@app.route('/api/admin/send-concert-message', methods=['POST'])
@require_admin_auth
def admin_send_concert_message():
    """Отправляет концертное сообщение в чат"""
    try:
        # Очищаем старые админские сообщения перед отправкой нового
        clear_old_admin_messages()
        
        data = request.get_json(silent=True) or {}
        logger.info(f"/api/admin/send-concert-message payload: {data}")
        
        if 'type' not in data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400
        
        message_type = data['type']
        content = data.get('content', {}) or {}
        
        if message_type == 'track_message':
            # content может быть либо строкой (готовое сообщение), либо объектом с полями
            if isinstance(content, str):
                message = content.strip()
            else:
                title = (content.get('title') or '').strip()
                description = (content.get('description') or '').strip()
                actors = (content.get('actors') or '').strip()

                # Доп. защита: подставляем плейсхолдеры, чтобы не падать на пустых значениях
                if not title:
                    title = 'Без названия'
                if not description:
                    description = 'Описание отсутствует'
                if not actors:
                    actors = '—'

                message = f"""📽️ **{title}**

{description}

**Актёры/персонажи:** {actors}

---

Какие образы или пейзажи возникают у вас, когда вы думаете об этой истории?"""
            
        elif message_type == 'concert_end':
            message = """Спасибо, что были с нами — Main Strings Orchestra × Neuroevent.
Оставьте короткий отзыв — это помогает нам становиться лучше!
P.S. Ответы анонимны."""
            
        else:
            return jsonify({"success": False, "message": "Неизвестный тип сообщения"}), 400
        
        # Отправляем сообщение всем пользователям Mini App
        logger.info(f"Отправка концертного сообщения ({message_type}) всем пользователям...")
        logger.info(f"Сообщение: {message[:200].replace(chr(10), ' ')}")
        
        sent_count = 0
        failed_count = 0
        
        # Получаем список всех пользователей из базы данных
        try:
            message_db.load_messages()
            # Получаем уникальных пользователей из Mini App
            mini_app_users = set()
            all_messages = message_db.messages
            logger.info(f"Всего сообщений в БД: {len(all_messages)}")
            
            for msg in all_messages:
                logger.info(f"Сообщение: source={msg.get('source')}, user_id={msg.get('user_id')}")
                if msg.get('source') == 'mini_app' and msg.get('user_id') is not None:
                    # Включаем пользователей с user_id = 0 для локальной разработки
                    mini_app_users.add(msg['user_id'])
            
            logger.info(f"Найдено {len(mini_app_users)} пользователей Mini App для отправки сообщения")
            logger.info(f"ID пользователей: {list(mini_app_users)}")
            
            # Отправляем сообщение каждому пользователю через Telegram Bot
            for user_id in mini_app_users:
                try:
                    logger.info(f"Отправка сообщения пользователю {user_id}")
                    
                    # Если user_id = 0, это локальная разработка - пропускаем отправку
                    if user_id == 0:
                        logger.info(f"Пропускаем отправку для user_id = 0 (локальная разработка)")
                        sent_count += 1  # Считаем как успешную отправку
                        continue
                    
                    # Отправляем уведомление с кнопкой вместо полного сообщения
                    notification_text = "🎬 **У вас новое сообщение в Mini App!**\n\nНажмите кнопку ниже, чтобы открыть чат и увидеть новое сообщение от администратора."
                    success = send_telegram_notification_with_button(user_id, notification_text)
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
                    failed_count += 1
            
            logger.info(f"Отправлено сообщений: {sent_count}, ошибок: {failed_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке концертного сообщения: {e}")
        
        # Save admin message to DB (с проверкой на дублирование)
        try:
            logger.info(f"💾 Проверяем, нужно ли сохранять админское сообщение в БД...")
            
            # Проверяем, не было ли уже сохранено такое же сообщение недавно (в течение 30 секунд)
            message_db.load_messages()
            current_time = time.time()
            recent_admin_messages = [
                msg for msg in message_db.messages 
                if (msg.get('source') == 'admin' and 
                    current_time - msg.get('timestamp', 0) < 30 and
                    msg.get('message', '').strip() == message.strip())
            ]
            
            if recent_admin_messages:
                logger.info(f"⚠️ Найдено {len(recent_admin_messages)} дублирующихся админских сообщений за последние 30 секунд")
                logger.info("🔄 Пропускаем сохранение дублирующегося сообщения")
            else:
                logger.info(f"💾 Сохраняем новое админское сообщение в БД: {message[:100]}...")
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
        
        return jsonify({
            "success": True, 
            "message": f"Сообщение типа '{message_type}' отправлено {sent_count} пользователям",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(mini_app_users)
        })
        
    except Exception as e:
        logger.exception("Ошибка отправки концертного сообщения")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"        }), 500

# Глобальная переменная для отслеживания статуса очистки чата
chat_clear_timestamp = None

# Глобальная переменная для отслеживания времени последнего админского сообщения
last_admin_message_time = 0

@app.route('/api/check-chat-clear-status', methods=['GET'])
def check_chat_clear_status():
    """Проверяет, была ли очищена история чата"""
    global chat_clear_timestamp
    return jsonify({
        "success": True,
        "chat_cleared": chat_clear_timestamp is not None,
        "clear_timestamp": chat_clear_timestamp
    })

@app.route('/api/admin/update-base-prompt', methods=['POST'])
def admin_update_base_prompt():
    """Обновляет базовый промт для AI"""
    try:
        data = request.get_json()
        
        if not data or 'prompt_type' not in data or 'prompt_content' not in data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400
        
        prompt_type = data['prompt_type']
        prompt_content = data['prompt_content']
        
        # Обновляем базовый промт через менеджер
        update_base_prompt(prompt_content)
        
        logger.info(f"Обновление базового промта ({prompt_type}): {prompt_content[:100]}...")
        logger.info(f"✅ Базовый промт для генерации изображений обновлен")
        
        return jsonify({
            "success": True, 
            "message": f"Базовый промт '{prompt_type}' успешно обновлен"
        })
        
    except Exception as e:
        logger.error(f"Ошибка обновления базового промта: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/generate-film-description', methods=['POST'])
def generate_film_description():
    """Генерировать красивое описание фильма на основе технического промта"""
    try:
        data = request.get_json()
        technical_prompt = data.get('technical_prompt', '')
        film_title = data.get('film_title', '')
        
        if not technical_prompt:
            return jsonify({"success": False, "message": "Технический промт не предоставлен"}), 400
        
        # Создаем промт для генерации красивого описания
        description_prompt = f"""
На основе этого технического описания кинематографического стиля создай КОРОТКОЕ, атмосферное описание фильма для зрителей концерта:

Техническое описание: {technical_prompt}

Требования:
- Напиши ОДНО ЗАВЕРШЕННОЕ предложение длиной НЕ БОЛЕЕ 200 символов
- Используй эмоциональные и образные слова
- Опиши атмосферу, настроение и визуальные образы
- Сделай текст понятным для обычных зрителей (не техническим)
- Вдохновляй на воображение и эмоции
- Используй русский язык
- ОБЯЗАТЕЛЬНО заверши предложение полностью - НЕ обрывай на середине
- Сделай описание цельным и законченным
- Строго соблюдай лимит в 200 символов

Пример стиля (200 символов):
"Погружаясь в атмосферу грязных улиц Филадельфии, зритель оказывается в потных спортзалах, где каждое дыхание наполнено решимостью и стойкостью."

ВАЖНО: Описание должно быть ЗАВЕРШЕННЫМ и не обрываться на середине предложения! Максимум 200 символов!
"""
        
        # Генерируем описание через OpenAI
        from openai_client import get_openai_response
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            description = loop.run_until_complete(get_openai_response(description_prompt))
            if not description:
                description = technical_prompt  # Fallback
            
            # Проверяем, что описание завершено
            description = description.strip()
            
            # Если описание слишком длинное, пытаемся найти последнее завершенное предложение
            if len(description) > 200:
                last_sentence_end = max(
                    description.rfind('.'),
                    description.rfind('!'),
                    description.rfind('?')
                )
                
                if last_sentence_end > 30:  # Если есть завершенное предложение
                    description = description[:last_sentence_end + 1]
                else:
                    # Если нет завершенных предложений, обрезаем аккуратно
                    description = description[:197] + '...'
            
            return jsonify({
                "success": True,
                "description": description
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка генерации описания фильма: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Проверка пароля администратора"""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        # Проверяем пароль
        if password == '440521':
            # Создаем сессию
            session['admin_authenticated'] = True
            session['admin_login_time'] = time.time()
            
            logger.info("✅ Администратор успешно вошел в систему")
            return jsonify({
                "success": True,
                "message": "Успешный вход в систему"
            })
        else:
            logger.warning("❌ Неверный пароль администратора")
            return jsonify({
                "success": False,
                "message": "Неверный пароль"
            }), 401
            
    except Exception as e:
        logger.error(f"Ошибка входа администратора: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Выход администратора"""
    try:
        session.pop('admin_authenticated', None)
        session.pop('admin_login_time', None)
        
        logger.info("👋 Администратор вышел из системы")
        return jsonify({
            "success": True,
            "message": "Успешный выход из системы"
        })
        
    except Exception as e:
        logger.error(f"Ошибка выхода администратора: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/check-auth', methods=['GET'])
def check_admin_auth():
    """Проверка аутентификации администратора"""
    try:
        is_authenticated = session.get('admin_authenticated', False)
        login_time = session.get('admin_login_time', 0)
        
        # Проверяем, не истекла ли сессия (24 часа)
        if is_authenticated and time.time() - login_time > 86400:
            session.pop('admin_authenticated', None)
            session.pop('admin_login_time', None)
            is_authenticated = False
        
        return jsonify({
            "success": True,
            "authenticated": is_authenticated,
            "login_time": login_time
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки аутентификации: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API ENDPOINTS ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ =====

@app.route('/api/admin/get-base-prompt', methods=['GET'])
def get_base_prompt():
    """Получает текущий базовый промт"""
    try:
        from prompt_manager import get_current_base_prompt
        current_prompt = get_current_base_prompt()
        
        return jsonify({
            "success": True,
            "prompt": current_prompt
        })
    except Exception as e:
        logger.error(f"Ошибка получения базового промта: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/generate-custom-image', methods=['POST'])
def generate_custom_image():
    """Генерирует изображение на основе пользовательского промта и базового промта"""
    try:
        data = request.get_json()
        custom_prompt = data.get('custom_prompt', '').strip()
        
        if not custom_prompt:
            return jsonify({"success": False, "message": "Промт не предоставлен"}), 400
        
        # Получаем базовый промт
        from prompt_manager import get_current_base_prompt
        base_prompt = get_current_base_prompt()
        
        # Объединяем промты
        full_prompt = f"Создай художественное изображение: {custom_prompt} {base_prompt}"
        
        logger.info(f"Генерация изображения с промтом: {full_prompt[:100]}...")
        
        # Генерируем изображение через Gemini API
        from gemini_client import generate_image_with_retry
        
        # Создаем event loop для async функции
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            image_b64 = loop.run_until_complete(generate_image_with_retry(full_prompt))
        finally:
            loop.close()
        
        # Сохраняем изображение
        import base64
        import uuid
        import time
        from PIL import Image
        from io import BytesIO
        
        # Декодируем base64
        image_data = base64.b64decode(image_b64)
        
        # Создаем папку если не существует
        os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)
        
        # Создаем имя файла
        timestamp = int(time.time())
        filename = f"custom_image_{timestamp}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(GENERATED_IMAGES_FOLDER, filename)
        
        # Обрабатываем и сохраняем изображение
        with Image.open(BytesIO(image_data)) as img:
            # Изменяем размер на 1920x1280 если нужно
            if img.size != (1920, 1280):
                img = img.resize((1920, 1280), Image.Resampling.LANCZOS)
            
            # Сохраняем изображение
            img.save(filepath, 'PNG', quality=95)
        
        # Создаем URL для доступа к изображению
        image_url = f"/generated_images/{filename}"
        
        logger.info(f"✅ Изображение сохранено: {filename}")
        
        return jsonify({
            "success": True,
            "image_url": image_url,
            "filename": filename,
            "message": "Изображение успешно сгенерировано"
        })
        
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Запуск сервера
if __name__ == '__main__':
    # Debug: print registered routes
    print('Registered routes:')
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule}")
    
    # Запускаем фоновый поток для автоматической генерации изображений
    auto_thread = threading.Thread(target=auto_generation_worker, daemon=True)
    auto_thread.start()
    logger.info("🚀 Фоновый поток автоматической генерации запущен")
    
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
