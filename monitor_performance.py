#!/usr/bin/env python3
"""
Мониторинг производительности системы Neuroevent Bot в реальном времени
"""

import asyncio
import aiohttp
import time
import json
import statistics
from datetime import datetime
import threading
import sys

BASE_URL = "https://neuroevent.ru"

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'response_times': [],
            'success_count': 0,
            'error_count': 0,
            'total_requests': 0,
            'start_time': time.time()
        }
        self.lock = threading.Lock()
        self.running = True
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    async def check_endpoint(self, session, endpoint, method='GET', data=None):
        """Проверяет endpoint и собирает метрики"""
        start_time = time.time()
        
        try:
            if method == 'GET':
                async with session.get(f"{BASE_URL}{endpoint}", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_time = time.time() - start_time
                    success = response.status < 400
            elif method == 'POST':
                async with session.post(f"{BASE_URL}{endpoint}", json=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_time = time.time() - start_time
                    success = response.status < 400
            
            with self.lock:
                self.metrics['total_requests'] += 1
                self.metrics['response_times'].append(response_time)
                
                if success:
                    self.metrics['success_count'] += 1
                else:
                    self.metrics['error_count'] += 1
            
            return {
                'endpoint': endpoint,
                'response_time': response_time,
                'success': success,
                'status': response.status if 'response' in locals() else 'ERROR'
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            with self.lock:
                self.metrics['total_requests'] += 1
                self.metrics['error_count'] += 1
                self.metrics['response_times'].append(response_time)
            
            return {
                'endpoint': endpoint,
                'response_time': response_time,
                'success': False,
                'error': str(e)
            }
    
    async def monitor_critical_endpoints(self, session):
        """Мониторит критические endpoints"""
        endpoints = [
            ('GET', '/api/mini-app/latest-message'),
            ('GET', '/api/check-chat-clear-status'),
            ('GET', '/api/admin/check-auth'),
            ('GET', '/api/admin/smart-batches/stats'),
            ('GET', '/api/admin/smart-batches/list')
        ]
        
        tasks = []
        for method, endpoint in endpoints:
            task = self.check_endpoint(session, endpoint, method)
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def simulate_user_activity(self, session, user_id):
        """Симулирует активность пользователя"""
        try:
            # Проверяем последнее сообщение
            await self.check_endpoint(session, '/api/mini-app/latest-message')
            await asyncio.sleep(0.1)
            
            # Проверяем статус очистки чата
            await self.check_endpoint(session, '/api/check-chat-clear-status')
            await asyncio.sleep(0.1)
            
            # Отправляем сообщение
            message_data = {
                'message': f'Monitor test message from user {user_id}',
                'user_id': f'monitor_user_{user_id}'
            }
            await self.check_endpoint(session, '/api/message', 'POST', message_data)
            
        except Exception as e:
            self.log(f"Ошибка в активности пользователя {user_id}: {e}")
    
    async def run_monitoring(self, duration=300):
        """Запускает мониторинг на указанное время"""
        self.log(f"📊 Начинаем мониторинг производительности на {duration} секунд")
        
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            start_time = time.time()
            end_time = start_time + duration
            
            while time.time() < end_time and self.running:
                # Мониторим критические endpoints
                await self.monitor_critical_endpoints(session)
                
                # Симулируем активность пользователей
                user_tasks = []
                for i in range(10):  # 10 одновременных пользователей
                    task = self.simulate_user_activity(session, i)
                    user_tasks.append(task)
                
                await asyncio.gather(*user_tasks, return_exceptions=True)
                
                # Пауза между циклами
                await asyncio.sleep(5)
                
                # Выводим статистику каждые 30 секунд
                elapsed = time.time() - start_time
                if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                    self.print_current_stats()
    
    def print_current_stats(self):
        """Выводит текущую статистику"""
        with self.lock:
            if not self.metrics['response_times']:
                return
            
            elapsed = time.time() - self.metrics['start_time']
            rps = self.metrics['total_requests'] / elapsed if elapsed > 0 else 0
            success_rate = (self.metrics['success_count'] / self.metrics['total_requests'] * 100) if self.metrics['total_requests'] > 0 else 0
            
            response_times = self.metrics['response_times']
            avg_time = statistics.mean(response_times)
            median_time = statistics.median(response_times)
            p95_time = sorted(response_times)[int(len(response_times) * 0.95)]
            
            self.log(f"📈 Статистика: {self.metrics['total_requests']} запросов, "
                    f"{rps:.1f} RPS, {success_rate:.1f}% успешных, "
                    f"среднее время: {avg_time:.3f}s, "
                    f"медиана: {median_time:.3f}s, "
                    f"95%: {p95_time:.3f}s")
    
    def generate_final_report(self):
        """Генерирует финальный отчет"""
        if not self.metrics['response_times']:
            self.log("❌ Нет данных для отчета")
            return
        
        elapsed = time.time() - self.metrics['start_time']
        rps = self.metrics['total_requests'] / elapsed if elapsed > 0 else 0
        success_rate = (self.metrics['success_count'] / self.metrics['total_requests'] * 100) if self.metrics['total_requests'] > 0 else 0
        
        response_times = self.metrics['response_times']
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        p95_time = sorted(response_times)[int(len(response_times) * 0.95)]
        p99_time = sorted(response_times)[int(len(response_times) * 0.99)]
        
        print("\n" + "="*80)
        print("📊 ОТЧЕТ О МОНИТОРИНГЕ ПРОИЗВОДИТЕЛЬНОСТИ")
        print("="*80)
        print(f"🎯 Целевой сервер: {BASE_URL}")
        print(f"⏱️  Время мониторинга: {elapsed:.2f} секунд")
        print(f"📈 Запросов в секунду: {rps:.2f}")
        print()
        
        print("📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего запросов: {self.metrics['total_requests']}")
        print(f"   Успешных: {self.metrics['success_count']} ({success_rate:.2f}%)")
        print(f"   Ошибок: {self.metrics['error_count']} ({100-success_rate:.2f}%)")
        print()
        
        print("⏱️  ВРЕМЯ ОТВЕТА:")
        print(f"   Среднее: {avg_time:.3f}s")
        print(f"   Медиана: {median_time:.3f}s")
        print(f"   95-й процентиль: {p95_time:.3f}s")
        print(f"   99-й процентиль: {p99_time:.3f}s")
        print(f"   Максимальное: {max(response_times):.3f}s")
        print(f"   Минимальное: {min(response_times):.3f}s")
        print()
        
        # Оценка производительности
        print("🎯 ОЦЕНКА ПРОИЗВОДИТЕЛЬНОСТИ:")
        
        issues = []
        if success_rate < 95:
            issues.append(f"Низкий процент успешных запросов: {success_rate:.1f}%")
        
        if avg_time > 2.0:
            issues.append(f"Высокое среднее время ответа: {avg_time:.3f}s")
        
        if p95_time > 5.0:
            issues.append(f"Высокий 95-й процентиль: {p95_time:.3f}s")
        
        if rps < 50:
            issues.append(f"Низкая пропускная способность: {rps:.1f} RPS")
        
        if issues:
            print("❌ ПРОБЛЕМЫ ПРОИЗВОДИТЕЛЬНОСТИ:")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print("✅ ПРОИЗВОДИТЕЛЬНОСТЬ В НОРМЕ!")
            print("   • Высокий процент успешных запросов")
            print("   • Приемлемое время ответа")
            print("   • Стабильная работа системы")
        
        print("="*80)
    
    def stop(self):
        """Останавливает мониторинг"""
        self.running = False

async def main():
    """Главная функция"""
    print("📊 NEUROEVENT BOT - МОНИТОРИНГ ПРОИЗВОДИТЕЛЬНОСТИ")
    print("="*60)
    
    monitor = PerformanceMonitor()
    
    try:
        # Запускаем мониторинг на 5 минут
        await monitor.run_monitoring(300)
        monitor.generate_final_report()
    except KeyboardInterrupt:
        print("\n⏹️  Мониторинг прерван пользователем")
        monitor.stop()
    except Exception as e:
        print(f"\n❌ Ошибка во время мониторинга: {e}")
    finally:
        print("\n🏁 Мониторинг завершен")

if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        print("❌ Необходимо установить aiohttp: pip install aiohttp")
        sys.exit(1)
    
    asyncio.run(main())
