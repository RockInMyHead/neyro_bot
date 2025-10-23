#!/usr/bin/env python3
"""
Запускающий скрипт для системы Neuroevent
Запускает бота и админ-панель одновременно
"""

import subprocess
import sys
import time
import signal
import os
from threading import Thread

def run_bot():
    """Запускает Telegram бота"""
    print("🤖 Запуск Telegram бота...")
    try:
        subprocess.run([sys.executable, "enhanced_bot.py"], check=True)
    except KeyboardInterrupt:
        print("🛑 Остановка бота...")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

def run_admin():
    """Запускает админ-панель"""
    print("📊 Запуск админ-панели...")
    try:
        subprocess.run([sys.executable, "app_admin_only.py"], check=True)
    except KeyboardInterrupt:
        print("🛑 Остановка админ-панели...")
    except Exception as e:
        print(f"❌ Ошибка запуска админ-панели: {e}")

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    print("\n🛑 Получен сигнал завершения...")
    print("🔄 Остановка всех процессов...")
    sys.exit(0)

def main():
    """Основная функция"""
    print("🚀 Запуск системы Neuroevent...")
    print("=" * 50)
    
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Запускаем бота в отдельном потоке
        bot_thread = Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Небольшая задержка перед запуском админ-панели
        time.sleep(2)
        
        # Запускаем админ-панель в основном потоке
        run_admin()
        
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал завершения...")
        print("🔄 Остановка системы...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        print("✅ Система остановлена")

if __name__ == '__main__':
    main()
