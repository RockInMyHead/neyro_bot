#!/usr/bin/env python3
"""
Фильтр контента для генерации изображений
"""

import re
import logging

logger = logging.getLogger(__name__)

class ContentFilter:
    """Фильтр некультурного контента"""
    
    def __init__(self):
        # Список запрещенных слов и фраз
        self.forbidden_words = [
            # Нецензурная лексика
            'гавно', 'ссанина', 'говно', 'дерьмо', 'пизда', 'хуй', 'блядь', 'сука', 'ебать',
            'fuck', 'shit', 'damn', 'bitch', 'asshole', 'crap', 'piss', 'dick', 'cock',
            
            # Оскорбления
            'идиот', 'дурак', 'тупой', 'дебил', 'кретин', 'мудак', 'сволочь', 'подонок',
            'idiot', 'stupid', 'dumb', 'moron', 'bastard', 'scum', 'loser',
            
            # Насилие и агрессия
            'убийство', 'смерть', 'кровь', 'кровавая', 'бойня', 'насилие', 'война', 'бомба', 'оружие',
            'murder', 'death', 'blood', 'violence', 'war', 'bomb', 'weapon',
            
            # Непристойности
            'порно', 'порнография', 'секс', 'голый', 'обнаженный', 'интим', 'эротика',
            'porn', 'sex', 'naked', 'nude', 'intimate', 'erotic',
            
            # Экстремизм
            'террор', 'экстремизм', 'расизм', 'фашизм', 'нацизм',
            'terror', 'extremism', 'racism', 'fascism', 'nazism'
        ]
        
        # Паттерны для более сложных проверок
        self.forbidden_patterns = [
            r'\b(убить|убийство|смерть)\b',
            r'\b(кровь|кровавый)\b',
            r'\b(насилие|насильственный)\b',
            r'\b(война|военный|вооружение)\b',
            r'\b(террор|террорист)\b',
            r'\b(экстремист|экстремизм)\b',
            r'\b(расист|расизм)\b',
            r'\b(фашист|фашизм)\b',
            r'\b(нацист|нацизм)\b',
            r'\b(порно|порнография)\b',
            r'\b(голый|обнаженный|ню)\b',
            r'\b(интим|эротика)\b'
        ]
        
        # Слова-исключения (могут быть в культурном контексте)
        self.exceptions = [
            'история', 'исторический', 'книга', 'фильм', 'искусство', 'музей',
            'медицина', 'медицинский', 'медицинская', 'медицинские', 'лечение', 'врач', 'больница',
            'history', 'historical', 'book', 'movie', 'art', 'museum',
            'medicine', 'medical', 'treatment', 'doctor', 'hospital'
        ]
    
    def is_safe_content(self, text: str) -> tuple[bool, str]:
        """
        Проверяет безопасность контента
        
        Args:
            text: Текст для проверки
            
        Returns:
            tuple: (is_safe, reason) - безопасен ли контент и причина блокировки
        """
        if not text or not isinstance(text, str):
            return True, ""
        
        text_lower = text.lower()
        
        # Проверка на запрещенные слова
        for word in self.forbidden_words:
            if word in text_lower:
                # Проверяем, не является ли это исключением
                if not self._is_exception(text_lower, word):
                    logger.warning(f"Запрещенное слово обнаружено: {word}")
                    return False, f"Обнаружено запрещенное слово: {word}"
        
        # Проверка на запрещенные паттерны
        for pattern in self.forbidden_patterns:
            if re.search(pattern, text_lower):
                # Проверяем контекст
                if not self._is_cultural_context(text_lower, pattern):
                    logger.warning(f"Запрещенный паттерн обнаружен: {pattern}")
                    return False, f"Обнаружен запрещенный контент: {pattern}"
        
        return True, ""
    
    def _is_exception(self, text: str, word: str) -> bool:
        """Проверяет, является ли слово исключением в культурном контексте"""
        for exception in self.exceptions:
            if exception in text:
                return True
        return False
    
    def _is_cultural_context(self, text: str, pattern: str) -> bool:
        """Проверяет, находится ли запрещенный паттерн в культурном контексте"""
        cultural_contexts = [
            'история', 'исторический', 'книга', 'фильм', 'искусство', 'музей',
            'медицина', 'медицинский', 'медицинская', 'медицинские', 'лечение', 'врач', 'больница',
            'образование', 'учебник', 'лекция', 'курс',
            'history', 'historical', 'book', 'movie', 'art', 'museum',
            'medicine', 'medical', 'treatment', 'doctor', 'hospital',
            'education', 'textbook', 'lecture', 'course'
        ]
        
        for context in cultural_contexts:
            if context in text:
                return True
        return False
    
    def sanitize_prompt(self, prompt: str) -> str:
        """
        Очищает промпт от нежелательного контента
        
        Args:
            prompt: Исходный промпт
            
        Returns:
            str: Очищенный промпт
        """
        if not prompt:
            return prompt
        
        # Заменяем запрещенные слова на нейтральные
        replacements = {
            'гавно': 'отходы',
            'говно': 'отходы', 
            'дерьмо': 'отходы',
            'пизда': 'женский орган',
            'хуй': 'мужской орган',
            'блядь': 'женщина',
            'сука': 'собака',
            'ебать': 'заниматься',
            'fuck': 'engage',
            'shit': 'waste',
            'damn': 'darn',
            'bitch': 'woman',
            'asshole': 'person',
            'crap': 'waste',
            'piss': 'urine',
            'dick': 'penis',
            'cock': 'rooster'
        }
        
        sanitized = prompt.lower()
        for bad_word, replacement in replacements.items():
            sanitized = sanitized.replace(bad_word, replacement)
        
        return sanitized

# Глобальный экземпляр фильтра
content_filter = ContentFilter()

def check_content_safety(text: str) -> tuple[bool, str]:
    """
    Проверяет безопасность контента для генерации изображений
    
    Args:
        text: Текст для проверки
        
    Returns:
        tuple: (is_safe, reason) - безопасен ли контент и причина блокировки
    """
    return content_filter.is_safe_content(text)

def sanitize_image_prompt(prompt: str) -> str:
    """
    Очищает промпт для генерации изображений
    
    Args:
        prompt: Исходный промпт
        
    Returns:
        str: Очищенный промпт
    """
    return content_filter.sanitize_prompt(prompt)
