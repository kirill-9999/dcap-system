#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование оффлайн-режима Scanner
"""

import sys
import os
import time
import asyncio
import uuid
from pathlib import Path
from datetime import datetime

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.offline.queue import OfflineQueue, OfflineFinding
from scanner.src.offline.storage import OfflineStorage
from scanner.src.offline.detector import ManagerDetector
from scanner.src.offline.sync import OfflineSync


def test_queue():
    """Тестирование оффлайн-очереди"""
    print("\n" + "=" * 60)
    print("📦 ТЕСТИРОВАНИЕ ОФФЛАЙН-ОЧЕРЕДИ")
    print("=" * 60)
    
    # Создаём очередь
    data_dir = Path("test_data/queue")
    queue = OfflineQueue(data_dir)
    
    # Создаём тестовые находки
    print("\n[1] Добавление находок в очередь...")
    findings = []
    for i in range(5):
        finding = OfflineFinding(
            id=str(uuid.uuid4()),
            task_id=f"task-{i % 2 + 1}",
            scanner_id="scanner-1",
            file_path=f"/test/file_{i}.txt",
            classifier_name="pii_classifier",
            category="PII_PER",
            subcategory="person_name",
            value=f"Иван Иванов {i}",
            confidence=0.95,
            detection_method="ml_bert",
            context=f"Контекст находки {i}",
            file_hash=f"hash_{i}",
            file_size=1024 * (i + 1),
            file_modified=datetime.now().isoformat(),
            created_at=datetime.now().isoformat()
        )
        findings.append(finding)
    
    # Добавляем в очередь
    added = queue.add_batch(findings)
    print(f"   ✅ Добавлено находок: {added}")
    
    # Проверяем статистику
    print("\n[2] Статистика очереди:")
    stats = queue.get_stats()
    print(f"   Всего: {stats['total']}")
    print(f"   Ожидает синхронизации: {stats['pending']}")
    print(f"   Синхронизировано: {stats['synced']}")
    print(f"   По категориям: {stats['by_category']}")
    
    # Получаем pending находки
    print("\n[3] Получение pending находок...")
    pending = queue.get_pending(limit=10)
    print(f"   Найдено: {len(pending)}")
    for f in pending[:3]:
        print(f"   - {f.id[:8]}... | {f.category} | {f.value[:20]}...")
    
    # Отмечаем как синхронизированные
    print("\n[4] Отметка как синхронизированных...")
    ids = [f.id for f in pending[:3]]
    marked = queue.mark_synced(ids)
    print(f"   Отмечено: {marked}")
    
    # Проверяем статистику после синхронизации
    stats2 = queue.get_stats()
    print(f"\n[5] Статистика после синхронизации:")
    print(f"   Всего: {stats2['total']}")
    print(f"   Ожидает синхронизации: {stats2['pending']}")
    print(f"   Синхронизировано: {stats2['synced']}")
    
    # Очищаем синхронизированные
    print("\n[6] Очистка синхронизированных...")
    cleared = queue.clear_synced()
    print(f"   Очищено: {cleared}")
    
    # Финальная статистика
    stats3 = queue.get_stats()
    print(f"\n[7] Финальная статистика:")
    print(f"   Всего: {stats3['total']}")
    print(f"   Ожидает синхронизации: {stats3['pending']}")
    
    print("\n✅ Тест очереди завершён!")
    return queue


def test_storage():
    """Тестирование оффлайн-хранилища"""
    print("\n" + "=" * 60)
    print("💾 ТЕСТИРОВАНИЕ ОФФЛАЙН-ХРАНИЛИЩА")
    print("=" * 60)
    
    data_dir = Path("test_data/storage")
    storage = OfflineStorage(data_dir)
    
    # Создаём сессии
    print("\n[1] Создание сессий...")
    resources = [
        ("/test/data1", "filesystem"),
        ("/test/data2", "filesystem"),
        ("s3://bucket/data", "s3")
    ]
    
    sessions = []
    for path, type_ in resources:
        session_id = storage.create_session(path, type_)
        sessions.append(session_id)
        print(f"   Создана сессия: {session_id[:8]}... | {path}")
    
    # Обновляем сессии
    print("\n[2] Обновление сессий...")
    for i, session_id in enumerate(sessions):
        storage.update_session(
            session_id=session_id,
            files_scanned=(i + 1) * 10,
            findings_count=(i + 1) * 3,
            completed=(i == len(sessions) - 1)
        )
        print(f"   Обновлена: {session_id[:8]}... | files={ (i+1)*10 } | findings={ (i+1)*3 }")
    
    # Получаем сессии
    print("\n[3] Получение сессий...")
    all_sessions = storage.get_all_sessions()
    print(f"   Всего сессий: {len(all_sessions)}")
    for s in all_sessions:
        print(f"   - {s.session_id[:8]}... | {s.resource_path} | files={s.files_scanned} | findings={s.findings_count}")
    
    # Сводка
    print("\n[4] Сводка по сессиям:")
    summary = storage.get_sessions_summary()
    print(f"   Всего сессий: {summary['total_sessions']}")
    print(f"   Завершено: {summary['completed']}")
    print(f"   В процессе: {summary['in_progress']}")
    print(f"   Всего файлов: {summary['total_files_scanned']}")
    print(f"   Всего находок: {summary['total_findings']}")
    
    print("\n✅ Тест хранилища завершён!")
    return storage


def test_detector():
    """Тестирование детектора Manager"""
    print("\n" + "=" * 60)
    print("🔍 ТЕСТИРОВАНИЕ ДЕТЕКТОРА MANAGER")
    print("=" * 60)
    
    endpoint = "localhost:50051"
    detector = ManagerDetector(endpoint, check_interval=3, max_interval=10)
    
    # Подписываемся на изменения
    def on_status_change(available):
        status = "ДОСТУПЕН" if available else "НЕДОСТУПЕН"
        print(f"   📡 Статус Manager: {status}")
    
    detector.on_change(on_status_change)
    
    # Запускаем проверку
    print(f"\n[1] Запуск детектора (endpoint={endpoint})...")
    detector.start()
    
    # Проверяем несколько раз
    print("\n[2] Проверка статуса...")
    for i in range(5):
        available = detector.is_available()
        status = "✅ ДОСТУПЕН" if available else "❌ НЕДОСТУПЕН"
        print(f"   Попытка {i+1}: {status}")
        time.sleep(2)
    
    # Статистика
    print("\n[3] Статистика детектора:")
    stats = detector.get_stats()
    print(f"   Endpoint: {stats['endpoint']}")
    print(f"   Доступен: {stats['available']}")
    print(f"   Текущий интервал: {stats['current_interval']}с")
    print(f"   Последовательных ошибок: {stats['consecutive_failures']}")
    print(f"   Последовательных успехов: {stats['consecutive_successes']}")
    
    # Останавливаем
    print("\n[4] Остановка детектора...")
    detector.stop()
    
    print("\n✅ Тест детектора завершён!")
    return detector


def test_sync():
    """Тестирование синхронизации"""
    print("\n" + "=" * 60)
    print("🔄 ТЕСТИРОВАНИЕ СИНХРОНИЗАЦИИ")
    print("=" * 60)
    
    data_dir = Path("test_data/sync")
    queue = OfflineQueue(data_dir / "queue")
    
    # Добавляем тестовые находки
    print("\n[1] Добавление тестовых находок...")
    findings = []
    for i in range(10):
        finding = OfflineFinding(
            id=str(uuid.uuid4()),
            task_id=f"sync-task-{i % 3 + 1}",
            scanner_id="scanner-1",
            file_path=f"/test/sync_file_{i}.txt",
            classifier_name="credentials_classifier",
            category="CRED_API_KEY",
            subcategory="api_key",
            value=f"test_api_key_{i}",
            confidence=0.9,
            detection_method="regex",
            context=f"Контекст API ключа {i}",
            file_hash=f"hash_{i}",
            file_size=512,
            file_modified=datetime.now().isoformat(),
            created_at=datetime.now().isoformat()
        )
        findings.append(finding)
    
    added = queue.add_batch(findings)
    print(f"   Добавлено: {added}")
    
    # Создаём детектор и синхронизатор
    print("\n[2] Создание синхронизатора...")
    detector = ManagerDetector("localhost:50051", check_interval=3)
    sync = OfflineSync(queue, detector, "scanner-1", batch_size=5)
    
    # Статистика до синхронизации
    print("\n[3] Статистика до синхронизации:")
    stats = sync.get_stats()
    print(f"   Всего в очереди: {stats['total_in_queue']}")
    print(f"   Ожидает синхронизации: {stats['pending_in_queue']}")
    print(f"   Синхронизировано ранее: {stats['total_synced']}")
    
    # Запускаем синхронизацию
    print("\n[4] Запуск синхронизации...")
    sync.start()
    
    # Ждём немного
    print("   Ожидание 10 секунд...")
    time.sleep(10)
    
    # Статистика после
    print("\n[5] Статистика после синхронизации:")
    stats2 = sync.get_stats()
    print(f"   Всего в очереди: {stats2['total_in_queue']}")
    print(f"   Ожидает синхронизации: {stats2['pending_in_queue']}")
    print(f"   Синхронизировано: {stats2['total_synced']}")
    print(f"   Ошибок синхронизации: {stats2['sync_errors']}")
    
    # Останавливаем
    print("\n[6] Остановка синхронизатора...")
    sync.stop()
    detector.stop()
    
    print("\n✅ Тест синхронизации завершён!")
    return sync


def test_offline_handler():
    """Тестирование обработчика для сохранения находок в оффлайн-очередь"""
    print("\n" + "=" * 60)
    print("📝 ТЕСТИРОВАНИЕ ОФФЛАЙН-ОБРАБОТЧИКА")
    print("=" * 60)
    
    from scanner.src.offline.queue import OfflineQueue, OfflineFinding
    from scanner.src.offline.storage import OfflineStorage
    from scanner.src.offline.detector import ManagerDetector
    
    class OfflineHandler:
        """Обработчик для сохранения находок в оффлайн-очередь"""
        
        def __init__(self, queue: OfflineQueue, storage: OfflineStorage, 
                     scanner_id: str, detector: ManagerDetector):
            self.queue = queue
            self.storage = storage
            self.scanner_id = scanner_id
            self.detector = detector
            self.buffer = []
            self.batch_size = 50
            self.findings_count = 0
            self.current_task_id = None
            self.current_session_id = None
        
        def start_session(self, task_id: str, resource_path: str, resource_type: str = "filesystem"):
            """Начать сессию"""
            self.current_task_id = task_id
            self.current_session_id = self.storage.create_session(resource_path, resource_type)
            print(f"   📂 Сессия начата: {self.current_session_id[:8]}...")
        
        def write(self, result, file_context):
            """Сохранить находку в очередь"""
            if not result.findings:
                return
            
            for finding in result.findings[:20]:
                # Создаём объект оффлайн-находки
                offline_finding = OfflineFinding(
                    id=str(uuid.uuid4()),
                    task_id=self.current_task_id or "offline",
                    scanner_id=self.scanner_id,
                    file_path=file_context.path,
                    classifier_name=result.classifier_name,
                    category=result.category.value,
                    subcategory=finding.subcategory,
                    value=finding.value[:200],
                    confidence=finding.confidence,
                    detection_method=finding.detection_method,
                    context=finding.context[:200] if finding.context else "",
                    file_hash=file_context.get("file_hash", ""),
                    file_size=file_context.size_bytes,
                    file_modified=file_context.modified_time.isoformat() if file_context.modified_time else None,
                    created_at=datetime.now().isoformat()
                )
                
                # Добавляем в буфер
                self.buffer.append(offline_finding)
                self.findings_count += 1
            
            # Отправляем при заполнении буфера
            if len(self.buffer) >= self.batch_size:
                self.flush()
        
        def flush(self):
            """Сбросить буфер в очередь"""
            if not self.buffer:
                return
            
            # Проверяем доступность Manager
            if self.detector.is_available():
                # Отправляем в Manager (через синхронизатор)
                print(f"   📤 Отправка {len(self.buffer)} находок в Manager...")
                # Здесь будет вызов sync
            else:
                # Сохраняем в локальную очередь
                print(f"   💾 Сохранение {len(self.buffer)} находок в локальную очередь...")
                added = self.queue.add_batch(self.buffer)
                print(f"   Сохранено: {added}")
            
            self.buffer = []
        
        def end_session(self, completed: bool = True, error: str = None):
            """Завершить сессию"""
            self.flush()
            if self.current_session_id:
                self.storage.update_session(
                    session_id=self.current_session_id,
                    findings_count=self.findings_count,
                    completed=completed,
                    error=error
                )
                print(f"   📂 Сессия завершена: {self.current_session_id[:8]}...")
            
            self.current_task_id = None
            self.current_session_id = None
        
        def close(self):
            """Закрыть обработчик"""
            self.flush()
    
    # Создаём компоненты
    data_dir = Path("test_data/offline_handler")
    queue = OfflineQueue(data_dir / "queue")
    storage = OfflineStorage(data_dir / "storage")
    detector = ManagerDetector("localhost:50051")
    
    # Создаём обработчик
    print("\n[1] Создание оффлайн-обработчика...")
    handler = OfflineHandler(queue, storage, "scanner-1", detector)
    print("   ✅ Обработчик создан")
    
    # Имитация сканирования
    print("\n[2] Имитация сканирования с сохранением в очередь...")
    
    class MockFileContext:
        def __init__(self, path, size):
            self.path = path
            self.size_bytes = size
            self.modified_time = datetime.now()
            self.get = lambda x, y="": y
    
    class MockResult:
        def __init__(self, classifier_name, category, findings):
            self.classifier_name = classifier_name
            self.category = category
            self.findings = findings
        
        class MockFinding:
            def __init__(self, subcategory, value, confidence, detection_method, context):
                self.subcategory = subcategory
                self.value = value
                self.confidence = confidence
                self.detection_method = detection_method
                self.context = context
    
    # Начинаем сессию
    handler.start_session("task-123", "/test/data", "filesystem")
    
    # Создаём тестовые находки
    for i in range(10):
        findings = [
            MockResult.MockFinding(
                subcategory="PII_PER",
                value=f"Имя пользователя {i}",
                confidence=0.95,
                detection_method="ml_bert",
                context=f"Контекст {i}"
            )
        ]
        result = MockResult(
            classifier_name="pii_classifier",
            category=type('Category', (), {'value': 'pii'})(),
            findings=findings
        )
        file_context = MockFileContext(f"/test/file_{i}.txt", 1024)
        
        handler.write(result, file_context)
        print(f"   Обработан файл {i+1}/10")
    
    # Завершаем сессию
    handler.end_session(completed=True)
    
    # Проверяем очередь
    print("\n[3] Проверка очереди после обработки:")
    stats = queue.get_stats()
    print(f"   Всего находок: {stats['total']}")
    print(f"   Ожидает синхронизации: {stats['pending']}")
    print(f"   По категориям: {stats['by_category']}")
    
    # Проверяем сессии
    print("\n[4] Проверка сессий:")
    sessions = storage.get_all_sessions()
    print(f"   Всего сессий: {len(sessions)}")
    for s in sessions:
        print(f"   - {s.session_id[:8]}... | {s.resource_path} | findings={s.findings_count}")
    
    print("\n✅ Тест оффлайн-обработчика завершён!")
    return handler


def cleanup():
    """Очистка тестовых данных"""
    print("\n" + "=" * 60)
    print("🧹 ОЧИСТКА ТЕСТОВЫХ ДАННЫХ")
    print("=" * 60)
    
    import shutil
    
    test_dirs = [
        Path("test_data")
    ]
    
    for dir_path in test_dirs:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"   Удалено: {dir_path}")
        else:
            print(f"   Не найдено: {dir_path}")
    
    print("\n✅ Очистка завершена!")


def run_all_tests(cleanup_after: bool = False):
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("🧪 ЗАПУСК ВСЕХ ТЕСТОВ ОФФЛАЙН-РЕЖИМА")
    print("=" * 60)
    
    try:
        # 1. Тест очереди
        queue = test_queue()
        
        # 2. Тест хранилища
        storage = test_storage()
        
        # 3. Тест детектора
        detector = test_detector()
        
        # 4. Тест синхронизации
        sync = test_sync()
        
        # 5. Тест обработчика
        handler = test_offline_handler()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        
        # Вывод финальной статистики
        print("\n📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
        print(f"   Очередь: {queue.get_stats()}")
        print(f"   Хранилище: {storage.get_sessions_summary()}")
        print(f"   Детектор: {detector.get_stats()}")
        print(f"   Синхронизация: {sync.get_stats()}")
        
        # Очистка
        if cleanup_after:
            cleanup()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Тестирование оффлайн-режима Scanner")
    parser.add_argument("--cleanup", action="store_true", help="Очистить тестовые данные после тестов")
    parser.add_argument("--test", choices=["queue", "storage", "detector", "sync", "handler", "all"],
                       default="all", help="Какой тест запустить")
    
    args = parser.parse_args()
    
    if args.test == "all":
        run_all_tests(args.cleanup)
    elif args.test == "queue":
        test_queue()
    elif args.test == "storage":
        test_storage()
    elif args.test == "detector":
        test_detector()
    elif args.test == "sync":
        test_sync()
    elif args.test == "handler":
        test_offline_handler()