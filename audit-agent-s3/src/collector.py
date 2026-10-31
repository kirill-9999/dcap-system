# audit-agent-s3/src/collector.py
import csv
import json
import time
import logging
from io import StringIO
from typing import List, Optional

import boto3
import botocore.exceptions

from .converters import s3_log_to_unified
from .state import StateManager
from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)


class S3LogCollector:
    """S3/MinIO лог-коллектор (polling-режим).

    Опрашивает бакет, скачивает логи (CSV/JSON), конвертирует в UnifiedEvent
    и отслеживает прогресс через StateManager (last_processed).
    """

    def __init__(self, config: dict):
        self.config = config
        self.s3_config = config["s3"]

        self.endpoint = self.s3_config.get("endpoint", "https://s3.amazonaws.com")
        self.bucket = self.s3_config["bucket"]
        self.prefix = self.s3_config.get("prefix", "access-logs/")
        self.poll_interval = int(self.s3_config.get("poll_interval", 60))
        self.source_type = self.s3_config.get("source_type", "s3")
        self.verify_ssl = self.s3_config.get("verify_ssl", True)

        self.state = StateManager(state_dir=self.config.get("state_dir", "data/state"))
        self.last_processed = self.state.get_last_processed()
        self.running = False

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.s3_config.get("access_key"),
            aws_secret_access_key=self.s3_config.get("secret_key"),
            verify=self.verify_ssl,
        )

        logger.info(
            f"S3LogCollector initialized: bucket={self.bucket}, prefix={self.prefix}"
        )

    def poll(self) -> List[UnifiedEvent]:
        """Опрос новых логов с обработкой throttling и крайних случаев."""
        self.running = True
        events: List[UnifiedEvent] = []

        # Проверка существования бакета
        if not self._bucket_exists():
            logger.error(f"Bucket {self.bucket} does not exist")
            return []

        # Проверка прав доступа
        if not self._has_read_access():
            logger.error(f"No read access to bucket {self.bucket}")
            return []

        try:
            kwargs = {"Bucket": self.bucket, "Prefix": self.prefix}
            if self.last_processed:
                kwargs["StartAfter"] = self.last_processed

            response = self.s3_client.list_objects_v2(**kwargs)

            # Проверка на throttling (service temporarily unavailable)
            if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 503:
                logger.warning("S3 throttling detected, waiting 30s...")
                time.sleep(30)
                return []

            objects = response.get("Contents", [])
            logger.debug(f"Found {len(objects)} log files")

            # Ограничение количества обрабатываемых файлов за одну итерацию
            max_files_per_poll = int(
                self.s3_config.get("max_files_per_poll", 100)
            )
            if len(objects) > max_files_per_poll:
                logger.warning(
                    f"Too many files ({len(objects)}), limiting to {max_files_per_poll}"
                )
                objects = objects[:max_files_per_poll]

            for obj in sorted(objects, key=lambda x: x["LastModified"]):
                if obj["Key"] == self.last_processed:
                    continue

                logger.info(f"Processing: {obj['Key']}")

                try:
                    log_data = self.s3_client.get_object(
                        Bucket=self.bucket,
                        Key=obj["Key"],
                    )["Body"].read().decode("utf-8")

                    if obj["Key"].endswith(".csv"):
                        records = self._parse_csv(log_data)
                    elif obj["Key"].endswith(".json"):
                        records = self._parse_json(log_data)
                    else:
                        logger.warning(f"Unknown format: {obj['Key']}")
                        continue

                    for record in records:
                        if not isinstance(record, dict):
                            continue
                        event = s3_log_to_unified(record, self.source_type)
                        if event:
                            event.metadata["log_file"] = obj["Key"]
                            events.append(event)

                    self.last_processed = obj["Key"]
                    self.state.set_last_processed(self.last_processed)

                except Exception as e:
                    logger.error(f"Error processing {obj['Key']}: {e}")

        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "SlowDown":
                logger.warning("S3 SlowDown error, waiting 60s...")
                time.sleep(60)
            elif error_code == "NoSuchBucket":
                logger.error(f"Bucket {self.bucket} does not exist")
                raise
            else:
                logger.error(f"S3 error ({error_code}): {e}")
                raise
        except Exception as e:
            logger.error(f"Error in poll: {e}")

        return events

    def _bucket_exists(self) -> bool:
        """Проверка существования бакета."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                return False
            logger.debug(f"head_bucket check error ({error_code}): {e}")
            raise
        except Exception as e:
            logger.debug(f"head_bucket check error: {e}")
            raise

    def _has_read_access(self) -> bool:
        """Проверка прав на чтение бакета."""
        try:
            self.s3_client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDenied", "403"):
                return False
            logger.debug(f"read access check error ({error_code}): {e}")
            raise
        except Exception as e:
            logger.debug(f"read access check error: {e}")
            raise

    def _parse_csv(self, content: str) -> List[dict]:
        """Парсинг CSV логов."""
        try:
            reader = csv.DictReader(StringIO(content))
            return list(reader)
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            return []

    def _parse_json(self, content: str) -> List[dict]:
        """Парсинг JSON логов (MinIO)."""
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            return data.get("Records", [data]) if isinstance(data, dict) else []
        except Exception as e:
            logger.error(f"JSON parse error: {e}")
            return []

    def stop(self):
        """Остановка коллектора."""
        self.running = False
        logger.info("Collector stopped")
