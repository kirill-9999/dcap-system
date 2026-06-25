#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Manager - Main Entry Point (with REST API)
"""

import os
import sys
import asyncio
import logging
import platform
import signal
from datetime import datetime
import threading

# Добавляем путь для импорта сгенерированных файлов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto_gen'))

import grpc
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from manager.src.db.session import init_db, close_db, get_session
from manager.src.services.manager_service import ManagerService
from manager.src.core.scheduler import SchedulerEngine
from manager.src.db.models import Scanner, ScannerStatus, ScanTask, TaskStatus, Finding

# Импортируем сгенерированный код
import dcap.manager_pb2_grpc as manager_pb2_grpc
import dcap.manager_pb2 as manager_pb2

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dcap-manager")

logger.info(f"Platform: {platform.system()} {platform.release()}")
logger.info(f"Python: {sys.version}")

# FastAPI приложение
app = FastAPI(title="DCAP Manager API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_scheduler = None
_grpc_stub = None
_grpc_loop = None


def get_stub():
    """Получить gRPC stub"""
    global _grpc_stub, _grpc_loop
    if _grpc_stub is None:
        # Создаём stub в текущем loop
        current_loop = asyncio.get_event_loop()
        channel = grpc.aio.insecure_channel('localhost:50051')
        _grpc_stub = manager_pb2_grpc.ManagerServiceStub(channel)
        _grpc_loop = current_loop
    return _grpc_stub


@app.get("/health")
async def health_check():
    """HealthCheck endpoint для мониторинга"""
    try:
        stub = get_stub()
        request = manager_pb2.HealthCheckRequest(service="manager")
        response = await stub.HealthCheck(request)
        
        return {
            "status": "success",
            "healthy": response.healthy,
            "service_status": response.status,
            "message": response.message,
            "timestamp": response.timestamp,
            "metrics": {
                "active_scanners": response.metrics.active_scanners,
                "pending_tasks": response.metrics.pending_tasks,
                "running_tasks": response.metrics.running_tasks,
                "completed_tasks": response.metrics.completed_tasks,
                "failed_tasks": response.metrics.failed_tasks,
                "total_findings": response.metrics.total_findings
            }
        }
    except Exception as e:
        logger.error(f"HealthCheck error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """Получить метрики (аналог /health)"""
    return await health_check()


@app.get("/")
async def root():
    return {
        "service": "DCAP Manager",
        "version": "3.0.0",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics"
        }
    }


async def serve_grpc(shutdown_event: asyncio.Event):
    """Запуск gRPC сервера"""
    global _scheduler, _grpc_stub
    
    logger.info("Starting DCAP Manager...")

    await init_db()

    server = grpc.aio.server()

    # Правильная регистрация сервиса
    manager_pb2_grpc.add_ManagerServiceServicer_to_server(
        ManagerService(),
        server
    )
    logger.info("✅ Manager service registered successfully!")

    port = os.environ.get("GRPC_PORT", "50051")
    server.add_insecure_port(f'[::]:{port}')

    logger.info(f"✅ gRPC server listening on port {port}")

    # Запуск планировщика
    _scheduler = SchedulerEngine(check_interval_seconds=60)
    await _scheduler.start()

    logger.info("Available methods:")
    for method in dir(ManagerService):
        if method.startswith(('Register', 'Heartbeat', 'GetTask', 'Create', 'List', 'Delete', 'Health')):
            logger.info(f"  - {method}")

    await server.start()

    try:
        await shutdown_event.wait()
        logger.info("Shutting down gracefully...")
        
        await _scheduler.stop()
        await server.stop(5)
        await close_db()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        await server.stop(0)


def run_rest():
    """Запуск REST API в отдельном потоке"""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def main():
    """Точка входа"""
    shutdown_event = asyncio.Event()
    
    # Обработка сигналов
    def signal_handler():
        logger.info("Received shutdown signal...")
        shutdown_event.set()
    
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        loop.add_signal_handler(signal.SIGINT, signal_handler)
    else:
        def wait_for_ctrl_c():
            try:
                while True:
                    import time
                    time.sleep(0.1)
                    if shutdown_event.is_set():
                        break
            except KeyboardInterrupt:
                signal_handler()
        threading.Thread(target=wait_for_ctrl_c, daemon=True).start()
    
    try:
        logger.info("✅ REST API listening on port 8000")
        
        # Запускаем REST в отдельном потоке
        rest_thread = threading.Thread(target=run_rest, daemon=True)
        rest_thread.start()
        
        # Запускаем gRPC сервер в основном loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(serve_grpc(shutdown_event))
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Manager shutdown complete")
        if sys.platform == "win32":
            os._exit(0)


if __name__ == "__main__":
    main()