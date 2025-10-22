#!/usr/bin/env python3
"""
Менеджер квоты для Gemini API - оптимизирует использование API
"""

import time
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class QuotaLimits:
    """Лимиты квоты для Gemini API"""
    # Бесплатный тариф
    requests_per_minute: int = 15  # Консервативная оценка
    requests_per_day: int = 1500   # Консервативная оценка
    tokens_per_minute: int = 32000 # Консервативная оценка
    
    # Время сброса
    minute_reset_seconds: int = 60
    day_reset_seconds: int = 86400  # 24 часа

class QuotaManager:
    """Менеджер квоты для контроля использования API"""
    
    def __init__(self, limits: QuotaLimits = None):
        self.limits = limits or QuotaLimits()
        self.usage = {
            'requests_per_minute': [],
            'requests_per_day': [],
            'tokens_per_minute': []
        }
        self.last_reset = {
            'minute': time.time(),
            'day': time.time()
        }
    
    def _clean_old_usage(self):
        """Очищает старые записи использования"""
        current_time = time.time()
        
        # Очищаем записи старше минуты
        minute_ago = current_time - self.limits.minute_reset_seconds
        self.usage['requests_per_minute'] = [
            req for req in self.usage['requests_per_minute'] 
            if req['timestamp'] > minute_ago
        ]
        self.usage['tokens_per_minute'] = [
            token for token in self.usage['tokens_per_minute'] 
            if token['timestamp'] > minute_ago
        ]
        
        # Очищаем записи старше дня
        day_ago = current_time - self.limits.day_reset_seconds
        self.usage['requests_per_day'] = [
            req for req in self.usage['requests_per_day'] 
            if req['timestamp'] > day_ago
        ]
    
    def can_make_request(self, estimated_tokens: int = 1000) -> tuple[bool, Optional[float]]:
        """
        Проверяет, можно ли сделать запрос
        
        Args:
            estimated_tokens: Примерное количество токенов в запросе
            
        Returns:
            tuple: (можно_ли_делать_запрос, время_ожидания_в_секундах)
        """
        self._clean_old_usage()
        current_time = time.time()
        
        # Проверяем лимит запросов в минуту
        if len(self.usage['requests_per_minute']) >= self.limits.requests_per_minute:
            oldest_request = min(self.usage['requests_per_minute'], key=lambda x: x['timestamp'])
            wait_time = oldest_request['timestamp'] + self.limits.minute_reset_seconds - current_time
            if wait_time > 0:
                return False, wait_time
        
        # Проверяем лимит запросов в день
        if len(self.usage['requests_per_day']) >= self.limits.requests_per_day:
            oldest_request = min(self.usage['requests_per_day'], key=lambda x: x['timestamp'])
            wait_time = oldest_request['timestamp'] + self.limits.day_reset_seconds - current_time
            if wait_time > 0:
                return False, wait_time
        
        # Проверяем лимит токенов в минуту
        current_tokens = sum(token['tokens'] for token in self.usage['tokens_per_minute'])
        if current_tokens + estimated_tokens > self.limits.tokens_per_minute:
            # Находим время, когда освободится достаточно токенов
            tokens_needed = estimated_tokens - (self.limits.tokens_per_minute - current_tokens)
            tokens_by_time = sorted(self.usage['tokens_per_minute'], key=lambda x: x['timestamp'])
            
            for token_usage in tokens_by_time:
                tokens_needed -= token_usage['tokens']
                if tokens_needed <= 0:
                    wait_time = token_usage['timestamp'] + self.limits.minute_reset_seconds - current_time
                    if wait_time > 0:
                        return False, wait_time
                    break
        
        return True, None
    
    def record_request(self, tokens_used: int = 1000):
        """
        Записывает использование API
        
        Args:
            tokens_used: Количество использованных токенов
        """
        current_time = time.time()
        
        # Записываем запрос
        self.usage['requests_per_minute'].append({
            'timestamp': current_time,
            'tokens': tokens_used
        })
        self.usage['requests_per_day'].append({
            'timestamp': current_time,
            'tokens': tokens_used
        })
        
        # Записываем токены
        self.usage['tokens_per_minute'].append({
            'timestamp': current_time,
            'tokens': tokens_used
        })
        
        logger.info(f"Recorded API usage: {tokens_used} tokens")
    
    def get_usage_stats(self) -> Dict:
        """Возвращает статистику использования"""
        self._clean_old_usage()
        
        return {
            'requests_per_minute': len(self.usage['requests_per_minute']),
            'requests_per_day': len(self.usage['requests_per_day']),
            'tokens_per_minute': sum(token['tokens'] for token in self.usage['tokens_per_minute']),
            'limits': {
                'requests_per_minute': self.limits.requests_per_minute,
                'requests_per_day': self.limits.requests_per_day,
                'tokens_per_minute': self.limits.tokens_per_minute
            }
        }
    
    async def wait_if_needed(self, estimated_tokens: int = 1000) -> bool:
        """
        Ждет, если необходимо, перед выполнением запроса
        
        Args:
            estimated_tokens: Примерное количество токенов
            
        Returns:
            bool: True если можно делать запрос, False если нужно подождать
        """
        can_request, wait_time = self.can_make_request(estimated_tokens)
        
        if not can_request and wait_time:
            logger.info(f"Quota limit reached, waiting {wait_time:.1f} seconds...")
            await asyncio.sleep(wait_time)
            return True
        
        return can_request

# Глобальный экземпляр менеджера квоты
quota_manager = QuotaManager()

def optimize_prompt(prompt: str) -> str:
    """
    Оптимизирует промпт для экономии токенов
    
    Args:
        prompt: Исходный промпт
        
    Returns:
        str: Оптимизированный промпт
    """
    # Убираем лишние пробелы и переносы строк
    optimized = ' '.join(prompt.split())
    
    # Сокращаем длинные фразы
    replacements = {
        'создай художественное изображение на основе этого текста': 'создай изображение',
        'художественное изображение': 'изображение',
        'на основе этого текста': '',
        'пожалуйста': '',
        'очень': '',
        'очень красивое': 'красивое',
        'очень детальное': 'детальное'
    }
    
    for old, new in replacements.items():
        optimized = optimized.replace(old, new)
    
    # Ограничиваем длину промпта
    max_length = 500  # Максимальная длина промпта
    if len(optimized) > max_length:
        optimized = optimized[:max_length].rsplit(' ', 1)[0] + '...'
    
    return optimized

def estimate_tokens(text: str) -> int:
    """
    Примерно оценивает количество токенов в тексте
    
    Args:
        text: Текст для оценки
        
    Returns:
        int: Примерное количество токенов
    """
    # Примерная оценка: 1 токен ≈ 4 символа для русского текста
    return len(text) // 4 + 1
