#!/usr/bin/env python3
"""
Последовательный процессор батчей для обработки сообщений
Профессиональная реализация с отслеживанием прогресса
"""

import asyncio
import logging
import time
import os
import base64
from typing import Optional, List, Dict
from PIL import Image, ImageOps
from io import BytesIO

from smart_batch_manager import smart_batch_manager, BatchStatus, SmartBatch
from openai_client import get_openai_response
from gemini_client import generate_image_with_retry, GeminiQuotaError
from config import GENERATED_IMAGES_FOLDER

logger = logging.getLogger(__name__)

# Импортируем функцию для получения текущего базового промта
try:
    from prompt_manager import get_current_base_prompt
except ImportError:
    # Fallback для случаев, когда импорт не работает
    def get_current_base_prompt():
        return "Мрачный кинематографичный реализм во вселенной Пиратов карибского моря; деревянные корабли с парусами и пушками; пираты; морская дымка, контраст, рим-свет; палитра: сталь/свинец воды, изумруд/бирюза, мох, мокрое дерево, патина бронзы, янтарные блики; фактуры: соль на канатах, камень, рваная парусина, брызги; широкий план, масштаб, без крупных лиц"


class SequentialBatchProcessor:
    """
    Последовательный процессор батчей
    
    Логика:
    1. Берет следующий батч из очереди
    2. Создает миксированный текст через LLM (до 100 символов)
    3. Генерирует изображение на основе миксированного текста
    4. Скачивает и сохраняет изображение
    5. Переходит к следующему батчу
    """
    
    MAX_MIXED_TEXT_LENGTH = 100
    IMAGE_SIZE = (1920, 1280)
    
    def __init__(self):
        self.is_processing = False
        self.current_batch_id: Optional[str] = None
        self.processing_stats = {
            'total_processed': 0,
            'total_failed': 0,
            'total_images_generated': 0,
            'average_processing_time': 0.0
        }
        
        # Убедимся что папка для изображений существует
        os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)
        
        logger.info("🚀 SequentialBatchProcessor инициализирован")
    
    async def process_next_batch(self) -> bool:
        """
        Обрабатывает следующий батч из очереди
        
        Returns:
            bool: True если батч обработан успешно, False иначе
        """
        if self.is_processing:
            logger.warning("⚠️ Обработка уже выполняется")
            return False
        
        # Получаем следующий батч
        batch = smart_batch_manager.get_next_batch()
        if not batch:
            logger.debug("📭 Нет доступных батчей для обработки")
            return False
        
        self.is_processing = True
        self.current_batch_id = batch.id
        
        try:
            logger.info(f"🚀 Начало обработки батча {batch.id[:8]} с {batch.message_count} сообщениями")
            
            # Шаг 1: Обновляем статус на "Обработка"
            smart_batch_manager.update_batch_status(batch.id, BatchStatus.PROCESSING)
            
            # Шаг 2: Создаем миксированный текст
            mixed_text = await self._create_mixed_text(batch)
            logger.info(f"✅ Миксированный текст создан ({len(mixed_text)} символов): {mixed_text}")
            
            smart_batch_manager.update_batch_status(
                batch.id, 
                BatchStatus.MIXED, 
                mixed_text=mixed_text
            )
            
            # Шаг 3: Генерируем изображение
            image_path = await self._generate_and_save_image(batch, mixed_text)
            logger.info(f"✅ Изображение сгенерировано и сохранено: {image_path}")
            
            # Шаг 4: Обновляем статус на "Завершено"
            smart_batch_manager.update_batch_status(
                batch.id,
                BatchStatus.COMPLETED,
                image_path=image_path
            )
            
            # Обновляем статистику
            self._update_stats(batch, success=True)
            
            processing_time = batch.processing_time or 0.0
            logger.info(f"🎉 Батч {batch.id[:8]} успешно обработан за {processing_time:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки батча {batch.id[:8]}: {e}", exc_info=True)
            
            smart_batch_manager.update_batch_status(
                batch.id,
                BatchStatus.FAILED,
                error_message=str(e)
            )
            
            self._update_stats(batch, success=False)
            return False
            
        finally:
            self.is_processing = False
            self.current_batch_id = None
    
    async def _create_mixed_text(self, batch: SmartBatch) -> str:
        """
        Создает яркий и красивый миксированный текст из сообщений батча
        
        Args:
            batch: Батч для обработки
            
        Returns:
            str: Миксированный текст (до 100 символов)
        """
        messages_content = [msg.content for msg in batch.messages]
        
        if not messages_content:
            raise ValueError("Батч не содержит сообщений")
        
        # Если только одно сообщение - обрабатываем его напрямую
        if len(messages_content) == 1:
            single_message = messages_content[0]
            
            # Если сообщение уже короткое, возвращаем как есть
            if len(single_message) <= self.MAX_MIXED_TEXT_LENGTH:
                return single_message
            
            # Иначе сокращаем через LLM
            prompt = f"""Преобразуй это сообщение в яркое художественное описание до {self.MAX_MIXED_TEXT_LENGTH} символов:

Сообщение: {single_message}

ТРЕБОВАНИЯ:
- Максимум {self.MAX_MIXED_TEXT_LENGTH} символов
- Яркое и образное описание
- Подходит для генерации изображения
- На русском языке
- Без лишних пояснений

Пример: "Бескрайнее море, шторм, корабль пиратов, золотые сокровища, приключения"""
        
        else:
            # Объединяем несколько сообщений
            combined = "; ".join(messages_content)
            
            prompt = f"""Объедини эти сообщения пользователей в одно яркое художественное описание до {self.MAX_MIXED_TEXT_LENGTH} символов:

Сообщения: {combined}

ТРЕБОВАНИЯ:
- Максимум {self.MAX_MIXED_TEXT_LENGTH} символов
- Объедини ключевые образы и эмоции
- Яркое и красочное описание
- Подходит для генерации изображения
- На русском языке
- Без лишних пояснений

Пример: "Туманное море, пиратский корабль, мистика, приключения, золото"""
        
        try:
            mixed_text = await get_openai_response(prompt)
            
            # Проверяем, что ответ не None
            if mixed_text is None:
                logger.warning("⚠️ get_openai_response вернул None, используем fallback")
                raise Exception("OpenAI response is None")
            
            # Принудительно обрезаем до максимальной длины
            if len(mixed_text) > self.MAX_MIXED_TEXT_LENGTH:
                mixed_text = mixed_text[:self.MAX_MIXED_TEXT_LENGTH - 3] + "..."
            
            return mixed_text.strip()
            
        except Exception as e:
            logger.error(f"Ошибка создания миксированного текста через LLM: {e}")
            
            # Fallback: простое объединение
            fallback = " ".join(messages_content[:3])
            if len(fallback) > self.MAX_MIXED_TEXT_LENGTH:
                fallback = fallback[:self.MAX_MIXED_TEXT_LENGTH - 3] + "..."
            
            return fallback
    
    async def _generate_and_save_image(self, batch: SmartBatch, mixed_text: str) -> str:
        """
        Генерирует изображение на основе миксированного текста и сохраняет его
        
        Args:
            batch: Батч для обработки
            mixed_text: Миксированный текст для генерации
            
        Returns:
            str: Путь к сохраненному изображению
        """
        # Обновляем статус
        smart_batch_manager.update_batch_status(batch.id, BatchStatus.GENERATING)
        
        # Создаем полный промпт с художественным стилем
        full_prompt = self._create_artistic_prompt(mixed_text)
        
        logger.info(f"🎨 Генерация изображения для батча {batch.id[:8]}")
        logger.info(f"📝 Полный промпт ({len(full_prompt)} символов): {full_prompt[:150]}...")
        
        try:
            # Генерируем изображение через Gemini API
            image_b64 = await generate_image_with_retry(full_prompt)
            
            # Декодируем base64
            image_data = base64.b64decode(image_b64)
            
            # Создаем имя файла
            timestamp = int(time.time())
            filename = f"batch_{batch.id[:8]}_{timestamp}.png"
            filepath = os.path.join(GENERATED_IMAGES_FOLDER, filename)
            
            # Обрабатываем и сохраняем изображение
            self._process_and_save_image(image_data, filepath)
            
            logger.info(f"✅ Изображение сохранено: {filename}")
            return filepath
            
        except GeminiQuotaError as e:
            logger.error(f"❌ Превышена квота Gemini API: {e}")
            raise Exception(f"Квота API превышена: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации изображения: {e}")
            raise
    
    def _create_artistic_prompt(self, mixed_text: str) -> str:
        """
        Создает художественный промпт для генерации изображения
        
        Args:
            mixed_text: Миксированный текст пользователей
            
        Returns:
            str: Полный промпт для генерации
        """
        # Проверяем, что mixed_text не None
        if mixed_text is None:
            logger.warning("⚠️ mixed_text is None, using fallback")
            mixed_text = "морской пейзаж, приключения, тайна"
        
        # Получаем текущий базовый промт из админ-панели с безопасной обработкой
        try:
            base_prompt = get_current_base_prompt()
            # Безопасная обработка промта
            if isinstance(base_prompt, str):
                # Удаляем недопустимые символы Unicode
                safe_base_prompt = base_prompt.encode('utf-8', errors='ignore').decode('utf-8')
            else:
                safe_base_prompt = str(base_prompt)
            
            style_addition = f" {safe_base_prompt}"
        except UnicodeDecodeError as e:
            logger.error(f"UnicodeDecodeError при получении базового промта: {e}")
            # Fallback на безопасный стиль
            style_addition = " Кинематографичный стиль; широкий план, масштаб, без крупных лиц."
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить базовый промт: {e}, используем fallback")
            # Fallback на безопасный стиль
            style_addition = " Кинематографичный стиль; широкий план, масштаб, без крупных лиц."
        
        # Безопасная обработка mixed_text
        try:
            if isinstance(mixed_text, str):
                safe_mixed_text = mixed_text.encode('utf-8', errors='ignore').decode('utf-8')
            else:
                safe_mixed_text = str(mixed_text)
        except UnicodeDecodeError as e:
            logger.error(f"UnicodeDecodeError в mixed_text: {e}")
            safe_mixed_text = "Пользовательское сообщение"
        
        full_prompt = f"Создай художественное изображение: {safe_mixed_text}{style_addition}"
        
        # Ограничиваем длину промпта
        max_prompt_length = 500
        if len(full_prompt) > max_prompt_length:
            # Сокращаем стилевую часть
            available_for_style = max_prompt_length - len(mixed_text) - 50
            if available_for_style > 0:
                style_addition = style_addition[:available_for_style] + "..."
                full_prompt = f"Создай художественное изображение: {mixed_text}{style_addition}"
            else:
                # Если даже это не помогает, используем только миксированный текст
                full_prompt = f"Создай художественное изображение: {mixed_text}"
        
        return full_prompt
    
    def _process_and_save_image(self, image_data: bytes, filepath: str):
        """
        Обрабатывает изображение и сохраняет его
        
        Args:
            image_data: Данные изображения в байтах
            filepath: Путь для сохранения
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Конвертируем в RGB если необходимо
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Изменяем размер с сохранением пропорций и обрезкой
                img = ImageOps.fit(img, self.IMAGE_SIZE, Image.Resampling.LANCZOS)
                
                # Сохраняем как PNG
                img.save(filepath, 'PNG', optimize=True)
                
                logger.info(f"🖼️ Изображение обработано: {self.IMAGE_SIZE[0]}x{self.IMAGE_SIZE[1]}")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка обработки изображения через PIL: {e}")
            logger.info("💾 Сохраняем оригинальное изображение")
            
            # Сохраняем как есть
            with open(filepath, 'wb') as f:
                f.write(image_data)
    
    def _update_stats(self, batch: SmartBatch, success: bool):
        """Обновляет статистику обработки"""
        if success:
            self.processing_stats['total_processed'] += 1
            if batch.image_path:
                self.processing_stats['total_images_generated'] += 1
            
            # Обновляем среднее время обработки
            if batch.processing_time:
                current_avg = self.processing_stats['average_processing_time']
                total = self.processing_stats['total_processed']
                
                new_avg = ((current_avg * (total - 1)) + batch.processing_time) / total
                self.processing_stats['average_processing_time'] = new_avg
        else:
            self.processing_stats['total_failed'] += 1
    
    async def process_all_batches(self) -> Dict[str, int]:
        """
        Обрабатывает все доступные батчи последовательно
        
        Returns:
            Dict: Статистика обработки
        """
        logger.info("🚀 Начало последовательной обработки всех батчей")
        
        processed = 0
        failed = 0
        
        while True:
            success = await self.process_next_batch()
            
            if success:
                processed += 1
            else:
                # Проверяем, есть ли еще батчи
                next_batch = smart_batch_manager.get_next_batch()
                if not next_batch:
                    break
                failed += 1
            
            # Небольшая пауза между батчами
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ Обработка завершена: {processed} успешно, {failed} с ошибками")
        
        return {
            'processed': processed,
            'failed': failed,
            'total': processed + failed
        }
    
    def get_stats(self) -> dict:
        """Получает текущую статистику"""
        return {
            **self.processing_stats,
            'is_processing': self.is_processing,
            'current_batch_id': self.current_batch_id
        }
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.processing_stats = {
            'total_processed': 0,
            'total_failed': 0,
            'total_images_generated': 0,
            'average_processing_time': 0.0
        }
        logger.info("🔄 Статистика процессора сброшена")


# Глобальный экземпляр процессора
sequential_processor = SequentialBatchProcessor()

