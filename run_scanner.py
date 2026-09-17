#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_scanner.py - Запуск Scanner в непрерывном режиме

Использование:
    python run_scanner.py scanner/config.json
    python run_scanner.py /path/to/config.json
"""

import sys
import os
import signal
import argparse
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.managed_scanner import ManagedScanner
from scanner.src.config_loader import load_config


def print_usage():
    """Вывод справки по использованию"""
    print("=" * 60)
    print("[X] DCAP SCANNER")
    print("=" * 60)
    print("Использование:")
    print("  python run_scanner.py <config_file>")
    print("")
    print("Примеры:")
    print("  python run_scanner.py scanner/config.json")
    print("  python run_scanner.py /path/to/config.json")
    print("")
    print("Опции:")
    print("  -h, --help    Показать эту справку")
    print("  --version     Показать версию")
    print("=" * 60)


def _setup_utf8():
    """UTF-8 обёртка для корректного вывода кириллицы (Windows console)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def main():
    """Запуск сканера"""
    _setup_utf8()
    # Проверяем аргументы
    args = sys.argv[1:]
    
    # Проверка на --help или -h
    if args and args[0] in ['-h', '--help']:
        print_usage()
        sys.exit(0)
    
    # Проверка на --version
    if args and args[0] == '--version':
        print("DCAP Scanner v1.0")
        sys.exit(0)
    
    # Проверяем, что передан путь к конфигу
    if not args:
        print("[ERROR] Ошибка: не указан путь к файлу конфигурации")
        print_usage()
        sys.exit(1)
    
    config_path = args[0]
    
    # Проверяем наличие дополнительных аргументов
    if len(args) > 1:
        print(f"[WARN] Предупреждение: лишние аргументы игнорируются: {args[1:]}")
    
    # Загружаем конфигурацию
    config = load_config(config_path)
    
    # Настройка логирования
    import logging
    log_level = getattr(logging, config.scanner.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger = logging.getLogger(__name__)
    
    # Выводим информацию о конфигурации
    print("=" * 60)
    print("[X] DCAP SCANNER")
    print("=" * 60)
    print(f"[X] Конфиг: {config_path}")
    print(f"[X] Имя сканера: {config.scanner.name}")
    print(f"[X] Manager URL: {config.scanner.manager_url}")
    print(f"[X] Scanner ID: {config.scanner.scanner_id or 'авто-регистрация'}")
    print(f"[TIME]  Интервал: {config.scanner.scan_interval} сек")
    print(f"[X] Уровень логов: {config.scanner.log_level}")
    print("=" * 60)
    
    # Создаем сканер с конфигурацией
    scanner = ManagedScanner(
        name=config.scanner.name,
        manager_url=config.scanner.manager_url,
        scanner_id=config.scanner.scanner_id,
        interval=config.scanner.scan_interval,
        config=config
    )
    
    # Обработка сигналов
    def signal_handler(sig, frame):
        print("\n[STOP] Получен сигнал остановки...")
        scanner.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        scanner.run_loop()
    except KeyboardInterrupt:
        print("\n[STOP] Прервано пользователем")
    finally:
        scanner.stop()


if __name__ == "__main__":
    main()