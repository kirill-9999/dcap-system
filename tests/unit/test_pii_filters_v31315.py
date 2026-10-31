"""Smoke-тесты фильтров PII для v3.13.15 (TASK-037..039)."""

import sys
from pathlib import Path

# Пути: корень репо (пакет scanner) + scanner/ (пакеты core/classifiers/connectors)
ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.finding import Finding  # noqa: E402
from scanner.classifiers.pii_classifier import PiiClassifier  # noqa: E402


def _f(category, line, match, line_text, start=0, end=10, fpath="C:/t.txt"):
    return Finding(
        line_number=line, line_text=line_text, match_text=match,
        start_pos=start, end_pos=end,
        finding_type="pii", category=category,
        fragment_path=fpath,
    )


class TestUrlOverEmail:
    def setup_method(self):
        self.c = PiiClassifier()

    def test_url_over_email_removed(self):
        """http://bob.new@test.example/x → url и email отброшены."""
        findings = [
            _f("email", 4, "bob.new@test.example",
               "url: http://bob.new@test.example/x", 15, 35),
            _f("url",   4, "http://bob.new",
               "url: http://bob.new@test.example/x", 5, 15),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 0

    def test_credentials_url_email_removed(self):
        """postgresql://user:pass@host/db → email отброшен."""
        line = "DATABASE_URL=postgresql://cleanuser:cleanpass@cleandb.local:5432/cleandb"
        findings = [
            _f("email", 1, "cleanpass@cleandb.local", line, 35, 60),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 0

    def test_plain_email_kept(self):
        """contact: user@example.com → email СОХРАНЯЕТСЯ (нет ://)."""
        findings = [
            _f("email", 1, "alice.new@example.org",
               "contact: alice.new@example.org", 9, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1


class TestSpacyNoise:
    def setup_method(self):
        self.c = PiiClassifier()

    def test_inn_abbrev_removed(self):
        """organization='INN' отброшен."""
        findings = [
            _f("organization", 3, "INN", "INN: 7712345678"),
        ]
        out = self.c._filter_spacy_noise(findings)
        assert len(out) == 0

    def test_real_org_kept(self):
        """organization='Apple Inc' НЕ отброшен."""
        findings = [
            _f("organization", 1, "Apple Inc", "at Apple Inc office"),
        ]
        out = self.c._filter_spacy_noise(findings)
        assert len(out) == 1


class TestUkNhsWithPhone:
    def setup_method(self):
        self.c = PiiClassifier()

    def test_uk_nhs_removed_when_phone(self):
        """uk_nhs отброшен, если phone в той же строке."""
        findings = [
            _f("phone",  3, "415 555 0199", "us: +1 415 555 0199"),
            _f("uk_nhs", 3, "415 555 0199", "us: +1 415 555 0199"),
        ]
        out = self.c._filter_uk_nhs_with_phone(findings)
        assert len(out) == 1
        assert out[0].category == "phone"

    def test_uk_nhs_kept_without_phone(self):
        """uk_nhs сохранён, если phone нет в строке."""
        findings = [
            _f("uk_nhs", 1, "123 456 7890", "NHS: 123 456 7890"),
        ]
        out = self.c._filter_uk_nhs_with_phone(findings)
        assert len(out) == 1