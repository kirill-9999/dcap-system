#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фабрика построчных коннекторов (день 53.1b, BACKLOG-097).

Регистрирует коннекторы, реализующие интерфейс FilesystemConnector
(scan_path / scan_file). В 53.1b зарегистрирован только filesystem;
S3LineConnector добавится в 53.2.
"""
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger("dcap-scanner")

_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def register_line_connector(source_type: str, factory: Callable[[Dict[str, Any]], Any]) -> None:
    """Зарегистрировать фабрику для source_type ('filesystem', 's3', 'minio')."""
    _REGISTRY[(source_type or "").lower()] = factory
    logger.debug("[Factory] Registered line connector: %s", source_type)


def create_line_connector(source_type: str, config: Dict[str, Any]) -> Any:
    """Создать построчный коннектор по source_type.

    В 53.1b зарегистрирован только 'filesystem'. Для 's3'/'minio' бросаем
    ValueError — S3LineConnector появится в 53.2; главное, чтобы сканер
    упал с понятным сообщением, а не пытался открыть 's3://bucket' как папку.
    """
    st = (source_type or "filesystem").lower()
    if st not in _REGISTRY:
        raise ValueError(
            f"Line connector for source_type={st!r} not registered. "
            f"Available: {sorted(_REGISTRY)}. "
            "S3 support arrives in day 53.2."
        )
    return _REGISTRY[st](config or {})


def registered_types() -> list:
    """Список зарегистрированных source_type (для диагностики/тестов)."""
    return sorted(_REGISTRY)


__all__ = ["register_line_connector", "create_line_connector", "registered_types"]
