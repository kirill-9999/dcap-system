#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Managed Scanner — получает задания от Manager и выполняет реальное сканирование
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import grpc

# Добавляем пути для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импорты из dcap-agent
from scanner.core.orchestrator import Orchestrator
from scanner.core.base import FileContext, ClassificationResult, DataCategory
from scanner.connectors.filesystem import FileSystemConnector

# Импорты для gRPC
sys.path.insert(0, str(Path(__file__).parent.parent))
import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dcap-scanner")


class GrpcHandler:
    """Обработчик, отправляющий находки в Manager через gRPC"""
    
    def __init__(self, stub, scanner_id: str, task_id: str):
        self.stub = stub
        self.scanner_id = scanner_id
        self.task_id = task_id
        self.buffer = []
        self.batch_size = 50
        self.findings_count = 0
    
    def write(self, result: ClassificationResult, file_context: FileContext):
        """Добавление находки в буфер"""
        if not result.findings:
            return
        
        for finding in result.findings[:20]:  # Ограничиваем количество
            self.buffer.append(manager_pb2.Finding(
                file_path=file_context.path,
                file_hash="",  # TODO: вычислить хэш
                file_size=file_context.size_bytes,
                file_modified=file_context.modified_time.isoformat() if file_context.modified_time else "",
                classifier_name=result.classifier_name,
                category=result.category.value,
                subcategory=finding.subcategory,
                value=finding.value[:200],
                confidence=finding.confidence,
                detection_method=finding.detection_method,
                context=finding.context[:200] if finding.context else ""
            ))
        
        self.findings_count += len(result.findings)
        
        # Отправка при заполнении буфера
        if len(self.buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Отправка буфера в Manager"""
        if not self.buffer:
            return
        
        try:
            # Отправляем через ReportBatch
            chunk = manager_pb2.ReportChunk(
                scanner_id=self.scanner_id,
                task_id=self.task_id,
                findings=self.buffer,
                catalog=[],  # TODO: добавить каталог
                failed=[]
            )
            
            # Синхронный вызов (для простоты)
            response = self.stub.ReportBatch(iter([chunk]))
            
            logger.info(f"📤 Отправлено {len(self.buffer)} находок в Manager")
            self.buffer = []
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Manager: {e}")
    
    def close(self):
        """Закрытие обработчика"""
        self.flush()


class ManagedScanner:
    """Управляемый сканер"""
    
    def __init__(self, name: str, manager_endpoint: str = "localhost:50051"):
        self.name = name
        self.manager_endpoint = manager_endpoint
        self.scanner_id = None
        self.stub = None
        self.channel = None
        
        # Подготовка классификаторов
        self.classifiers = []
        self._load_classifiers()
    
    def _load_classifiers(self):
        """Загрузка классификаторов"""
        try:
            from scanner.classifiers.pii_classifier import PiiClassifier
            from scanner.classifiers.credentials_classifier import CredentialsClassifier
            from scanner.classifiers.code_classifier import CodeClassifier
            
            pii = PiiClassifier()
            pii.configure({"ocr_enabled": True})
            self.classifiers.append(pii)
            
            cred = CredentialsClassifier()
            cred.configure({})
            self.classifiers.append(cred)
            
            code = CodeClassifier()
            code.configure({})
            self.classifiers.append(code)
            
            logger.info(f"✅ Загружено {len(self.classifiers)} классификаторов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки классификаторов: {e}")
    
    async def connect(self):
        """Подключение к Manager"""
        self.channel = grpc.aio.insecure_channel(self.manager_endpoint)
        self.stub = manager_pb2_grpc.ManagerStub(self.channel)
        
        logger.info(f"📝 Регистрация сканера '{self.name}'...")
        response = await self.stub.Register(manager_pb2.RegisterRequest(
            scanner_name=self.name,
            endpoint="localhost:0"
        ))
        
        if response.success:
            self.scanner_id = response.scanner_id
            logger.info(f"✅ Зарегистрирован! ID: {self.scanner_id}")
            return True
        else:
            logger.error(f"❌ Ошибка регистрации: {response.message}")
            return False
    
    async def get_task(self):
        """Получение задания от Manager"""
        try:
            response = await self.stub.GetTask(manager_pb2.GetTaskRequest(
                scanner_id=self.scanner_id
            ))
            
            if response.has_task:
                logger.info(f"📋 Получено задание: {response.task_id}")
                logger.info(f"   Ресурс: {response.resource_path}")
                return response
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения задания: {e}")
            return None
    
    async def execute_task(self, task):
        """Выполнение задания (реальное сканирование)"""
        logger.info(f"🔍 Начало сканирования: {task.resource_path}")
        
        # Создаём обработчик для отправки в Manager
        grpc_handler = GrpcHandler(
            self.stub,
            self.scanner_id,
            task.task_id
        )
        
        # Создаём Orchestrator с нашими классификаторами
        orchestrator = Orchestrator(
            config={
                "state_file": "state.json",
                "logs_folder": "logs",
                "catalog_dir": "catalog"
            },
            shared_classifiers=self.classifiers,
            shared_handlers=[grpc_handler]
        )
        
        # Настраиваем коннектор
        connector = FileSystemConnector()
        connector.configure({
            "extensions": ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
            "max_file_size_mb": 50
        })
        
        orchestrator.configure(connector)
        
        try:
            # Запускаем сканирование
            orchestrator.process_source(task.resource_path)
            
            # Отправляем оставшиеся находки
            grpc_handler.close()
            
            stats = orchestrator.get_statistics()
            
            logger.info(f"✅ Сканирование завершено!")
            logger.info(f"   Обработано: {stats.get('processed_files', 0)} файлов")
            logger.info(f"   Находок: {grpc_handler.findings_count}")
            
            # Завершаем задание
            await self.complete_task(task.task_id, stats, grpc_handler.findings_count)
            
        except Exception as e:
            logger.error(f"❌ Ошибка сканирования: {e}")
            await self.complete_task(task.task_id, {}, 0, success=False, error=str(e))
        
        # Очистка памяти
        orchestrator.stop()
        del orchestrator
    
    async def complete_task(self, task_id: str, stats: Dict, findings_count: int, 
                           success: bool = True, error: str = ""):
        """Завершение задания"""
        try:
            response = await self.stub.CompleteTask(manager_pb2.CompleteTaskRequest(
                scanner_id=self.scanner_id,
                task_id=task_id,
                files_scanned=stats.get('processed_files', 0),
                findings_count=findings_count,
                success=success,
                error_message=error
            ))
            
            if response.success:
                logger.info(f"📋 Задание {task_id} завершено!")
            else:
                logger.warning(f"⚠️ Ошибка завершения задания: {response.message}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка CompleteTask: {e}")
    
    async def heartbeat_loop(self):
        """Фоновый heartbeat"""
        while True:
            try:
                await asyncio.sleep(10)
                response = await self.stub.Heartbeat(manager_pb2.HeartbeatRequest(
                    scanner_id=self.scanner_id
                ))
                if not response.success:
                    logger.warning(f"⚠️ Heartbeat failed: {response.message}")
            except Exception as e:
                logger.warning(f"⚠️ Heartbeat error: {e}")
    
    async def run(self):
        """Основной цикл Scanner"""
        print("=" * 60)
        print("🔍 DCAP MANAGED SCANNER")
        print("=" * 60)
        
        if not await self.connect():
            return
        
        # Запускаем heartbeat
        asyncio.create_task(self.heartbeat_loop())
        
        logger.info("⏳ Ожидание заданий...")
        
        while True:
            try:
                task = await self.get_task()
                
                if task:
                    await self.execute_task(task)
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(5)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        """Остановка Scanner"""
        if self.channel:
            await self.channel.close()
        logger.info("👋 Scanner остановлен")


async def main():
    scanner = ManagedScanner("real-scanner-1")
    try:
        await scanner.run()
    except KeyboardInterrupt:
        print("\n⏹️ Остановка...")
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())