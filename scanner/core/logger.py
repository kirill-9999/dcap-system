#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Логирование
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class AgentLogger:
    """Логгер агента - только консоль и основной лог"""
    
    def __init__(self, log_dir: str = None):
        if not log_dir:
            raise ValueError("log_dir обязателен")
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger("dcap_agent")
        self.logger.setLevel(logging.INFO)
        
        # Только консольный вывод
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(console_handler)
    
    def info(self, message: str) -> None:
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        self.logger.error(message)
    
    def debug(self, message: str) -> None:
        self.logger.debug(message)