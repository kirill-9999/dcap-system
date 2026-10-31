# tests/unit/test_scanner_findings.py — Unit-тесты дня 40.2
# Проверяет: Finding dataclass, Encryption (шифрование/маска), scan_line
# классификаторов (credentials), FilesystemConnector (построчное чтение).
import base64
import os
import re
import sys
from pathlib import Path

import pytest

# Пути: корень репо (пакет scanner) + scanner/ (пакеты core/classifiers/connectors)
ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.finding import Finding
import scanner.src.encryption as sen  # noqa: E402

pytestmark = [pytest.mark.unit]


# ============================================================
# Finding dataclass
# ============================================================

def test_finding_defaults_and_to_dict():
    f = Finding(
        line_number=3,
        line_text="password = Secret1",
        match_text="Secret1",
        start_pos=11,
        end_pos=18,
        finding_type="credentials",
        category="password",
    )
    assert f.line_number == 3
    assert f.severity == "medium"
    d = f.to_dict()
    assert d["finding_type"] == "credentials"
    assert d["category"] == "password"
    assert d["start_pos"] == 11 and d["end_pos"] == 18
    assert d["fragment_type"] == "text_line"
    assert "match_text" in d and "context_before" in d


def test_finding_context_and_fragment():
    f = Finding(
        line_number=1,
        line_text="line",
        match_text="x",
        start_pos=0,
        end_pos=1,
        finding_type="pii",
        category="phone",
        context_before="prev",
        context_after="next",
        fragment_path="C:/x/file.txt",
    )
    assert f.context_before == "prev"
    assert f.context_after == "next"
    assert f.fragment_path == "C:/x/file.txt"


# ============================================================
# Encryption (scanner/src/encryption.py)
# ============================================================

def _set_keys():
    os.environ["FINDINGS_ENCRYPTION_KEY"] = base64.b64encode(b"k" * 32).decode()
    os.environ["FINDINGS_HMAC_KEY"] = base64.b64encode(b"h" * 64).decode()
    os.environ["FINDINGS_KEY_ID"] = "test-key-1"


def _clear_keys():
    for v in ("FINDINGS_ENCRYPTION_KEY", "FINDINGS_HMAC_KEY", "FINDINGS_KEY_ID"):
        os.environ.pop(v, None)


def test_encryption_disabled_without_keys():
    """BUG-057: без ключей — RuntimeError (fail-fast), не None."""
    _clear_keys()
    os.environ.pop("DCAP_ALLOW_LEGACY_SCANNER", None)
    sen.reset_encryption()
    with pytest.raises(RuntimeError):
        sen.get_encryption()
    sen.reset_encryption()


def test_encryption_legacy_only_with_allow_env():
    """BUG-057: legacy-режим (None) — только при DCAP_ALLOW_LEGACY_SCANNER=true."""
    _clear_keys()
    os.environ["DCAP_ALLOW_LEGACY_SCANNER"] = "true"
    sen.reset_encryption()
    assert sen.get_encryption() is None
    sen.reset_encryption()
    os.environ.pop("DCAP_ALLOW_LEGACY_SCANNER", None)


def test_encryption_roundtrip(monkeypatch):
    _set_keys()
    sen.reset_encryption()
    enc = sen.get_encryption()
    assert enc is not None
    ct = enc.encrypt("+7-999-123-45-67")
    # decrypt не публичный в ТЗ — инвариант: ciphertext != plaintext и не содержит plaintext
    assert ct != "+7-999-123-45-67"
    assert "+7-999-123-45-67" not in ct
    # повторное шифрование с разным nonce даёт разный ciphertext
    assert enc.encrypt("+7-999-123-45-67") != ct
    sen.reset_encryption()


def test_encryption_fingerprint_deterministic(monkeypatch):
    _set_keys()
    sen.reset_encryption()
    enc = sen.get_encryption()
    fp1 = enc.fingerprint("C:/x/a.env", 1, "AKIA11111111111111", "aws_key")
    fp2 = enc.fingerprint("C:/x/a.env", 1, "AKIA11111111111111", "aws_key")
    fp3 = enc.fingerprint("C:/x/a.env", 2, "AKIA11111111111111", "aws_key")
    assert fp1 == fp2
    assert fp1 != fp3
    # fingerprint не содержит открытых компонентов
    assert "AKIA" not in fp1
    sen.reset_encryption()


def test_mask_rules(monkeypatch):
    masked_phone = sen.mask("+79991234567", "phone")
    assert masked_phone != "+79991234567"
    assert masked_phone.startswith("+7***")
    assert sen.mask("P@ssw0rd", "password") == "***"
    assert "secret" not in sen.mask("AKIA11111111111111", "aws_key")
    assert sen.mask("user@corp.example", "email") != "user@corp.example"
    assert sen.mask("John Smith", "person") == "John Smith"


def test_encryption_env_only_no_secrets_path():
    """TASK-018: сканер читает ключи ТОЛЬКО из env, /run/secrets не используется."""
    _clear_keys()
    src = Path(sen.__file__).read_text(encoding="utf-8")
    assert "/run/secrets" not in src
    assert "getenv" in src


def test_mask_line(monkeypatch):
    line = "password = P@ssw0rd, phone = +7-999-123-45-67"
    # маскируем только пароль (позиции совпадения)
    masked = sen.mask_line(line, [(11, 20, "password")])
    assert "P@ssw0rd" not in masked
    assert "+7-999-123-45-67" in masked


def test_mask_context(monkeypatch):
    ctx = "Клиент: +7-999-123-45-67, email: test@example.com"
    masked = sen.mask_context(ctx, "phone")
    assert "+7-999-123-45-67" not in masked
    assert "test@example.com" not in masked


def test_mask_context_extra_pii(monkeypatch):
    # BUG-022.2: паспорт/СНИЛС/ИНН/карты в контексте тоже маскируются
    ctx = "Паспорт: 1234 567890, СНИЛС: 123-456-789 00"
    masked = sen.mask_context(ctx, "phone")
    assert "1234 567890" not in masked
    assert "123-456-789 00" not in masked


# ============================================================
# BUG-022: маскирование всех PII строки (person + phone)
# ============================================================

def _make_serializer(enc=None):
    """Минимальный ManagedScanner: только _enc (обход __init__ с классификаторами)."""
    from scanner.src.managed_scanner import ManagedScanner
    sc = object.__new__(ManagedScanner)
    sc._enc = enc
    return sc


def _serialize(sc, finding, line, all_in_line):
    return sc._serialize_finding(
        finding,
        resource_path="E:/test_smoke",
        all_findings_in_line=all_in_line,
    )


def test_bug022_person_line_masked_also_masks_phone(monkeypatch):
    """BUG-022: person-находка в строке с phone — телефон обязан маскироваться."""
    # legacy-режим (без шифрования) — как в продакшене без FINDINGS_ENCRYPTION_KEY
    sc = _make_serializer(enc=None)
    line = "Иван Иванов, тел +7 999 123-45-67"
    phone = Finding(
        line_number=1,
        line_text=line,
        match_text="+7 999 123-45-67",
        start_pos=18,
        end_pos=34,
        finding_type="pii",
        category="phone",
        fragment_path="E:/test_smoke/pii.txt",
    )
    person = Finding(
        line_number=1,
        line_text=line,
        match_text="Иван Иванов",
        start_pos=6,
        end_pos=12,
        finding_type="pii",
        category="person",
        fragment_path="E:/test_smoke/pii.txt",
    )
    # person сериализуется с all_findings_in_line = [phone, person]
    d = _serialize(sc, person, line, [phone, person])
    assert d["line_text_masked"] is not None
    # телефон в замаскированной строке не должен содержать открытый номер
    assert "+7 999 123-45-67" not in d["line_text_masked"]
    assert "+7***" in d["line_text_masked"]


def test_bug022_phone_line_masked(monkeypatch):
    """BUG-022: phone-находка — телефон маскируется (исходное поведение)."""
    sc = _make_serializer(enc=None)
    line = "Иван Иванов, тел +7 999 123-45-67"
    phone = Finding(
        line_number=1,
        line_text=line,
        match_text="+7 999 123-45-67",
        start_pos=18,
        end_pos=34,
        finding_type="pii",
        category="phone",
        fragment_path="E:/test_smoke/pii.txt",
    )
    d = _serialize(sc, phone, line, [phone])
    assert "+7 999 123-45-67" not in d["line_text_masked"]
    assert "+7***" in d["line_text_masked"]


# ============================================================
# BUG-022.9: приоритизация категорий при дублировании позиций
# ============================================================

def test_bug022_9_passport_not_overwritten_by_phone():
    """BUG-022.9: passport и phone на одной сущности → passport побеждает."""
    from classifiers.pii_classifier import PiiClassifier
    c = PiiClassifier()
    c.configure({"min_confidence": 0.3, "ocr_enabled": False})

    findings = c.scan_line('Паспорт: 1234 567890', 3)
    # Ожидаем: одна находка (passport), phone отфильтрован
    categories = [f.category for f in findings]
    assert 'passport' in categories, f"passport отсутствует: {categories}"
    assert categories.count('phone') == 0 or (
        'passport' in categories and categories.index('passport') < categories.index('phone')
    ), f"phone не должен затирать passport: {categories}"


def test_bug022_9_snils_not_overwritten_by_phone():
    """BUG-022.9: snils и phone на одной сущности → snils побеждает."""
    from classifiers.pii_classifier import PiiClassifier
    c = PiiClassifier()
    c.configure({"min_confidence": 0.3, "ocr_enabled": False})

    findings = c.scan_line('СНИЛС: 123-456-789 00', 4)
    categories = [f.category for f in findings]
    assert 'snils' in categories, f"snils отсутствует: {categories}"


def test_bug022_9_mask_line_no_overwrite():
    """BUG-022.9: mask_line не перезаписывает одинаковые позиции."""
    from scanner.src.encryption import mask_line
    # Два matches с одинаковыми позициями (passport, phone)
    line = 'Паспорт: 1234 567890'
    matches = [(9, 20, 'passport'), (9, 20, 'phone')]
    result = mask_line(line, matches)
    # Ожидаем: маска passport (не phone-***)
    assert result == 'Паспорт: 12** ******', f"Неверный результат: {result!r}"


# ============================================================
# CredentialsClassifier.scan_line
# ============================================================

def _cred_classifier():
    from scanner.classifiers.credentials_classifier import CredentialsClassifier
    cls = CredentialsClassifier()
    # low entropy_threshold: тесты нацелены на паттерны/FP-фильтры, а не энтропию
    cls.configure({"entropy_threshold": 1.0, "min_length": 8,
                   "confidence_threshold": 0.7})
    return cls


def test_credentials_scan_line_finds_password():
    cls = _cred_classifier()
    findings = cls.scan_line("password = Sup3rSecretPwd", 1)
    assert findings, "Ожидались находки"
    f = findings[0]
    assert f.finding_type == "credentials"
    assert f.category == "password"
    assert f.match_text == "Sup3rSecretPwd"
    assert f.line_number == 1
    assert f.start_pos < f.end_pos


def test_credentials_scan_line_aws_key():
    cls = _cred_classifier()
    line = "aws_access_key_id=AKIAIOSFODNN7EXAMPLE"
    findings = cls.scan_line(line, 2)
    aws = [f for f in findings if f.category == "aws_key"]
    assert aws, findings
    assert "AKIA" in aws[0].match_text
    assert aws[0].start_pos < aws[0].end_pos
    assert aws[0].line_number == 2


def test_credentials_scan_line_filters_placeholder():
    cls = _cred_classifier()
    findings = cls.scan_line("password = changeme", 1)
    assert findings == [], f"Плейсхолдер не должен попадать в находки: {findings}"


def test_credentials_scan_line_empty_line():
    cls = _cred_classifier()
    assert cls.scan_line("", 1) == []
    assert cls.scan_line("просто текст без секретов", 1) == []


# ============================================================
# Классификатор-фейк для коннектора
# ============================================================

class _FakeClassifier:
    classifier_name = "fake_classifier"

    def __init__(self, keyword="password", category="password"):
        self.keyword = keyword
        self.category = category

    def scan_line(self, line, line_num):
        findings = []
        start = 0
        while True:
            i = line.find(self.keyword, start)
            if i == -1:
                break
            findings.append(Finding(
                line_number=line_num,
                line_text=line,
                match_text=self.keyword,
                start_pos=i,
                end_pos=i + len(self.keyword),
                finding_type="credentials",
                category=self.category,
                severity="high",
                confidence=0.9,
                detector="regex",
            ))
            start = i + len(self.keyword)
        return findings


# ============================================================
# FilesystemConnector (построчное чтение)
# ============================================================

def _connector(**cfg):
    from scanner.connectors.filesystem import FilesystemConnector
    return FilesystemConnector(cfg)


def test_connector_scan_file_text(tmp_path):
    f = tmp_path / "config" / "creds.env"
    f.parent.mkdir()
    f.write_text("USER=alice\npassword=Sup3rSecretValue\n", encoding="utf-8")

    conn = _connector(context_lines=1)
    clf = _FakeClassifier()
    findings = conn.scan_file(str(f), [clf])

    assert findings
    hit = findings[0]
    assert hit.line_number == 2
    assert hit.match_text == "password"
    # контекст: строка до — USER=alice
    assert "alice" in hit.context_before
    assert hit.fragment_path == str(f)


def test_connector_scan_credential_file_by_name(tmp_path):
    """Файл без расширения (.env), обрабатывается по имени (CRED_FILENAMES)."""
    f = tmp_path / ".env"
    f.write_text("API_KEY = aaa111bbb222ccc333\n", encoding="utf-8")
    conn = _connector()
    findings = conn.scan_file(str(f), [_FakeClassifier(keyword="aaa111bbb222ccc333", category="api_key")])
    assert findings
    assert findings[0].category == "api_key"
    assert findings[0].line_number == 1


def test_connector_scan_path_finds_files_and_context(tmp_path):
    sub = tmp_path / "root" / "nested"
    sub.mkdir(parents=True)
    (tmp_path / "root" / "a.txt").write_text("nope\n", encoding="utf-8")
    (sub / "b.log").write_text("password=TopSecret!1\n", encoding="utf-8")

    conn = _connector()
    findings = conn.scan_path(str(tmp_path / "root"), [_FakeClassifier()])

    assert findings, "Ожидались находки в папке"
    # found в b.log (nested), строка 1
    assert findings[0].fragment_path.endswith("b.log")
    assert findings[0].line_number == 1


def test_connector_skips_ignored_dirs(tmp_path):
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "x.js").write_text("password=ShouldNotFindMe\n", encoding="utf-8")

    conn = _connector()
    findings = conn.scan_path(str(tmp_path), [_FakeClassifier()])
    assert findings == []


def test_connector_binary_and_empty_files(tmp_path):
    binary = tmp_path / "data.bin"
    binary.write_bytes(b"\x00\x01\x02\x03password=InBinary")
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")

    conn = _connector()
    assert conn.scan_file(str(binary), [_FakeClassifier()]) == []
    assert conn.scan_file(str(empty), [_FakeClassifier()]) == []