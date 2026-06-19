#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Менеджер конфигурации с поддержкой плагинов
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List


class ConfigManager:
    """Менеджер конфигурации с проверкой обязательных параметров"""
    
    REQUIRED_KEYS = ["source_folders", "logs_folder", "state_file", "pipeline"]
    
    def __init__(self, config_path: str = "config.json"):
        if not config_path:
            raise ValueError("Путь к конфигурационному файлу обязателен")
        
        self.config_path = Path(config_path)
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
        
        self.config: Dict[str, Any] = {}
        self._load()
        self._validate()
    
    def _load(self) -> None:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            print(f"[CONFIG] Загружена конфигурация из {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга конфигурации: {e}")
        except Exception as e:
            raise IOError(f"Ошибка чтения конфигурации: {e}")
    
    def _validate(self) -> None:
        """Проверка обязательных параметров"""
        for key in self.REQUIRED_KEYS:
            if key not in self.config:
                raise ValueError(f"Отсутствует обязательный параметр: {key}")
        
        if not self.config["source_folders"]:
            raise ValueError("source_folders не может быть пустым")
        
        if not isinstance(self.config["source_folders"], list):
            raise ValueError("source_folders должен быть списком")
        
        if not self.config.get("pipeline", {}).get("classifiers"):
            raise ValueError("pipeline.classifiers не может быть пустым")
    
    def get(self, key: str, default=None) -> Any:
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def get_sources(self) -> list:
        return self.config.get("source_folders", [])
    
    def get_s3_buckets(self) -> list:
        return self.config.get("s3_buckets", [])
    
    def get_enabled_classifiers(self) -> list:
        """Получение списка включённых классификаторов из pipeline"""
        pipeline = self.config.get("pipeline", {})
        return pipeline.get("classifiers", [])
    
    def get_connector_name(self) -> str:
        """Получение имени коннектора из pipeline"""
        pipeline = self.config.get("pipeline", {})
        return pipeline.get("connector", "filesystem")
    
    def get_handlers(self) -> list:
        """Получение списка обработчиков из pipeline"""
        pipeline = self.config.get("pipeline", {})
        return pipeline.get("handlers", [])
    
    def get_classifier_config(self, name: str) -> dict:
        """
        Получение конфигурации классификатора.
        Поддерживает новую структуру (с вложенным config) и старую (прямые параметры)
        """
        classifiers_section = self.config.get("classifiers", {})
        classifier_config = classifiers_section.get(name, {})
        
        # Новая структура: параметры внутри поля "config"
        if "config" in classifier_config:
            return classifier_config.get("config", {})
        
        # Старая структура: прямые параметры
        return classifier_config
    
    def is_classifier_enabled(self, name: str) -> bool:
        """Проверка, включён ли классификатор"""
        classifiers_section = self.config.get("classifiers", {})
        classifier_config = classifiers_section.get(name, {})
        
        # Новая структура: поле "enabled"
        if "enabled" in classifier_config:
            return classifier_config.get("enabled", True)
        
        # Старая структура: проверяем, есть ли он в pipeline
        return name in self.get_enabled_classifiers()
    
    def get_connector_config(self, name: str) -> dict:
        """
        Получение конфигурации коннектора.
        Поддерживает новую структуру (с вложенным config) и старую (прямые параметры)
        """
        connectors_section = self.config.get("connectors", {})
        connector_config = connectors_section.get(name, {})
        
        # Новая структура: параметры внутри поля "config"
        if "config" in connector_config:
            return connector_config.get("config", {})
        
        # Старая структура: прямые параметры
        return connector_config
    
    def is_connector_enabled(self, name: str) -> bool:
        """Проверка, включён ли коннектор"""
        connectors_section = self.config.get("connectors", {})
        connector_config = connectors_section.get(name, {})
        
        # Новая структура: поле "enabled"
        if "enabled" in connector_config:
            return connector_config.get("enabled", True)
        
        # Старая структура: по умолчанию включён
        return True
    
    def get_handler_config(self, name: str) -> dict:
        """
        Получение конфигурации обработчика.
        Поддерживает новую структуру (с вложенным config) и старую (прямые параметры)
        """
        handlers_section = self.config.get("handlers", {})
        handler_config = handlers_section.get(name, {})
        
        # Новая структура: параметры внутри поля "config"
        if "config" in handler_config:
            return handler_config.get("config", {})
        
        # Старая структура: прямые параметры
        return handler_config
    
    def is_handler_enabled(self, name: str) -> bool:
        """Проверка, включён ли обработчик"""
        handlers_section = self.config.get("handlers", {})
        handler_config = handlers_section.get(name, {})
        
        # Новая структура: поле "enabled"
        if "enabled" in handler_config:
            return handler_config.get("enabled", True)
        
        # Старая структура: проверяем, есть ли он в pipeline
        return name in self.get_handlers()
    
    def get_all_classifier_names(self) -> List[str]:
        """Получение всех имён классификаторов из конфига"""
        classifiers_section = self.config.get("classifiers", {})
        return list(classifiers_section.keys())
    
    def get_all_connector_names(self) -> List[str]:
        """Получение всех имён коннекторов из конфига"""
        connectors_section = self.config.get("connectors", {})
        return list(connectors_section.keys())
    
    def get_all_handler_names(self) -> List[str]:
        """Получение всех имён обработчиков из конфига"""
        handlers_section = self.config.get("handlers", {})
        return list(handlers_section.keys())


__all__ = ['ConfigManager']