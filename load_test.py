#!/usr/bin/env python3
"""
Комплексное нагрузочное тестирование системы Neuroevent Bot
Тестирование на 1000 одновременных пользователей
"""

import asyncio
import aiohttp
import time
import json
import random
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading
import sys
import os

# Конфигурация тестирования
BASE_URL = "https://neuroevent.ru"
TEST_USERS = 1000
CONCURRENT_REQUESTS = 50
TEST_DURATION = 300  # 5 минут
REQUEST_TIMEOUT = 30

class LoadTester:
    def __init__(self):
        self.results = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'errors': {},
            'endpoints': {},
            'start_time': None,
            'end_time': None
        }
        self.lock = threading.Lock()
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    async def make_request(self, session, method, url, data=None, headers=None):
        """Выполняет HTTP запрос и собирает метрики"""
        start_time = time.time()
        
        try:
            async with session.request(
                method, url, 
                json=data, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                response_time = time.time() - start_time
                
                # Читаем содержимое ответа
                content = await response.text()
                
                with self.lock:
                    self.results['total_requests'] += 1
                    self.results['response_times'].append(response_time)
                    
                    if response.status < 400:
                        self.results['successful_requests'] += 1
                    else:
                        self.results['failed_requests'] += 1
                        error_key = f"HTTP_{response.status}"
                        self.results['errors'][error_key] = self.results['errors'].get(error_key, 0) + 1
                    
                    # Статистика по endpoint
                    endpoint = url.replace(BASE_URL, '')
                    if endpoint not in self.results['endpoints']:
                        self.results['endpoints'][endpoint] = {
                            'requests': 0,
                            'success': 0,
                            'errors': 0,
                            'avg_time': 0,
                            'times': []
                        }
                    
                    ep = self.results['endpoints'][endpoint]
                    ep['requests'] += 1
                    ep['times'].append(response_time)
                    ep['avg_time'] = statistics.mean(ep['times'])
                    
                    if response.status < 400:
                        ep['success'] += 1
                    else:
                        ep['errors'] += 1
                
                return {
                    'status': response.status,
                    'response_time': response_time,
                    'content_length': len(content),
                    'success': response.status < 400
                }
                
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            with self.lock:
                self.results['total_requests'] += 1
                self.results['failed_requests'] += 1
                self.results['errors']['TIMEOUT'] = self.results['errors'].get('TIMEOUT', 0) + 1
                self.results['response_times'].append(response_time)
            
            return {
                'status': 'TIMEOUT',
                'response_time': response_time,
                'content_length': 0,
                'success': False
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            with self.lock:
                self.results['total_requests'] += 1
                self.results['failed_requests'] += 1
                error_key = f"EXCEPTION_{type(e).__name__}"
                self.results['errors'][error_key] = self.results['errors'].get(error_key, 0) + 1
                self.results['response_times'].append(response_time)
            
            return {
                'status': 'ERROR',
                'response_time': response_time,
                'content_length': 0,
                'success': False,
                'error': str(e)
            }
    
    async def test_mini_app_endpoints(self, session, user_id):
        """Тестирует endpoints Mini App"""
        endpoints = [
            ('GET', '/api/mini-app/latest-message'),
            ('GET', '/api/check-chat-clear-status'),
            ('POST', '/api/message', {'message': f'Test message from user {user_id}', 'user_id': f'user_{user_id}'}),
            ('GET', '/api/chat', {'user_id': f'user_{user_id}'})
        ]
        
        tasks = []
        for method, endpoint, *data in endpoints:
            url = f"{BASE_URL}{endpoint}"
            data = data[0] if data else None
            tasks.append(self.make_request(session, method, url, data))
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def test_admin_endpoints(self, session, admin_id):
        """Тестирует endpoints Admin Panel"""
        endpoints = [
            ('GET', '/api/admin/check-auth'),
            ('GET', '/api/admin/smart-batches/stats'),
            ('GET', '/api/admin/smart-batches/list'),
            ('GET', '/api/admin/smart-batches/current-mixed-text'),
            ('GET', '/api/admin/smart-batches/images'),
            ('GET', '/api/admin/messages')
        ]
        
        tasks = []
        for method, endpoint in endpoints:
            url = f"{BASE_URL}{endpoint}"
            tasks.append(self.make_request(session, method, url))
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def test_static_resources(self, session, user_id):
        """Тестирует статические ресурсы"""
        static_files = [
            '/static/mini_app/mini_app.css',
            '/static/mini_app/mini_app.js',
            '/static/mini_app/neuroevent_logo.png',
            '/static/admin_app/admin_mini_app.css',
            '/static/admin_app/admin_mini_app.js'
        ]
        
        tasks = []
        for file_path in static_files:
            url = f"{BASE_URL}{file_path}"
            tasks.append(self.make_request(session, 'GET', url))
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def simulate_user_session(self, session, user_id, user_type='mini_app'):
        """Симулирует сессию пользователя"""
        try:
            if user_type == 'mini_app':
                # Симуляция пользователя Mini App
                await self.test_mini_app_endpoints(session, user_id)
                await asyncio.sleep(random.uniform(0.1, 0.5))  # Пауза между запросами
                await self.test_static_resources(session, user_id)
                
            elif user_type == 'admin':
                # Симуляция администратора
                await self.test_admin_endpoints(session, user_id)
                await asyncio.sleep(random.uniform(0.2, 1.0))  # Пауза между запросами
                
        except Exception as e:
            self.log(f"Ошибка в сессии пользователя {user_id}: {e}")
    
    async def run_load_test(self):
        """Запускает нагрузочное тестирование"""
        self.log(f"🚀 Начинаем нагрузочное тестирование для {TEST_USERS} пользователей")
        self.log(f"🎯 Целевой сервер: {BASE_URL}")
        self.log(f"⏱️  Длительность теста: {TEST_DURATION} секунд")
        self.log(f"🔄 Одновременных запросов: {CONCURRENT_REQUESTS}")
        
        self.results['start_time'] = time.time()
        
        # Создаем сессию с настройками
        connector = aiohttp.TCPConnector(
            limit=CONCURRENT_REQUESTS * 2,
            limit_per_host=CONCURRENT_REQUESTS,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Neuroevent Load Tester 1.0'}
        ) as session:
            
            # Тестируем доступность сервера
            self.log("🔍 Проверяем доступность сервера...")
            try:
                async with session.get(f"{BASE_URL}/", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        self.log("✅ Сервер доступен")
                    else:
                        self.log(f"⚠️  Сервер вернул статус {response.status}")
            except Exception as e:
                self.log(f"❌ Сервер недоступен: {e}")
                return
            
            # Запускаем нагрузочное тестирование
            self.log("🔥 Запускаем нагрузочное тестирование...")
            
            start_time = time.time()
            end_time = start_time + TEST_DURATION
            
            # Создаем задачи для пользователей
            tasks = []
            user_count = 0
            
            while time.time() < end_time and user_count < TEST_USERS:
                # Создаем батч задач
                batch_tasks = []
                for _ in range(min(CONCURRENT_REQUESTS, TEST_USERS - user_count)):
                    user_type = 'mini_app' if random.random() < 0.9 else 'admin'  # 90% обычных пользователей, 10% админов
                    task = self.simulate_user_session(session, user_count, user_type)
                    batch_tasks.append(task)
                    user_count += 1
                
                # Выполняем батч
                if batch_tasks:
                    await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Небольшая пауза между батчами
                await asyncio.sleep(0.1)
                
                # Логируем прогресс каждые 30 секунд
                elapsed = time.time() - start_time
                if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                    self.log(f"📊 Прогресс: {user_count} пользователей, {self.results['total_requests']} запросов")
        
        self.results['end_time'] = time.time()
        self.log("✅ Нагрузочное тестирование завершено")
    
    def generate_report(self):
        """Генерирует отчет о тестировании"""
        if not self.results['response_times']:
            self.log("❌ Нет данных для отчета")
            return
        
        total_time = self.results['end_time'] - self.results['start_time']
        rps = self.results['total_requests'] / total_time if total_time > 0 else 0
        
        success_rate = (self.results['successful_requests'] / self.results['total_requests'] * 100) if self.results['total_requests'] > 0 else 0
        
        response_times = self.results['response_times']
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
        p99_response_time = sorted(response_times)[int(len(response_times) * 0.99)]
        
        print("\n" + "="*80)
        print("📊 ОТЧЕТ О НАГРУЗОЧНОМ ТЕСТИРОВАНИИ")
        print("="*80)
        print(f"🎯 Целевой сервер: {BASE_URL}")
        print(f"⏱️  Длительность теста: {total_time:.2f} секунд")
        print(f"👥 Пользователей: {TEST_USERS}")
        print(f"📈 Запросов в секунду: {rps:.2f}")
        print()
        
        print("📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего запросов: {self.results['total_requests']}")
        print(f"   Успешных: {self.results['successful_requests']} ({success_rate:.2f}%)")
        print(f"   Ошибок: {self.results['failed_requests']} ({100-success_rate:.2f}%)")
        print()
        
        print("⏱️  ВРЕМЯ ОТВЕТА:")
        print(f"   Среднее: {avg_response_time:.3f}s")
        print(f"   Медиана: {median_response_time:.3f}s")
        print(f"   95-й процентиль: {p95_response_time:.3f}s")
        print(f"   99-й процентиль: {p99_response_time:.3f}s")
        print(f"   Максимальное: {max(response_times):.3f}s")
        print(f"   Минимальное: {min(response_times):.3f}s")
        print()
        
        if self.results['errors']:
            print("❌ ОШИБКИ:")
            for error, count in self.results['errors'].items():
                print(f"   {error}: {count}")
            print()
        
        print("🔗 СТАТИСТИКА ПО ENDPOINTS:")
        for endpoint, stats in self.results['endpoints'].items():
            success_rate_ep = (stats['success'] / stats['requests'] * 100) if stats['requests'] > 0 else 0
            print(f"   {endpoint}:")
            print(f"     Запросов: {stats['requests']}")
            print(f"     Успешных: {stats['success']} ({success_rate_ep:.1f}%)")
            print(f"     Ошибок: {stats['errors']}")
            print(f"     Среднее время: {stats['avg_time']:.3f}s")
            print()
        
        # Оценка готовности к продакшену
        print("🎯 ОЦЕНКА ГОТОВНОСТИ К ПРОДАКШЕНУ:")
        issues = []
        
        if success_rate < 95:
            issues.append(f"Низкий процент успешных запросов: {success_rate:.1f}%")
        
        if avg_response_time > 2.0:
            issues.append(f"Высокое среднее время ответа: {avg_response_time:.3f}s")
        
        if p95_response_time > 5.0:
            issues.append(f"Высокий 95-й процентиль: {p95_response_time:.3f}s")
        
        if rps < 100:
            issues.append(f"Низкая пропускная способность: {rps:.1f} RPS")
        
        if issues:
            print("❌ ПРОБЛЕМЫ:")
            for issue in issues:
                print(f"   • {issue}")
            print()
            print("🔧 РЕКОМЕНДАЦИИ:")
            print("   • Увеличить количество воркеров")
            print("   • Оптимизировать базу данных")
            print("   • Добавить кэширование")
            print("   • Настроить балансировщик нагрузки")
        else:
            print("✅ СИСТЕМА ГОТОВА К ПРОДАКШЕНУ!")
            print("   • Высокий процент успешных запросов")
            print("   • Приемлемое время ответа")
            print("   • Стабильная работа под нагрузкой")
        
        print("="*80)

async def main():
    """Главная функция"""
    print("🚀 NEUROEVENT BOT - НАГРУЗОЧНОЕ ТЕСТИРОВАНИЕ")
    print("="*60)
    
    tester = LoadTester()
    
    try:
        await tester.run_load_test()
        tester.generate_report()
    except KeyboardInterrupt:
        print("\n⏹️  Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка во время тестирования: {e}")
    finally:
        print("\n🏁 Тестирование завершено")

if __name__ == "__main__":
    # Проверяем зависимости
    try:
        import aiohttp
    except ImportError:
        print("❌ Необходимо установить aiohttp: pip install aiohttp")
        sys.exit(1)
    
    # Запускаем тестирование
    asyncio.run(main())
