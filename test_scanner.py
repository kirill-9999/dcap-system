#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый клиент Scanner для проверки Manager
"""

import asyncio
import sys
from pathlib import Path

import grpc

# Добавляем путь к сгенерированным файлам
proto_gen_path = Path(__file__).parent / "manager" / "src" / "proto_gen"
sys.path.insert(0, str(proto_gen_path))

# Теперь импорт работает
import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


async def test_scanner():
    """Тестовый сканер"""
    
    # Подключение к Manager
    channel = grpc.aio.insecure_channel('localhost:50051')
    stub = manager_pb2_grpc.ManagerStub(channel)
    
    scanner_name = "test-scanner-1"
    endpoint = "localhost:0"
    
    # 1. Регистрация
    print(f"[1] Регистрация сканера '{scanner_name}'...")
    register_response = await stub.Register(manager_pb2.RegisterRequest(
        scanner_name=scanner_name,
        endpoint=endpoint
    ))
    
    if register_response.success:
        scanner_id = register_response.scanner_id
        print(f"    ✅ Зарегистрирован! ID: {scanner_id}")
        print(f"    Сообщение: {register_response.message}")
    else:
        print(f"    ❌ Ошибка: {register_response.message}")
        return
    
    # 2. Heartbeat цикл
    print("\n[2] Отправка Heartbeat (каждые 5 секунд, 3 раза)...")
    
    for i in range(3):
        await asyncio.sleep(5)
        
        heartbeat_response = await stub.Heartbeat(manager_pb2.HeartbeatRequest(
            scanner_id=scanner_id
        ))
        
        if heartbeat_response.success:
            print(f"    [{i+1}] ✅ Heartbeat OK")
        else:
            print(f"    [{i+1}] ❌ Heartbeat failed: {heartbeat_response.message}")
    
    # 3. Получение задания
    print("\n[3] Проверка заданий...")
    task_response = await stub.GetTask(manager_pb2.GetTaskRequest(
        scanner_id=scanner_id
    ))
    
    if task_response.has_task:
        print(f"    ✅ Получено задание: {task_response.task_id}")
        print(f"       Ресурс: {task_response.resource_path}")
    else:
        print(f"    ℹ️  Нет заданий")
    
    print("\n✅ Тест завершён!")
    await channel.close()


def main():
    try:
        asyncio.run(test_scanner())
    except KeyboardInterrupt:
        print("\n⏹️ Прервано")
    except ConnectionRefusedError:
        print("\n❌ Manager не запущен!")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()