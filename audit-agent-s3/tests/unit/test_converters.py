# audit-agent-s3/tests/unit/test_converters.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.converters import s3_log_to_unified


def test_s3_access_log_get():
    record = {
        "bucket": "audit-bucket",
        "key": "reports/2026.docx",
        "operation": "REST.GET.OBJECT",
        "requester": "user1",
        "remote_ip": "10.0.0.5",
        "object_size": 2048,
        "http_status": 200,
        "time": "2026-08-31T10:00:00.000Z",
    }
    event = s3_log_to_unified(record, "s3")
    assert event is not None
    assert event.event_type == "read"
    assert event.event_source == "s3_agent"
    assert event.user == "user1"
    assert event.file_path == "s3://audit-bucket/reports/2026.docx"
    assert event.source_host == "10.0.0.5"
    assert event.metadata["operation"] == "REST.GET.OBJECT"


def test_s3_access_log_put_delete():
    put = s3_log_to_unified({
        "bucket": "b", "key": "k.txt", "operation": "REST.PUT.OBJECT",
        "requester": "u", "time": "2026-08-31 10:00:00",
    }, "s3")
    assert put is not None and put.event_type == "write"

    d = s3_log_to_unified({
        "bucket": "b", "key": "k.txt", "operation": "REST.DELETE.OBJECT",
        "requester": "u", "time": "2026-08-31 10:00:00",
    }, "s3")
    assert d is not None and d.event_type == "delete"


def test_s3_unknown_operation():
    e = s3_log_to_unified({
        "bucket": "b", "key": "k", "operation": "REST.WEIRD.OP",
        "time": "2026-08-31 10:00:00",
    }, "s3")
    assert e is not None and e.event_type == "unknown"


def test_minio_webhook():
    record = {
        "eventName": "s3:ObjectCreated:Put",
        "bucket": {"name": "minio-bucket"},
        "object": {"key": "files/a.csv"},
        "userIdentity": {"principalId": "minio-user"},
        "source": {"host": "192.168.1.10"},
        "eventTime": "2026-08-31T12:00:00.000Z",
    }
    e = s3_log_to_unified(record, "minio")
    assert e is not None
    assert e.event_type == "write"
    assert e.event_source == "s3_agent"
    assert e.user == "minio-user"
    assert e.file_path == "s3://minio-bucket/files/a.csv"
    assert e.metadata["event_name"] == "s3:ObjectCreated:Put"


def test_minio_records_wrap():
    payload = {
        "Records": [{
            "eventName": "s3:ObjectRemoved:Delete",
            "bucket": {"name": "b"},
            "object": {"key": "gone.txt"},
            "userIdentity": {"principalId": "x"},
            "eventTime": "2026-08-31T12:00:00.000Z",
        }]
    }
    e = s3_log_to_unified(payload, "minio")
    assert e is not None and e.event_type == "delete"


def test_unknown_format_returns_none():
    assert s3_log_to_unified({"foo": 1}, "s3") is None


def test_unparsable_timestamp_ok():
    e = s3_log_to_unified({
        "bucket": "b", "key": "k", "operation": "REST.GET.OBJECT",
        "requester": "u", "time": "not-a-date",
    }, "s3")
    assert e is not None
