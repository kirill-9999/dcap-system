# tests/unit/test_mask_context_v31321.py — BUG-086 (TASK-053, v3.13.21)
# mask_context покрывает все категории MASK_RULES через _CONTEXT_PATTERNS
# (credentials: github/slack/aws/api_key/basic_auth/database_url/jwt/password/token;
#  телефоны RU/US/международные; регрессии PII; person не маскируется).
"""BUG-086 (TASK-053, v3.13.21): mask_context покрывает все категории."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.encryption import mask_context  # noqa: E402

pytestmark = [pytest.mark.unit]


class TestMaskContextCredentials:
    def test_github_token_masked(self):
        ctx = "GITHUB_TOKEN=ghp_cleanabcdefghijklmnopqrstuvwxyz012345"
        out = mask_context(ctx)
        assert "ghp_cleanabcdefghijklmnopqrstuvwxyz012345" not in out
        assert "ghp_" in out and "***" in out

    def test_slack_token_masked(self):
        ctx = "SLACK_TOKEN=xoxb-clean-1234567890-abcdef"
        out = mask_context(ctx)
        assert "xoxb-clean-1234567890-abcdef" not in out
        assert "xoxb-" in out and "***" in out

    def test_aws_key_masked(self):
        ctx = "AWS_KEY=AKIAIOSFODNN7EXAMPLE"
        out = mask_context(ctx)
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "AKIA" in out and "***" in out

    def test_api_key_masked(self):
        ctx = "API_KEY=sk-clean-1234567890abcdefghij"
        out = mask_context(ctx)
        assert "sk-clean-1234567890abcdefghij" not in out

    def test_basic_auth_masked(self):
        ctx = "BASIC_AUTH=Basic Y2xlYW51c2VyOmNsZWFucGFzcw=="
        out = mask_context(ctx)
        assert "Y2xlYW51c2VyOmNsZWFucGFzcw==" not in out
        assert "Basic ***" in out

    def test_database_url_masked(self):
        ctx = "DATABASE_URL=postgresql://cleanuser:cleanpass@cleandb.local:5432/cleandb"
        out = mask_context(ctx)
        assert "cleanpass" not in out
        assert "cleanuser" not in out

    def test_jwt_token_masked(self):
        ctx = "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdef"
        out = mask_context(ctx)
        assert "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdef" not in out

    def test_password_masked(self):
        ctx = "password=supersecret123"
        out = mask_context(ctx)
        assert "supersecret123" not in out

    def test_generic_token_masked(self):
        ctx = "secret=abcdefghijklmnopqrstuvwxyz"
        out = mask_context(ctx)
        assert "abcdefghijklmnopqrstuvwxyz" not in out


class TestMaskContextPhone:
    def test_ru_phone_masked(self):
        ctx = "office: +7 999 123-45-67"
        out = mask_context(ctx)
        assert "+7 999 123-45-67" not in out

    def test_us_phone_masked(self):
        """BUG-086: US-формат (не покрыт раньше)."""
        ctx = "us: +1 415 555 0199"
        out = mask_context(ctx)
        assert "+1 415 555 0199" not in out

    def test_us_phone_with_parens(self):
        ctx = "us: +1 (415) 555-0199"
        out = mask_context(ctx)
        assert "+1 (415) 555-0199" not in out


class TestMaskContextRegressions:
    """Старые категории (email, inn, snils, passport, credit_card) — не сломать."""

    def test_email_masked(self):
        ctx = "contact: user@example.com"
        out = mask_context(ctx)
        assert "user@example.com" not in out

    def test_inn_masked(self):
        ctx = "inn: 771234567890"
        out = mask_context(ctx)
        assert "771234567890" not in out

    def test_passport_masked(self):
        ctx = "passport: 4510 123456"
        out = mask_context(ctx)
        assert "4510 123456" not in out

    def test_credit_card_masked(self):
        ctx = "card: 4532 1234 5678 9010"
        out = mask_context(ctx)
        assert "4532 1234 5678 9010" not in out

    def test_person_not_masked(self):
        """person — не маскируется (по решению)."""
        ctx = "person: Ivan Ivanov"
        out = mask_context(ctx)
        assert "person: Ivan Ivanov" == out  # без изменений


class TestMaskContextEdge:
    def test_empty_context(self):
        assert mask_context("") == ""
        assert mask_context(None) is None

    def test_no_secrets(self):
        ctx = "plain text without secrets"
        assert mask_context(ctx) == ctx

    def test_multiple_secrets(self):
        ctx = "GITHUB_TOKEN=ghp_abc123456789012345678901234567890123\nBASIC_AUTH=Basic dXNlcjpwYXNz"
        out = mask_context(ctx)
        assert "ghp_abc123456789012345678901234567890123" not in out
        assert "dXNlcjpwYXNz" not in out