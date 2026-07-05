#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Managed Scanner — работает в непрерывном цикле, получает задания от Manager
"""

import asyncio
import sys
import io
import logging
import signal
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Set

import grpc

# Принудительно UTF-8 — обязательно до любого print/logging
os.environ.setdefault('PYTHONUTF8', '1')
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.core.orchestrator import Orchestrator
from scanner.core.base import FileContext, ClassificationResult
from scanner.connectors.filesystem import FileSystemConnector

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

logger = logging.getLogger("dcap-scanner")


CATALOG_FLUSH_INTERVAL = 30  # секунд между периодическими сбросами каталога


class GrpcHandler:
    """Обработчик, отправляющий находки и каталог в Manager через gRPC"""

    def __init__(self, endpoint: str, scanner_id: int, task_id: int):
        # Синхронный stub — flush() вызывается из синхронного кода Orchestrator
        self._sync_channel = grpc.insecure_channel(endpoint)
        self.stub = manager_pb2_grpc.ManagerServiceStub(self._sync_channel)
        self.scanner_id = scanner_id
        self.task_id = task_id

        # Буфер находок
        self.buffer = []
        self.batch_size = 50
        self.findings_count = 0
        self.sent = False

        # Каталог: папка → множество классификаторов, которые нашли там что-либо
        self.catalog_dict: Dict[str, Set[str]] = {}
        self._last_catalog_flush: float = time.time()

    def write(self, result: ClassificationResult, file_context: FileContext):
        """Добавление находки в буфер и обновление каталога"""
        if not result.findings:
            return

        for finding in result.findings[:20]:
            self.buffer.append(manager_pb2.Finding(
                file_path=file_context.path,
                file_hash="",
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

        # Обновляем каталог: непосредственная папка файла
        folder = str(Path(file_context.path).parent)
        if folder not in self.catalog_dict:
            self.catalog_dict[folder] = set()
        self.catalog_dict[folder].add(result.classifier_name)

        # Сброс буфера находок при достижении размера батча
        if len(self.buffer) >= self.batch_size:
            self.flush()

        # Периодический сброс каталога
        if time.time() - self._last_catalog_flush >= CATALOG_FLUSH_INTERVAL:
            self.flush_catalog()

    def flush(self):
        """Отправка буфера находок в Manager"""
        if not self.buffer:
            return

        # Сбрасываем буфер сразу, чтобы не отправить повторно при ошибке
        batch = self.buffer
        self.buffer = []

        try:
            chunk = manager_pb2.ReportChunk(
                scanner_id=str(self.scanner_id),
                task_id=str(self.task_id),
                findings=batch,
                catalog=[],
                failed=[]
            )
            response = self.stub.ReportBatch(iter([chunk]))
            if response.success:
                logger.info(f"Sent {len(batch)} findings to Manager")
                self.sent = True
            else:
                logger.warning(f"ReportBatch warning: {response.message}")
        except Exception as e:
            logger.error(f"Error sending findings: {e}")

    def flush_catalog(self):
        """Отправка текущего снимка каталога в Manager"""
        if not self.catalog_dict:
            return

        entries = [
            manager_pb2.CatalogEntry(
                folder_path=folder,
                classifiers=sorted(classifiers),  # сортируем для стабильного порядка
            )
            for folder, classifiers in self.catalog_dict.items()
        ]

        try:
            chunk = manager_pb2.ReportChunk(
                scanner_id=str(self.scanner_id),
                task_id=str(self.task_id),
                findings=[],
                catalog=entries,
                failed=[]
            )
            response = self.stub.ReportBatch(iter([chunk]))
            if response.success:
                logger.info(f"Catalog sent: {len(entries)} folders")
            else:
                logger.warning(f"Catalog flush warning: {response.message}")
        except Exception as e:
            logger.error(f"Error sending catalog: {e}")
        finally:
            self._last_catalog_flush = time.time()

    def close(self):
        """Закрытие: сброс остатков находок, затем финальный сброс каталога"""
        if self.buffer:
            self.flush()
        self.flush_catalog()
        return self.sent


class ScannerState:
    """Состояние сканера для восстановления после перезапуска"""
    
    def __init__(self, state_dir: Path = Path("scanner_state")):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "state.json"
        self.task_file = self.state_dir / "current_task.json"
        self.offline_findings = self.state_dir / "offline_findings.jsonl"
        
        self.current_task: Optional[Dict[str, Any]] = None
        self.is_processing = False
    
    def load(self) -> Dict[str, Any]:
        """Загрузка состояния"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"scanner_id": None, "last_heartbeat": None}
    
    def save(self, state: Dict[str, Any]):
        """Сохранение состояния"""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def save_current_task(self, task: Dict[str, Any]):
        """Сохранение текущего задания"""
        self.current_task = task
        with open(self.task_file, 'w') as f:
            json.dump(task, f, indent=2)
    
    def load_current_task(self) -> Optional[Dict[str, Any]]:
        """Загрузка текущего задания"""
        if self.task_file.exists():
            try:
                with open(self.task_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def clear_current_task(self):
        """Очистка текущего задания"""
        self.current_task = None
        if self.task_file.exists():
            self.task_file.unlink()
    
    def save_offline_finding(self, finding: Dict[str, Any]):
        """Сохранение находки в оффлайн-режиме"""
        with open(self.offline_findings, 'a', encoding='utf-8') as f:
            f.write(json.dumps(finding, ensure_ascii=False) + '\n')
    
    def get_offline_findings(self) -> list:
        """Получение оффлайн-находок"""
        findings = []
        if self.offline_findings.exists():
            with open(self.offline_findings, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            findings.append(json.loads(line))
                        except:
                            pass
        return findings
    
    def clear_offline_findings(self):
        """Очистка оффлайн-находок"""
        if self.offline_findings.exists():
            self.offline_findings.unlink()


class ManagedScanner:
    """Управляемый сканер — непрерывный цикл"""
    
    def __init__(self, name: str, manager_endpoint: str = "localhost:50051", 
                 state_dir: Path = Path("scanner_state")):
        self.name = name
        self.manager_endpoint = manager_endpoint
        self.scanner_id = None
        self.stub = None
        self.channel = None
        
        self.state = ScannerState(state_dir)
        self._should_exit = False
        self._is_running = False
        
        # Текущее задание
        self.current_task = None
        self.current_handler = None
        self.current_orchestrator = None
        
        # Классификаторы (загружаются один раз)
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
    
    async def connect(self) -> bool:
        """Подключение к Manager с восстановлением ID"""
        self.channel = grpc.aio.insecure_channel(self.manager_endpoint)
        self.stub = manager_pb2_grpc.ManagerServiceStub(self.channel)
        
        # Загружаем сохранённое состояние
        saved_state = self.state.load()
        saved_scanner_id = saved_state.get("scanner_id")
        
        # Пробуем восстановить регистрацию
        if saved_scanner_id:
            logger.info(f"♻️ Восстановление сканера ID: {saved_scanner_id}")
            try:
                # Проверяем, жив ли сканер через Heartbeat
                response = await self.stub.Heartbeat(manager_pb2.HeartbeatRequest(
                    scanner_id=str(saved_scanner_id)
                ))
                if response.success:
                    self.scanner_id = int(saved_scanner_id)
                    logger.info(f"✅ Сканер восстановлен! ID: {self.scanner_id}")
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Не удалось восстановить сканер: {e}")
        
        # Регистрируем новый сканер
        logger.info(f"📝 Регистрация сканера '{self.name}'...")
        try:
            response = await self.stub.Register(manager_pb2.RegisterRequest(
                scanner_name=self.name,
                endpoint="localhost:0"
            ))
            
            if response.success:
                self.scanner_id = int(response.scanner_id)
                logger.info(f"✅ Зарегистрирован! ID: {self.scanner_id}")
                
                # Сохраняем ID
                saved_state["scanner_id"] = self.scanner_id
                self.state.save(saved_state)
                
                return True
            else:
                logger.error(f"❌ Ошибка регистрации: {response.message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False
    
    async def restore_task(self) -> Optional[Dict]:
        """Восстановление прерванного задания"""
        saved_task = self.state.load_current_task()
        
        if not saved_task:
            return None
        
        task_id = saved_task.get("task_id")
        logger.info(f"♻️ Обнаружено незавершённое задание: {task_id}")
        
        # Проверяем статус задания в Manager
        try:
            # Пытаемся получить статус (если есть такой метод)
            # Или просто пробуем продолжить
            logger.info(f"   Продолжаем выполнение задания {task_id}...")
            return saved_task
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить статус задания: {e}")
            return saved_task
    
    async def get_task(self) -> Optional[Dict]:
        """Получение задания от Manager"""
        try:
            response = await self.stub.GetTask(manager_pb2.GetTaskRequest(
                scanner_id=str(self.scanner_id)
            ))
            
            if response.has_task:
                task = {
                    "task_id": int(response.task_id),
                    "resource_id": int(response.resource_id),
                    "resource_path": response.resource_path,
                    "resource_type": response.resource_type,
                    "batch_size": response.batch_size,
                    "assigned_at": datetime.now().isoformat()
                }
                logger.info(f"📋 Получено задание: {task['task_id']}")
                logger.info(f"   Ресурс: {task['resource_path']}")
                return task
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения задания: {e}")
            return None
    
    async def execute_task(self, task: Dict) -> bool:
        """Выполнение задания"""
        task_id = task["task_id"]
        resource_path = task["resource_path"]
        
        logger.info(f"🔍 Начало сканирования: {resource_path}")
        
        # Сохраняем текущее задание
        self.state.save_current_task(task)
        self.current_task = task
        
        # Создаём обработчик
        handler = GrpcHandler(self.manager_endpoint, self.scanner_id, task_id)
        self.current_handler = handler
        
        # Создаём Orchestrator
        orchestrator = Orchestrator(
            config={
                "state_file": f"state_{task_id}.json",
                "logs_folder": "logs",
                "catalog_dir": f"catalog_{task_id}"
            },
            shared_classifiers=self.classifiers,
            shared_handlers=[handler]
        )
        self.current_orchestrator = orchestrator
        
        # Настраиваем коннектор
        connector = FileSystemConnector()
        connector.configure({
            "extensions": ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg", "json", "csv", "log"],
            "max_file_size_mb": 50
        })
        
        orchestrator.configure(connector)
        
        try:
            # Запускаем сканирование
            orchestrator.process_source(resource_path)
            
            # Отправляем остатки
            handler.close()
            
            # Получаем статистику
            stats = orchestrator.get_statistics()
            
            logger.info(f"✅ Сканирование завершено!")
            logger.info(f"   Обработано: {stats.get('processed_files', 0)} файлов")
            logger.info(f"   Находок: {handler.findings_count}")
            
            # Завершаем задание
            success = await self.complete_task(task_id, stats, handler.findings_count)
            
            # Очищаем состояние
            self.state.clear_current_task()
            self.current_task = None
            self.current_handler = None
            self.current_orchestrator = None
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка сканирования: {e}")
            
            # Пытаемся завершить с ошибкой
            await self.complete_task(task_id, {}, 0, success=False, error=str(e))
            
            # Задание остаётся в состоянии для восстановления
            # При следующем запуске будет продолжено
            return False
    
    async def complete_task(self, task_id: int, stats: Dict, findings_count: int,
                           success: bool = True, error: str = ""):
        """Завершение задания в Manager"""
        try:
            response = await self.stub.CompleteTask(manager_pb2.CompleteTaskRequest(
                scanner_id=str(self.scanner_id),
                task_id=str(task_id),
                files_scanned=stats.get('processed_files', 0),
                findings_count=findings_count,
                success=success,
                error_message=error[:500]  # Ограничиваем длину
            ))
            
            if response.success:
                logger.info(f"📋 Задание {task_id} завершено!")
                return True
            else:
                logger.warning(f"⚠️ Ошибка завершения задания: {response.message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка CompleteTask: {e}")
            return False
    
    async def heartbeat_loop(self):
        """Фоновый heartbeat"""
        while not self._should_exit:
            try:
                await asyncio.sleep(10)
                if self.scanner_id:
                    response = await self.stub.Heartbeat(manager_pb2.HeartbeatRequest(
                        scanner_id=str(self.scanner_id)
                    ))
                    if not response.success:
                        logger.warning(f"⚠️ Heartbeat failed: {response.message}")
                    else:
                        logger.debug("💓 Heartbeat OK")
            except Exception as e:
                logger.warning(f"⚠️ Heartbeat error: {e}")
    
    async def run_continuous(self):
        """Непрерывный цикл работы Scanner"""
        print("=" * 60)
        print("🔍 DCAP MANAGED SCANNER (непрерывный режим)")
        print("=" * 60)
        print(f"   Имя: {self.name}")
        print(f"   Manager: {self.manager_endpoint}")
        print("   Режим: получение и выполнение заданий")
        print("   Для остановки: Ctrl+C")
        print("=" * 60)
        
        # Подключаемся к Manager
        if not await self.connect():
            logger.error("❌ Не удалось подключиться к Manager")
            return
        
        # Запускаем heartbeat
        asyncio.create_task(self.heartbeat_loop())
        
        # Проверяем, есть ли незавершённое задание
        restored_task = await self.restore_task()
        if restored_task:
            logger.info("🔄 Продолжение прерванного задания...")
            await self.execute_task(restored_task)
        
        # Основной цикл
        while not self._should_exit:
            try:
                # Получаем задание
                task = await self.get_task()
                
                if task:
                    # Выполняем задание
                    await self.execute_task(task)
                    await asyncio.sleep(1)
                else:
                    # Нет заданий — ждём
                    if self._is_running:
                        logger.debug("⏳ Нет заданий, ожидание...")
                    await asyncio.sleep(5)
                    
            except KeyboardInterrupt:
                break
            except grpc.RpcError as e:
                logger.error(f"❌ gRPC ошибка: {e.code()} - {e.details()}")
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    logger.warning("⚠️ Manager недоступен, повторная попытка через 10 сек...")
                    await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                await asyncio.sleep(5)
        
        await self.stop()
    
    async def stop(self):
        """Корректная остановка"""
        self._should_exit = True
        self._is_running = False
        
        # Если есть текущее задание — сохраняем состояние
        if self.current_task:
            logger.info(f"💾 Сохранение состояния задания {self.current_task['task_id']}")
            self.state.save_current_task(self.current_task)
        
        # Останавливаем оркестратор
        if self.current_orchestrator:
            try:
                self.current_orchestrator.stop()
            except:
                pass
        
        # Закрываем канал
        if self.channel:
            await self.channel.close()
        
        logger.info("👋 Scanner остановлен")
    
    async def run(self):
        """Основной метод запуска (совместимость)"""
        await self.run_continuous()


async def main():
    """Точка входа"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Создаём сканер
    scanner = ManagedScanner(
        name=os.environ.get("SCANNER_NAME", f"scanner-{os.getpid()}"),
        manager_endpoint=os.environ.get("MANAGER_ENDPOINT", "localhost:50051")
    )
    
    # Обработка сигналов
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        print("\n⏹️ Получен сигнал остановки...")
        asyncio.create_task(scanner.stop())
    
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        loop.add_signal_handler(signal.SIGINT, signal_handler)
    
    try:
        await scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n⏹️ Прервано пользователем")
    finally:
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())