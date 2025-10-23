"""
Умный менеджер батчей для обработки сообщений пользователей
Профессиональная реализация с отслеживанием прогресса
"""

import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class BatchStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    MIXED = "mixed"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Message:
    id: str
    user_id: int
    username: str
    first_name: str
    content: str
    timestamp: float

@dataclass
class SmartBatch:
    id: str
    messages: List[Message]
    status: BatchStatus
    created_at: float
    mixed_text: Optional[str] = None
    image_path: Optional[str] = None
    completed_at: Optional[float] = None
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    
    @property
    def message_count(self) -> int:
        """Количество сообщений в батче"""
        return len(self.messages)

class SmartBatchManager:
    def __init__(self, data_file='smart_batch_data.json'):
        self.data_file = data_file
        self.messages: List[Message] = []
        self.batches: List[SmartBatch] = []
        self.current_batch_index = 0
        self.is_processing = False
        self.processed_message_ids: set = set()  # NEW: Отслеживание обработанных сообщений
        
        # Загружаем данные из файла при инициализации
        self._load_from_file()
        
        logger.info("🚀 SmartBatchManager инициализирован")
    
    def _save_to_file(self):
        """Сохранить данные в файл"""
        try:
            import json
            data = {
                'messages': [
                    {
                        'id': msg.id,
                        'user_id': msg.user_id,
                        'username': msg.username,
                        'first_name': msg.first_name,
                        'content': msg.content,
                        'timestamp': msg.timestamp
                    }
                    for msg in self.messages
                ],
                'batches': [
                    {
                        'id': batch.id,
                        'messages': [
                            {
                                'id': msg.id,
                                'user_id': msg.user_id,
                                'username': msg.username,
                                'first_name': msg.first_name,
                                'content': msg.content,
                                'timestamp': msg.timestamp
                            }
                            for msg in batch.messages
                        ],
                        'status': batch.status.value,
                        'created_at': batch.created_at,
                        'mixed_text': batch.mixed_text,
                        'image_path': batch.image_path,
                        'completed_at': batch.completed_at,
                        'processing_time': batch.processing_time,
                        'error_message': batch.error_message
                    }
                    for batch in self.batches
                ],
                'processed_message_ids': list(self.processed_message_ids)
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
    
    def _load_from_file(self):
        """Загрузить данные из файла"""
        try:
            import json
            import os
            
            if not os.path.exists(self.data_file):
                return
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Загружаем сообщения
            self.messages = [
                Message(
                    id=msg['id'],
                    user_id=msg['user_id'],
                    username=msg['username'],
                    first_name=msg['first_name'],
                    content=msg['content'],
                    timestamp=msg['timestamp']
                )
                for msg in data.get('messages', [])
            ]
            
            # Загружаем батчи
            self.batches = [
                SmartBatch(
                    id=batch['id'],
                    messages=[
                        Message(
                            id=msg['id'],
                            user_id=msg['user_id'],
                            username=msg['username'],
                            first_name=msg['first_name'],
                            content=msg['content'],
                            timestamp=msg['timestamp']
                        )
                        for msg in batch['messages']
                    ],
                    status=BatchStatus(batch['status']),
                    created_at=batch['created_at'],
                    mixed_text=batch.get('mixed_text'),
                    image_path=batch.get('image_path'),
                    completed_at=batch.get('completed_at'),
                    processing_time=batch.get('processing_time'),
                    error_message=batch.get('error_message')
                )
                for batch in data.get('batches', [])
            ]
            
            # Загружаем обработанные ID
            self.processed_message_ids = set(data.get('processed_message_ids', []))
            
            logger.info(f"📂 Загружено из файла: {len(self.messages)} сообщений, {len(self.batches)} батчей")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных: {e}")

    def add_message(self, user_id: int, username: str, first_name: str, content: str) -> str:
        """Добавить новое сообщение"""
        message = Message(
            id=str(uuid.uuid4()),
            user_id=user_id,
            username=username or f"user_{user_id}",
            first_name=first_name or "Unknown",
            content=content,
            timestamp=time.time()
        )

        # Проверяем, не было ли это сообщение уже обработано (дополнительная защита)
        if message.id in self.processed_message_ids:
            logger.warning(f"⚠️ Попытка добавить уже обработанное сообщение: {message.id}")
            return message.id

        self.messages.append(message)
        logger.info(f"✅ Сообщение добавлено: {message.id} от {first_name} ({len(self.messages)} всего)")
        
        # Сохраняем данные в файл
        self._save_to_file()

        return message.id

    def create_batches(self) -> List[SmartBatch]:
        """Создать батчи из накопленных сообщений"""
        if not self.messages:
            logger.info("📝 Нет сообщений для создания батчей")
            return []

        # Создаем снимок сообщений для обработки
        messages_snapshot = self.messages.copy()
        total_messages = len(messages_snapshot)
        
        logger.info(f"📊 Создание батчей из {total_messages} сообщений")

        created_batches = []
        
        if total_messages >= 10:
            # Создаем 10 пропорциональных батчей
            batch_size = total_messages // 10
            remainder = total_messages % 10
            
            logger.info(f"📊 Создание 10 пропорциональных батчей (размер: {batch_size}, остаток: {remainder})")
            
            start_idx = 0
            for i in range(10):
                # Добавляем остаток к первым батчам
                current_batch_size = batch_size + (1 if i < remainder else 0)
                end_idx = start_idx + current_batch_size
                
                batch_messages = messages_snapshot[start_idx:end_idx]
                
                batch = SmartBatch(
                    id=str(uuid.uuid4()),
                    messages=batch_messages,
                    status=BatchStatus.PENDING,
                    created_at=time.time()
                )
                
                created_batches.append(batch)
                logger.info(f"  ✅ Батч {i+1}/10: {len(batch_messages)} сообщений от {batch_messages[0].first_name}")
                start_idx = end_idx
        else:
            # Создаем батчи по 1 сообщению
            logger.info(f"📊 Создание {total_messages} батчей по 1 сообщению")
            
            for i, message in enumerate(messages_snapshot):
                batch = SmartBatch(
                    id=str(uuid.uuid4()),
                    messages=[message],
                    status=BatchStatus.PENDING,
                    created_at=time.time()
                )
                
                created_batches.append(batch)
                logger.info(f"  ✅ Батч {i+1}/{total_messages}: 1 сообщение от {message.first_name}")

        # Добавляем созданные батчи в очередь
        self.batches.extend(created_batches)

        # Отмечаем все сообщения из батчей как обработанные
        for message in messages_snapshot:
            self.processed_message_ids.add(message.id)

        # ВАЖНО: Очищаем использованные сообщения СРАЗУ после создания батчей
        # Это предотвращает повторное использование тех же сообщений
        self.messages.clear()
        logger.info(f"🗑️ Очищено {total_messages} обработанных сообщений из очереди")
        logger.info(f"📝 Всего отслеживается {len(self.processed_message_ids)} обработанных сообщений")

        # Сохраняем данные в файл после создания батчей
        self._save_to_file()

        logger.info(f"🎉 Создано {len(created_batches)} батчей для обработки")
        return created_batches

    def get_next_batch(self) -> Optional[SmartBatch]:
        """Получить следующий батч для обработки"""
        pending_batches = [b for b in self.batches if b.status == BatchStatus.PENDING]
        
        if not pending_batches:
            return None
            
        # Возвращаем первый ожидающий батч
        return pending_batches[0]

    def update_batch_status(self, batch_id: str, status: BatchStatus, **kwargs):
        """Обновить статус батча"""
        for batch in self.batches:
            if batch.id == batch_id:
                batch.status = status
                
                # Обновляем дополнительные поля
                for key, value in kwargs.items():
                    if hasattr(batch, key):
                        setattr(batch, key, value)
                
                logger.info(f"📝 Батч {batch_id} обновлен: {status.value}")
                
                # Сохраняем данные в файл после обновления
                self._save_to_file()
                break

    def get_statistics(self) -> Dict:
        """Получить статистику"""
        stats = {
            'total_messages': len(self.messages),
            'total_batches': len(self.batches),
            'pending_batches': len([b for b in self.batches if b.status == BatchStatus.PENDING]),
            'processing_batches': len([b for b in self.batches if b.status == BatchStatus.PROCESSING]),
            'mixed_batches': len([b for b in self.batches if b.status == BatchStatus.MIXED]),
            'generating_batches': len([b for b in self.batches if b.status == BatchStatus.GENERATING]),
            'completed_batches': len([b for b in self.batches if b.status == BatchStatus.COMPLETED]),
            'failed_batches': len([b for b in self.batches if b.status == BatchStatus.FAILED]),
            'current_batch_index': self.current_batch_index,
            'is_processing': self.is_processing
        }
        return stats

    def get_all_batches_info(self) -> List[Dict]:
        """Получить информацию о всех батчах"""
        batches_info = []
        
        for batch in self.batches:
            batch_info = {
                'id': batch.id,
                'status': batch.status.value,
                'message_count': len(batch.messages),
                'created_at': batch.created_at,
                'mixed_text': batch.mixed_text,
                'image_path': batch.image_path,
                'completed_at': batch.completed_at,
                'processing_time': batch.processing_time,
                'error_message': batch.error_message
            }
            batches_info.append(batch_info)
        
        return batches_info

    def clear_all_batches(self) -> int:
        """Очистить все батчи"""
        before_count = len(self.batches)
        self.batches = []
        self.current_batch_index = 0
        self.processed_message_ids.clear()
        logger.info(f"🗑️ Очищено {before_count} батчей")
        return before_count

    def clear_completed_batches(self, older_than_hours: int = 1) -> int:
        """Очистить старые завершенные батчи"""
        cutoff_time = time.time() - (older_than_hours * 3600)
        before_count = len(self.batches)
        
        # Собираем ID сообщений из удаляемых батчей для очистки
        removed_message_ids = set()
        for batch in self.batches:
            if batch.status in [BatchStatus.COMPLETED, BatchStatus.FAILED] and batch.created_at < cutoff_time:
                for message in batch.messages:
                    removed_message_ids.add(message.id)

        self.batches = [
            batch for batch in self.batches
            if not (batch.status in [BatchStatus.COMPLETED, BatchStatus.FAILED]
                   and batch.created_at < cutoff_time)
        ]
        after_count = len(self.batches)

        # Очищаем ID старых обработанных сообщений
        if removed_message_ids:
            self.processed_message_ids -= removed_message_ids
            logger.info(f"🧹 Очищено {len(removed_message_ids)} ID старых обработанных сообщений")

        removed_count = before_count - after_count
        if removed_count > 0:
            logger.info(f"🧹 Удалено {removed_count} старых батчей")

        return removed_count

    def reset(self):
        """Полный сброс менеджера"""
        self.messages.clear()
        self.batches.clear()
        self.processed_message_ids.clear()  # NEW: Clear processed message IDs
        self.current_batch_index = 0
        self.is_processing = False
        logger.info("🔄 SmartBatchManager сброшен")

# Создаем глобальный экземпляр
smart_batch_manager = SmartBatchManager()