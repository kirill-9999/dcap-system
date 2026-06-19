#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый клиент для HealthCheck
"""

import sys
from pathlib import Path

import grpc
import requests
import json

sys.path.insert(0, str(Path(__file__).parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


def test_grpc_health():
    """Проверка gRPC HealthCheck"""
    print("=" * 60)
    print("🔍 gRPC HEALTHCHECK")
    print("=" * 60)
    
    try:
        channel = grpc.insecure_channel('localhost:50051')
        stub = manager_pb2_grpc.ManagerStub(channel)
        
        response = stub.HealthCheck(manager_pb2.HealthCheckRequest(service="manager"))
        
        print(f"\n✅ HealthCheck успешен!")
        print(f"   Healthy: {response.healthy}")
        print(f"   Status: {response.status}")
        print(f"   Message: {response.message}")
        print(f"   Timestamp: {response.timestamp}")
        
        print(f"\n📊 Метрики:")
        print(f"   Активные Scanner'ы: {response.metrics.active_scanners}")
        print(f"   Заданий в очереди: {response.metrics.pending_tasks}")
        print(f"   Выполняется: {response.metrics.running_tasks}")
        print(f"   Завершено: {response.metrics.completed_tasks}")
        print(f"   Ошибок: {response.metrics.failed_tasks}")
        print(f"   Всего находок: {response.metrics.total_findings}")
        
        channel.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def test_rest_health():
    """Проверка REST HealthCheck — как curl"""
    print("\n" + "=" * 60)
    print("🌐 REST HEALTHCHECK (как curl)")
    print("=" * 60)
    
    try:
        # Так же как curl делает запрос
        headers = {
            'User-Agent': 'curl/8.0.0',
            'Accept': '*/*'
        }
        
        response = requests.get(
            'http://localhost:8000/health',
            headers=headers,
            timeout=10
        )
        
        print(f"\n✅ Статус: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Ответ:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ Ошибка: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Ошибка: Не удалось подключиться к localhost:8000")
        print("   Проверьте, что Manager запущен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


def test_rest_root():
    """Проверка корневого REST эндпоинта"""
    print("\n" + "=" * 60)
    print("🌐 REST ROOT")
    print("=" * 60)
    
    try:
        response = requests.get('http://localhost:8000/', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ REST Root доступен!")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ Ошибка: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


def test_curl_style():
    """Тест в стиле curl — прямой вывод"""
    print("\n" + "=" * 60)
    print("🌐 ПРЯМОЙ ЗАПРОС (как curl -v)")
    print("=" * 60)
    
    import socket
    import http.client
    
    try:
        conn = http.client.HTTPConnection("localhost", 8000, timeout=5)
        conn.request("GET", "/health")
        response = conn.getresponse()
        
        print(f"\n✅ HTTP/1.1 {response.status} {response.reason}")
        print(f"   Content-Type: {response.getheader('content-type', 'unknown')}")
        print(f"   Content-Length: {response.getheader('content-length', 'unknown')}")
        
        data = response.read().decode('utf-8')
        print(f"\n📊 Тело ответа:")
        print(data)
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    test_grpc_health()
    test_rest_health()
    test_rest_root()
    test_curl_style()