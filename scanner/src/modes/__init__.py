"""Режимы работы Scanner"""

from scanner.src.modes.base import ScannerMode
from scanner.src.modes.standalone import StandaloneMode
from scanner.src.modes.managed import ManagedMode
from scanner.src.modes.hybrid import HybridMode

__all__ = ['ScannerMode', 'StandaloneMode', 'ManagedMode', 'HybridMode']