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

class BatchImageGenerator:
    """Генератор изображений для батчей запросов"""
    
    def __init__(self):
        self.is_processing = False
        self.current_batch_id: Optional[str] = None
        
    async def process_next_batch(self) -> bool:
        """Обрабатывает следующий батч в очереди"""
        if self.is_processing:
            print("⚠️ Уже обрабатывается другой батч")
            return False
        
        batch = queue_manager.get_next_batch()
        if not batch:
            print("📭 Нет готовых батчей для обработки")
            return False
        
        self.is_processing = True
        self.current_batch_id = batch.id
        
        try:
            print(f"🎯 Начинаем обработку батча {batch.id} с {len(batch.requests)} запросами")
            
            # 1. Создаем миксированный текст из сообщений батча
            mixed_text = await self._create_mixed_text(batch)
            print(f"📝 Создан миксированный текст: {mixed_text[:100]}...")
            
            # 2. Генерируем изображения для батча
            generated_images = await self._generate_batch_images(batch, mixed_text)
            print(f"🎨 Сгенерировано {len(generated_images)} изображений")
            
            # 3. Завершаем батч
            queue_manager.complete_batch(batch.id, mixed_text, generated_images)
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обработки батча {batch.id}: {e}")
            queue_manager.fail_batch(batch.id, str(e))
            return False
            
        finally:
            self.is_processing = False
            self.current_batch_id = None
    
    async def _create_mixed_text(self, batch: Batch) -> str:
        """Создает миксированный текст из сообщений батча"""
        messages_list = [req.message for req in batch.requests]
        
        if not messages_list:
            return "Нет сообщений для генерации миксированного текста."
        
        prompt = f"""Создай связный художественный текст, объединяющий следующие сообщения пользователей в единое повествование.

Сообщения пользователей: {'; '.join(messages_list)}

ВАЖНО: 
- Максимум 150 слов
- Текст должен быть связным и осмысленным
- Используй образы и ассоциации из сообщений
- Создай атмосферное повествование
- Пиши на русском языке"""
        
        mixed_text = await get_openai_response(prompt)
        
        # Добавляем стилевой промпт для изображений
        mixed_text += " Мрачный кинематографичный реализм во вселенной Пиратов карибского моря; морская дымка, контраст, рим-свет; палитра: сталь/свинец воды, изумруд/бирюза, мох, мокрое дерево, патина бронзы, янтарные блики; фактуры: соль на канатах, камень, рваная парусина, брызги; широкий план, масштаб, без крупных лиц."
        
        return mixed_text
    
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
        
        try:
            # Используем новый клиент с обработкой ошибок квоты
            full_prompt = f"Создай художественное изображение на основе этого текста: {prompt}"
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


