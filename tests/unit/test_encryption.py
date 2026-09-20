"""Unit-тесты шифрования находок (День 40.1)."""
from pathlib import Path

import pytest
import manager.src.core.encryption as finding_encryption

pytestmark = pytest.mark.unit

from manager.src.core.encryption import (
    mask,
    mask_line,
    MASK_RULES,
    get_encryption,
    reset_encryption,
)


class TestMask:
    def test_rules_defined(self):
        assert "phone" in MASK_RULES
        assert "email" in MASK_RULES
        assert "password" in MASK_RULES
        assert "api_key" in MASK_RULES

    def test_phone_rus(self):
        assert mask("+7-999-123-45-67", "phone") == "+7***123-45-67"

    def test_phone_bare(self):
        # без кода страны — по ТЗ форматируем родной regex
        assert mask("+79991234567", "phone") == "+7***123-45-67"

    def test_email(self):
        result = mask("user@example.com", "email")
        assert "user" not in result
        assert "example" not in result
        # BUG-044: маскируются и local-part, и домен; TLD видимый.
        assert result == "us***@ex***.com"

    def test_password(self):
        assert mask("P@ssw0rd", "password") == "***"

    def test_api_key(self):
        result = mask("sk-1234567890abcdef", "api_key")
        assert result != "sk-1234567890abcdef"
        assert result.startswith("sk-")
        assert result.endswith("***")

    def test_unknown_type_default_mask(self):
        # Безопасный дефолт — полная маска
        assert mask("secret-value", "unknown_type") == "***"

    def test_empty_unchanged(self):
        assert mask("", "phone") == ""
        assert mask(None, "phone") is None


class TestMaskLine:
    def test_line_masks_found_values(self):
        line = "password = P@ssw0rd, email = user@example.com"
        # (start, end, category) — позиции значений в строке
        pw_start = line.index("P@ssw0rd")
        pw_end = pw_start + len("P@ssw0rd")
        em_start = line.index("user@example.com")
        em_end = em_start + len("user@example.com")
        result = mask_line(line, [(pw_start, pw_end, "password"), (em_start, em_end, "email")])
        assert "P@ssw0rd" not in result
        assert result != line

    def test_clean_line_unchanged(self):
        line = "простая строка без секретов"
        assert mask_line(line, []) == line


class TestFindingEncryption:
    def test_singleton(self):
        reset_encryption()
        a = get_encryption()
        b = get_encryption()
        assert a is b
        reset_encryption()

    def test_encrypt_roundtrip(self):
        reset_encryption()
        enc = get_encryption()
        ct = enc.encrypt("super-secret-value")
        assert ct != "super-secret-value"
        assert enc.decrypt(ct) == "super-secret-value"
        reset_encryption()

    def test_encrypt_random_iv(self):
        reset_encryption()
        enc = get_encryption()
        a = enc.encrypt("same value")
        b = enc.encrypt("same value")
        assert a != b
        reset_encryption()

    def test_decrypt_wrong_key_fails(self):
        reset_encryption()
        enc = get_encryption()
        ct = enc.encrypt("secret")
        reset_encryption()
        enc2 = get_encryption()
        with pytest.raises(Exception):
            enc2.decrypt(ct)

    def test_fingerprint_deterministic(self):
        reset_encryption()
        enc = get_encryption()
        fp1 = enc.fingerprint("/path/file.txt", 10, "value", "pii")
        fp2 = enc.fingerprint("/path/file.txt", 10, "value", "pii")
        assert fp1 == fp2

    def test_fingerprint_sensitive(self):
        reset_encryption()
        enc = get_encryption()
        fp1 = enc.fingerprint("/path/file.txt", 10, "value", "pii")
        fp2 = enc.fingerprint("/path/file.txt", 11, "value", "pii")
        assert fp1 != fp2

    def test_key_id_present(self):
        reset_encryption()
        enc = get_encryption()
        assert enc.key_id
        reset_encryption()


class TestFindingEncryptionEnvOnly:
    """TASK-018: ключи находок читаются ТОЛЬКО из env (Docker Secrets убраны)."""

    _ENV_NAMES = (
        "FINDINGS_ENCRYPTION_KEY",
        "FINDINGS_HMAC_KEY",
        "FINDINGS_KEY_ID",
    )

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for name in self._ENV_NAMES:
            monkeypatch.delenv(name, raising=False)

    def test_module_has_no_secrets_path(self):
        """Регрессионный guard: /run/secrets полностью убран из модуля."""
        src = Path(finding_encryption.__file__).read_text(encoding="utf-8")
        assert "/run/secrets" not in src
        assert "getenv" in src

    def test_from_env_roundtrip(self, monkeypatch):
        monkeypatch.setenv("FINDINGS_ENCRYPTION_KEY", "A" * 32)
        monkeypatch.setenv("FINDINGS_HMAC_KEY", "B" * 32)
        monkeypatch.setenv("FINDINGS_KEY_ID", "key-test-env")
        enc = finding_encryption.FindingEncryption.from_env()
        assert enc.key_id == "key-test-env"
        ct = enc.encrypt("secret")
        assert enc.decrypt(ct) == "secret"
        assert enc.fingerprint("/f", 1, "secret", "credentials") == enc.fingerprint(
            "/f", 1, "secret", "credentials"
        )

    def test_from_env_missing_keys_raises(self):
        with pytest.raises(Exception):
            finding_encryption.FindingEncryption.from_env()

    def test_from_env_or_default_ephemeral_when_unset(self):
        """Без env - ephemeral-fallback в DEV (не падает при пустой конфигурации)."""
        enc = finding_encryption.FindingEncryption.from_env_or_default()
        assert enc.key_id

    def test_encryption_env_only(self, monkeypatch):
        """env-only: значение из env используется при любой окружающей среде."""
        monkeypatch.setenv("FINDINGS_ENCRYPTION_KEY", "C" * 32)
        monkeypatch.setenv("FINDINGS_HMAC_KEY", "D" * 32)
        monkeypatch.setenv("FINDINGS_KEY_ID", "key-2026-09")
        enc = finding_encryption.FindingEncryption.from_env()
        ct = enc.encrypt("payload")
        assert enc.decrypt(ct) == "payload"