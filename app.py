from flask import Flask, render_template, send_from_directory, request, jsonify
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

app = Flask(__name__, static_folder='static', template_folder='templates')
# Enable CORS for API routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Serve Mini App
@app.route('/')
def mini_app():
    return render_template('mini_app.html')

# Serve Admin Panel
@app.route('/admin')
def admin_app():
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
    data = request.get_json()
    message = data.get('message', '').strip()
    user_id = data.get('user_id', 0)
    username = data.get('username', 'MiniApp')
    first_name = data.get('first_name', 'MiniApp')
    
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
        ai_response = "Извините, произошла ошибка при обработке сообщения."
    
    response_data = {
        'success': True,
        'response': ai_response,
        'timestamp': int(time.time() * 1000)
    }
    
    response = jsonify(response_data)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Alias endpoint for compatibility
@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def api_chat():
    """Alias for /api/message"""
    return api_message()

# Admin stats endpoint
@app.route('/api/admin/stats', methods=['GET'])
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
        completed_batches.sort(key=lambda x: x.get('completed_at', 0), reverse=True)
        
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
                    'completed_at': batch.get('completed_at'),
                    'processing_time': batch.get('processing_time', 0),
                    'message_count': batch.get('message_count', 0)
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

@app.route('/api/mini-app/latest-message', methods=['GET'])
def get_latest_message():
    """Получает последнее сообщение для отображения в mini_app"""
    try:
        # Получаем последнее сообщение от админа
        message_db.load_messages()
        admin_messages = [msg for msg in message_db.messages if msg.get('source') == 'admin']
        
        if admin_messages:
            latest_message = max(admin_messages, key=lambda x: x.get('timestamp', 0))
            return jsonify({
                "success": True,
                "message": latest_message.get('message', ''),
                "timestamp": latest_message.get('timestamp', 0)
            })
        else:
            return jsonify({
                "success": True,
                "message": "",
                "timestamp": 0
            })
    except Exception as e:
        logger.error(f"Ошибка получения последнего сообщения: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/admin/send-concert-message', methods=['POST'])
def admin_send_concert_message():
    """Отправляет концертное сообщение в чат"""
    try:
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
                    
                    success = send_telegram_message(user_id, message)
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
        
        # Save admin message to DB
        try:
            message_db.add_message(
                user_id=0,
                username='Admin',
                first_name='Admin',
                message=message,
                source='admin'
            )
        except Exception as e:
            logger.warning(f"Не удалось сохранить админское сообщение: {e}")
        
        return jsonify({
            "success": True, 
            "message": f"Сообщение типа '{message_type}' отправлено {sent_count} пользователям",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(mini_app_users)
        })
        
    except Exception as e:
        logger.exception("Ошибка отправки концертного сообщения")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@app.route('/api/admin/update-base-prompt', methods=['POST'])
def admin_update_base_prompt():
    """Обновляет базовый промт для AI"""
    try:
        data = request.get_json()
        
        if not data or 'prompt_type' not in data or 'prompt_content' not in data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400
        
        prompt_type = data['prompt_type']
        prompt_content = data['prompt_content']
        
        # Здесь можно добавить логику сохранения промта в базу данных
        # или обновления глобальной переменной
        logger.info(f"Обновление базового промта ({prompt_type}): {prompt_content[:100]}...")
        
        # В будущем здесь будет сохранение в базу данных или файл конфигурации
        # Пока просто логируем и возвращаем успех
        
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
На основе этого технического описания кинематографического стиля создай красивое, атмосферное описание фильма для зрителей концерта:

Техническое описание: {technical_prompt}

Требования:
- Напиши 2-3 абзаца красивого описания
- Используй эмоциональные и образные слова
- Опиши атмосферу, настроение и визуальные образы
- Сделай текст понятным для обычных зрителей (не техническим)
- Вдохновляй на воображение и эмоции
- Используй русский язык

Пример стиля:
"Погружаясь в мрачную атмосферу Пиратов Карибского моря, зритель поднимается на борт деревянных кораблей, окутанных морской дымкой, и отправляется в эпическое плавание по волнам бурного приключения. Фильм затрагивает вопросы свободы, предательства и вечной борьбы за сокровища, погружая зрителя в сказочный мир пиратства и суровой морской судьбы."
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
            
            return jsonify({
                "success": True,
                "description": description.strip()
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка генерации описания фильма: {e}")
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
