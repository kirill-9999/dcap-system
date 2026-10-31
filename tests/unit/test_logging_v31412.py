"""Тесты файлового лога (53.4n, v3.14.12, BUG-283)."""
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import run_scanner


def test_setup_logging_creates_file():
    with tempfile.TemporaryDirectory() as d:
        cfg = {
            "logging": {"level": "INFO", "file": str(Path(d) / "scanner.log"),
                        "max_size_mb": 1, "backup_count": 1},
            "scanner": {"log_level": "INFO"},
        }
        log_file = run_scanner._setup_logging(cfg)
        assert log_file is not None
        assert Path(log_file).exists()
        root = logging.getLogger()
        assert any(isinstance(h, logging.handlers.RotatingFileHandler)
                   for h in root.handlers)
        logging.shutdown()


def test_setup_logging_missing_file_no_crash():
    # недоступный путь (файл — каталог) не должен падать
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "blocked"
        bad.mkdir()
        cfg = {"logging": {"file": str(bad / "x.log")}, "scanner": {"log_level": "INFO"}}
        # не должно бросать
        run_scanner._setup_logging(cfg)
        logging.shutdown()
