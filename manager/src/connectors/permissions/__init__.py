# manager/src/connectors/permissions/__init__.py

from .base import PermissionCollector
from .local import LocalPermissionCollector
from .ad import ADPermissionCollector
from .remote import RemotePermissionCollector
from .factory import PermissionCollectorFactory

__all__ = [
    'PermissionCollector',
    'LocalPermissionCollector',
    'ADPermissionCollector',
    'RemotePermissionCollector',
    'PermissionCollectorFactory',
]