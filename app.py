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
from PIL import Image, ImageOps
from io import BytesIO
import base64
from content_filter import check_content_safety, sanitize_image_prompt

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
    conversation_history = data.get('history', [])
    
    if not message:
        return jsonify(success=False, error="Message is required"), 400
    
    ai_response = asyncio.run(get_openai_response(message, conversation_history))
    
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
    msgs = message_db.get_user_messages_only(15)
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
            # Synchronously call async OpenAI
            mixed = asyncio.run(get_openai_response(prompt))
    
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
        image_b64 = asyncio.run(generate_image_with_retry(clean_prompt))
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

def admin_send_concert_message():
    """Отправляет сообщения концерта всем пользователям"""
    try:
        data = request.get_json()
        
        if not data or 'type' not in data or 'content' not in data:
            return jsonify({"success": False, "message": "Неверные данные"}), 400
        
        message_type = data['type']
        content = data['content']
        
        # Здесь можно добавить логику отправки сообщений всем пользователям
        # Пока просто логируем и возвращаем успех
        logger.info(f"Концертное сообщение ({message_type}): {content[:100]}...")
        
        # В будущем здесь будет интеграция с Telegram Bot API для массовой рассылки
        # или сохранение в базу данных для последующей отправки
        
        return jsonify({
            "success": True, 
            "message": f"Сообщение типа '{message_type}' подготовлено к отправке"
        })
        
    except Exception as e:
        logger.error(f"Ошибка отправки концертного сообщения: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    # Debug: print registered routes
    print('Registered routes:')
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule}")
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
