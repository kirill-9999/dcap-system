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
import logging
import argparse
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from scanner.src.managed_scanner import ManagedScanner
from scanner.src.config_loader import load_config
from scanner.src.encryption import get_encryption


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


_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _config_value(config, section: str, key: str, default=None):
    """Достать значение из AppConfig или обычного dict (для тестов)."""
    if config is None:
        return default
    if isinstance(config, dict):
        section_data = config.get(section) or {}
    else:
        section_data = getattr(config, section, None)
    if section_data is None:
        return default
    if isinstance(section_data, dict):
        return section_data.get(key, default)
    return getattr(section_data, key, default)


def _setup_logging(config):
    """Логирование: консоль DEBUG + файл (info) — BUG-283 (53.4n, v3.14.12).

    Раньше _execute_task_linewise работал часами без единой записи в лог.
    Теперь значимые события (INFO+) дублируются в файл с ротацией, а
    отладочные сообщения ([OCR] ...) остаются только в консоли.

    Возвращает путь к лог-файлу (или None, если файл недоступен).
    """
    try:
        level_name = str(_config_value(config, "logging", "level", "INFO") or "INFO").upper()
    except Exception:
        level_name = "INFO"
    file_level = getattr(logging, level_name, logging.INFO)

    log_file = _config_value(config, "logging", "file", "logs/scanner.log")
    try:
        max_size_mb = int(_config_value(config, "logging", "max_size_mb", 100) or 100)
    except (TypeError, ValueError):
        max_size_mb = 100
    try:
        backup_count = int(_config_value(config, "logging", "backup_count", 5) or 5)
    except (TypeError, ValueError):
        backup_count = 5

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_path = None
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            file_path = str(Path(log_file).resolve())
        except OSError as exc:
            print(f"[WARN] Не удалось открыть лог-файл {log_file}: {exc}")

    root.setLevel(logging.DEBUG)

    # Шумные библиотеки — только предупреждения (иначе DEBUG-консоль тонет)
    for name in (
        "urllib3",
        "botocore",
        "boto3",
        "s3transfer",
        "requests",
        "presidio",
        "spacy",
        "pypdf",
        "PIL",
        "asyncio",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    return file_path


def main():
    """Запуск сканера"""
    _setup_utf8()
    # BUG-148 (v3.13.39): start_scanner.bat читал только FINDINGS_* из secrets/,
    # .env (S3_ACCESS_KEY / S3_SECRET_KEY и др.) не загружался. Python-dotenv
    # подтягивает корневой .env до загрузки конфига — переменные попадают
    # в os.environ (config_loader/ManagedScanner их уважают).
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        print("[WARN] python-dotenv не установлен — .env не загружается. "
              "pip install python-dotenv")
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
    
    # Настройка логирования: консоль DEBUG + файл INFO (BUG-283, 53.4n)
    log_file = _setup_logging(config)

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
    print(f"[X] Лог-файл: {log_file or 'недоступен'}")
    print("=" * 60)

    # BUG-057: fail-fast — без ключей шифрования сканер не стартует.
    # Legacy (plaintext) — только при DCAP_ALLOW_LEGACY_SCANNER=true.
    try:
        _enc = get_encryption(fail_if_missing=True)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        print("[ERROR] Задайте FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY "
              "(env или Docker Secrets) или включайте legacy "
              "DCAP_ALLOW_LEGACY_SCANNER=true (только для разработки!)")
        sys.exit(2)
    print(f"[X] Шифрование находок: {'включено' if _enc else 'LEGACY (без шифрования!)'}")

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