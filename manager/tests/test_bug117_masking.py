"""BUG-117: Manager маскирует контексты findings."""
import pytest
from manager.src.core.encryption import mask, mask_context


class TestMaskContext:
    def test_password_eq(self):
        assert "secret123" not in mask_context("password=secret123")
        assert "password=***" in mask_context("password=secret123")

    def test_github_token(self):
        out = mask_context("GITHUB_TOKEN=ghp_abc123def456ghi789jkl012mno345pqr678")
        assert "ghp_abc123" not in out
        assert "GITHUB_TOKEN=ghp_***" in out

    def test_aws_key(self):
        out = mask_context("AWS_KEY=AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "AKIA***" in out

    def test_email(self):
        out = mask_context("contact: user@example.com")
        assert "user@example.com" not in out
        assert "us***@ex***.com" in out

    def test_phone_ru(self):
        out = mask_context("tel: +79161234567")
        assert "+79161234567" not in out
        assert "+7***" in out

    def test_jwt(self):
        out = mask_context("token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdef")
        assert "eyJhbGciOiJIUzI1NiJ9" not in out
        assert "eyJhbGci***" in out

    def test_database_url(self):
        out = mask_context("db: postgresql://user:pass@host:5432/db")
        assert "user:pass" not in out
        assert "postgresql://***@host" in out

    def test_person_not_masked(self):
        out = mask_context("person: Иван Иванов")
        assert "Иван Иванов" in out

    def test_multiple(self):
        text = "password=secret123, email=user@example.com, phone=+79161234567"
        out = mask_context(text)
        assert "secret123" not in out
        assert "user@example.com" not in out
        assert "+79161234567" not in out


class TestMaskCategories:
    def test_github_token_category(self):
        assert mask("ghp_abc123def456", "github_token") == "ghp_***"

    def test_slack_token_category(self):
        assert mask("xoxb-12345-67890", "slack_token") == "xoxb***"

    def test_jwt_token_category(self):
        assert mask("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdef", "jwt_token") == "eyJhbGci***"

    def test_ssh_key_category(self):
        assert mask("-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----", "ssh_key") == "***ssh-private-key***"

    def test_database_url_category(self):
        assert mask("postgresql://user:pass@host:5432/db", "database_url") == "postgresql://***@host:5432/db"

    def test_basic_auth_category(self):
        assert mask("Basic dXNlcjpwYXNz", "basic_auth") == "Basic ***"

    def test_high_entropy_category(self):
        assert mask("aB3xK9mN2pQ7rT5v", "high_entropy") == "aB3xK9***"
