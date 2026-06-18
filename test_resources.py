#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый клиент для управления ресурсами и расписаниями
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


async def test_resources():
    """Тестирование CRUD ресурсов и расписаний"""
    
    channel = grpc.aio.insecure_channel('localhost:50051')
    stub = manager_pb2_grpc.ManagerStub(channel)
    
    print("=" * 60)
    print("📁 ТЕСТИРОВАНИЕ РЕСУРСОВ И РАСПИСАНИЙ")
    print("=" * 60)
    
    resource_path = "E:\\test_data"
    
    # 1. Проверяем существование ресурса
    print(f"\n[1] Проверка ресурса: {resource_path}")
    resource_id = await get_resource_id(stub, resource_path)
    
    if resource_id:
        print(f"    ✅ Ресурс уже существует! ID: {resource_id}")
    else:
        print(f"    ℹ️  Ресурс не найден, создаём...")
        create_response = await stub.CreateResource(manager_pb2.CreateResourceRequest(
            resource_type="filesystem",  # В верхнем регистре!
            path=resource_path,
            config={"extensions": "txt,pdf,docx"}
        ))
        
        if create_response.success:
            resource_id = create_response.resource_id
            print(f"    ✅ Ресурс создан! ID: {resource_id}")
        else:
            print(f"    ❌ Ошибка: {create_response.message}")
            return
    
    # 2. Создаём расписание на через 1 минуту
    print("\n[2] Создание расписания...")
    
    # Вычисляем время через 1 минуту
    now = datetime.now()
    next_minute = now + timedelta(minutes=1)
    cron_expression = f"{next_minute.minute} {next_minute.hour} * * *"
    
    print(f"    ⏰ Расписание: {cron_expression} (через 1 минуту)")
    
    schedule_response = await stub.CreateSchedule(manager_pb2.CreateScheduleRequest(
        resource_id=resource_id,
        cron_expression=cron_expression,
        priority=10,
        max_files_per_batch=500
    ))
    
    if schedule_response.success:
        schedule_id = schedule_response.schedule_id
        print(f"    ✅ Расписание создано! ID: {schedule_id}")
    else:
        print(f"    ❌ Ошибка: {schedule_response.message}")
    
    # 3. Список расписаний
    print("\n[3] Список расписаний...")
    schedules_response = await stub.ListSchedules(manager_pb2.ListSchedulesRequest(
        resource_id=resource_id
    ))
    
    for s in schedules_response.schedules:
        print(f"    📅 Cron: {s.cron_expression}, приоритет: {s.priority}, батч: {s.max_files_per_batch}")
        print(f"       next_run: {s.next_run}")
    
    print("\n" + "=" * 60)
    print("⏳ Ждите 1 минуту, затем запустите Scanner!")
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