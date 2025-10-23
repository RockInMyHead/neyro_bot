"""
Генератор изображений для батчей запросов
"""
import asyncio
import time
import httpx
import base64
import uuid
import os
from typing import List, Dict, Optional
from PIL import Image, ImageOps
from io import BytesIO
from image_queue_manager import queue_manager, Batch
from openai_client import get_openai_response
from config import GEMINI_API_KEY, GEMINI_URL, GENERATED_IMAGES_FOLDER
from gemini_client import generate_image_with_retry, GeminiQuotaError

# Импортируем функцию для получения текущего базового промта
try:
    from prompt_manager import get_current_base_prompt
except ImportError:
    # Fallback для случаев, когда импорт не работает
    def get_current_base_prompt():
        return "Мрачный кинематографичный реализм во вселенной Пиратов карибского моря; деревянные корабли с парусами и пушками; пираты; морская дымка, контраст, рим-свет; палитра: сталь/свинец воды, изумруд/бирюза, мох, мокрое дерево, патина бронзы, янтарные блики; фактуры: соль на канатах, камень, рваная парусина, брызги; широкий план, масштаб, без крупных лиц"

class BatchImageGenerator:
    """Генератор изображений для батчей запросов"""
    
    def __init__(self):
        self.is_processing = False
        self.current_batch_id: Optional[str] = None
        
    async def process_next_batch(self) -> bool:
        """Обрабатывает следующий батч в очереди с приоритетной системой"""
        if self.is_processing:
            print("⚠️ Уже обрабатывается другой батч")
            return False
        
        # Ищем любой доступный батч (готовый или только что созданный)
        batch = queue_manager.get_next_batch()
        if not batch:
            print("📭 Нет доступных батчей для обработки")
            return False
        
        # Помечаем батч как обрабатываемый
        queue_manager.start_batch_processing(batch.id)
        self.is_processing = True
        self.current_batch_id = batch.id
        
        try:
            print(f"🚀 ПРИОРИТЕТНАЯ обработка батча {batch.id} с {len(batch.requests)} запросами")
            
            # 1. Создаем миксированный текст из сообщений батча
            mixed_text = await self._create_mixed_text(batch)
            print(f"📝 Создан миксированный текст: {mixed_text[:100]}...")
            
            # 2. Генерируем изображения для батча
            generated_images = await self._generate_batch_images(batch, mixed_text)
            print(f"🎨 Сгенерировано {len(generated_images)} изображений")
            
            # 3. Завершаем батч
            queue_manager.complete_batch(batch.id, mixed_text, generated_images)
            
            print(f"✅ Батч {batch.id} успешно завершен за {time.time() - batch.created_at:.1f} секунд")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обработки батча {batch.id}: {e}")
            queue_manager.fail_batch(batch.id, str(e))
            return False
            
        finally:
            self.is_processing = False
            self.current_batch_id = None
    
    async def _create_mixed_text(self, batch: Batch) -> str:
        """Создает краткий миксированный текст из сообщений батча (до 100 символов)"""
        messages_list = [req.message for req in batch.requests]
        
        if not messages_list:
            return "Нет сообщений для генерации миксированного текста."
        
        # Если только одно сообщение, используем его напрямую (сокращенное)
        if len(messages_list) == 1:
            single_message = messages_list[0]
            # Сокращаем до 100 символов
            if len(single_message) > 100:
                return single_message[:97] + "..."
            return single_message
        
        # Для множественных сообщений создаем краткий усредненный промпт
        prompt = f"""Создай краткий усредненный промпт (максимум 100 символов) из этих сообщений пользователей:

Сообщения: {'; '.join(messages_list)}

ТРЕБОВАНИЯ:
- Максимум 100 символов
- Объедини ключевые слова и образы
- Используй только самые важные элементы
- Пиши на русском языке
- Создай единый краткий образ

Пример: "Море, шторм, корабль, приключения" """
        
        try:
            mixed_text = await get_openai_response(prompt)
            
            # Принудительно ограничиваем до 100 символов
            if len(mixed_text) > 100:
                mixed_text = mixed_text[:97] + "..."
            
            return mixed_text
            
        except Exception as e:
            print(f"⚠️ Ошибка создания миксированного текста: {e}")
            # Fallback: простое объединение ключевых слов
            fallback_text = " ".join(messages_list[:3])  # Берем первые 3 сообщения
            if len(fallback_text) > 100:
                fallback_text = fallback_text[:97] + "..."
            return fallback_text
    
    async def _generate_batch_images(self, batch: Batch, mixed_text: str) -> List[str]:
        """Генерирует изображения для батча"""
        generated_images = []
        
        # Генерируем одно изображение на основе миксированного текста
        # (в будущем можно генерировать по одному на каждый запрос)
        try:
            image_path = await self._generate_single_image(mixed_text, batch.id)
            if image_path:
                generated_images.append(image_path)
                print(f"✅ Сгенерировано изображение: {image_path}")
        except Exception as e:
            print(f"❌ Ошибка генерации изображения: {e}")
            raise
        
        return generated_images
    
    async def _generate_single_image(self, prompt: str, batch_id: str) -> str:
        """Генерирует одно изображение с обработкой ошибок квоты"""
        print(f"🎨 Генерируем изображение для батча {batch_id}...")
        print(f"📝 Краткий промпт ({len(prompt)} символов): {prompt}")
        
        try:
            # Создаем полный промпт для генерации изображения с безопасной обработкой
            try:
                base_prompt = get_current_base_prompt()
                # Безопасная обработка промта
                if isinstance(base_prompt, str):
                    safe_base_prompt = base_prompt.encode('utf-8', errors='ignore').decode('utf-8')
                else:
                    safe_base_prompt = str(base_prompt)
                
                style_addition = f" {safe_base_prompt}"
            except UnicodeDecodeError as e:
                print(f"❌ UnicodeDecodeError при получении базового промта: {e}")
                style_addition = " Кинематографичный стиль; широкий план, масштаб, без крупных лиц."
            except Exception as e:
                print(f"⚠️ Не удалось получить базовый промт: {e}, используем fallback")
                # Fallback на безопасный стиль
                style_addition = " Кинематографичный стиль; широкий план, масштаб, без крупных лиц."
            
            # Безопасная обработка prompt
            try:
                if isinstance(prompt, str):
                    safe_prompt = prompt.encode('utf-8', errors='ignore').decode('utf-8')
                else:
                    safe_prompt = str(prompt)
            except UnicodeDecodeError as e:
                print(f"❌ UnicodeDecodeError в prompt: {e}")
                safe_prompt = "Пользовательское сообщение"
            
            full_prompt = f"Создай художественное изображение: {safe_prompt}{style_addition}"
            
            # Проверяем общую длину промпта
            if len(full_prompt) > 500:
                # Если промпт слишком длинный, сокращаем стилевую часть
                max_style_length = 500 - len(prompt) - 50  # Оставляем место для основного текста
                style_addition = style_addition[:max_style_length] + "..."
                full_prompt = f"Создай художественное изображение: {prompt}{style_addition}"
            
            print(f"🎯 Полный промпт ({len(full_prompt)} символов): {full_prompt[:100]}...")
            
            image_b64 = await generate_image_with_retry(full_prompt)
            
        except GeminiQuotaError as e:
            print(f"❌ Превышена квота Gemini API: {e}")
            if e.retry_after:
                print(f"⏰ Рекомендуется повторить через {e.retry_after} секунд")
            raise Exception(f"Превышена квота API. Попробуйте позже. ({e})")
        
        except Exception as e:
            print(f"❌ Ошибка генерации изображения: {e}")
            raise
        
        # Сохраняем изображение
        filename = f"batch_{batch_id}_{uuid.uuid4().hex[:8]}_{int(time.time())}.png"
        filepath = os.path.join(GENERATED_IMAGES_FOLDER, filename)
        
        # Декодируем и изменяем размер на 1920x1280
        image_data = base64.b64decode(image_b64)
        
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Конвертируем в RGB если нужно
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Изменяем размер изображения с сохранением пропорций и обрезкой по центру
                img = ImageOps.fit(img, (1920, 1280), Image.Resampling.LANCZOS)
                
                # Сохраняем как PNG
                img.save(filepath, 'PNG')
                print(f"✅ Изображение изменено до размера 1920x1280 и сохранено: {filename}")
        except Exception as e:
            # Если PIL не может обработать, сохраняем как есть
            print(f"⚠️ Не удалось изменить размер, сохраняем оригинал: {e}")
            with open(filepath, 'wb') as f:
                f.write(image_data)
        
        return filepath
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Возвращает статус батча"""
        batch = queue_manager._find_batch(batch_id)
        if not batch:
            return None
        
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "requests_count": len(batch.requests),
            "created_at": batch.created_at,
            "started_at": batch.started_at,
            "completed_at": batch.completed_at,
            "mixed_text": batch.mixed_text,
            "generated_images_count": len(batch.generated_images) if batch.generated_images else 0,
            "generated_images": batch.generated_images or []
        }
    
    def get_processing_status(self) -> Dict:
        """Возвращает статус обработки"""
        return {
            "is_processing": self.is_processing,
            "current_batch_id": self.current_batch_id
        }

# Глобальный экземпляр генератора
batch_generator = BatchImageGenerator()


