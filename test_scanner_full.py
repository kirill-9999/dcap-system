#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый Scanner — получает задания от Manager и отправляет результаты
"""

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime

import grpc

# Добавляем путь к сгенерированным файлам
sys.path.insert(0, str(Path(__file__).parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


class TestScanner:
    """Тестовый сканер, который получает задания от Manager и отправляет результаты"""

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
        print(f"\n🔍 Requesting task for scanner: {self.scanner_id}")
        
        try:
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

            # Имитация сканирования с генерацией находок
            print(f"\n🔍 Сканирование ресурса '{response.resource_path}'...")
            
            # Генерируем тестовые находки
            findings = []
            for i in range(3):
                await asyncio.sleep(1)
                print(f"   Обработка... {i+1}/5")
                findings.append(manager_pb2.Finding(
                    file_path=f"E:\\test_data\\file_{i+1}.txt",
                    file_hash=f"hash_{i+1}",
                    file_size=1024 * (i + 1),
                    file_modified=datetime.now().isoformat(),
                    classifier_name="pii_classifier",
                    category="pii",
                    subcategory="PII_PER",
                    value=f"Тестовое_имя_{i+1}",
                    confidence=0.95,
                    detection_method="ml_bert",
                    context=f"Контекст находки {i+1}"
                ))
            
            print("   Обработка... 4/5")
            await asyncio.sleep(1)
            
            # Добавляем каталог
            catalog_entries = [
                manager_pb2.CatalogEntry(
                    folder_path="E:\\test_data",
                    source_type="filesystem",
                    classifiers=["pii_classifier", "credentials_classifier"],
                    subcategories=["PII_PER", "PII_DATE"],
                    findings_count=3
                )
            ]
            
            print("   Обработка... 5/5")
            await asyncio.sleep(1)
            
            # ========== ОТПРАВКА РЕЗУЛЬТАТОВ ==========
            print(f"\n📤 Отправка результатов в Manager...")
            
            report_response = await self.stub.ReportBatch(
                iter([manager_pb2.ReportChunk(
                    scanner_id=self.scanner_id,
                    task_id=response.task_id,
                    findings=findings,
                    catalog=catalog_entries,
                    failed=[]
                )])
            )
            
            if report_response.success:
                print(f"   ✅ Результаты отправлены!")
                print(f"      Находок: {report_response.findings_received}")
                print(f"      Каталог: {report_response.catalog_entries_received}")
            else:
                print(f"   ❌ Ошибка отправки: {report_response.message}")
            
            # ========== ЗАВЕРШЕНИЕ ЗАДАНИЯ ==========
            print(f"\n📋 Завершение задания...")
            complete_response = await self.stub.CompleteTask(manager_pb2.CompleteTaskRequest(
                scanner_id=self.scanner_id,
                task_id=response.task_id,
                files_scanned=5,
                findings_count=3,
                success=True,
                error_message=""
            ))
            
            if complete_response.success:
                print(f"   ✅ Задание завершено!")
            else:
                print(f"   ❌ Ошибка: {complete_response.message}")

            return True

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def run(self):
        """Основной цикл Scanner"""
        print("=" * 60)
        print("🔍 ЗАПУСК ТЕСТОВОГО SCANNER")
        print("=" * 60)

        if not await self.connect():
            return

        asyncio.create_task(self.heartbeat_loop())

        print("\n⏳ Ожидание заданий...")
        while True:
            try:
                has_task = await self.get_and_execute_task()
                
                if not has_task:
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(2)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                await asyncio.sleep(5)

    async def stop(self):
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