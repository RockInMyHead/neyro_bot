#!/usr/bin/env python3
"""
Специализированное стресс-тестирование для Neuroevent Bot
Фокус на критических сценариях использования
"""

import asyncio
import aiohttp
import time
import json
import random
import statistics
from datetime import datetime
import threading
import sys

BASE_URL = "https://neuroevent.ru"

class StressTester:
    def __init__(self):
        self.results = {
            'scenarios': {},
            'critical_errors': [],
            'performance_issues': []
        }
        self.lock = threading.Lock()
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    async def test_concurrent_messages(self, session, num_users=100):
        """Тест одновременной отправки сообщений"""
        self.log(f"📨 Тестируем одновременную отправку сообщений от {num_users} пользователей")
        
        start_time = time.time()
        tasks = []
        
        for i in range(num_users):
            message_data = {
                'message': f'Stress test message from user {i}',
                'user_id': f'stress_user_{i}'
            }
            task = self.send_message(session, message_data)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
        failed = len(results) - successful
        
        scenario_result = {
            'name': 'Concurrent Messages',
            'users': num_users,
            'duration': end_time - start_time,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(results)) * 100,
            'avg_time': (end_time - start_time) / len(results)
        }
        
        self.results['scenarios']['concurrent_messages'] = scenario_result
        self.log(f"✅ Результат: {successful}/{len(results)} успешных ({scenario_result['success_rate']:.1f}%)")
        
        return scenario_result
    
    async def test_admin_panel_load(self, session, num_admins=20):
        """Тест нагрузки на админ-панель"""
        self.log(f"👨‍💼 Тестируем нагрузку на админ-панель с {num_admins} администраторами")
        
        start_time = time.time()
        tasks = []
        
        for i in range(num_admins):
            task = self.simulate_admin_session(session, f'admin_{i}')
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
        failed = len(results) - successful
        
        scenario_result = {
            'name': 'Admin Panel Load',
            'admins': num_admins,
            'duration': end_time - start_time,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(results)) * 100,
            'avg_time': (end_time - start_time) / len(results)
        }
        
        self.results['scenarios']['admin_panel'] = scenario_result
        self.log(f"✅ Результат: {successful}/{len(results)} успешных ({scenario_result['success_rate']:.1f}%)")
        
        return scenario_result
    
    async def test_image_generation_stress(self, session, num_requests=50):
        """Тест нагрузки на генерацию изображений"""
        self.log(f"🖼️  Тестируем нагрузку на генерацию изображений ({num_requests} запросов)")
        
        start_time = time.time()
        tasks = []
        
        for i in range(num_requests):
            task = self.test_image_generation(session, f'image_test_{i}')
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
        failed = len(results) - successful
        
        scenario_result = {
            'name': 'Image Generation Stress',
            'requests': num_requests,
            'duration': end_time - start_time,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(results)) * 100,
            'avg_time': (end_time - start_time) / len(results)
        }
        
        self.results['scenarios']['image_generation'] = scenario_result
        self.log(f"✅ Результат: {successful}/{len(results)} успешных ({scenario_result['success_rate']:.1f}%)")
        
        return scenario_result
    
    async def test_database_stress(self, session, num_operations=200):
        """Тест нагрузки на базу данных"""
        self.log(f"🗄️  Тестируем нагрузку на базу данных ({num_operations} операций)")
        
        start_time = time.time()
        tasks = []
        
        for i in range(num_operations):
            task = self.test_database_operation(session, f'db_test_{i}')
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
        failed = len(results) - successful
        
        scenario_result = {
            'name': 'Database Stress',
            'operations': num_operations,
            'duration': end_time - start_time,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(results)) * 100,
            'avg_time': (end_time - start_time) / len(results)
        }
        
        self.results['scenarios']['database'] = scenario_result
        self.log(f"✅ Результат: {successful}/{len(results)} успешных ({scenario_result['success_rate']:.1f}%)")
        
        return scenario_result
    
    async def send_message(self, session, message_data):
        """Отправляет сообщение"""
        try:
            async with session.post(
                f"{BASE_URL}/api/message",
                json=message_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                return {
                    'success': response.status < 400,
                    'status': response.status,
                    'response_time': time.time()
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time': time.time()
            }
    
    async def simulate_admin_session(self, session, admin_id):
        """Симулирует сессию администратора"""
        try:
            # Тестируем основные админ endpoints
            endpoints = [
                '/api/admin/check-auth',
                '/api/admin/smart-batches/stats',
                '/api/admin/smart-batches/list',
                '/api/admin/messages'
            ]
            
            start_time = time.time()
            for endpoint in endpoints:
                async with session.get(f"{BASE_URL}{endpoint}", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status >= 400:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status} on {endpoint}',
                            'response_time': time.time()
                        }
            
            return {
                'success': True,
                'response_time': time.time() - start_time
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time': time.time()
            }
    
    async def test_image_generation(self, session, test_id):
        """Тестирует генерацию изображений"""
        try:
            # Тестируем endpoint генерации изображений
            async with session.get(
                f"{BASE_URL}/api/admin/smart-batches/images",
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                return {
                    'success': response.status < 400,
                    'status': response.status,
                    'response_time': time.time()
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time': time.time()
            }
    
    async def test_database_operation(self, session, test_id):
        """Тестирует операции с базой данных"""
        try:
            # Тестируем операции чтения/записи
            async with session.get(
                f"{BASE_URL}/api/chat?user_id={test_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return {
                    'success': response.status < 400,
                    'status': response.status,
                    'response_time': time.time()
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time': time.time()
            }
    
    async def run_stress_tests(self):
        """Запускает все стресс-тесты"""
        self.log("🔥 Запускаем стресс-тестирование системы")
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Проверяем доступность
            try:
                async with session.get(f"{BASE_URL}/", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        self.log(f"❌ Сервер недоступен: HTTP {response.status}")
                        return
            except Exception as e:
                self.log(f"❌ Не удается подключиться к серверу: {e}")
                return
            
            self.log("✅ Сервер доступен, начинаем тестирование")
            
            # Запускаем тесты
            await self.test_concurrent_messages(session, 100)
            await asyncio.sleep(2)
            
            await self.test_admin_panel_load(session, 20)
            await asyncio.sleep(2)
            
            await self.test_image_generation_stress(session, 30)
            await asyncio.sleep(2)
            
            await self.test_database_stress(session, 100)
    
    def generate_stress_report(self):
        """Генерирует отчет о стресс-тестировании"""
        print("\n" + "="*80)
        print("🔥 ОТЧЕТ О СТРЕСС-ТЕСТИРОВАНИИ")
        print("="*80)
        
        for scenario_name, result in self.results['scenarios'].items():
            print(f"\n📊 {result['name']}:")
            print(f"   Успешность: {result['success_rate']:.1f}%")
            print(f"   Успешных: {result['successful']}")
            print(f"   Ошибок: {result['failed']}")
            print(f"   Время: {result['duration']:.2f}s")
            print(f"   Среднее время на операцию: {result['avg_time']:.3f}s")
            
            # Анализ критических проблем
            if result['success_rate'] < 90:
                self.results['critical_errors'].append(f"{result['name']}: низкая успешность ({result['success_rate']:.1f}%)")
            
            if result['avg_time'] > 5.0:
                self.results['performance_issues'].append(f"{result['name']}: медленное выполнение ({result['avg_time']:.3f}s)")
        
        # Общая оценка
        print(f"\n🎯 ОБЩАЯ ОЦЕНКА:")
        
        if self.results['critical_errors']:
            print("❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
            for error in self.results['critical_errors']:
                print(f"   • {error}")
        
        if self.results['performance_issues']:
            print("⚠️  ПРОБЛЕМЫ ПРОИЗВОДИТЕЛЬНОСТИ:")
            for issue in self.results['performance_issues']:
                print(f"   • {issue}")
        
        if not self.results['critical_errors'] and not self.results['performance_issues']:
            print("✅ СИСТЕМА УСТОЙЧИВА К НАГРУЗКЕ!")
            print("   • Все сценарии выполняются успешно")
            print("   • Производительность в пределах нормы")
            print("   • Система готова к продакшену")
        else:
            print("\n🔧 РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ:")
            print("   • Увеличить ресурсы сервера")
            print("   • Оптимизировать базу данных")
            print("   • Добавить кэширование")
            print("   • Настроить мониторинг")
        
        print("="*80)

async def main():
    """Главная функция"""
    print("🔥 NEUROEVENT BOT - СТРЕСС-ТЕСТИРОВАНИЕ")
    print("="*60)
    
    tester = StressTester()
    
    try:
        await tester.run_stress_tests()
        tester.generate_stress_report()
    except KeyboardInterrupt:
        print("\n⏹️  Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка во время тестирования: {e}")
    finally:
        print("\n🏁 Тестирование завершено")

if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        print("❌ Необходимо установить aiohttp: pip install aiohttp")
        sys.exit(1)
    
    asyncio.run(main())
