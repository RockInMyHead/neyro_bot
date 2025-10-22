#!/usr/bin/env python3
"""
Скрипт для управления генерацией изображений
"""

import os
import sys

def update_config_file(enable: bool):
    """Обновляет файл config.py"""
    config_path = "config.py"
    
    if not os.path.exists(config_path):
        print(f"❌ Файл {config_path} не найден")
        return False
    
    # Читаем файл
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Обновляем настройку
    old_line = f"ENABLE_IMAGE_GENERATION = {not enable}"
    new_line = f"ENABLE_IMAGE_GENERATION = {enable}"
    
    if old_line in content:
        content = content.replace(old_line, new_line)
        
        # Записываем обратно
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Обновлен {config_path}: ENABLE_IMAGE_GENERATION = {enable}")
        return True
    else:
        print(f"⚠️  Настройка ENABLE_IMAGE_GENERATION не найдена в {config_path}")
        return False

def update_nanabanana_file(enable: bool):
    """Обновляет файл NanaBanana/app.py"""
    app_path = "NanaBanana/app.py"
    
    if not os.path.exists(app_path):
        print(f"❌ Файл {app_path} не найден")
        return False
    
    # Читаем файл
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Обновляем настройку
    old_line = f"ENABLE_IMAGE_GENERATION = {not enable}"
    new_line = f"ENABLE_IMAGE_GENERATION = {enable}"
    
    if old_line in content:
        content = content.replace(old_line, new_line)
        
        # Записываем обратно
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Обновлен {app_path}: ENABLE_IMAGE_GENERATION = {enable}")
        return True
    else:
        print(f"⚠️  Настройка ENABLE_IMAGE_GENERATION не найдена в {app_path}")
        return False

def check_status():
    """Проверяет текущий статус"""
    try:
        from config import ENABLE_IMAGE_GENERATION, IMAGE_GENERATION_MESSAGE
        
        print("📊 Текущий статус генерации изображений:")
        print(f"   Включена: {'✅ Да' if ENABLE_IMAGE_GENERATION else '❌ Нет'}")
        print(f"   Сообщение: {IMAGE_GENERATION_MESSAGE}")
        
        return ENABLE_IMAGE_GENERATION
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return None

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("🔧 Управление генерацией изображений")
        print("=" * 50)
        print("Использование:")
        print("  python manage_image_generation.py status    # Проверить статус")
        print("  python manage_image_generation.py enable    # Включить генерацию")
        print("  python manage_image_generation.py disable   # Отключить генерацию")
        print("  python manage_image_generation.py toggle    # Переключить статус")
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        check_status()
    
    elif command == "enable":
        print("🔄 Включаем генерацию изображений...")
        success1 = update_config_file(True)
        success2 = update_nanabanana_file(True)
        
        if success1 and success2:
            print("✅ Генерация изображений включена!")
        else:
            print("⚠️  Частично обновлено. Проверьте файлы вручную.")
    
    elif command == "disable":
        print("🔄 Отключаем генерацию изображений...")
        success1 = update_config_file(False)
        success2 = update_nanabanana_file(False)
        
        if success1 and success2:
            print("✅ Генерация изображений отключена!")
        else:
            print("⚠️  Частично обновлено. Проверьте файлы вручную.")
    
    elif command == "toggle":
        current_status = check_status()
        if current_status is None:
            print("❌ Не удалось определить текущий статус")
            return
        
        new_status = not current_status
        print(f"🔄 Переключаем с {'включено' if current_status else 'отключено'} на {'включено' if new_status else 'отключено'}...")
        
        success1 = update_config_file(new_status)
        success2 = update_nanabanana_file(new_status)
        
        if success1 and success2:
            print(f"✅ Генерация изображений {'включена' if new_status else 'отключена'}!")
        else:
            print("⚠️  Частично обновлено. Проверьте файлы вручную.")
    
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("Доступные команды: status, enable, disable, toggle")

if __name__ == "__main__":
    main()
