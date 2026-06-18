#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Manager - Main Entry Point
"""

import os
import sys
import asyncio
import logging
import platform
import signal

# Добавляем путь для импорта сгенерированных файлов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto_gen'))

import grpc

from manager.src.db.session import init_db, close_db
from manager.src.services.manager_service import ManagerService

# Импортируем сгенерированный код
import dcap.manager_pb2_grpc as manager_pb2_grpc

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dcap-manager")

logger.info(f"Platform: {platform.system()} {platform.release()}")
logger.info(f"Python: {sys.version}")


async def serve() -> None:
    """Запуск gRPC сервера"""
    logger.info("Starting DCAP Manager...")
    
    # Инициализация БД
    await init_db()
    
    # Создание gRPC сервера
    server = grpc.aio.server()
    
    # Регистрация сервиса
    manager_pb2_grpc.add_ManagerServicer_to_server(
        ManagerService(), 
        server
    )
    logger.info("✅ Manager service registered successfully!")
    
    port = os.environ.get("GRPC_PORT", "50051")
    server.add_insecure_port(f'[::]:{port}')
    
    logger.info(f"✅ gRPC server listening on port {port}")
    
    # Настройка graceful shutdown
    shutdown_event = asyncio.Event()
    
    def handle_signal():
        logger.info("Received shutdown signal...")
        shutdown_event.set()
    
    # Регистрируем обработчики сигналов
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, handle_signal)
        loop.add_signal_handler(signal.SIGINT, handle_signal)
    else:
        # Windows: используем другой подход
        def signal_handler():
            logger.info("Received shutdown signal (Ctrl+C)...")
            shutdown_event.set()
        
        # Для Windows — отдельный поток для ожидания Ctrl+C
        import threading
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
    
    await server.start()
    
    try:
        # Ждём сигнал завершения
        await shutdown_event.wait()
        logger.info("Shutting down gracefully...")
        
        # Останавливаем сервер с таймаутом
        await server.stop(5)
        logger.info("Server stopped")
        
        # Закрываем соединение с БД
        await close_db()
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        await server.stop(0)


def main():
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Manager shutdown complete")
        # Принудительный выход для Windows
        if sys.platform == "win32":
            os._exit(0)


if __name__ == "__main__":
    main()