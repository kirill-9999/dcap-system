#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый клиент для управления ресурсами и расписаниями
Создаёт ресурс и сразу PENDING задание
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

import grpc

# Добавляем путь к сгенерированным файлам
sys.path.insert(0, str(Path(__file__).parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


async def get_resource_id(stub, path: str) -> str:
    """Получить ID ресурса по пути"""
    response = await stub.ListResources(manager_pb2.ListResourcesRequest(
        include_disabled=True
    ))
    
    for r in response.resources:
        if r.path == path:
            return r.id
    return None


async def create_task_direct(stub, resource_id: str) -> bool:
    """
    Создать задание напрямую через SQL (поскольку gRPC метод CreateTask пока не реализован)
    Используем прямую вставку в БД через коннектор
    """
    import sqlite3
    import uuid
    
    db_path = Path(__file__).parent / "manager" / "src" / "db" / "dcap.db"
    
    if not db_path.exists():
        print(f"❌ База данных не найдена: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Генерируем ID задания
        task_id = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO scan_tasks (id, resource_id, status, files_total, files_scanned, findings_count, created_at)
            VALUES (?, ?, 'PENDING', 0, 0, 0, datetime('now'))
        """, (task_id, resource_id))
        
        conn.commit()
        conn.close()
        
        print(f"    ✅ Задание создано! ID: {task_id}")
        return True
        
    except Exception as e:
        print(f"    ❌ Ошибка создания задания: {e}")
        return False


async def test_resources():
    """Тестирование CRUD ресурсов и создание задания"""
    
    channel = grpc.aio.insecure_channel('localhost:50051')
    stub = manager_pb2_grpc.ManagerStub(channel)
    
    print("=" * 60)
    print("📁 ТЕСТИРОВАНИЕ РЕСУРСОВ И СОЗДАНИЕ ЗАДАНИЯ")
    print("=" * 60)
    
    resource_path = "E:\\test_data"
    resource_id = None
    
    # 1. Проверяем существование ресурса
    print(f"\n[1] Проверка ресурса: {resource_path}")
    existing_id = await get_resource_id(stub, resource_path)
    
    if existing_id:
        resource_id = existing_id
        print(f"    ✅ Ресурс уже существует! ID: {resource_id}")
    else:
        print(f"    ℹ️  Ресурс не найден, создаём...")
        create_response = await stub.CreateResource(manager_pb2.CreateResourceRequest(
            resource_type="FILESYSTEM",
            path=resource_path,
            config={"extensions": "txt,pdf,docx"}
        ))
        
        if create_response.success:
            resource_id = create_response.resource_id
            print(f"    ✅ Ресурс создан! ID: {resource_id}")
        else:
            print(f"    ❌ Ошибка: {create_response.message}")
            return
    
    # 2. Создаём задание напрямую в БД
    print("\n[2] Создание задания...")
    await create_task_direct(stub, resource_id)
    
    # 3. Проверяем создание через SQL
    import sqlite3
    db_path = Path(__file__).parent / "manager" / "src" / "db" / "dcap.db"
    
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, resource_id FROM scan_tasks WHERE resource_id = ? ORDER BY created_at DESC LIMIT 1", (resource_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            print(f"\n[3] Проверка задания в БД:")
            print(f"    ID: {row[0]}")
            print(f"    Статус: {row[1]}")
            print(f"    Ресурс: {row[2]}")
        else:
            print(f"\n[3] ⚠️ Задание не найдено в БД")
    
    # 4. Список расписаний (если есть)
    print("\n[4] Список расписаний...")
    schedules_response = await stub.ListSchedules(manager_pb2.ListSchedulesRequest(
        resource_id=resource_id
    ))
    
    if schedules_response.schedules:
        for s in schedules_response.schedules:
            print(f"    📅 Cron: {s.cron_expression}, приоритет: {s.priority}")
    else:
        print(f"    ℹ️  Нет расписаний")
    
    print("\n" + "=" * 60)
    print("✅ Готово! Запустите Scanner:")
    print("   python test_scanner_full.py")
    print("=" * 60)
    
    await channel.close()


async def main():
    try:
        await test_resources()
    except ConnectionRefusedError:
        print("❌ Manager не запущен!")
        print("   Запустите: python -m manager.src.main")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())