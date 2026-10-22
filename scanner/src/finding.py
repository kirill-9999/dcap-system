#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель находки в сканере.

Находка = конкретное совпадение в строке файла (или фрагменте).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Finding:
    """Находка в сканере (до шифрования)."""
    # Где найдено
    line_number: int
    line_text: str
    match_text: str
    start_pos: int
    end_pos: int

    # Классификация
    finding_type: str          # pii, credentials, code
    category: str              # phone, email, api_key
    severity: str = "medium"

    # Метаданные
    confidence: float = 0.0
    detector: str = "regex"    # presidio, regex, entropy, ocr

    # Контекст
    context_before: str = ""
    context_after: str = ""

    # Для не-текстовых (заполняется позже)
    fragment_type: str = "text_line"
    fragment_path: Optional[str] = None
    bounding_box: Optional[dict] = None
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None
    hex_preview: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # 53.4l: locations[] и др.

    def to_dict(self) -> dict:
        """Для сериализации (без шифрования — оно позже)."""
        return {
            "line_number": self.line_number,
            "line_text": self.line_text,
            "match_text": self.match_text,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "finding_type": self.finding_type,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "detector": self.detector,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "fragment_type": self.fragment_type,
            "fragment_path": self.fragment_path,
            "bounding_box": self.bounding_box,
            "byte_offset": self.byte_offset,
            "byte_length": self.byte_length,
            "hex_preview": self.hex_preview,
            "metadata": self.metadata,
        }


__all__ = ["Finding"]
