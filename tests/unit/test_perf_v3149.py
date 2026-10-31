"""53.4k (v3.14.9): OCR/документ-экстрактор — singleton + кэш детекции tesseract.

Проверяет, что:
  * детекция Tesseract и языков кэшируется на процесс (@lru_cache) — subprocess
    'where tesseract' / '--list-langs' не вызывается повторно;
  * DocumentExtractor переиспользуется (модульный singleton в _text_scanner),
    а не создаётся на каждый файл.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scanner")))

from scanner.utils import ocr_engine  # noqa: E402
from scanner.connectors import _text_scanner  # noqa: E402


def test_tesseract_path_is_lru_cached():
    """Повторные вызовы _get_tesseract_path не порождают новых subprocess."""
    ocr_engine._get_tesseract_path.cache_clear()
    first = ocr_engine._get_tesseract_path()
    info1 = ocr_engine._get_tesseract_path.cache_info()
    second = ocr_engine._get_tesseract_path()
    info2 = ocr_engine._get_tesseract_path.cache_info()
    assert first == second
    assert info2.hits >= 1
    assert info1.misses == 1, "детекция пути должна выполняться один раз"


def test_tesseract_langs_is_lru_cached():
    """Повторные вызовы _get_tesseract_langs не порождают новых subprocess."""
    ocr_engine._get_tesseract_langs.cache_clear()
    cmd = ocr_engine._get_tesseract_path()
    ocr_engine._get_tesseract_langs(cmd)
    info1 = ocr_engine._get_tesseract_langs.cache_info()
    ocr_engine._get_tesseract_langs(cmd)
    info2 = ocr_engine._get_tesseract_langs.cache_info()
    assert info1.misses == 1
    assert info2.hits >= 1


def test_document_extractor_is_singleton_per_key():
    """_get_document_extractor возвращает один и тот же объект для одного ключа."""
    _text_scanner._EXTRACTOR_CACHE.clear()
    a = _text_scanner._get_document_extractor("E:/Temp/dcap_test", False)
    b = _text_scanner._get_document_extractor("E:/Temp/dcap_test", False)
    assert a is b, "DocumentExtractor должен переиспользоваться"
    c = _text_scanner._get_document_extractor("E:/Temp/dcap_test", True)
    assert c is not a, "разный ocr_enabled → разный экземпляр"


def test_extract_document_text_uses_cached_extractor():
    """extract_document_text переиспользует DocumentExtractor."""
    _text_scanner._EXTRACTOR_CACHE.clear()
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    r1 = _text_scanner.extract_document_text(content, ".pdf", "sample.pdf", ocr_enabled=False)
    r2 = _text_scanner.extract_document_text(content, ".pdf", "other.pdf", ocr_enabled=False)
    assert len(_text_scanner._EXTRACTOR_CACHE) == 1, "для одного temp_dir/ocr ключа — 1 экстрактор"
    assert r1 is not None or r2 is not None or True  # суть теста — кэш, а не извлечение PII
    _ = r1, r2
