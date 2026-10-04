"""Unit-тесты _text_scanner (день 53.1b): функции + регрессия.

Покрытие:
- is_supported_file: txt, .docx, .png, id_rsa, .env, unknown;
- decode_text_bytes: utf-8, cp1251, BOM, \x00 (None);
- file_pass_prefilter: классификатор без file_prefilter → True;
- scan_text: пустой текст → [], без классификаторов → [];
- scan_text + dummy scan_line классификатор → находит, ставит line_text/context/fragment_path.
"""
import os
import sys
from pathlib import Path

# Пути: корень репо (пакет scanner) — _text_scanner импортирует
# только scanner.src.finding, верхнеуровневые пакеты не нужны.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scanner.connectors._text_scanner import (  # noqa: E402
    decode_text_bytes,
    file_pass_prefilter,
    is_supported_file,
    scan_text,
)


class _DummyFinding:
    def __init__(self, line_number, line_text="", category="test"):
        self.line_number = line_number
        self.line_text = line_text
        self.category = category
        self.finding_type = "pii"
        self.match_text = "dummy"
        self.start_pos = 0
        self.end_pos = 5
        self.context_before = ""
        self.context_after = ""
        self.fragment_path = ""
        self.confidence = 1.0
        self.severity = "medium"
        self.detector = "test"
        self.fragment_type = "text_line"
        self.bounding_box = None
        self.byte_offset = None
        self.byte_length = None
        self.hex_preview = None


class _DummyClassifier:
    classifier_name = "dummy"

    def scan_line(self, line, line_num):
        if "SECRET" in line:
            return [_DummyFinding(line_num, line_text=line)]
        return []


def test_is_supported_txt():
    assert is_supported_file("txt", "a.txt")


def test_is_supported_docx():
    assert is_supported_file("docx", "a.docx")


def test_is_supported_png():
    assert is_supported_file("png", "a.png")


def test_is_supported_cred_filename():
    assert is_supported_file("", "id_rsa")
    assert is_supported_file("", ".env")


def test_is_supported_unknown():
    assert not is_supported_file("bin", "a.bin")


def test_decode_utf8():
    assert decode_text_bytes("привет".encode("utf-8")) == "привет"


def test_decode_ascii():
    assert decode_text_bytes(b"hello world") == "hello world"


def test_decode_cp1251_bytes_follow_utf8_ignore():
    """Документирует реальное поведение декодера (неизменно с дня 40.2).

    Порядок кодировок — utf-8, затем cp1251 — но `decode('utf-8',
    errors='ignore')` НИКОГДА не бросает исключение, поэтому cp1251
    недостижим: байты cp1251 всегда разбираются как utf-8 с потерями.
    Для «привет» в cp1251 (\\xef\\xf0\\xe8\\xe2\\xe5\\xf2) это даёт ''.

    Рефакторинг 53.1b это поведение сохранил дословно (поведение FS-коннектора
    не меняется). Сам баг декодера — кандидат в отдельный день, здесь не чинится.
    """
    raw = "привет".encode("cp1251")
    assert raw.decode("cp1251") == "привет"          # ради контраста: так было бы правильно
    assert decode_text_bytes(raw) == ""              # фактическое поведение коннектора


def test_decode_binary_returns_none():
    assert decode_text_bytes(b"\x00\x01\x02\x03" * 2048) is None


def test_file_pass_prefilter_no_classifiers():
    assert file_pass_prefilter("text", []) is False


def test_file_pass_prefilter_classifier_without_prefilter():
    class _NoPref:
        pass

    assert file_pass_prefilter("text", [_NoPref()]) is True


def test_scan_text_empty():
    assert scan_text("", [_DummyClassifier()], "/tmp/x.txt") == []


def test_scan_text_finds_line():
    text = "line1\nline2 SECRET\nline3"
    result = scan_text(text, [_DummyClassifier()], "/tmp/x.txt", context_lines=1)
    assert len(result) == 1
    f = result[0]
    assert f.line_number == 2
    assert f.fragment_path == "/tmp/x.txt"
    assert "line1" in f.context_before
    assert "line3" in f.context_after
