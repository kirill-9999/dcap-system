"""53.4l (v3.14.10): дедуп находок в рамках файла (3.4.0) + отключение NER.

Дедуп по (category, match_text): одно совпадение в N строках → 1 Finding
с metadata["locations"] = все вхождения. line_number / context_* — первого
вхождения.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCANNER_DIR = os.path.join(ROOT, "scanner")
for _p in (ROOT, SCANNER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.finding import Finding  # noqa: E402
from scanner.connectors._text_scanner import dedup_findings_by_file  # noqa: E402

_CLF = None


def _classifier():
    """PiiClassifier — синглтон; конфигурируем один раз на процесс тестов."""
    global _CLF
    if _CLF is None:
        from scanner.classifiers.pii_classifier import PiiClassifier
        _CLF = PiiClassifier()
        try:
            _CLF.configure({
                "min_confidence": 0.3,
                "quick_filter_enabled": True,
                "analyzer_pool_size": 1,
                "ocr_enabled": False,
            })
        except Exception:
            pass
        _CLF.config["min_confidence"] = 0.3
    return _CLF


def _f(category, line, match, line_text="x", start=0, end=10, fpath="C:/t.txt"):
    return Finding(
        line_number=line, line_text=line_text, match_text=match,
        start_pos=start, end_pos=end,
        finding_type="pii", category=category,
        fragment_path=fpath,
    )


class TestDedupLogic:
    """Дедуп-логика без Presidio (быстрые тесты)."""

    def test_same_match_many_lines(self):
        findings = [_f("email", i, "test@example.com") for i in range(1, 101)]
        out = dedup_findings_by_file(findings)
        assert len(out) == 1
        assert len(out[0].metadata["locations"]) == 100
        assert out[0].line_number == 1

    def test_different_matches_kept(self):
        findings = [
            _f("email", 1, "a@x.com"),
            _f("email", 2, "b@x.com"),
            _f("email", 3, "c@x.com"),
        ]
        out = dedup_findings_by_file(findings)
        assert len(out) == 3

    def test_same_text_different_category_kept(self):
        """Один match_text, но разные категории — разные находки."""
        findings = [
            _f("email", 1, "abc123", start=0, end=6),
            _f("api_key", 2, "abc123", start=0, end=6),
        ]
        out = dedup_findings_by_file(findings)
        assert len(out) == 2

    def test_locations_sorted_by_line(self):
        findings = [_f("phone", 5, "+79991234567"),
                    _f("phone", 2, "+79991234567"),
                    _f("phone", 9, "+79991234567")]
        out = dedup_findings_by_file(findings)
        assert len(out) == 1
        lines = [loc["line"] for loc in out[0].metadata["locations"]]
        assert lines == sorted(lines)
        assert out[0].line_number == 2

    def test_single_finding_gets_locations(self):
        out = dedup_findings_by_file([_f("email", 7, "x@y.com")])
        assert len(out) == 1
        assert out[0].metadata["locations"][0]["line"] == 7
        assert out[0].metadata["locations_count"] == 1

    def test_empty_list(self):
        assert dedup_findings_by_file([]) == []

    def test_finding_metadata_default(self):
        """Finding имеет поле metadata (пустой dict по умолчанию)."""
        f = _f("email", 1, "x@y.com")
        assert f.metadata == {}

    def test_metadata_preserved_for_kept_finding(self):
        """Прочие ключи metadata не теряются."""
        f = _f("email", 1, "x@y.com")
        f.metadata["custom"] = "value"
        out = dedup_findings_by_file([f])
        assert out[0].metadata["custom"] == "value"
        assert "locations" in out[0].metadata


class TestDedupWithPresidio:
    """Поведенческий тест на реальном Presidio (медленнее)."""

    def test_dedup_same_email_in_multiple_lines(self):
        c = _classifier()
        text = "\n".join(["test@example.com"] * 100)
        findings = dedup_findings_by_file(c.scan_text(text))
        emails = [f for f in findings if f.category == "email"]
        assert len(emails) == 1, "один email в 100 строках → 1 Finding"
        assert len(emails[0].metadata["locations"]) == 100
        assert emails[0].line_number == 1

    def test_ner_categories_excluded(self):
        """NER-категории (person/location/...) не попадают в находки."""
        c = _classifier()
        text = "John Smith родился 12.05.1990 в London, UK."
        findings = c.scan_text(text)
        cats = {f.category for f in findings}
        assert not (cats & {"person", "location", "organization", "date_time", "nrp"}), cats


class TestNerFilter:
    """Проверка фильтра entity-типов Presidio."""

    def test_excluded_entities_default(self):
        from scanner.classifiers.pii_classifier import NER_ENTITY_TYPES
        assert set(NER_ENTITY_TYPES) == {
            "PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "NRP"
        }

    def test_analyze_entities_excludes_ner(self):
        c = _classifier()
        analyzer = c._analyzer
        if analyzer is None:
            return
        assert c._analyze_entities is not None
        assert not (set(c._analyze_entities) & {
            "PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "NRP"
        })
