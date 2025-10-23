#!/usr/bin/env python3
"""
Простая файловая база данных для сообщений
"""
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any

class SimpleMessageDB:
    def __init__(self, db_file="messages.json"):
        self.db_file = db_file
        self.messages = []
        self.load_messages()
    
    def load_messages(self):
        """Загружает сообщения из файла"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages = data.get('messages', [])
            except Exception as e:
                print(f"Ошибка загрузки сообщений: {e}")
                self.messages = []
    
    def save_messages(self):
        """Сохраняет сообщения в файл"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump({'messages': self.messages}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения сообщений: {e}")
    
    def add_message(self, user_id: int, username: str, first_name: str, message: str, source: str):
        """Добавляет новое сообщение с безопасной обработкой кодировки"""
        try:
            # Безопасная обработка строковых данных
            def safe_encode(text):
                if isinstance(text, str):
                    return text.encode('utf-8', errors='ignore').decode('utf-8')
                return str(text)
            
            message_data = {
                'user_id': user_id,
                'username': safe_encode(username),
                'first_name': safe_encode(first_name),
                'message': safe_encode(message),
                'timestamp': time.time(),
                'source': safe_encode(source)
            }
            
            self.messages.append(message_data)
            self.save_messages()
            
            print(f"✅ Сообщение добавлено в БД: {safe_encode(first_name)} ({source}): {safe_encode(message)[:30]}...")
            
        except UnicodeDecodeError as e:
            print(f"❌ UnicodeDecodeError при добавлении сообщения: {e}")
            # Добавляем сообщение с безопасными значениями
            safe_message_data = {
                'user_id': user_id,
                'username': 'user',
                'first_name': 'User',
                'message': 'Message with encoding issues',
                'timestamp': time.time(),
                'source': source
            }
            self.messages.append(safe_message_data)
            self.save_messages()
        except Exception as e:
            print(f"❌ Ошибка при добавлении сообщения: {e}")
    
    def get_stats(self):
        """Возвращает статистику"""
        current_time = time.time()
        recent_threshold = current_time - 15  # 15 секунд
        
        recent_messages = [msg for msg in self.messages if msg['timestamp'] > recent_threshold]
        unique_users = len(set(msg['user_id'] for msg in self.messages))
        
        # Статистика по часам
        messages_by_hour = {}
        for msg in self.messages:
            hour = datetime.fromtimestamp(msg['timestamp']).hour
            messages_by_hour[hour] = messages_by_hour.get(hour, 0) + 1
        
        return {
            'total_messages': len(self.messages),
            'unique_users_count': unique_users,
            'recent_messages_count': len(recent_messages),
            'messages_by_hour': messages_by_hour,
            'last_reset': current_time,
            'uptime_hours': 0.1  # Примерное время работы
        }
    
    def get_messages(self, limit=50):
        """Возвращает последние сообщения"""
        return self.messages[-limit:]
    
    def get_user_messages_only(self, limit=50):
        """Возвращает только сообщения пользователей (не бота)"""
        # Фильтруем только сообщения от пользователей (source = mini_app, telegram и т.д., но не bot)
        user_messages = [msg for msg in self.messages if msg.get('source') != 'bot']
        return user_messages[-limit:]
    
    def clean_old_messages(self, max_age_seconds=20):
        """Удаляет сообщения старше указанного времени"""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds
        
        old_count = len(self.messages)
        self.messages = [msg for msg in self.messages if msg['timestamp'] > cutoff_time]
        new_count = len(self.messages)
        
        if old_count != new_count:
            self.save_messages()
            print(f"🧹 Очищено старых сообщений: {old_count - new_count} (осталось: {new_count})")
        
        return old_count - new_count
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.messages = []
        self.save_messages()
        print("🗑️ Статистика сброшена")
        return len(self.messages)
    
    def clear_all_messages(self):
        """Удаляет все сообщения из базы данных"""
        count = len(self.messages)
        self.messages = []
        self.save_messages()
        print(f"🗑️ Очищено {count} сообщений")
        return count

# Глобальный экземпляр
message_db = SimpleMessageDB()
