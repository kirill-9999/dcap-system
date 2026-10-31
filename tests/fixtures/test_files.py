# tests/fixtures/test_files.py — генерация тестовых файлов (PII / credentials / code).
from pathlib import Path

PII_TEXT = "Иван Иванов, +7-999-123-45-67, ivan@example.com"
CREDS_ENV = "AWS_KEY=AKIAIOSFODNN7EXAMPLE\nSECRET=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
CODE_TEXT = "password = 'hardcoded123'"
CLEAN_TEXT = "Hello world, no secrets here."


def make_test_files(directory: Path) -> Path:
    """Создаёт папку с тестовыми файлами и возвращает путь к ней."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    (d / "pii.txt").write_text(PII_TEXT, encoding="utf-8")
    (d / "creds.env").write_text(CREDS_ENV, encoding="utf-8")
    (d / "code.py").write_text(CODE_TEXT, encoding="utf-8")
    (d / "clean.txt").write_text(CLEAN_TEXT, encoding="utf-8")
    return d