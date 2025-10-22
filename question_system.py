#!/usr/bin/env python3
"""
Система вопросов для бота
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os

logger = logging.getLogger(__name__)

class QuestionSystem:
    """Система управления вопросами бота"""
    
    def __init__(self):
        self.questions = [
            "Какие эмоции у вас вызывает эта музыка? 🎵",
            "Какой цвет ассоциируется у вас с этой мелодией? 🌈",
            "Какое настроение вы хотели бы видеть на сцене? 🎭"
        ]
        self.question_interval = 180  # 3 минуты в секундах
        self.user_states_file = "user_question_states.json"
        self.user_states = self.load_user_states()
        
    def load_user_states(self) -> Dict:
        """Загружает состояния пользователей из файла"""
        try:
            if os.path.exists(self.user_states_file):
                with open(self.user_states_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки состояний пользователей: {e}")
        return {}
    
    def save_user_states(self):
        """Сохраняет состояния пользователей в файл"""
        try:
            with open(self.user_states_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения состояний пользователей: {e}")
    
    def get_user_state(self, user_id: int) -> Dict:
        """Получает состояние пользователя"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                'current_question_index': 0,
                'last_question_time': None,
                'questions_asked_today': 0,
                'last_reset_date': datetime.now().strftime('%Y-%m-%d')
            }
        return self.user_states[user_id]
    
    def should_ask_question(self, user_id: int) -> bool:
        """Проверяет, нужно ли задать вопрос пользователю"""
        state = self.get_user_state(user_id)
        now = datetime.now()
        
        # Сбрасываем счетчик вопросов каждый день
        today = now.strftime('%Y-%m-%d')
        if state['last_reset_date'] != today:
            state['questions_asked_today'] = 0
            state['current_question_index'] = 0
            state['last_reset_date'] = today
            state['last_question_time'] = None
        
        # Если уже задали 3 вопроса, проверяем, прошло ли 3 минуты
        if state['questions_asked_today'] >= 3:
            if state['last_question_time'] is None:
                return True
            
            last_question_time = datetime.fromisoformat(state['last_question_time'])
            time_since_last = now - last_question_time
            
            # Если прошло 3 минуты, сбрасываем счетчик
            if time_since_last.total_seconds() >= self.question_interval:
                state['questions_asked_today'] = 0
                state['current_question_index'] = 0
                state['last_question_time'] = None
                self.save_user_states()
                return True
            
            return False
        
        # Если еще не задали 3 вопроса, задаем следующий
        return True
    
    def get_next_question(self, user_id: int) -> Optional[str]:
        """Получает следующий вопрос для пользователя"""
        state = self.get_user_state(user_id)
        
        # Если уже задали 3 вопроса, возвращаем None
        if state['questions_asked_today'] >= 3:
            return None
        
        # Проверяем, нужно ли задать вопрос (первый раз или прошло 3 минуты)
        if not self.should_ask_question(user_id):
            return None
        
        # Получаем текущий вопрос
        question_index = state['current_question_index']
        question = self.questions[question_index]
        
        # Обновляем состояние
        state['current_question_index'] = (question_index + 1) % len(self.questions)
        state['questions_asked_today'] += 1
        state['last_question_time'] = datetime.now().isoformat()
        
        # Сохраняем состояние
        self.save_user_states()
        
        logger.info(f"Задан вопрос {state['questions_asked_today']}/3 пользователю {user_id}: {question}")
        return question
    
    def get_question_status(self, user_id: int) -> str:
        """Получает статус вопросов для пользователя"""
        state = self.get_user_state(user_id)
        return f"Вопросов задано сегодня: {state['questions_asked_today']}/3"
    
    def reset_user_questions(self, user_id: int):
        """Сбрасывает счетчик вопросов для пользователя"""
        if user_id in self.user_states:
            self.user_states[user_id]['questions_asked_today'] = 0
            self.user_states[user_id]['current_question_index'] = 0
            self.user_states[user_id]['last_reset_date'] = datetime.now().strftime('%Y-%m-%d')
            self.save_user_states()

# Глобальный экземпляр системы вопросов
question_system = QuestionSystem()
