"""Smoke-тесты фильтра url-over-email для v3.13.16 (TASK-040, BUG-075)."""

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


class TestBug075UrlInEmail:
    """BUG-075: url = доменная часть email (без '://' в строке)."""

    def setup_method(self):
        self.c = PiiClassifier()

    def test_domain_of_email_removed(self):
        """carol.new@company.example → email ok, url 'company.example' отброшен."""
        line = "plain: carol.new@company.example"
        findings = [
            _f("email", 5, "carol.new@company.example", line, 7, 33),
            _f("url",   5, "company.example",           line, 18, 33),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        cats = [f.category for f in out]
        assert "url" not in cats
        assert "email" in cats

    def test_multiple_urls_same_line_removed(self):
        """Дубль url (1338/1339) в одной строке — оба отброшены."""
        line = "contact: alice.new@example.org"
        findings = [
            _f("email", 1, "alice.new@example.org", line, 9, 30),
            _f("url",   1, "example.org",           line, 19, 30),
            _f("url",   1, "example.org",           line, 18, 29),  # дубль
        ]
        out = self.c._filter_url_over_email_finding(findings)
        cats = [f.category for f in out]
        assert cats.count("url") == 0
        assert cats.count("email") == 1

    def test_real_url_kept(self):
        """URL без email в строке — сохраняется."""
        line = "visit https://example.com/page for details"
        findings = [
            _f("url", 1, "https://example.com/page", line, 6, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1
        assert out[0].category == "url"

    def test_email_without_url_kept(self):
        """Email без url-finding — сохраняется."""
        line = "contact: alice.new@example.org"
        findings = [
            _f("email", 1, "alice.new@example.org", line, 9, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1
        assert out[0].category == "email"


class TestRegressionPrevious:
    """Регрессия ТЗ №6 (BUG-071/074) — не должны сломаться."""

    def setup_method(self):
        self.c = PiiClassifier()

    def test_url_over_email_with_scheme_removed(self):
        """http://bob.new@test.example/x → url и email отброшены."""
        line = "url: http://bob.new@test.example/x"
        findings = [
            _f("email", 4, "bob.new@test.example", line, 15, 35),
            _f("url",   4, "http://bob.new",       line, 5, 20),
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

    def test_plain_email_no_scheme_kept(self):
        """contact: user@example.com (нет '://') → email сохранён."""
        line = "contact: alice.new@example.org"
        findings = [
            _f("email", 1, "alice.new@example.org", line, 9, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1