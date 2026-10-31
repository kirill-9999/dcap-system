# manager/src/connectors/audit/__init__.py
"""Коллекторы событий аудита (Windows Event Log)"""

from manager.src.connectors.audit.windows_audit import WindowsAuditCollector

__all__ = ["WindowsAuditCollector"]
