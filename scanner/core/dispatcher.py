#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Диспетчер модулей с динамической загрузкой
"""

import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type

from core.base import IClassifier, ISourceConnector, IOutputHandler


class ModuleDispatcher:
    """Диспетчер модулей с автоматическим обнаружением"""
    
    def __init__(self):
        self.classifiers: Dict[str, IClassifier] = {}
        self.connectors: Dict[str, ISourceConnector] = {}
        self.handlers: Dict[str, IOutputHandler] = {}
        
        # Автоматическое обнаружение всех модулей
        self._discover_all()
    
    def _discover_all(self) -> None:
        """Обнаружение всех модулей во всех директориях"""
        self._discover_classifiers()
        self._discover_connectors()
        self._discover_handlers()
    
    def _is_abstract_class(self, cls) -> bool:
        """Проверка, является ли класс абстрактным"""
        return inspect.isabstract(cls)
    
    def _discover_classifiers(self) -> None:
        """Автоматическое обнаружение всех классификаторов в папке classifiers/"""
        classifiers_dir = Path(__file__).parent.parent / "classifiers"
        
        if not classifiers_dir.exists():
            print(f"[DISPATCHER] Директория классификаторов не найдена: {classifiers_dir}")
            return
        
        for file_path in classifiers_dir.glob("*.py"):
            # Пропускаем base.py и __init__.py
            if file_path.name in ['base.py', '__init__.py']:
                continue
            
            module_name = file_path.stem
            try:
                # Импортируем модуль
                module = importlib.import_module(f"classifiers.{module_name}")
                
                # Ищем классы, наследующие IClassifier
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, IClassifier) and 
                        attr is not IClassifier and
                        not self._is_abstract_class(attr)):
                        
                        # Создаём экземпляр
                        try:
                            instance = attr()
                            key = instance.classifier_name
                            # Проверяем, не дублируется ли ключ
                            if key not in self.classifiers:
                                self.classifiers[key] = instance
                                print(f"[DISPATCHER] Загружен классификатор: {key} (из {module_name}.py)")
                            else:
                                print(f"[DISPATCHER] Классификатор {key} уже загружен, пропускаем дубликат из {module_name}.py")
                        except TypeError as e:
                            # Класс может требовать аргументы
                            print(f"[DISPATCHER] Пропущен {attr_name} из {module_name}.py: {e}")
                        
            except Exception as e:
                print(f"[DISPATCHER] Ошибка загрузки классификатора {module_name}: {e}")
        
        if self.classifiers:
            print(f"[DISPATCHER] Всего загружено классификаторов: {len(self.classifiers)}")
        else:
            print(f"[DISPATCHER] ⚠️ Классификаторы не найдены")
    
    def _discover_connectors(self) -> None:
        """Автоматическое обнаружение всех коннекторов в папке connectors/"""
        connectors_dir = Path(__file__).parent.parent / "connectors"
        
        if not connectors_dir.exists():
            print(f"[DISPATCHER] Директория коннекторов не найдена: {connectors_dir}")
            return
        
        for file_path in connectors_dir.glob("*.py"):
            # Пропускаем base.py и __init__.py
            if file_path.name in ['base.py', '__init__.py']:
                continue
            
            module_name = file_path.stem
            try:
                # Импортируем модуль
                module = importlib.import_module(f"connectors.{module_name}")
                
                # Ищем классы, наследующие ISourceConnector
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ISourceConnector) and 
                        attr is not ISourceConnector and
                        not self._is_abstract_class(attr)):
                        
                        # Создаём экземпляр
                        try:
                            instance = attr()
                            key = instance.connector_type.value
                            if key not in self.connectors:
                                self.connectors[key] = instance
                                print(f"[DISPATCHER] Загружен коннектор: {key} (из {module_name}.py)")
                            else:
                                print(f"[DISPATCHER] Коннектор {key} уже загружен, пропускаем дубликат из {module_name}.py")
                        except TypeError as e:
                            print(f"[DISPATCHER] Пропущен {attr_name} из {module_name}.py: {e}")
                        
            except Exception as e:
                print(f"[DISPATCHER] Ошибка загрузки коннектора {module_name}: {e}")
        
        if self.connectors:
            print(f"[DISPATCHER] Всего загружено коннекторов: {len(self.connectors)}")
    
    def _discover_handlers(self) -> None:
        """Автоматическое обнаружение всех обработчиков в папке handlers/"""
        handlers_dir = Path(__file__).parent.parent / "handlers"
        
        if not handlers_dir.exists():
            print(f"[DISPATCHER] Директория обработчиков не найдена: {handlers_dir}")
            return
        
        for file_path in handlers_dir.glob("*.py"):
            # Пропускаем base.py и __init__.py
            if file_path.name in ['base.py', '__init__.py']:
                continue
            
            module_name = file_path.stem
            try:
                # Импортируем модуль
                module = importlib.import_module(f"handlers.{module_name}")
                
                # Ищем классы, наследующие IOutputHandler
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, IOutputHandler) and 
                        attr is not IOutputHandler and
                        not self._is_abstract_class(attr)):
                        
                        # Создаём экземпляр
                        try:
                            instance = attr()
                            key = instance.handler_name
                            if key not in self.handlers:
                                self.handlers[key] = instance
                                print(f"[DISPATCHER] Загружен обработчик: {key} (из {module_name}.py)")
                            else:
                                print(f"[DISPATCHER] Обработчик {key} уже загружен, пропускаем дубликат из {module_name}.py")
                        except TypeError as e:
                            print(f"[DISPATCHER] Пропущен {attr_name} из {module_name}.py: {e}")
                        
            except Exception as e:
                print(f"[DISPATCHER] Ошибка загрузки обработчика {module_name}: {e}")
        
        if self.handlers:
            print(f"[DISPATCHER] Всего загружено обработчиков: {len(self.handlers)}")
    
    def get_classifier(self, name: str) -> Optional[IClassifier]:
        """Получение классификатора по имени"""
        return self.classifiers.get(name)
    
    def get_connector(self, name: str) -> Optional[ISourceConnector]:
        """Получение коннектора по имени"""
        return self.connectors.get(name)
    
    def get_handler(self, name: str) -> Optional[IOutputHandler]:
        """Получение обработчика по имени"""
        return self.handlers.get(name)
    
    def get_all_classifiers(self) -> List[IClassifier]:
        """Получение всех классификаторов"""
        return list(self.classifiers.values())
    
    def get_enabled_classifiers(self, enabled_names: List[str]) -> List[IClassifier]:
        """Получение только включённых классификаторов"""
        result = []
        for name in enabled_names:
            classifier = self.get_classifier(name)
            if classifier:
                result.append(classifier)
        return result
    
    def reload_classifier(self, name: str) -> bool:
        """Перезагрузка конкретного классификатора"""
        if name in self.classifiers:
            try:
                self.classifiers[name].reload_models()
                return True
            except Exception as e:
                print(f"[DISPATCHER] Ошибка перезагрузки {name}: {e}")
                return False
        return False


__all__ = ['ModuleDispatcher']