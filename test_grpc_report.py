# test_grpc_report.py
import grpc
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

def test_report():
    channel = grpc.insecure_channel('localhost:50051')
    stub = manager_pb2_grpc.ManagerServiceStub(channel)  # ← исправлено
    
    # Создаём тестовую находку
    finding = manager_pb2.Finding(
        file_path="test.txt",
        file_hash="hash",
        file_size=100,
        file_modified="2026-06-25T00:00:00",
        classifier_name="test",
        category="test",
        subcategory="test",
        value="test_value",
        confidence=0.9,
        detection_method="test",
        context="test_context"
    )
    
    chunk = manager_pb2.ReportChunk(
        scanner_id="1",
        task_id="1",
        findings=[finding],
        catalog=[],
        failed=[]
    )
    
    try:
        response = stub.ReportBatch(iter([chunk]))
        print(f"✅ ReportBatch success: {response.success}")
        print(f"   Findings received: {response.findings_received}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_report()