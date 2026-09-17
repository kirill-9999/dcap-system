#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - S3/MinIO Connector
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterator, Optional

from core.base import SourceType, FileContext
from connectors.base import BaseConnector

try:
    import boto3
    from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
    from botocore.config import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class S3Connector(BaseConnector):
    def __init__(self):
        super().__init__()
        self.client = None
        self.endpoint = None
        self.bucket = None
        self.access_key = None
        self.secret_key = None
        self.secure = None
        self.use_path_style = None
        self._extensions = None
        self._max_file_size_mb = None
        self._recursive = None
    
    @property
    def connector_type(self) -> SourceType:
        return SourceType.S3
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Настройка коннектора для S3/MinIO"""
        super().configure(config)
        
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 не установлен. Установите: pip install boto3")
        
        # Все параметры ТОЛЬКО из конфига
        self.endpoint = config.get("endpoint")
        self.bucket = config.get("bucket")
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
        self.secure = config.get("secure")
        self.use_path_style = config.get("use_path_style")
        self._extensions = config.get("extensions")
        self._max_file_size_mb = config.get("max_file_size_mb")
        self._recursive = config.get("recursive")
        
        # Проверка обязательных параметров
        if self.endpoint is None:
            raise ValueError("S3 connector: параметр 'endpoint' обязателен")
        if self.bucket is None:
            raise ValueError("S3 connector: параметр 'bucket' обязателен")
        if self.access_key is None:
            raise ValueError("S3 connector: параметр 'access_key' обязателен")
        if self.secret_key is None:
            raise ValueError("S3 connector: параметр 'secret_key' обязателен")
        if self.secure is None:
            raise ValueError("S3 connector: параметр 'secure' обязателен (true/false)")
        if self.use_path_style is None:
            raise ValueError("S3 connector: параметр 'use_path_style' обязателен (true/false)")
        if self._extensions is None:
            raise ValueError("S3 connector: параметр 'extensions' обязателен")
        if self._max_file_size_mb is None:
            raise ValueError("S3 connector: параметр 'max_file_size_mb' обязателен")
        
        # Формируем endpoint URL
        protocol = "https" if self.secure else "http"
        endpoint_url = f"{protocol}://{self.endpoint}"
        
        # Настройка клиента
        s3_config = Config(
            s3={
                'addressing_style': 'path' if self.use_path_style else 'virtual'
            },
            connect_timeout=30,
            read_timeout=60,
            retries={
                'max_attempts': 3,
                'mode': 'standard'
            }
        )
        
        print(f"[S3] Коннектор настроен:")
        print(f"   Endpoint: {endpoint_url}")
        print(f"   Bucket: {self.bucket}")
        print(f"   Path-style: {self.use_path_style}")
        print(f"   Secure: {self.secure}")
        print(f"   Extensions: {self._extensions}")
        print(f"   Max file size: {self._max_file_size_mb} MB")
        
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=s3_config,
                verify=False if not self.secure else True
            )
            
            # Проверяем подключение
            self.client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
            print(f"[S3] [OK] Подключено успешно")
            
        except ConnectTimeoutError as e:
            print(f"[S3] [ERROR] Таймаут подключения к {endpoint_url}")
            print(f"[S3] Проверьте доступность сервера {self.endpoint}")
            self.client = None
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidAccessKeyId':
                print(f"[S3] [ERROR] Неверный Access Key")
            elif error_code == 'SignatureDoesNotMatch':
                print(f"[S3] [ERROR] Неверный Secret Key")
            elif error_code == 'NoSuchBucket':
                print(f"[S3] [ERROR] Бакет не найден: {self.bucket}")
            elif error_code == 'AccessDenied':
                print(f"[S3] [ERROR] Доступ запрещен к бакету {self.bucket}")
            else:
                print(f"[S3] [ERROR] Ошибка: {error_code}")
            self.client = None
        except Exception as e:
            print(f"[S3] [ERROR] Ошибка подключения: {e}")
            self.client = None
    
    def test_connection(self) -> bool:
        """Тестирование подключения к S3/MinIO"""
        if not self.client:
            return False
        
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except:
            return False
    
    def list_files(self, source: str) -> Iterator[FileContext]:
        """Получение списка файлов из бакета"""
        if not self.client:
            print(f"[S3] Клиент не инициализирован. Пропуск сканирования")
            return
        
        bucket = source if source else self.bucket
        
        if not bucket:
            print(f"[S3] Бакет не указан")
            return
        
        print(f"[S3] Сканирование бакета: {bucket}")
        
        try:
            continuation_token = None
            total_objects = 0
            filtered_objects = 0
            
            while True:
                params = {
                    'Bucket': bucket,
                    'MaxKeys': 1000
                }
                
                if continuation_token:
                    params['ContinuationToken'] = continuation_token
                
                response = self.client.list_objects_v2(**params)
                
                if 'Contents' not in response:
                    break
                
                for obj in response['Contents']:
                    total_objects += 1
                    key = obj['Key']
                    size_bytes = obj['Size']
                    last_modified = obj['LastModified']
                    
                    if key.endswith('/'):
                        continue
                    
                    ext = Path(key).suffix.lower().lstrip('.')
                    if ext not in self._extensions:
                        continue
                    
                    size_mb = size_bytes / (1024 * 1024)
                    if size_mb > self._max_file_size_mb:
                        continue
                    
                    filtered_objects += 1
                    
                    yield FileContext(
                        id=f"s3://{bucket}/{key}",
                        path=key,
                        source_type=SourceType.S3,
                        size_bytes=size_bytes,
                        modified_time=last_modified,
                        bucket=bucket,
                        key=key,
                        endpoint=self.endpoint,
                        metadata={
                            "etag": obj.get('ETag', '').strip('"'),
                            "storage_class": obj.get('StorageClass', 'STANDARD')
                        }
                    )
                
                if not response.get('IsTruncated', False):
                    break
                
                continuation_token = response.get('NextContinuationToken')
            
            print(f"[S3] Бакет '{bucket}': найдено {total_objects} объектов, отфильтровано {filtered_objects} файлов")
            
        except Exception as e:
            print(f"[S3] [ERROR] Ошибка при сканировании: {e}")
    
    def get_content(self, file_context: FileContext) -> Optional[FileContext]:
        """Загрузка содержимого файла"""
        if not self.client:
            return None
        
        try:
            response = self.client.get_object(
                Bucket=file_context.bucket,
                Key=file_context.key
            )
            
            file_context.content = response['Body'].read()
            response['Body'].close()
            
            return file_context
            
        except Exception as e:
            print(f"[S3] Ошибка загрузки {file_context.key}: {e}")
            return None


__all__ = ['S3Connector']