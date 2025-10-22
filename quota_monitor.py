#!/usr/bin/env python3
"""
Скрипт для мониторинга использования квоты Gemini API
"""

import asyncio
import time
from quota_manager import quota_manager
from gemini_client import test_gemini_connection

async def monitor_quota():
    """Мониторинг квоты в реальном времени"""
    print("🔍 Мониторинг квоты Gemini API")
    print("=" * 50)
    
    while True:
        try:
            stats = quota_manager.get_usage_stats()
            
            print(f"\n📊 Статистика использования ({time.strftime('%H:%M:%S')}):")
            print(f"   Запросов в минуту: {stats['requests_per_minute']}/{stats['limits']['requests_per_minute']}")
            print(f"   Запросов в день: {stats['requests_per_day']}/{stats['limits']['requests_per_day']}")
            print(f"   Токенов в минуту: {stats['tokens_per_minute']}/{stats['limits']['tokens_per_minute']}")
            
            # Проверяем, можно ли сделать запрос
            can_request, wait_time = quota_manager.can_make_request()
            if can_request:
                print("   ✅ Можно делать запросы")
            else:
                print(f"   ⏰ Нужно подождать {wait_time:.1f} секунд")
            
            # Проверяем подключение к API
            if test_gemini_connection():
                print("   🔗 API подключение: OK")
            else:
                print("   ❌ API подключение: ОШИБКА")
            
            await asyncio.sleep(10)  # Обновляем каждые 10 секунд
            
        except KeyboardInterrupt:
            print("\n👋 Мониторинг остановлен")
            break
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
            await asyncio.sleep(5)

def print_quota_info():
    """Выводит информацию о квоте"""
    print("📋 Информация о квоте Gemini API")
    print("=" * 50)
    
    stats = quota_manager.get_usage_stats()
    
    print(f"Лимиты (бесплатный тариф):")
    print(f"  • Запросов в минуту: {stats['limits']['requests_per_minute']}")
    print(f"  • Запросов в день: {stats['limits']['requests_per_day']}")
    print(f"  • Токенов в минуту: {stats['limits']['tokens_per_minute']}")
    
    print(f"\nТекущее использование:")
    print(f"  • Запросов в минуту: {stats['requests_per_minute']}")
    print(f"  • Запросов в день: {stats['requests_per_day']}")
    print(f"  • Токенов в минуту: {stats['tokens_per_minute']}")
    
    # Процент использования
    req_percent = (stats['requests_per_minute'] / stats['limits']['requests_per_minute']) * 100
    day_percent = (stats['requests_per_day'] / stats['limits']['requests_per_day']) * 100
    token_percent = (stats['tokens_per_minute'] / stats['limits']['tokens_per_minute']) * 100
    
    print(f"\nПроцент использования:")
    print(f"  • Запросов в минуту: {req_percent:.1f}%")
    print(f"  • Запросов в день: {day_percent:.1f}%")
    print(f"  • Токенов в минуту: {token_percent:.1f}%")
    
    if req_percent > 80 or day_percent > 80 or token_percent > 80:
        print("\n⚠️  ВНИМАНИЕ: Высокое использование квоты!")
    elif req_percent > 50 or day_percent > 50 or token_percent > 50:
        print("\n⚡ Предупреждение: Среднее использование квоты")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        asyncio.run(monitor_quota())
    else:
        print_quota_info()
