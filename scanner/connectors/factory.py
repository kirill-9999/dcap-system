#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фабрика построчных коннекторов (день 53.1b / 53.2, BACKLOG-097).

Регистрирует коннекторы, реализующие интерфейс FilesystemConnector
(scan_path / scan_file). Зарегистрированы: filesystem (53.1b),
s3 и minio (53.2, S3LineConnector).
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

    День 53.2 (BACKLOG-097): зарегистрированы 's3' и 'minio' → S3LineConnector.
    Неизвестный source_type по-прежнему даёт понятный ValueError со списком
    доступных — сканер упадёт с сообщением, а не откроет 's3://bucket' как папку.
    """
    st = (source_type or "filesystem").lower()
    if st not in _REGISTRY:
        raise ValueError(
            f"Line connector for source_type={st!r} not registered. "
            f"Available: {sorted(_REGISTRY)}."
        )
    return _REGISTRY[st](config or {})


def registered_types() -> list:
    """Список зарегистрированных source_type (для диагностики/тестов)."""
    return sorted(_REGISTRY)


__all__ = ["register_line_connector", "create_line_connector", "registered_types"]


# Регистрация S3/MinIO (день 53.2, BACKLOG-097).
# s3_line_connector не импортирует factory — циклических импортов нет.
from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402

register_line_connector("s3", lambda cfg: S3LineConnector(cfg))
register_line_connector("minio", lambda cfg: S3LineConnector(cfg))
