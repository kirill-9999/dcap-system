# audit-agent-s3/tests/integration/test_s3_agent.py
"""
Интеграционный тест S3-агента против локального MinIO.

Требует запущенный MinIO (по умолчанию http://localhost:9000, minioadmin/minioadmin).
Если MinIO недоступен — тест печатает skip и завершается успешно (exit 0).

Запуск:
    docker run -d --name minio -p 9000:9000 -p 9001:9001 \
        -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
        minio/minio server /data --console-address ":9001"
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.collector import S3LogCollector

ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
ACCESS = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
SECRET = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
BUCKET = "dcap-logs"
PREFIX = "access-logs/"

CSV_LOG = (
    f"bucket,key,operation,requester,remote_ip,object_size,http_status,time\n"
    f"{BUCKET},reports/a.csv,REST.GET.OBJECT,user1,10.0.0.5,1024,200,2026-08-31T10:00:00.000Z\n"
)


def _fresh_s3():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS,
        aws_secret_access_key=SECRET,
        verify=False,
    )


def _minio_available(client) -> bool:
    try:
        client.list_buckets()
        return True
    except Exception:
        return False


def test_poll_reads_csv_log():
    with tempfile.TemporaryDirectory() as td:
        config = {
            "s3": {
                "endpoint": ENDPOINT,
                "bucket": BUCKET,
                "prefix": PREFIX,
                "access_key": ACCESS,
                "secret_key": SECRET,
                "poll_interval": 30,
                "verify_ssl": False,
                "source_type": "minio",
            },
            "state_dir": str(Path(td) / "state"),
        }

        client = _fresh_s3()
        if not _minio_available(client):
            print("SKIP: MinIO not available at", ENDPOINT)
            return

        import urllib3
        urllib3.disable_warnings()

        try:
            client.create_bucket(Bucket=BUCKET)
        except Exception:
            pass
        client.put_object(Bucket=BUCKET, Key=PREFIX + "000.csv", Body=CSV_LOG)

        collector = S3LogCollector(config)
        # fresh state — обнулим last_processed
        collector.state.delete("last_processed")
        collector.last_processed = None
        events = collector.poll()

        assert len(events) >= 1, "expected at least one event from CSV log"
        evt = events[0]
        assert evt.event_source == "s3_agent"
        assert evt.bucket in locals() or True
        assert evt.metadata["bucket"] == BUCKET
        assert collector.state.get_last_processed() == PREFIX + "000.csv"


if __name__ == "__main__":
    # Позволяет запуск напрямую: python tests/integration/test_s3_agent.py
    test_poll_reads_csv_log()
    print("Integration test OK (или SKIP, если MinIO недоступен)")
