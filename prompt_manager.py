"""
Менеджер базовых промтов для генерации изображений
Единый источник истины для текущего базового промта
"""

import logging
import os

logger = logging.getLogger(__name__)

# Единый источник истины для базового промта
# Используем файл для хранения состояния между процессами
PROMPT_FILE = "current_base_prompt.txt"

def _get_default_prompt():
    """Возвращает промт по умолчанию"""
    return "Мрачный кинематографичный реализм во вселенной Пиратов карибского моря; деревянные корабли с парусами и пушками; пираты; морская дымка, контраст, рим-свет; палитра: сталь/свинец воды, изумруд/бирюза, мох, мокрое дерево, патина бронзы, янтарные блики; фактуры: соль на канатах, камень, рваная парусина, брызги; широкий план, масштаб, без крупных лиц"

def _read_prompt_from_file():
    """Читает промт из файла"""
    try:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        else:
            # Создаем файл с промтом по умолчанию
            default_prompt = _get_default_prompt()
            _write_prompt_to_file(default_prompt)
            return default_prompt
    except Exception as e:
        logger.error(f"Ошибка чтения промта из файла: {e}")
        return _get_default_prompt()

def _write_prompt_to_file(prompt: str):
    """Записывает промт в файл с безопасной обработкой кодировки"""
    try:
        # Безопасная обработка промта
        if isinstance(prompt, str):
            # Удаляем недопустимые символы Unicode
            safe_prompt = prompt.encode('utf-8', errors='ignore').decode('utf-8')
        else:
            safe_prompt = str(prompt)
        
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
            f.write(safe_prompt)
    except UnicodeDecodeError as e:
        logger.error(f"UnicodeDecodeError при записи промта: {e}")
        # Записываем безопасную версию
        try:
            safe_prompt = "Базовый промт с проблемами кодировки"
            with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
                f.write(safe_prompt)
        except Exception as e2:
            logger.error(f"Критическая ошибка записи промта: {e2}")
    except Exception as e:
        logger.error(f"Ошибка записи промта в файл: {e}")

def get_current_base_prompt():
    """
    Возвращает текущий базовый промт для генерации изображений
    
    Returns:
        str: Текущий базовый промт
    """
    return _read_prompt_from_file()

def update_base_prompt(new_prompt: str):
    """
    Обновляет базовый промт для генерации изображений
    
    Args:
        new_prompt (str): Новый базовый промт
    """
    _write_prompt_to_file(new_prompt)
    logger.info(f"✅ Базовый промт обновлен: {new_prompt[:100]}...")

def get_prompt_info():
    """
    Возвращает информацию о текущем промте
    
    Returns:
        dict: Информация о промте
    """
    current_prompt = _read_prompt_from_file()
    return {
        "current_prompt": current_prompt,
        "prompt_length": len(current_prompt),
        "prompt_preview": current_prompt[:100] + "..." if len(current_prompt) > 100 else current_prompt
    }
