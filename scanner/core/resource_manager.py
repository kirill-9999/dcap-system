#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Менеджер ресурсов
Управляет распределением ресурсов между классификаторами
"""

import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ResourceRequirements:
    """Требования к ресурсам"""
    memory_mb: int = 0
    cpu_cores: int = 1
    gpu_memory_mb: int = 0
    models: List[str] = None


class ResourceManager:
    """Менеджер ресурсов"""
    
    def __init__(self, total_memory_mb: int = 8192):
        self.total_memory_mb = total_memory_mb
        self.allocated_memory_mb = 0
        self.lock = threading.Lock()
        self.classifier_resources: Dict[str, ResourceRequirements] = {}
    
    def register_classifier(self, name: str, requirements: ResourceRequirements) -> bool:
        """Регистрация классификатора с его требованиями"""
        with self.lock:
            if self.allocated_memory_mb + requirements.memory_mb <= self.total_memory_mb:
                self.classifier_resources[name] = requirements
                self.allocated_memory_mb += requirements.memory_mb
                return True
            return False
    
    def unregister_classifier(self, name: str) -> None:
        """Удаление классификатора"""
        with self.lock:
            if name in self.classifier_resources:
                self.allocated_memory_mb -= self.classifier_resources[name].memory_mb
                del self.classifier_resources[name]
    
    def can_allocate(self, memory_mb: int) -> bool:
        """Проверка возможности выделения памяти"""
        with self.lock:
            return self.allocated_memory_mb + memory_mb <= self.total_memory_mb
    
    def get_available_memory(self) -> int:
        """Получение доступной памяти"""
        with self.lock:
            return self.total_memory_mb - self.allocated_memory_mb
    
    def get_usage_report(self) -> Dict[str, Any]:
        """Отчёт об использовании ресурсов"""
        return {
            "total_memory_mb": self.total_memory_mb,
            "allocated_memory_mb": self.allocated_memory_mb,
            "available_memory_mb": self.total_memory_mb - self.allocated_memory_mb,
            "classifiers": {
                name: {
                    "memory_mb": req.memory_mb,
                    "models": req.models
                }
                for name, req in self.classifier_resources.items()
            }
        }