"""Unit-тесты S3LineConnector (день 53.2) с mock boto3."""
import io
import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scanner")))

# Изолируем от реального boto3: в тесте подменяем клиент.
os.environ.setdefault("S3_ACCESS_KEY", "test-access")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")

from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402


class _BodyEmpty:
    """Пустой поток boto3 Body."""

    def iter_chunks(self, chunk_size=1024):
        return iter(())

    def close(self):
        pass


class _DummyClassifier:
    classifier_name = "dummy"

    def scan_line(self, line, line_num):
        from scanner.src.finding import Finding
        if "SECRET" in line:
            return [Finding(
                line_number=line_num,
                line_text=line,
                match_text="SECRET",
                start_pos=0,
                end_pos=6,
                finding_type="credentials",
                category="test",
                confidence=1.0,
                severity="medium",
                detector="test",
                fragment_type="text_line",
            )]
        return []


def _make_connector(mock_list, mock_get=None):
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.list_objects_v2.side_effect = mock_list
        if mock_get is not None:
            mock_client.get_object.side_effect = mock_get
        connector = S3LineConnector({
            "endpoint": "test.local:9000",
            "bucket": "test-bucket",
            "prefix": "",
            "secure": False,
            "use_path_style": True,
        })
    return connector, mock_client


def _list_one_page(keys):
    def _list(**kwargs):
        return {
            "Contents": [{"Key": k, "Size": 100, "LastModified": None} for k in keys],
            "IsTruncated": False,
        }
    return _list


def test_discover_keys_filters_by_extension():
    connector, _ = _make_connector(_list_one_page(["a.txt", "b.bin", "c.pdf"]))
    keys = connector._discover_keys("")
    assert "a.txt" in keys
    assert "c.pdf" in keys
    assert "b.bin" not in keys


def test_scan_path_sets_s3_uri_in_findings():
    """file_path в findings = s3://bucket/key — критично для fingerprint."""
    fake_body = io.BytesIO(b"line1\nline2 SECRET\nline3")

    class _Body:
        def iter_chunks(self, chunk_size=1024):
            yield fake_body.read()

        def close(self):
            pass

    def _get(**kwargs):
        return {"Body": _Body()}

    connector, _ = _make_connector(_list_one_page(["notes.txt"]), mock_get=_get)

    findings = connector.scan_path("s3://test-bucket/", [_DummyClassifier()])
    assert len(findings) == 1
    assert findings[0].fragment_path == "s3://test-bucket/notes.txt"
    assert findings[0].line_number == 2


def test_scan_path_uses_prefix_from_arg():
    connector, mock_client = _make_connector(_list_one_page([]))
    connector.scan_path("s3://test-bucket/logs/", [_DummyClassifier()])
    call_kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert call_kwargs["Prefix"] == "logs/"


def test_constructor_reads_secrets_from_env(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "env-access")
    monkeypatch.setenv("S3_SECRET_KEY", "env-secret")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        S3LineConnector({"bucket": "b"})
        kwargs = mock_boto.client.call_args.kwargs
        assert kwargs["aws_access_key_id"] == "env-access"
        assert kwargs["aws_secret_access_key"] == "env-secret"


def test_constructor_allows_missing_bucket_with_path():
    """BUG-149: bucket можно не указывать в config — он определяется из path
    (s3://bucket/prefix) в scan_path (legacy-ресурсы без connector.s3)."""
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        connector = S3LineConnector({"endpoint": "x:9000"})
        assert connector._bucket == ""  # bucket отложен до scan_path


def test_scan_path_bucket_fallback_from_path():
    """BUG-149: bucket из path, когда в config его нет; чтение — тот же bucket."""
    connector, mock_client = _make_connector(
        _list_one_page(["x.txt"]),
        mock_get=lambda **kw: {"Body": _BodyEmpty()},
    )
    connector.config.pop("bucket", None)
    connector._bucket = ""
    connector.scan_path("s3://legacy-bucket/logs", [_DummyClassifier()])
    kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert kwargs["Bucket"] == "legacy-bucket", (
        "bucket должен браться из path при отсутствии в config"
    )
    assert kwargs["Prefix"] == "logs"
    # self._bucket запомнен — чтение использует тот же bucket.
    assert connector._bucket == "legacy-bucket"


def test_scan_path_without_bucket_anywhere_raises():
    """BUG-149: bucket нет ни в config, ни в path → понятный ValueError."""
    connector, _ = _make_connector(_list_one_page(["x.txt"]))
    connector.config.pop("bucket", None)
    connector._bucket = ""
    with pytest.raises(ValueError) as exc:
        connector.scan_path("/plain/folder/path", [_DummyClassifier()])
    assert "bucket" in str(exc.value)


def test_stop_event_stops_iteration():
    """stop_event прерывает скан между объектами."""
    import threading
    stop = threading.Event()
    stop.set()

    def _get(**kwargs):
        raise AssertionError("не должен вызываться")

    connector, _ = _make_connector(_list_one_page(["a.txt", "b.txt"]), mock_get=_get)
    findings = connector.scan_path("s3://test-bucket/", [_DummyClassifier()], stop_event=stop)
    assert findings == []


def test_constructor_requires_env_secrets(monkeypatch):
    """Без S3_ACCESS_KEY/S3_SECRET_KEY — понятный ValueError (политика TASK-018)."""
    monkeypatch.delenv("S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("S3_SECRET_KEY", raising=False)
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        with pytest.raises(ValueError) as exc:
            S3LineConnector({"bucket": "b", "endpoint": "x:9000"})
        assert "S3_ACCESS_KEY" in str(exc.value)


def test_discover_keys_uses_pagination():
    """IsTruncated=True → следующая страница по ContinuationToken."""
    pages = [
        {"Contents": [{"Key": "a.txt", "Size": 10}], "IsTruncated": True,
         "NextContinuationToken": "tok1"},
        {"Contents": [{"Key": "b.txt", "Size": 10}], "IsTruncated": False},
    ]
    calls = []

    def _list(**kwargs):
        calls.append(kwargs)
        return pages[len(calls) - 1]

    connector, _ = _make_connector(_list)
    keys = connector._discover_keys("logs/")
    assert keys == ["a.txt", "b.txt"]
    assert calls[0]["Prefix"] == "logs/"
    assert "ContinuationToken" not in calls[0]
    assert calls[1]["ContinuationToken"] == "tok1"


def test_discover_keys_skips_dirs_and_oversize():
    objects = [
        {"Key": "logs/", "Size": 0},
        {"Key": "big.txt", "Size": 200 * 1024 * 1024},   # 200 МБ > max_file_size_mb=50
        {"Key": "ok.log", "Size": 10},
    ]
    connector, _ = _make_connector(lambda **kw: {"Contents": objects, "IsTruncated": False})
    keys = connector._discover_keys("")
    assert keys == ["ok.log"]


def test_discover_keys_credential_filename_without_extension():
    """Файл-кред по имени (id_rsa) сканируется, несмотря на отсутствие расширения."""
    connector, _ = _make_connector(
        _list_one_page(["id_rsa", "photo.png.bak"])
    )
    keys = connector._discover_keys("")
    assert "id_rsa" in keys
    assert "photo.png.bak" not in keys


def test_scan_path_reads_prefix_from_path_over_config():
    """Prefix берётся из path; bucket остаётся из config (в path только префикс)."""
    connector, mock_client = _make_connector(
        _list_one_page(["x.txt"]), mock_get=lambda **kw: {"Body": _BodyEmpty()}
    )
    connector.scan_path("s3://test-bucket/logs", [_DummyClassifier()])
    kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Prefix"] == "logs"


def test_read_text_returns_none_on_binary():
    """Бинарный объект (\\x00) → decode_text_bytes вернул None → findings нет."""
    class _Body:
        def iter_chunks(self, chunk_size=1024):
            yield b"\x00\x01\x02" * 100

        def close(self):
            pass

    connector, _ = _make_connector(
        _list_one_page(["notes.txt"]), mock_get=lambda **kw: {"Body": _Body()}
    )
    assert connector.scan_path("s3://test-bucket/", [_DummyClassifier()]) == []


def test_scan_file_sets_ocr_fields_for_images(monkeypatch):
    """Изображение → fragment_type=image_region, detector=ocr, bounding_box=None."""
    monkeypatch.setattr(
        "scanner.connectors.s3_line_connector.extract_document_text",
        lambda content, ext, filename, ocr_enabled=False: "line1\nline2 SECRET",
    )

    class _Body:
        def iter_chunks(self, chunk_size=1024):
            yield b"\xff\xd8\xff\xe0fake-jpeg"

        def close(self):
            pass

    connector, _ = _make_connector(
        _list_one_page(["p.png"]), mock_get=lambda **kw: {"Body": _Body()}
    )
    findings = connector.scan_path("s3://test-bucket/", [_DummyClassifier()])
    assert len(findings) == 1
    assert findings[0].fragment_type == "image_region"
    assert findings[0].detector == "ocr"
    assert findings[0].bounding_box is None
    assert findings[0].fragment_path == "s3://test-bucket/p.png"


def test_scan_path_progress_callback_reports_progress():
    """progress_callback(stage, current, total, file_path) вызывается на каждый объект."""
    seen = []

    def _cb(stage, current, total, file_path):
        seen.append((stage, current, total, file_path))

    def _get(**kwargs):
        class _Body:
            def iter_chunks(self, chunk_size=1024):
                yield b"nothing here"

            def close(self):
                pass
        return {"Body": _Body()}

    connector, _ = _make_connector(
        _list_one_page(["a.txt", "b.txt"]), mock_get=_get
    )
    connector.scan_path("s3://test-bucket/", [_DummyClassifier()], progress_callback=_cb)
    assert seen == [(1, 1, 2, "a.txt"), (1, 2, 2, "b.txt")]


def test_scan_path_empty_bucket_calls_progress_with_zeros():
    seen = []
    connector, _ = _make_connector(_list_one_page([]))
    findings = connector.scan_path(
        "s3://test-bucket/empty/", [_DummyClassifier()],
        progress_callback=lambda *a: seen.append(a),
    )
    assert findings == []
    assert seen == [(1, 0, 0, "s3://test-bucket/empty/")]


def test_config_secrets_ignored_when_env_set(monkeypatch):
    """Секреты в config игнорируются, если есть ENV (политика TASK-018)."""
    monkeypatch.setenv("S3_ACCESS_KEY", "env-access")
    monkeypatch.setenv("S3_SECRET_KEY", "env-secret")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        S3LineConnector({
            "bucket": "b", "endpoint": "x:9000",
            "access_key": "cfg-access", "secret_key": "cfg-secret",
        })
        kwargs = mock_boto.client.call_args.kwargs
        assert kwargs["aws_access_key_id"] == "env-access"
        assert kwargs["aws_secret_access_key"] == "env-secret"


# ======================= 53.3-fix: bucket только из scan_config =======================


def test_bucket_in_path_is_ignored_and_config_wins():
    """Bucket из path игнорируется: в list_objects_v2 идёт bucket из config.

    Контракт: bucket фиксируется в scan_config.connector.s3.bucket (payload
    задачи от Manager, 53.1a); path — только суффикс префикса.
    """
    connector, mock_client = _make_connector(
        _list_one_page(["x.txt"]), mock_get=lambda **kw: {"Body": _BodyEmpty()}
    )
    connector.scan_path("s3://other-bucket/logs", [_DummyClassifier()])
    kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket", "bucket должен браться только из config"
    assert kwargs["Prefix"] == "logs"


def test_bucket_in_path_mismatch_emits_no_warning(caplog):
    """Чужой bucket в path не логирует WARNING (сравнение удалено в 53.3-fix)."""
    connector, _ = _make_connector(
        _list_one_page([]), mock_get=lambda **kw: {"Body": _BodyEmpty()}
    )
    with caplog.at_level(logging.WARNING, logger="dcap-scanner"):
        connector.scan_path("s3://other-bucket/logs", [_DummyClassifier()])
    bucket_warnings = [r.getMessage() for r in caplog.records if "ucket" in r.getMessage()]
    assert bucket_warnings == [], f"bucket-WARNING не ожидается: {bucket_warnings}"


def test_path_without_prefix_falls_back_to_config_prefix():
    """Пустой prefix в пути → prefix из config (`_discover_keys`: prefix or self._prefix)."""
    connector, mock_client = _make_connector(
        _list_one_page([]), mock_get=lambda **kw: {"Body": _BodyEmpty()}
    )
    connector.config["prefix"] = "cfg/prefix"
    connector._prefix = "cfg/prefix"
    connector.scan_path("s3://any-bucket/", [_DummyClassifier()])
    kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Prefix"] == "cfg/prefix"
