"""
Менеджер очереди запросов на генерацию изображений
"""
import time
import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass
from simple_message_db import message_db

@dataclass
class ImageRequest:
    """Запрос на генерацию изображения"""
    id: str
    user_id: int
    username: str
    first_name: str
    message: str
    timestamp: float
    status: str = "pending"  # pending, processing, completed, failed
    batch_id: Optional[str] = None
    generated_image_path: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class Batch:
    """Батч запросов для обработки"""
    id: str
    requests: List[ImageRequest]
    created_at: float
    status: str = "pending"  # pending, processing, completed, failed
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    mixed_text: Optional[str] = None
    generated_images: Optional[List[str]] = None  # Пути к сгенерированным изображениям

class ImageQueueManager:
    """Менеджер очереди запросов на генерацию изображений"""
    
    def __init__(self):
        self.requests: List[ImageRequest] = []
        self.batches: List[Batch] = []
        self.current_batch: Optional[Batch] = None
        self.batch_size = 14  # Размер батча
        
    def add_request(self, user_id: int, username: str, first_name: str, message: str) -> str:
        """Добавляет новый запрос в очередь"""
        request_id = str(uuid.uuid4())
        request = ImageRequest(
            id=request_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
            message=message,
            timestamp=time.time()
        )
        
        self.requests.append(request)
        print(f"📝 Добавлен запрос в очередь: {request_id} от {first_name}")
        
        # Автоматически создаем батч если накопилось достаточно запросов
        self._try_create_batch()
        
        return request_id
    
    def _try_create_batch(self):
        """Пытается создать новый батч из ожидающих запросов"""
        pending_requests = [r for r in self.requests if r.status == "pending"]
        
        if len(pending_requests) >= self.batch_size:
            # Создаем батч из первых 14 запросов
            batch_requests = pending_requests[:self.batch_size]
            
            batch_id = str(uuid.uuid4())
            batch = Batch(
                id=batch_id,
                requests=batch_requests,
                created_at=time.time()
            )
            
            # Обновляем статус запросов
            for request in batch_requests:
                request.batch_id = batch_id
                request.status = "in_batch"
            
            self.batches.append(batch)
            print(f"🎯 Создан батч {batch_id} с {len(batch_requests)} запросами")
    
    def get_next_batch(self) -> Optional[Batch]:
        """Возвращает следующий батч для обработки"""
        if self.current_batch and self.current_batch.status == "processing":
            return None  # Текущий батч еще обрабатывается
        
        # Ищем следующий pending батч
        for batch in self.batches:
            if batch.status == "pending":
                self.current_batch = batch
                return batch
        
        return None
    
    def start_batch_processing(self, batch_id: str):
        """Начинает обработку батча"""
        batch = self._find_batch(batch_id)
        if batch:
            batch.status = "processing"
            batch.started_at = time.time()
            print(f"🚀 Начата обработка батча {batch_id}")
    
    def complete_batch(self, batch_id: str, mixed_text: str, generated_images: List[str]):
        """Завершает обработку батча"""
        batch = self._find_batch(batch_id)
        if batch:
            batch.status = "completed"
            batch.completed_at = time.time()
            batch.mixed_text = mixed_text
            batch.generated_images = generated_images
            
            # Обновляем статус всех запросов в батче
            for request in batch.requests:
                request.status = "completed"
            
            print(f"✅ Батч {batch_id} завершен. Сгенерировано {len(generated_images)} изображений")
    
    def fail_batch(self, batch_id: str, error_message: str):
        """Помечает батч как неудачный"""
        batch = self._find_batch(batch_id)
        if batch:
            batch.status = "failed"
            batch.completed_at = time.time()
            
            # Обновляем статус всех запросов в батче
            for request in batch.requests:
                request.status = "failed"
                request.error_message = error_message
            
            print(f"❌ Батч {batch_id} провален: {error_message}")
    
    def _find_batch(self, batch_id: str) -> Optional[Batch]:
        """Находит батч по ID"""
        for batch in self.batches:
            if batch.id == batch_id:
                return batch
        return None
    
    def get_queue_stats(self) -> Dict:
        """Возвращает статистику очереди"""
        total_requests = len(self.requests)
        pending_requests = len([r for r in self.requests if r.status == "pending"])
        in_batch_requests = len([r for r in self.requests if r.status == "in_batch"])
        processing_requests = len([r for r in self.requests if r.status == "processing"])
        completed_requests = len([r for r in self.requests if r.status == "completed"])
        failed_requests = len([r for r in self.requests if r.status == "failed"])
        
        total_batches = len(self.batches)
        pending_batches = len([b for b in self.batches if b.status == "pending"])
        processing_batches = len([b for b in self.batches if b.status == "processing"])
        completed_batches = len([b for b in self.batches if b.status == "completed"])
        failed_batches = len([b for b in self.batches if b.status == "failed"])
        
        return {
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "in_batch_requests": in_batch_requests,
            "processing_requests": processing_requests,
            "completed_requests": completed_requests,
            "failed_requests": failed_requests,
            "total_batches": total_batches,
            "pending_batches": pending_batches,
            "processing_batches": processing_batches,
            "completed_batches": completed_batches,
            "failed_batches": failed_batches,
            "current_batch_id": self.current_batch.id if self.current_batch else None,
            "batch_size": self.batch_size
        }
    
    def get_current_batch(self) -> Optional[Batch]:
        """Возвращает текущий обрабатываемый батч"""
        return self.current_batch
    
    def get_batch_requests(self, batch_id: str) -> List[ImageRequest]:
        """Возвращает запросы из батча"""
        batch = self._find_batch(batch_id)
        return batch.requests if batch else []
    
    def clear_completed_requests(self, older_than_hours: int = 24):
        """Очищает завершенные запросы старше указанного времени"""
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        # Удаляем старые завершенные запросы
        old_requests = [r for r in self.requests if r.status in ["completed", "failed"] and r.timestamp < cutoff_time]
        self.requests = [r for r in self.requests if r not in old_requests]
        
        # Удаляем старые завершенные батчи
        old_batches = [b for b in self.batches if b.status in ["completed", "failed"] and b.created_at < cutoff_time]
        self.batches = [b for b in self.batches if b not in old_batches]
        
        print(f"🧹 Очищено {len(old_requests)} старых запросов и {len(old_batches)} старых батчей")
        return len(old_requests) + len(old_batches)

# Глобальный экземпляр менеджера очереди
queue_manager = ImageQueueManager()
