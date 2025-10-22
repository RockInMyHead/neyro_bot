"""
Система сбора и анализа сообщений пользователей
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
from openai_client import get_openai_response
import logging

logger = logging.getLogger(__name__)

@dataclass
class UserMessage:
    """Структура сообщения пользователя"""
    user_id: int
    username: str
    first_name: str
    message: str
    timestamp: float
    source: str  # 'telegram' или 'mini_app'

class MessageCollector:
    """Класс для сбора и анализа сообщений пользователей"""
    
    def __init__(self):
        self.messages: List[UserMessage] = []
        self.stats = {
            'total_messages': 0,
            'unique_users': set(),
            'messages_by_hour': {},
            'last_reset': time.time()
        }
        self.is_running = False
        self.task = None
    
    def add_message(self, user_id: int, username: str, first_name: str, 
                   message: str, source: str = 'telegram'):
        """Добавляет сообщение в коллекцию"""
        print(f"🔍 MessageCollector.add_message вызван: user_id={user_id}, message='{message[:30]}...'")
        
        user_message = UserMessage(
            user_id=user_id,
            username=username or f"user_{user_id}",
            first_name=first_name or "Unknown",
            message=message,
            timestamp=time.time(),
            source=source
        )
        
        self.messages.append(user_message)
        self.stats['total_messages'] += 1
        self.stats['unique_users'].add(user_id)
        
        # Статистика по часам
        hour = datetime.fromtimestamp(user_message.timestamp).hour
        self.stats['messages_by_hour'][hour] = self.stats['messages_by_hour'].get(hour, 0) + 1
        
        print(f"✅ Сообщение добавлено! Всего сообщений: {self.stats['total_messages']}")
        
        # Ограничиваем количество сообщений в памяти
        if len(self.messages) > 1000:
            self.messages = self.messages[-500:]  # Оставляем последние 500
        
        logger.info(f"📨 Сообщение добавлено: {first_name} ({user_id}): {message[:50]}...")
    
    def get_recent_messages(self, minutes: int = 15) -> List[UserMessage]:
        """Получает сообщения за последние N минут"""
        cutoff_time = time.time() - (minutes * 60)
        return [msg for msg in self.messages if msg.timestamp >= cutoff_time]
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        recent_messages = self.get_recent_messages(15)
        
        return {
            'total_messages': self.stats['total_messages'],
            'unique_users_count': len(self.stats['unique_users']),
            'recent_messages_count': len(recent_messages),
            'messages_by_hour': self.stats['messages_by_hour'],
            'last_reset': self.stats['last_reset'],
            'uptime_hours': (time.time() - self.stats['last_reset']) / 3600
        }
    
    async def generate_mixed_text(self) -> str:
        """Генерирует миксированный текст из всех сообщений за последние 15 минут"""
        recent_messages = self.get_recent_messages(15)
        
        if not recent_messages:
            return "Нет сообщений за последние 15 минут"
        
        # Собираем все сообщения в один текст
        all_messages = [msg.message for msg in recent_messages]
        combined_text = " ".join(all_messages)
        
        if len(combined_text) > 2000:  # Ограничиваем длину
            combined_text = combined_text[:2000] + "..."
        
        try:
            # Отправляем в LLM для создания миксированного текста
            prompt = f"Создай одно предложение, объединяющее смысл всех этих сообщений пользователей: {combined_text}"
            mixed_text = await get_openai_response(prompt)
            
            logger.info(f"🎭 Сгенерирован миксированный текст: {mixed_text[:100]}...")
            return mixed_text
            
        except Exception as e:
            logger.error(f"Ошибка генерации миксированного текста: {e}")
            return f"Ошибка генерации: {str(e)}"
    
    async def start_periodic_analysis(self, callback_func=None):
        """Запускает периодический анализ сообщений"""
        self.is_running = True
        logger.info("🔄 Запуск периодического анализа сообщений...")
        
        while self.is_running:
            try:
                # Генерируем миксированный текст
                mixed_text = await self.generate_mixed_text()
                
                # Вызываем callback функцию если она есть
                if callback_func:
                    await callback_func(mixed_text, self.get_stats())
                
                # Ждем 15 секунд
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Ошибка в периодическом анализе: {e}")
                await asyncio.sleep(5)  # Короткая пауза при ошибке
    
    def stop_periodic_analysis(self):
        """Останавливает периодический анализ"""
        self.is_running = False
        logger.info("⏹️ Остановка периодического анализа сообщений")
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.stats = {
            'total_messages': 0,
            'unique_users': set(),
            'messages_by_hour': {},
            'last_reset': time.time()
        }
        self.messages = []
        logger.info("🔄 Статистика сброшена")

# Глобальный экземпляр коллектора (синглтон)
_message_collector_instance = None

def get_message_collector():
    """Получает единственный экземпляр MessageCollector (синглтон)"""
    global _message_collector_instance
    if _message_collector_instance is None:
        _message_collector_instance = MessageCollector()
    return _message_collector_instance

# Создаем глобальную ссылку для обратной совместимости
message_collector = get_message_collector()
