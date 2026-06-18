#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый Scanner — получает задания от Manager и "сканирует"
"""

import asyncio
import sys
import time
from pathlib import Path

import grpc

# Добавляем путь к сгенерированным файлам
sys.path.insert(0, str(Path(__file__).parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


class TestScanner:
    """Тестовый сканер, который получает задания от Manager"""

    def __init__(self, name: str, manager_endpoint: str = "localhost:50051"):
        self.name = name
        self.manager_endpoint = manager_endpoint
        self.scanner_id = None
        self.stub = None
        self.channel = None

    async def connect(self):
        """Подключение к Manager"""
        self.channel = grpc.aio.insecure_channel(self.manager_endpoint)
        self.stub = manager_pb2_grpc.ManagerStub(self.channel)

        # Регистрация
        print(f"📝 Регистрация сканера '{self.name}'...")
        response = await self.stub.Register(manager_pb2.RegisterRequest(
            scanner_name=self.name,
            endpoint="localhost:0"
        ))

        if response.success:
            self.scanner_id = response.scanner_id
            print(f"✅ Зарегистрирован! ID: {self.scanner_id}")
            return True
        else:
            print(f"❌ Ошибка регистрации: {response.message}")
            return False

    async def heartbeat_loop(self):
        """Фоновый heartbeat"""
        while True:
            try:
                await asyncio.sleep(10)
                response = await self.stub.Heartbeat(manager_pb2.HeartbeatRequest(
                    scanner_id=self.scanner_id
                ))
                if not response.success:
                    print(f"⚠️ Heartbeat failed: {response.message}")
            except Exception as e:
                print(f"⚠️ Heartbeat error: {e}")

    async def get_and_execute_task(self):
        """Получение и выполнение задания"""
        print("\n🔍 Запрос задания...")
        
        try:
            print(f"🔍 Requesting task for scanner: {self.scanner_id}")
            response = await self.stub.GetTask(manager_pb2.GetTaskRequest(
                scanner_id=self.scanner_id
            ))

            if not response.has_task:
                print("ℹ️  Нет заданий")
                return False

            print(f"✅ Получено задание!")
            print(f"   ID: {response.task_id}")
            print(f"   Ресурс: {response.resource_path}")
            print(f"   Тип: {response.resource_type}")
            print(f"   Размер батча: {response.batch_size}")

            # Имитация сканирования
            print(f"\n🔍 Сканирование ресурса '{response.resource_path}'...")
            
            # TODO: Здесь будет реальный сканер
            # Сейчас просто имитируем работу
            for i in range(5):
                await asyncio.sleep(1)
                print(f"   Обработка... {i+1}/5")
            
            print(f"✅ Сканирование завершено!")
            
            # TODO: Отправить результаты в Manager
            # await self.report_results(response.task_id, findings)

            return True

        except Exception as e:
            print(f"❌ Ошибка получения задания: {e}")
            return False

    async def run(self):
        """Основной цикл Scanner"""
        print("=" * 60)
        print("🔍 ЗАПУСК ТЕСТОВОГО SCANNER")
        print("=" * 60)

        # Подключение к Manager
        if not await self.connect():
            return

        # Запускаем heartbeat в фоне
        asyncio.create_task(self.heartbeat_loop())

        # Основной цикл
        print("\n⏳ Ожидание заданий...")
        while True:
            try:
                # Пытаемся получить задание
                has_task = await self.get_and_execute_task()
                
                if not has_task:
                    # Нет заданий — ждём
                    await asyncio.sleep(5)
                else:
                    # Задание выполнено — небольшая пауза
                    await asyncio.sleep(2)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Остановка Scanner"""
        if self.channel:
            await self.channel.close()
        print("👋 Scanner остановлен")


async def main():
    scanner = TestScanner("test-scanner-1")
    try:
        await scanner.run()
    except KeyboardInterrupt:
        print("\n⏹️ Остановка...")
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())