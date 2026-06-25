#!/usr/bin/env python3
"""Диагностика Scanner gRPC вызовов"""

import grpc
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

print("🔍 ДИАГНОСТИКА GRPC SCANNER")
print("=" * 60)

try:
    channel = grpc.insecure_channel('localhost:50051')
    stub = manager_pb2_grpc.ManagerStub(channel)
    
    # 1. Регистрация
    print("\n[1] Регистрация...")
    try:
        reg_response = stub.Register(manager_pb2.RegisterRequest(
            scanner_name="debug-scanner",
            endpoint="localhost:0"
        ))
        scanner_id = int(reg_response.scanner_id)
        print(f"   ✅ Зарегистрирован: ID={scanner_id}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        sys.exit(1)
    
    # 2. GetTask с разными типами
    print("\n[2] GetTask с int...")
    try:
        response = stub.GetTask(manager_pb2.GetTaskRequest(scanner_id=scanner_id))
        print(f"   ✅ has_task={response.has_task}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n[3] GetTask с str...")
    try:
        response = stub.GetTask(manager_pb2.GetTaskRequest(scanner_id=str(scanner_id)))
        print(f"   ✅ has_task={response.has_task}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Heartbeat
    print("\n[4] Heartbeat с int...")
    try:
        response = stub.Heartbeat(manager_pb2.HeartbeatRequest(scanner_id=scanner_id))
        print(f"   ✅ success={response.success}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. CompleteTask
    print("\n[5] CompleteTask с int...")
    try:
        response = stub.CompleteTask(manager_pb2.CompleteTaskRequest(
            scanner_id=scanner_id,
            task_id=1,
            files_scanned=0,
            findings_count=0,
            success=True,
            error_message=""
        ))
        print(f"   ✅ success={response.success}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    channel.close()
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()