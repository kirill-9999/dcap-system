#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика gRPC вызовов Scanner -> Manager
Проверяет все RPC методы, чтобы найти проблему с типами
"""

import sys
import grpc
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем сгенерированные protobuf
import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


def test_grpc_calls():
    """Тестирование всех gRPC методов"""
    
    print("=" * 70)
    print("🔍 ДИАГНОСТИКА GRPC SCANNER -> MANAGER")
    print("=" * 70)
    
    try:
        # Подключение к Manager
        channel = grpc.insecure_channel('localhost:50051')
        stub = manager_pb2_grpc.ManagerStub(channel)
        
        # ========== 1. Регистрация ==========
        print("\n[1] РЕГИСТРАЦИЯ")
        print("-" * 40)
        try:
            reg_response = stub.Register(manager_pb2.RegisterRequest(
                scanner_name="debug-scanner",
                endpoint="localhost:0"
            ))
            scanner_id = int(reg_response.scanner_id)
            print(f"   ✅ Зарегистрирован: ID={scanner_id} (тип: {type(scanner_id).__name__})")
            print(f"      message={reg_response.message}")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return
        
        # ========== 2. GetTask ==========
        print("\n[2] GET_TASK")
        print("-" * 40)
        
        # 2a. GetTask с int
        print("   [2a] с int...")
        try:
            response = stub.GetTask(manager_pb2.GetTaskRequest(scanner_id=scanner_id))
            print(f"      ✅ has_task={response.has_task}")
            if response.has_task:
                print(f"         task_id={response.task_id}")
                print(f"         resource_path={response.resource_path}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # 2b. GetTask с str
        print("   [2b] с str...")
        try:
            response = stub.GetTask(manager_pb2.GetTaskRequest(scanner_id=str(scanner_id)))
            print(f"      ✅ has_task={response.has_task}")
            if response.has_task:
                print(f"         task_id={response.task_id}")
                print(f"         resource_path={response.resource_path}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # ========== 3. Heartbeat ==========
        print("\n[3] HEARTBEAT")
        print("-" * 40)
        
        # 3a. Heartbeat с int
        print("   [3a] с int...")
        try:
            response = stub.Heartbeat(manager_pb2.HeartbeatRequest(scanner_id=scanner_id))
            print(f"      ✅ success={response.success}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # 3b. Heartbeat с str
        print("   [3b] с str...")
        try:
            response = stub.Heartbeat(manager_pb2.HeartbeatRequest(scanner_id=str(scanner_id)))
            print(f"      ✅ success={response.success}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # ========== 4. ReportBatch ==========
        print("\n[4] REPORT_BATCH")
        print("-" * 40)
        
        # Создаём тестовую находку
        test_finding = manager_pb2.Finding(
            file_path="E:\\test_data\\test.txt",
            file_hash="test_hash",
            file_size=1024,
            file_modified="2026-01-01T00:00:00",
            classifier_name="test_classifier",
            category="test",
            subcategory="test_sub",
            value="test_value",
            confidence=0.9,
            detection_method="test",
            context="test_context"
        )
        
        # 4a. ReportBatch с int (как есть)
        print("   [4a] ReportBatch с int (как есть)...")
        try:
            chunk = manager_pb2.ReportChunk(
                scanner_id=scanner_id,
                task_id=1,
                findings=[test_finding],
                catalog=[],
                failed=[]
            )
            response = stub.ReportBatch(iter([chunk]))
            print(f"      ✅ success={response.success}")
            print(f"         findings_received={response.findings_received}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # 4b. ReportBatch с str
        print("   [4b] ReportBatch с str...")
        try:
            chunk = manager_pb2.ReportChunk(
                scanner_id=str(scanner_id),
                task_id=1,
                findings=[test_finding],
                catalog=[],
                failed=[]
            )
            response = stub.ReportBatch(iter([chunk]))
            print(f"      ✅ success={response.success}")
            print(f"         findings_received={response.findings_received}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # 4c. ReportBatch с int64 (через float/int)
        print("   [4c] ReportBatch с int64 (через long)...")
        try:
            chunk = manager_pb2.ReportChunk(
                scanner_id=scanner_id + 0,  # пытаемся создать int64
                task_id=1,
                findings=[test_finding],
                catalog=[],
                failed=[]
            )
            response = stub.ReportBatch(iter([chunk]))
            print(f"      ✅ success={response.success}")
            print(f"         findings_received={response.findings_received}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # ========== 5. CompleteTask ==========
        print("\n[5] COMPLETE_TASK")
        print("-" * 40)
        
        # 5a. CompleteTask с int
        print("   [5a] CompleteTask с int...")
        try:
            response = stub.CompleteTask(manager_pb2.CompleteTaskRequest(
                scanner_id=scanner_id,
                task_id=1,
                files_scanned=10,
                findings_count=5,
                success=True,
                error_message=""
            ))
            print(f"      ✅ success={response.success}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # 5b. CompleteTask с str
        print("   [5b] CompleteTask с str...")
        try:
            response = stub.CompleteTask(manager_pb2.CompleteTaskRequest(
                scanner_id=str(scanner_id),
                task_id=1,
                files_scanned=10,
                findings_count=5,
                success=True,
                error_message=""
            ))
            print(f"      ✅ success={response.success}")
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        # ========== 6. HealthCheck ==========
        print("\n[6] HEALTH_CHECK")
        print("-" * 40)
        try:
            response = stub.HealthCheck(manager_pb2.HealthCheckRequest(service="debug"))
            print(f"   ✅ healthy={response.healthy}")
            print(f"      status={response.status}")
            print(f"      message={response.message}")
            print(f"      active_scanners={response.metrics.active_scanners}")
            print(f"      pending_tasks={response.metrics.pending_tasks}")
            print(f"      total_findings={response.metrics.total_findings}")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        # ========== 7. Итог ==========
        print("\n" + "=" * 70)
        print("📊 ИТОГ:")
        print("=" * 70)
        print("   GetTask:   работает со строкой")
        print("   Heartbeat: работает со строкой")
        print("   ReportBatch: см. результат выше")
        print("   CompleteTask: см. результат выше")
        print("   HealthCheck: см. результат выше")
        
        channel.close()
        
    except grpc.RpcError as e:
        print(f"\n❌ GRPC Ошибка: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_grpc_calls()