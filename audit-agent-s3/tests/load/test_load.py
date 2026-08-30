# audit-agent-s3/tests/load/test_load.py
import sys
import time
import tempfile
import json
import csv
import io
import unittest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.buffer import BufferManager
from src.sender import Sender

try:
    from shared.event_schema import UnifiedEvent
except ImportError:
    # fallback: для унитарного запуска без shared/
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from shared.event_schema import UnifiedEvent


def make_event(i: int) -> UnifiedEvent:
    return UnifiedEvent(
        event_type="read",
        event_source="s3_agent",
        user=f"user{i}",
        file_path=f"s3://bucket/key{i}.txt",
        metadata={"i": i},
        created_at="2026-09-01T00:00:00.000Z",
    )


class TestLoad(unittest.TestCase):
    """Нагрузочное тестирование агента."""

    def test_buffer_performance(self):
        """Тест производительности буфера: 10 000 событий < 5с (запись) и < 2с (чтение)."""
        import shutil

        tmpdir_obj = tempfile.TemporaryDirectory()
        tmpdir = tmpdir_obj.name
        buffer = None
        try:
            config = {
                "path": f"{tmpdir}/buffer.db",
                "max_events": 100000,
                "cleanup_days": 7,
            }
            buffer = BufferManager(config)

            start = time.time()
            for i in range(10000):
                buffer.store_event(make_event(i))
            write_time = time.time() - start

            start = time.time()
            unsent = buffer.get_unsent(limit=10000)
            read_time = time.time() - start

            print(f"Write 10 000 events: {write_time:.2f}s ({10000 / write_time:.0f} events/sec)")
            print(f"Read 10 000 events: {read_time:.2f}s ({10000 / read_time:.0f} events/sec)")

            self.assertLess(write_time, 5.0)  # < 5 секунд
            self.assertLess(read_time, 2.0)   # < 2 секунды
            self.assertEqual(len(unsent), 10000)
        finally:
            if buffer is not None:
                buffer.close()
            # На Windows WAL-файлы могут удерживать блокировку после close
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_large_csv_parsing(self):
        """Тест парсинга 10 000 CSV строк < 1 секунды."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "bucket", "key", "operation", "requester", "remote_ip",
            "object_size", "http_status", "time",
        ])
        writer.writeheader()

        for i in range(10000):
            writer.writerow({
                "bucket": f"bucket{i % 10}",
                "key": f"key{i}.txt",
                "operation": "REST.GET.OBJECT" if i % 2 == 0 else "REST.PUT.OBJECT",
                "requester": f"user{i % 100}",
                "remote_ip": f"10.0.0.{i % 255}",
                "object_size": str(i * 1024),
                "http_status": "200",
                "time": f"2026-09-01T{i % 86400:06d}Z",
            })

        content = output.getvalue()

        start = time.time()
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        parse_time = time.time() - start

        print(f"Parse 10 000 CSV rows: {parse_time:.2f}s ({10000 / parse_time:.0f} rows/sec)")

        self.assertEqual(len(rows), 10000)
        self.assertLess(parse_time, 1.0)  # < 1 секунда

    def test_batch_send_performance(self):
        """Тест сериализации 1000 событий < 0.5 секунды."""
        config = {
            "manager": {
                "url": "http://localhost:8000",
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1,
            }
        }
        sender = Sender(config)

        events = []
        for i in range(1000):
            events.append(UnifiedEvent(
                event_type="read",
                event_source="s3_agent",
                user=f"user{i}",
                file_path=f"s3://bucket/file{i}.txt",
                created_at=datetime.now().astimezone().isoformat(),
            ))

        start = time.time()
        data = [e.model_dump() for e in events]
        serialize_time = time.time() - start

        print(f"Serialize 1000 events: {serialize_time:.3f}s")
        self.assertLess(serialize_time, 0.5)
        self.assertEqual(len(data), 1000)


if __name__ == "__main__":
    unittest.main()
