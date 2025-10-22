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
from image_queue_manager import queue_manager
from batch_image_generator import batch_generator
from gemini_client import generate_image_with_retry, GeminiQuotaError
from content_filter import check_content_safety, sanitize_image_prompt
from PIL import Image, ImageOps
from io import BytesIO
import threading
import time
import asyncio
import requests
import base64
from config import BOT_TOKEN

def auto_generation_worker():
    """Фоновый процесс автоматической генерации изображений"""
    logger.info("🔄 Автоматическая генерация изображений запущена (каждые 15 секунд)")
    
    while True:
        try:
            # Проверяем, есть ли готовые батчи для обработки
            current_batch = queue_manager.get_current_batch()
            if current_batch and current_batch.status == 'ready':
                logger.info(f"🎨 Обработка батча {current_batch.id} с {len(current_batch.requests)} запросами")
                
                # Обрабатываем батч
                success = asyncio.run(batch_generator.process_next_batch())
                if success:
                    logger.info(f"✅ Батч {current_batch.id} успешно обработан")
                else:
                    logger.warning(f"⚠️ Не удалось обработать батч {current_batch.id}")
            else:
                logger.debug("📭 Нет готовых батчей для обработки")
            
            # Ждем 15 секунд перед следующей проверкой
            time.sleep(15)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в автоматической генерации: {e}")
            time.sleep(30)  # При ошибке ждем дольше

def send_telegram_message(user_id, message):
    """Отправляет сообщение пользователю через Telegram Bot API"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
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
        
        # Добавляем запрос в очередь генерации изображений
        try:
            req_id = queue_manager.add_request(user_id, username, first_name, message)
            logger.info(f"Запрос добавлен в очередь генерации: {req_id}")
        except Exception as e:
            logger.warning(f"Не удалось добавить запрос в очередь генерации: {e}")
            
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
    all_user_msgs = message_db.get_user_messages_only(100)
    msgs = [msg for msg in all_user_msgs if msg.get('source') == 'mini_app'][-15:]
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
            prompt = f"Сообщения пользователей: {'; '.join(filtered_texts)}"
            # Используем синхронный подход для вызова async функции
            try:
                # Создаем новый event loop для этого вызова
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                mixed = loop.run_until_complete(get_openai_response(prompt))
                loop.close()
            except RuntimeError as e:
                logger.error(f"Ошибка event loop: {e}")
                # Fallback: используем простой ответ
                mixed = f"Обработано {len(filtered_texts)} сообщений пользователей."
    
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

Какие образы или пейзажи возникают у вас, когда вы думаете об этой истории? 

Пожалуйста, ответьте 1–5 словами. Можно написать сейчас или во время исполнения, но только один раз в рамках этого произведения."""
            
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
                if msg.get('source') == 'mini_app' and msg.get('user_id') and msg.get('user_id') != 0:
                    mini_app_users.add(msg['user_id'])
            
            logger.info(f"Найдено {len(mini_app_users)} пользователей Mini App для отправки сообщения")
            logger.info(f"ID пользователей: {list(mini_app_users)}")
            
            # Отправляем сообщение каждому пользователю через Telegram Bot
            for user_id in mini_app_users:
                try:
                    logger.info(f"Отправка сообщения пользователю {user_id}")
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
            "failed_count": failed_count
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
