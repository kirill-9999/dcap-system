# audit-agent-s3/src/converters.py
import logging
from datetime import datetime
from typing import Optional

from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)


def s3_log_to_unified(record: dict, source_type: str = "s3") -> Optional[UnifiedEvent]:
    """Конвертация S3/MinIO лога в UnifiedEvent.

    Поддерживает:
    - S3 Server Access Logs (CSV-словарь)
    - MinIO Audit Logs (JSON): {"eventName": ...} или {"Records": [...]}
    """
    try:
        if "bucket" in record and "key" in record and "operation" in record:
            return _s3_access_log_to_unified(record, source_type)
        elif "eventName" in record or "EventName" in record:
            return _minio_webhook_to_unified(record, source_type)
        elif "Records" in record and record["Records"]:
            return _minio_webhook_to_unified(record["Records"][0], source_type)
        else:
            logger.warning(f"Unknown log format: {list(record.keys())}")
            return None
    except Exception as e:
        logger.error(f"Error converting record: {e}")
        return None


def _s3_access_log_to_unified(record: dict, source_type: str = "s3") -> Optional[UnifiedEvent]:
    """S3 Server Access Log -> UnifiedEvent."""
    try:
        bucket = record.get("bucket", record.get("bucket_name", ""))
        key = record.get("key", record.get("object_key", ""))
        operation = record.get("operation", record.get("op", "UNKNOWN"))
        user = record.get("requester", record.get("user", "")) or "anonymous"
        remote_ip = record.get("remote_ip", record.get("source_ip", ""))
        object_size = record.get("object_size", record.get("bytes_sent", 0))
        http_status = record.get("http_status", record.get("status", 200))
        timestamp = record.get("time", record.get("timestamp", None))

        event_type_map = {
            "REST.GET.OBJECT": "read",
            "REST.HEAD.OBJECT": "read",
            "REST.GET.LOGGING": "read",
            "REST.PUT.OBJECT": "write",
            "REST.POST.OBJECT": "write",
            "REST.COPY.OBJECT": "write",
            "REST.MULTIPART": "write",
            "REST.PUT.LOGGING": "write",
            "REST.DELETE.OBJECT": "delete",
        }

        event_type = event_type_map.get(operation, "unknown")

        return UnifiedEvent(
            event_type=event_type,
            event_source="s3_agent",
            user=str(user),
            file_path=f"s3://{bucket}/{key}" if key else f"s3://{bucket}",
            source_host=remote_ip or None,
            metadata={
                "bucket": bucket or None,
                "key": key or None,
                "operation": operation,
                "object_size": object_size,
                "http_status": http_status,
                "source": source_type,
            },
            created_at=_parse_timestamp(timestamp),
        )
    except Exception as e:
        logger.error(f"Error converting S3 log: {e}")
        return None


def _minio_webhook_to_unified(record: dict, source_type: str = "minio") -> Optional[UnifiedEvent]:
    """MinIO Webhook -> UnifiedEvent."""
    try:
        event_name = record.get("eventName", record.get("EventName", ""))
        bucket = ""
        key = ""
        if isinstance(record.get("bucket"), dict):
            bucket = record["bucket"].get("name", "")
        elif "bucket" in record:
            bucket = str(record.get("bucket", ""))
        if isinstance(record.get("object"), dict):
            key = record["object"].get("key", "")
        user = record.get("userIdentity", {}).get("principalId", "anonymous")
        remote_ip = ""
        if isinstance(record.get("source"), dict):
            remote_ip = record["source"].get("host", "")
        timestamp = record.get("eventTime", record.get("time", None))

        event_type_map = {
            "s3:ObjectCreated": "write",
            "s3:ObjectCreated:Put": "write",
            "s3:ObjectCreated:Post": "write",
            "s3:ObjectCreated:Copy": "write",
            "s3:ObjectCreated:CompleteMultipartUpload": "write",
            "s3:ObjectRemoved": "delete",
            "s3:ObjectRemoved:Delete": "delete",
            "s3:ObjectAccessed": "read",
            "s3:ObjectAccessed:Get": "read",
            "s3:ObjectAccessed:Head": "read",
        }

        event_type = event_type_map.get(event_name, "unknown")

        return UnifiedEvent(
            event_type=event_type,
            event_source="s3_agent",
            user=str(user),
            file_path=f"s3://{bucket}/{key}" if key else f"s3://{bucket}",
            source_host=remote_ip or None,
            metadata={
                "bucket": bucket or None,
                "key": key or None,
                "event_name": event_name,
                "source": source_type,
            },
            created_at=_parse_timestamp(timestamp),
        )
    except Exception as e:
        logger.error(f"Error converting MinIO log: {e}")
        return None


def _parse_timestamp(ts) -> Optional[str]:
    """Парсинг timestamp из разных форматов, возврат ISO-строки."""
    if ts is None or ts == "":
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    ts = str(ts)
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%b %d %H:%M:%S %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt).isoformat()
        except ValueError:
            continue
    logger.debug(f"Unparsable timestamp: {ts!r}, using None")
    return None
