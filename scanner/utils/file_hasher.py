#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - File Hasher
SHA-256 хэширование для всех типов файлов
"""

import hashlib
from typing import Optional
from pathlib import Path


class FileHasher:
    """Вычисление SHA-256 хэша для файлов из разных источников"""
    
    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """Вычисление хэша из байтов"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def hash_file(file_path: Path, chunk_size: int = 8192) -> Optional[str]:
        """
        Вычисление SHA-256 хэша для локального файла
        Читает файл по частям для экономии памяти
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None
    
    @staticmethod
    def hash_s3_object(client, bucket: str, key: str) -> Optional[str]:
        """
        Вычисление SHA-256 хэша для S3 объекта
        Скачивает и хэширует по частям
        """
        try:
            sha256 = hashlib.sha256()
            response = client.get_object(Bucket=bucket, Key=key)
            for chunk in response['Body'].iter_chunks(chunk_size=8192):
                sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None