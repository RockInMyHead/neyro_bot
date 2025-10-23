#!/usr/bin/env python3
"""
Быстрый тест исправлений для проверки устранения критических ошибок
"""

import asyncio
import aiohttp
import time
import json
import random

BASE_URL = "http://localhost:8000"

async def test_unicode_handling(session):
    """Тестирует обработку Unicode ошибок"""
    print("🧪 Тестируем обработку Unicode ошибок...")
    
    # Тестовые данные с проблемными символами
    test_cases = [
        "Нормальное сообщение",
        "Сообщение с эмодзи: 😀🎉🚀",
        "Сообщение с проблемными символами: \x00\x01\x02",
        "Русский текст: привет мир",
        "Смешанный текст: Hello 世界 🌍"
    ]
    
    success_count = 0
    error_count = 0
    
    for i, message in enumerate(test_cases):
        try:
            async with session.post(
                f"{BASE_URL}/api/chat",
                json={
                    'message': message,
                    'user_id': f'test_unicode_{i}',
                    'username': f'user_{i}',
                    'first_name': f'User {i}'
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status < 400:
                    success_count += 1
                    print(f"  ✅ Тест {i+1}: Успешно обработан")
                else:
                    error_count += 1
                    print(f"  ❌ Тест {i+1}: HTTP {response.status}")
        except Exception as e:
            error_count += 1
            print(f"  ❌ Тест {i+1}: Ошибка {e}")
    
    print(f"📊 Результат Unicode тестов: {success_count} успешных, {error_count} ошибок")
    return success_count, error_count

async def test_endpoint_methods(session):
    """Тестирует различные методы HTTP для endpoints"""
    print("🧪 Тестируем HTTP методы endpoints...")
    
    endpoints = [
        ('GET', '/api/chat?user_id=123'),
        ('POST', '/api/chat'),
        ('GET', '/api/mini-app/latest-message'),
        ('GET', '/api/check-chat-clear-status')
    ]
    
    success_count = 0
    error_count = 0
    
    for method, endpoint in endpoints:
        try:
            if method == 'GET':
                async with session.get(f"{BASE_URL}{endpoint}", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status < 400:
                        success_count += 1
                        print(f"  ✅ {method} {endpoint}: HTTP {response.status}")
                    else:
                        error_count += 1
                        print(f"  ❌ {method} {endpoint}: HTTP {response.status}")
            elif method == 'POST':
                async with session.post(
                    f"{BASE_URL}{endpoint}",
                    json={'message': 'test', 'user_id': 123},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status < 400:
                        success_count += 1
                        print(f"  ✅ {method} {endpoint}: HTTP {response.status}")
                    else:
                        error_count += 1
                        print(f"  ❌ {method} {endpoint}: HTTP {response.status}")
        except Exception as e:
            error_count += 1
            print(f"  ❌ {method} {endpoint}: Ошибка {e}")
    
    print(f"📊 Результат HTTP методов: {success_count} успешных, {error_count} ошибок")
    return success_count, error_count

async def test_concurrent_requests(session, num_requests=20):
    """Тестирует одновременные запросы"""
    print(f"🧪 Тестируем {num_requests} одновременных запросов...")
    
    tasks = []
    for i in range(num_requests):
        task = session.post(
            f"{BASE_URL}/api/chat",
            json={
                'message': f'Concurrent test message {i}',
                'user_id': f'concurrent_{i}',
                'username': f'user_{i}',
                'first_name': f'User {i}'
            },
            timeout=aiohttp.ClientTimeout(total=10)
        )
        tasks.append(task)
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    success_count = sum(1 for r in results if not isinstance(r, Exception) and r.status < 400)
    error_count = len(results) - success_count
    
    print(f"📊 Результат одновременных запросов: {success_count} успешных, {error_count} ошибок")
    print(f"⏱️  Время выполнения: {end_time - start_time:.2f}s")
    
    return success_count, error_count

async def main():
    """Главная функция тестирования"""
    print("🚀 БЫСТРЫЙ ТЕСТ ИСПРАВЛЕНИЙ")
    print("="*50)
    
    connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Тест 1: Unicode обработка
        unicode_success, unicode_errors = await test_unicode_handling(session)
        
        # Тест 2: HTTP методы
        method_success, method_errors = await test_endpoint_methods(session)
        
        # Тест 3: Одновременные запросы
        concurrent_success, concurrent_errors = await test_concurrent_requests(session)
        
        # Итоговый отчет
        total_success = unicode_success + method_success + concurrent_success
        total_errors = unicode_errors + method_errors + concurrent_errors
        
        print("\n" + "="*50)
        print("📊 ИТОГОВЫЙ ОТЧЕТ")
        print("="*50)
        print(f"✅ Всего успешных запросов: {total_success}")
        print(f"❌ Всего ошибок: {total_errors}")
        print(f"📈 Процент успешности: {(total_success / (total_success + total_errors) * 100):.1f}%")
        
        if total_errors == 0:
            print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        elif total_errors < 5:
            print("✅ Большинство тестов прошли успешно")
        else:
            print("⚠️  Обнаружены проблемы, требующие внимания")

if __name__ == "__main__":
    asyncio.run(main())
