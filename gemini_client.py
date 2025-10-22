#!/usr/bin/env python3
"""
Модуль для работы с Gemini API с обработкой ошибок квоты и повторными попытками
"""

import httpx
import asyncio
import json
import logging
from typing import Optional, Dict, Any
from config import GEMINI_API_KEY, GEMINI_URL, ENABLE_IMAGE_GENERATION, IMAGE_GENERATION_MESSAGE
from quota_manager import quota_manager, optimize_prompt, estimate_tokens

logger = logging.getLogger(__name__)

class GeminiQuotaError(Exception):
    """Исключение для ошибок квоты Gemini API"""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after

class GeminiClient:
    """Клиент для работы с Gemini API с обработкой ошибок квоты"""
    
    def __init__(self, api_key: str = None, max_retries: int = 3, base_delay: float = 1.0):
        self.api_key = api_key or GEMINI_API_KEY
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.url = GEMINI_URL
        
    async def generate_image(self, prompt: str, retry_count: int = 0) -> str:
        """
        Генерирует изображение с обработкой ошибок квоты
        
        Args:
            prompt: Текст для генерации изображения
            retry_count: Текущее количество попыток
            
        Returns:
            str: Base64 строка изображения
            
        Raises:
            GeminiQuotaError: При превышении квоты
            Exception: При других ошибках
        """
        if retry_count >= self.max_retries:
            raise Exception(f"Превышено максимальное количество попыток ({self.max_retries})")
        
        # Оптимизируем промпт для экономии токенов
        optimized_prompt = optimize_prompt(prompt)
        estimated_tokens = estimate_tokens(optimized_prompt)
        
        # Проверяем квоту перед запросом
        if retry_count == 0:  # Только при первой попытке
            await quota_manager.wait_if_needed(estimated_tokens)
        
        # Формируем запрос к Gemini API
        payload = {
            "contents": [
                {
                    "parts": [
                        { "text": optimized_prompt }
                    ]
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, headers=headers, json=payload, timeout=30)
                
                # Проверяем статус ответа
                if resp.status_code == 429:
                    # Обрабатываем ошибку квоты
                    error_data = resp.json()
                    retry_after = self._extract_retry_after(error_data)
                    
                    logger.warning(f"Превышена квота Gemini API. Попытка {retry_count + 1}/{self.max_retries}")
                    logger.warning(f"Ошибка: {error_data}")
                    
                    if retry_count < self.max_retries - 1:
                        # Ждем перед повторной попыткой
                        delay = retry_after or (self.base_delay * (2 ** retry_count))
                        logger.info(f"Ожидание {delay} секунд перед повторной попыткой...")
                        await asyncio.sleep(delay)
                        
                        # Рекурсивно вызываем функцию с увеличенным счетчиком
                        return await self.generate_image(prompt, retry_count + 1)
                    else:
                        raise GeminiQuotaError(
                            f"Превышена квота Gemini API после {self.max_retries} попыток",
                            retry_after
                        )
                
                resp.raise_for_status()
                resp_json = resp.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Дополнительная обработка 429 ошибки
                try:
                    error_data = e.response.json()
                    retry_after = self._extract_retry_after(error_data)
                    raise GeminiQuotaError(
                        f"HTTP Error: {e.response.status_code} — {e.response.text}",
                        retry_after
                    )
                except:
                    raise GeminiQuotaError(f"HTTP Error: {e.response.status_code} — {e.response.text}")
            else:
                raise Exception(f"HTTP Error: {e.response.status_code} — {e.response.text}")
        
        # Извлекаем изображение из ответа
        image_b64 = None
        candidates = resp_json.get("candidates", [])
        logger.info(f"Получено {len(candidates)} кандидатов от Gemini API")
        
        for i, candidate in enumerate(candidates):
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            logger.info(f"Кандидат {i}: {len(parts)} частей")
            
            for j, part in enumerate(parts):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    image_b64 = inline["data"]
                    logger.info(f"Найдено изображение в кандидате {i}, части {j}")
                    break
            if image_b64:
                break
        
        if not image_b64:
            logger.error(f"Не удалось найти изображение в ответе API: {resp_json}")
            raise Exception("Не удалось получить изображение из API")
        
        # Записываем использование API
        quota_manager.record_request(estimated_tokens)
        
        logger.info(f"Изображение успешно сгенерировано (попытка {retry_count + 1})")
        return image_b64
    
    def _extract_retry_after(self, error_data: Dict[str, Any]) -> Optional[int]:
        """
        Извлекает время ожидания из ошибки API
        
        Args:
            error_data: Данные ошибки от API
            
        Returns:
            Optional[int]: Время ожидания в секундах или None
        """
        try:
            # Ищем RetryInfo в details
            details = error_data.get("error", {}).get("details", [])
            for detail in details:
                if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                    retry_info = detail.get("retryDelay", "")
                    if retry_info.endswith("s"):
                        return int(float(retry_info[:-1]))
            
            # Ищем в message
            message = error_data.get("error", {}).get("message", "")
            if "retry in" in message.lower():
                import re
                match = re.search(r'retry in ([\d.]+)s', message.lower())
                if match:
                    return int(float(match.group(1)))
                    
        except Exception as e:
            logger.warning(f"Не удалось извлечь время ожидания: {e}")
        
        return None

# Глобальный экземпляр клиента
gemini_client = GeminiClient()

async def generate_image_with_retry(prompt: str) -> str:
    """
    Удобная функция для генерации изображения с повторными попытками
    
    Args:
        prompt: Текст для генерации изображения
        
    Returns:
        str: Base64 строка изображения или сообщение об ошибке
    """
    if not ENABLE_IMAGE_GENERATION:
        raise Exception(IMAGE_GENERATION_MESSAGE)
    
    return await gemini_client.generate_image(prompt)

def test_gemini_connection() -> bool:
    """
    Тестирует подключение к Gemini API
    
    Returns:
        bool: True если подключение успешно, False иначе
    """
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            generate_image_with_retry("Test image generation")
        )
        
        loop.close()
        logger.info("Gemini API connection test successful")
        return True
    except Exception as e:
        logger.error(f"Gemini API connection test failed: {e}")
        return False
