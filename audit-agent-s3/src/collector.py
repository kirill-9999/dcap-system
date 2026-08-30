# audit-agent-s3/src/collector.py
import csv
import json
import logging
from io import StringIO
from typing import List, Optional

import boto3

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
        """Опрос новых логов."""
        self.running = True
        events: List[UnifiedEvent] = []

        try:
            kwargs = {"Bucket": self.bucket, "Prefix": self.prefix}
            if self.last_processed:
                kwargs["StartAfter"] = self.last_processed

            response = self.s3_client.list_objects_v2(**kwargs)
            objects = response.get("Contents", [])
            logger.debug(f"Found {len(objects)} log files")

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

        except Exception as e:
            logger.error(f"Error in poll: {e}")

        return events

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
