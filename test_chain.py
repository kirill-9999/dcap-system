#!/usr/bin/env python3
"""
Скрипт для тестирования цепочки Manager → Scanner → БД.
Проверяет полный цикл: создание задачи, сканирование, сохранение результатов в БД.

Версия: 2.0
Проект: DCAP System
"""

import sys
import argparse
import time
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Tuple

# ============================================================
# НАСТРОЙКА ПУТЕЙ К МОДУЛЯМ ПРОЕКТА
# ============================================================
PROJECT_ROOT = Path(__file__).parent  # e:\projects\dcap-system
sys.path.insert(0, str(PROJECT_ROOT / "manager"))
sys.path.insert(0, str(PROJECT_ROOT / "scanner"))

# ============================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ChainTester:
    """Класс для тестирования цепочки Manager → Scanner → БД"""
    
    def __init__(self, scan_path: str, manager_address: str = "localhost:50051"):
        """
        Инициализация тестера цепочки.
        
        Args:
            scan_path: Путь к папке для сканирования
            manager_address: Адрес Manager сервера (gRPC)
        """
        self.scan_path = Path(scan_path)
        self.manager_address = manager_address
        
        # Путь к БД относительно корня проекта
        self.db_path = PROJECT_ROOT / "manager" / "src" / "db" / "dcap.db"
        
        logger.info(f"Путь к БД: {self.db_path}")
        logger.info(f"Путь для сканирования: {self.scan_path}")
        
        # Проверяем существование папки для сканирования
        if not self.scan_path.exists():
            raise FileNotFoundError(
                f"Папка для сканирования не существует: {scan_path}\n"
                f"Укажите корректный путь через аргумент --path"
            )
        
        if not self.scan_path.is_dir():
            raise NotADirectoryError(
                f"Указанный путь не является директорией: {scan_path}"
            )
    
    def initialize_database(self):
        """
        Инициализация БД Manager через DatabaseManager.
        
        Returns:
            DatabaseManager: Экземпляр менеджера БД
        """
        try:
            from manager.src.db.database import DatabaseManager
            
            logger.info("Инициализация DatabaseManager...")
            db_manager = DatabaseManager()
            
            # Проверяем, что БД создалась
            if not self.db_path.exists():
                logger.warning(f"Файл БД не найден, будет создан: {self.db_path}")
            
            logger.info("DatabaseManager успешно инициализирован")
            return db_manager
            
        except ImportError as e:
            logger.error(f"Ошибка импорта DatabaseManager: {e}")
            logger.error("Проверьте структуру проекта и пути к модулям")
            raise
        except Exception as e:
            logger.error(f"Ошибка при инициализации DatabaseManager: {e}")
            raise
    
    def create_scan_task(self, db_manager) -> int:
        """
        Создание задания на сканирование через ManagerService.
        
        Args:
            db_manager: Экземпляр DatabaseManager
            
        Returns:
            int: ID созданной задачи
        """
        try:
            from manager.src.services.manager_service import ManagerService
            
            logger.info("Создание задачи сканирования...")
            
            # Создаем сервис и задачу
            manager_service = ManagerService(db_manager)
            task_id = manager_service.create_task(
                source_path=str(self.scan_path),
                task_type="full_scan",
                description=f"Тестовое сканирование директории {self.scan_path.name}"
            )
            
            logger.info(f"Задача успешно создана с ID: {task_id}")
            return task_id
            
        except ImportError as e:
            logger.error(f"Ошибка импорта ManagerService: {e}")
            raise
        except AttributeError as e:
            logger.error(f"Метод create_task не найден в ManagerService: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {e}")
            raise
    
    def run_scanner(self, task_id: int):
        """
        Запуск сканирования через ManagedScanner.
        
        Args:
            task_id: ID задачи для сканирования
        """
        try:
            from scanner.src.managed_scanner import ManagedScanner
            
            logger.info(f"Запуск ManagedScanner для задачи {task_id}...")
            logger.info(f"Адрес Manager: {self.manager_address}")
            
            # Создаем экземпляр сканера
            scanner = ManagedScanner(
                manager_address=self.manager_address,
                task_id=task_id,
                source_path=str(self.scan_path)
            )
            
            # Запускаем сканирование
            logger.info("Запуск процесса сканирования...")
            scanner.start()
            
            # Ожидаем завершения сканирования
            logger.info("Ожидание завершения сканирования...")
            scan_start_time = time.time()
            
            while scanner.is_running():
                time.sleep(1)
                elapsed = int(time.time() - scan_start_time)
                logger.debug(f"Сканирование выполняется... прошло {elapsed} сек.")
            
            elapsed_total = int(time.time() - scan_start_time)
            logger.info(f"Сканирование завершено за {elapsed_total} сек.")
            
        except ImportError as e:
            logger.error(f"Ошибка импорта ManagedScanner: {e}")
            raise
        except ConnectionError as e:
            logger.error(f"Ошибка подключения к Manager ({self.manager_address}): {e}")
            logger.error("Убедитесь, что Manager запущен и доступен")
            raise
        except Exception as e:
            logger.error(f"Ошибка при сканировании: {e}")
            raise
    
    def get_findings(self, task_id: int) -> Tuple[int, List[Tuple]]:
        """
        Получение находок из БД для указанной задачи.
        
        Args:
            task_id: ID задачи
            
        Returns:
            Tuple[int, List[Tuple]]: (количество находок, список первых 5 записей)
        """
        conn = None
        try:
            logger.info(f"Подключение к БД: {self.db_path}")
            
            # Проверяем существование БД
            if not self.db_path.exists():
                raise FileNotFoundError(f"Файл БД не найден: {self.db_path}")
            
            # Подключаемся к БД
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Проверяем существование таблицы findings
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='findings'
            """)
            
            if not cursor.fetchone():
                logger.warning("Таблица 'findings' не найдена в БД")
                return 0, []
            
            # Подсчитываем количество записей для задачи
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM findings 
                WHERE task_id = ?
            """, (task_id,))
            
            count = cursor.fetchone()['count']
            logger.info(f"Найдено записей в таблице findings: {count}")
            
            # Получаем первые 5 записей
            examples = []
            if count > 0:
                cursor.execute("""
                    SELECT 
                        file_path, 
                        entity_type, 
                        value, 
                        confidence 
                    FROM findings 
                    WHERE task_id = ?
                    ORDER BY id
                    LIMIT 5
                """, (task_id,))
                
                examples = cursor.fetchall()
                
                # Выводим примеры
                logger.info("\n" + "=" * 60)
                logger.info("ПРИМЕРЫ ПЕРВЫХ 5 НАХОДОК:")
                logger.info("=" * 60)
                
                for i, row in enumerate(examples, 1):
                    logger.info(f"\n  Запись #{i}:")
                    logger.info(f"    Файл:        {row['file_path']}")
                    logger.info(f"    Тип:         {row['entity_type']}")
                    logger.info(f"    Значение:    {row['value']}")
                    logger.info(f"    Уверенность: {row['confidence']}")
            
            return count, examples
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка SQLite при работе с БД: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении находок из БД: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def run_test(self) -> int:
        """
        Запуск полного цикла тестирования.
        
        Returns:
            int: Код возврата (0 - успех, 1 - ошибка)
        """
        try:
            logger.info("\n" + "=" * 60)
            logger.info("ТЕСТИРОВАНИЕ ЦЕПОЧКИ Manager → Scanner → БД")
            logger.info("=" * 60)
            
            # Шаг 1: Инициализация БД
            logger.info("\n[ШАГ 1/4] Инициализация базы данных...")
            db_manager = self.initialize_database()
            
            # Шаг 2: Создание задачи
            logger.info("\n[ШАГ 2/4] Создание задачи сканирования...")
            task_id = self.create_scan_task(db_manager)
            
            # Шаг 3: Запуск сканирования
            logger.info("\n[ШАГ 3/4] Запуск сканирования...")
            self.run_scanner(task_id)
            
            # Шаг 4: Получение результатов из БД
            logger.info("\n[ШАГ 4/4] Получение результатов из БД...")
            count, examples = self.get_findings(task_id)
            
            # Итоговый вывод
            logger.info("\n" + "=" * 60)
            logger.info("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
            logger.info("=" * 60)
            logger.info(f"Просканированная папка: {self.scan_path}")
            logger.info(f"ID созданного задания:  {task_id}")
            logger.info(f"Количество находок:     {count}")
            
            if count > 0:
                logger.info("\n" + "=" * 60)
                logger.info("✓ ТЕСТ УСПЕШНО ПРОЙДЕН")
                logger.info("=" * 60)
                return 0
            else:
                logger.warning("\n" + "=" * 60)
                logger.warning("! ТЕСТ ПРОЙДЕН, НО НАХОДОК НЕТ")
                logger.warning("=" * 60)
                return 1
                
        except FileNotFoundError as e:
            logger.error(f"\nОШИБКА: {e}")
            return 1
            
        except NotADirectoryError as e:
            logger.error(f"\nОШИБКА: {e}")
            return 1
            
        except ImportError as e:
            logger.error(f"\nОШИБКА ИМПОРТА: {e}")
            logger.error("Проверьте, что все необходимые модули установлены")
            return 1
            
        except ConnectionError as e:
            logger.error(f"\nОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
            logger.error(f"Проверьте, что Manager доступен по адресу {self.manager_address}")
            return 1
            
        except Exception as e:
            logger.error(f"\nНЕОЖИДАННАЯ ОШИБКА: {e}")
            logger.exception("Полная информация об ошибке:")
            return 1


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description="Тестирование цепочки Manager → Scanner → БД (DCAP System)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python test_chain.py
  python test_chain.py --path E:\\test_data
  python test_chain.py --path D:\\scans\\folder --manager 192.168.1.100:50051
        """
    )
    
    parser.add_argument(
        '--path',
        type=str,
        default='E:\\test_data',
        help='Путь к папке для сканирования (по умолчанию: E:\\test_data)'
    )
    
    parser.add_argument(
        '--manager',
        type=str,
        default='localhost:50051',
        help='Адрес Manager сервера в формате host:port (по умолчанию: localhost:50051)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Включить отладочный режим логирования'
    )
    
    return parser.parse_args()


def main():
    """Главная функция"""
    # Парсим аргументы
    args = parse_arguments()
    
    # Настройка уровня логирования
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Отладочный режим включен")
    
    # Вывод информации о запуске
    logger.info("=" * 60)
    logger.info("DCAP System - Тестирование цепочки компонентов")
    logger.info(f"Корень проекта: {PROJECT_ROOT}")
    logger.info(f"Путь для сканирования: {args.path}")
    logger.info(f"Адрес Manager: {args.manager}")
    logger.info("=" * 60)
    
    try:
        # Создаем тестер и запускаем
        tester = ChainTester(
            scan_path=args.path,
            manager_address=args.manager
        )
        
        exit_code = tester.run_test()
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.warning("\nТестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске тестера: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()