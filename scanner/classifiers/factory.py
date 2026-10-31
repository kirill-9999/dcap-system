#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фабрика классификаторов с ленивой инициализацией (53.4m, v3.14.11).

Зачем: классификаторы — синглтоны с загруженными spaCy/Presidio-моделями,
они не picklable. Для ProcessPoolExecutor нельзя передать экземпляры из
родительского процесса в воркеры (Windows/spawn). Вместо этого передаётся
сериализуемый spec (имя + конфиг), а воркер создаёт классификатор лениво,
при первом файле, и кеширует его на процесс.
"""
from __future__ import annotations

import importlib
import threading
from typing import Any, Dict, List, Optional

# имя классификатора -> (модуль, класс)
_REGISTRY: Dict[str, tuple] = {
    "pii_classifier": ("scanner.classifiers.pii_classifier", "PiiClassifier"),
    "credentials_classifier": (
        "scanner.classifiers.credentials_classifier",
        "CredentialsClassifier",
    ),
    "code_classifier": ("scanner.classifiers.code_classifier", "CodeClassifier"),
}

_CLASS_TO_NAME = {
    "PiiClassifier": "pii_classifier",
    "CredentialsClassifier": "credentials_classifier",
    "CodeClassifier": "code_classifier",
}

# Кеш на процесс: в дочернем процессе модуль импортируется заново,
# поэтому кеш пустой и модели грузятся здесь, а не копируются из родителя.
_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.Lock()


def classifier_spec(classifier: Any) -> Optional[Dict[str, Any]]:
    """Сериализуемое описание классификатора: {"name": ..., "config": {...}}.

    Возвращает None, если классификатор неизвестен или его конфиг не
    сериализуется (тогда коннектор откатывается на thread-режим).
    """
    name = getattr(classifier, "classifier_name", None)
    if name not in _REGISTRY:
        name = _CLASS_TO_NAME.get(type(classifier).__name__)
    if name not in _REGISTRY:
        return None

    config = getattr(classifier, "config", None)
    if config is None:
        config = {}
    if not isinstance(config, dict):
        return None
    config = dict(config)

    try:
        import pickle

        pickle.dumps({"name": name, "config": config})
    except Exception:
        return None

    return {"name": name, "config": config}


def classifier_specs(classifiers: Optional[List[Any]]) -> Optional[List[Dict[str, Any]]]:
    """Список picklable spec'ов для всех классификаторов (None — не вышло)."""
    if not classifiers:
        return []
    specs: List[Dict[str, Any]] = []
    for classifier in classifiers:
        spec = classifier_spec(classifier)
        if spec is None:
            return None
        specs.append(spec)
    return specs


def get_classifier(name: str, config: Optional[Dict[str, Any]] = None) -> Any:
    """Вернуть классификатор по имени; кеш на процесс (53.4m)."""
    with _CACHE_LOCK:
        instance = _CACHE.get(name)
    if instance is not None:
        return instance

    entry = _REGISTRY.get(name)
    if entry is None:
        raise ValueError("Неизвестный классификатор: %s" % name)
    module_name, class_name = entry
    cls = getattr(importlib.import_module(module_name), class_name)

    instance = cls()
    if config is not None:
        instance.configure(dict(config))

    with _CACHE_LOCK:
        existing = _CACHE.get(name)
        if existing is not None:
            return existing
        _CACHE[name] = instance
    return instance


def build_classifiers(specs: Optional[List[Dict[str, Any]]]) -> List[Any]:
    """Создать классификаторы из spec'ов (лениво, с кешем на процесс)."""
    if not specs:
        return []
    result: List[Any] = []
    for spec in specs:
        name = spec.get("name")
        if not name:
            continue
        result.append(get_classifier(name, spec.get("config") or {}))
    return result


def worker_specs(specs: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Spec'ы для процесс-воркеров (53.4m).

    В воркере один поток на процесс, поэтому пул Presidio-анализаторов
    ограничиваем 1 (память) и не поднимаем OCRWorker PII-классификатора
    (OCR изображений в построчном пути идёт через DocumentExtractor
    коннектора, см. _text_scanner.extract_document_text).
    """
    if specs is None:
        return None
    result: List[Dict[str, Any]] = []
    for spec in specs:
        cfg = dict(spec.get("config") or {})
        if spec.get("name") == "pii_classifier":
            cfg["analyzer_pool_size"] = 1
            cfg["start_ocr_worker"] = False
        result.append({"name": spec.get("name"), "config": cfg})
    return result


__all__ = [
    "get_classifier",
    "build_classifiers",
    "classifier_spec",
    "classifier_specs",
    "worker_specs",
]
