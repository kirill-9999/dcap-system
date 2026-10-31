📋 ТЗ: День 40.2 — Findings Refactor: Сканер (построчно + FP + дедуп)
Дата: 12.09.2026
Роль: Кодер
Версия (целевая): v3.10.0
Ветка: feature/day_40.2_scanner_findings
Предыдущая версия: v3.9.0
Этап: 2 из 4 (Findings Refactor)

🎯 Цель дня
Перевести сканер на новую модель находок:

Классификаторы возвращают Finding с позициями (строка, start/end, category)

Filesystem connector — построчное чтение с контекстом

Шифрование + маскирование на стороне сканера

HMAC-fingerprint для каждой находки

FP-фильтр — batch-проверка перед отправкой

Отправка нового формата в Manager

Дедупликация в Manager (не создавать повторно FP/confirmed)

ВАЖНО: сканер должен сохранить обратную совместимость — если Manager старый (без check-fingerprints), работать как раньше. Но целевой режим — новый.

📦 Часть 1. Модель Finding в сканере
1.1. Dataclass Finding
NEW: scanner/src/finding.py

python
"""
Модель находки в сканере.

Находка = конкретное совпадение в строке файла (или фрагменте).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    """Находка в сканере (до шифрования)."""
    # Где найдено
    line_number: int
    line_text: str
    match_text: str
    start_pos: int
    end_pos: int

    # Классификация
    finding_type: str          # pii, credentials, code
    category: str              # phone, email, api_key
    severity: str = "medium"

    # Метаданные
    confidence: float = 0.0
    detector: str = "regex"    # presidio, regex, entropy, ocr

    # Контекст
    context_before: str = ""
    context_after: str = ""

    # Для не-текстовых (заполняется позже)
    fragment_type: str = "text_line"
    fragment_path: Optional[str] = None
    bounding_box: Optional[dict] = None
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None
    hex_preview: Optional[str] = None

    def to_dict(self) -> dict:
        """Для сериализации (без шифрования — оно позже)."""
        return {
            "line_number": self.line_number,
            "line_text": self.line_text,
            "match_text": self.match_text,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "finding_type": self.finding_type,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "detector": self.detector,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "fragment_type": self.fragment_type,
            "fragment_path": self.fragment_path,
            "bounding_box": self.bounding_box,
            "byte_offset": self.byte_offset,
            "byte_length": self.byte_length,
            "hex_preview": self.hex_preview,
        }
📦 Часть 2. Шифрование и маскирование в сканере
2.1. Модуль scanner/src/encryption.py
NEW: scanner/src/encryption.py

python
"""
Шифрование и маскирование находок (на стороне сканера).

Дублирует логику Manager — сканер шифрует перед отправкой,
чтобы открытый текст не покидал хост сканирования.
"""
import os
import re
import hmac
import hashlib
import base64
import logging
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


# ========== КЛЮЧИ ==========

def _read_secret(name: str, default: Optional[bytes] = None) -> bytes:
    """Читает секрет из Docker Secrets → env → default."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read().strip()

    env_val = os.getenv(name.upper())
    if env_val:
        return env_val.encode()

    if default is not None:
        return default

    raise RuntimeError(f"Secret '{name}' not found.")


# ========== МАСКИРОВАНИЕ ==========

MASK_RULES = {
    "phone": lambda s: _mask_phone(s),
    "email": lambda s: re.sub(r"(\w{2})\w+@", r"\1***@", s),
    "api_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "aws_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "password": lambda s: "***",
    "token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "passport": lambda s: (s[:2] + "** ******") if len(s) >= 2 else "***",
    "snils": lambda s: "***-***-*** **",
    "inn": lambda s: (s[:2] + "**********") if len(s) >= 2 else "***",
    "credit_card": lambda s: "**** **** **** " + s[-4:] if len(s) >= 4 else "***",
    "person": lambda s: s,
}


def _mask_phone(s: str) -> str:
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("7"):
        return "+7***" + digits[4:7] + "-" + digits[7:9] + "-" + digits[9:11]
    if len(digits) >= 10:
        return digits[:2] + "***" + digits[-3:]
    return "***"


def mask(value: str, category: str) -> str:
    if not value:
        return value
    fn = MASK_RULES.get(category)
    if fn is None:
        return "***"
    try:
        return fn(value)
    except Exception as e:
        logger.warning("Mask failed for category=%s: %s", category, e)
        return "***"


def mask_line(line: str, matches: list) -> str:
    """matches: [(start, end, category), ...]"""
    if not matches:
        return line
    sorted_matches = sorted(matches, key=lambda m: m[0], reverse=True)
    result = line
    for start, end, category in sorted_matches:
        original = result[start:end]
        masked = mask(original, category)
        result = result[:start] + masked + result[end:]
    return result


def mask_context(context: str, category: str) -> str:
    """
    Маскирует контекст (строки до/после).
    Простая эвристика: маскирует всё, что похоже на секрет.
    """
    if not context:
        return context
    # Маскируем по общим паттернам
    result = context
    # Телефоны
    result = re.sub(r"\+\d{11}", lambda m: mask(m.group(), "phone"), result)
    # Email
    result = re.sub(r"\S+@\S+\.\S+", lambda m: mask(m.group(), "email"), result)
    return result


# ========== ШИФРОВАНИЕ ==========

class ScannerEncryption:
    """
    AES-256-GCM + HMAC-fingerprint (на стороне сканера).

    Ключи — env или Docker Secrets:
      FINDINGS_ENCRYPTION_KEY (base64, 32 байта)
      FINDINGS_HMAC_KEY       (base64, 32 байта)
      FINDINGS_KEY_ID         (строка)
    """

    def __init__(self, key: bytes, hmac_key: bytes, key_id: str):
        if len(key) != 32:
            raise ValueError(f"Encryption key must be 32 bytes, got {len(key)}")
        if len(hmac_key) < 32:
            raise ValueError(f"HMAC key must be >= 32 bytes")

        self.aes = AESGCM(key)
        self.hmac_key = hmac_key
        self.key_id = key_id

    @classmethod
    def from_env(cls) -> Optional["ScannerEncryption"]:
        """
        Загружает ключи из env. Если не заданы — возвращает None
        (сканер работает в legacy-режиме без шифрования).
        """
        enc_key = os.getenv("FINDINGS_ENCRYPTION_KEY")
        hmac_key = os.getenv("FINDINGS_HMAC_KEY")

        if not enc_key or not hmac_key:
            logger.warning(
                "FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY not set. "
                "Scanner will send findings in legacy format (no encryption). "
                "Manager will encrypt on receipt."
            )
            return None

        try:
            key = base64.b64decode(enc_key)
            hm = base64.b64decode(hmac_key)
            key_id = os.getenv("FINDINGS_KEY_ID", "key-2026-09")
            return cls(key, hm, key_id)
        except Exception as e:
            logger.error("Failed to load encryption keys: %s", e)
            return None

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        nonce = os.urandom(12)
        ct = self.aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def fingerprint(self, file_path: str, line: int, match: str, category: str) -> str:
        msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
        return hmac.new(self.hmac_key, msg, hashlib.sha256).hexdigest()


# ========== СИНГЛТОН ==========

_instance: Optional[ScannerEncryption] = None
_initialized = False


def get_encryption() -> Optional[ScannerEncryption]:
    """Синглтон. Возвращает None, если ключи не заданы (legacy-режим)."""
    global _instance, _initialized
    if not _initialized:
        _instance = ScannerEncryption.from_env()
        _initialized = True
    return _instance


def reset_encryption():
    global _instance, _initialized
    _instance = None
    _initialized = False
ВАЖНО: Если ключи не заданы — сканер работает в legacy-режиме (шлёт открытый текст, Manager шифрует сам). Это позволяет не ломать существующий флоу.

📦 Часть 3. Классификаторы — возвращают Finding
3.1. Общий интерфейс
MODIFIED: все классификаторы в scanner/classifiers/ — добавить метод scan_line(line, line_num) -> list[Finding].

Сохранить существующий метод scan_text(text) -> ... для обратной совместимости.

3.2. PII-классификатор
MODIFIED: scanner/classifiers/pii_classifier.py

python
"""
PII-классификатор: возвращает Finding с позициями.
"""
import logging
from typing import Optional

from scanner.src.finding import Finding

logger = logging.getLogger(__name__)


class PIIClassifier:
    # ... существующий __init__ ...

    def scan_line(self, line: str, line_num: int) -> list[Finding]:
        """
        Сканирует одну строку, возвращает список Finding.
        """
        findings = []

        # 1. Presidio (если доступен)
        if self.presidio_analyzer:
            try:
                results = self.presidio_analyzer.analyze(
                    text=line,
                    language="ru",
                    score_threshold=self.min_score,
                )
                for r in results:
                    match_text = line[r.start:r.end]
                    findings.append(Finding(
                        line_number=line_num,
                        line_text=line,
                        match_text=match_text,
                        start_pos=r.start,
                        end_pos=r.end,
                        finding_type="pii",
                        category=self._map_presidio_entity(r.entity_type),
                        severity=self._severity(r.entity_type),
                        confidence=r.score,
                        detector="presidio",
                    ))
            except Exception as e:
                logger.warning("Presidio failed on line %d: %s", line_num, e)

        # 2. Regex-паттерны (кастомные)
        for pattern, category, severity in self.custom_patterns:
            for m in pattern.finditer(line):
                findings.append(Finding(
                    line_number=line_num,
                    line_text=line,
                    match_text=m.group(),
                    start_pos=m.start(),
                    end_pos=m.end(),
                    finding_type="pii",
                    category=category,
                    severity=severity,
                    confidence=0.85,
                    detector="regex",
                ))

        # Дедупликация внутри строки (по позиции)
        return self._deduplicate(findings)

    def _map_presidio_entity(self, entity_type: str) -> str:
        """PHONE_NUMBER → phone, EMAIL_ADDRESS → email, и т.д."""
        mapping = {
            "PHONE_NUMBER": "phone",
            "EMAIL_ADDRESS": "email",
            "PERSON": "person",
            "CREDIT_CARD": "credit_card",
            "RU_PASSPORT": "passport",
            "RU_SNILS": "snils",
            "RU_INN": "inn",
        }
        return mapping.get(entity_type, entity_type.lower())

    def _severity(self, entity_type: str) -> str:
        high = {"CREDIT_CARD", "RU_PASSPORT", "RU_SNILS"}
        return "high" if entity_type in high else "medium"

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Убирает дубликаты (одинаковые позиции)."""
        seen = set()
        result = []
        for f in findings:
            key = (f.start_pos, f.end_pos, f.category)
            if key not in seen:
                seen.add(key)
                result.append(f)
        return result
3.3. Credentials-классификатор
MODIFIED: scanner/classifiers/credentials_classifier.py

python
"""
Credentials-классификатор: возвращает Finding с позициями.
"""
import logging

from scanner.src.finding import Finding

logger = logging.getLogger(__name__)


class CredentialsClassifier:
    # ... существующий __init__ (префильтр, FP-фильтры, CRED_FILE_NAMES) ...

    def scan_line(self, line: str, line_num: int) -> list[Finding]:
        """Сканирует строку на credentials."""
        # Префильтр (быстрый)
        if not self.prefilter.search(line):
            return []

        findings = []

        for pattern, category, severity in self.patterns:
            for m in pattern.finditer(line):
                match_text = m.group()
                # FP-фильтры (существующие)
                if self._is_false_positive(match_text, line):
                    continue

                findings.append(Finding(
                    line_number=line_num,
                    line_text=line,
                    match_text=match_text,
                    start_pos=m.start(),
                    end_pos=m.end(),
                    finding_type="credentials",
                    category=category,
                    severity=severity,
                    confidence=0.90,
                    detector="regex",
                ))

        # Entropy-детекция (если есть)
        if self.entropy_enabled:
            for m in self.entropy_pattern.finditer(line):
                value = m.group()
                if self._entropy(value) >= self.min_entropy:
                    findings.append(Finding(
                        line_number=line_num,
                        line_text=line,
                        match_text=value,
                        start_pos=m.start(),
                        end_pos=m.end(),
                        finding_type="credentials",
                        category="high_entropy",
                        severity="high",
                        confidence=0.75,
                        detector="entropy",
                    ))

        return self._deduplicate(findings)
3.4. Code-классификатор
MODIFIED: scanner/classifiers/code_classifier.py — аналогично, scan_line.

Примечание: Code-классификатор может не возвращать построчные находки (если он определяет язык/фреймворк). Тогда scan_line возвращает [], а результаты — на уровне файла (отдельный метод).

📦 Часть 4. Filesystem connector — построчное чтение
4.1. Обновление scanner/connectors/filesystem.py
MODIFIED: scanner/connectors/filesystem.py

python
"""
Filesystem connector: построчное чтение с контекстом.
"""
import logging
from pathlib import Path

from scanner.src.finding import Finding

logger = logging.getLogger(__name__)

CONTEXT_LINES = 3  # строк до/после


class FilesystemConnector:
    # ... существующий __init__ ...

    def scan_file(self, file_path: str) -> list[Finding]:
        """
        Сканирует файл построчно, возвращает список Finding.
        """
        findings = []

        # 1. Определить тип файла
        ext = Path(file_path).suffix.lower()

        # 2. Текстовые — построчно
        if self._is_text_file(ext):
            findings = self._scan_text_file(file_path)
        # 3. Документы (docx, xlsx, pdf) — через document_extractor
        elif self._is_document(ext):
            findings = self._scan_document(file_path)
        # 4. Изображения — через OCR (Этап 40.4)
        elif self._is_image(ext):
            findings = self._scan_image(file_path)
        # 5. Бинарные — пропускаем (Этап 40.4)
        else:
            logger.debug("Skipping binary: %s", file_path)

        return findings

    def _is_text_file(self, ext: str) -> bool:
        return ext in self.text_extensions

    def _scan_text_file(self, file_path: str) -> list[Finding]:
        """Построчное чтение с контекстом."""
        findings = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            return []

        # Нормализация (убрать \n)
        lines = [line.rstrip("\n\r") for line in lines]

        for i, line in enumerate(lines, start=1):
            # Пропускаем пустые
            if not line.strip():
                continue

            # Все классификаторы
            for classifier in self.classifiers:
                try:
                    line_findings = classifier.scan_line(line, i)
                except Exception as e:
                    logger.warning("Classifier failed on %s:%d: %s", file_path, i, e)
                    continue

                # Добавляем контекст
                for f in line_findings:
                    f.context_before = self._get_context(lines, i, before=True)
                    f.context_after = self._get_context(lines, i, before=False)
                    findings.append(f)

        return findings

    def _get_context(self, lines: list[str], line_num: int, before: bool) -> str:
        """Возвращает N строк контекста (до или после)."""
        if before:
            start = max(0, line_num - 1 - CONTEXT_LINES)
            end = line_num - 1
        else:
            start = line_num
            end = min(len(lines), line_num + CONTEXT_LINES)

        return "\n".join(lines[start:end])

    def _scan_document(self, file_path: str) -> list[Finding]:
        """Сканирует документ (docx, xlsx, pdf)."""
        from scanner.utils.document_extractor import extract_text

        try:
            text = extract_text(file_path)
        except Exception as e:
            logger.warning("Failed to extract %s: %s", file_path, e)
            return []

        findings = []
        lines = text.splitlines()

        for i, line in enumerate(lines, start=1):
            for classifier in self.classifiers:
                try:
                    line_findings = classifier.scan_line(line, i)
                except Exception:
                    continue
                findings.extend(line_findings)

        return findings

    def _scan_image(self, file_path: str) -> list[Finding]:
        """OCR изображений (Этап 40.4 — заглушка)."""
        logger.debug("Image scanning not implemented yet: %s", file_path)
        return []
4.2. Конфигурация
MODIFIED: scanner/config/scanner_config.json — добавить:

json
{
  "scanner": {
    "context_lines": 3,
    "text_extensions": [".txt", ".log", ".md", ".py", ".js", ".json", ".yaml", ".yml", ".xml", ".html", ".css", ".csv", ".env", ".ini", ".cfg", ".conf", ".sql", ".sh", ".bat", ".ps1"]
  }
}
📦 Часть 5. Managed Scanner — FP-фильтр + отправка
5.1. Обновление scanner/src/managed_scanner.py
MODIFIED: scanner/src/managed_scanner.py

python
"""
Managed Scanner: FP-фильтр + шифрование + отправка.
"""
import logging
from scanner.src.finding import Finding
from scanner.src.encryption import get_encryption, mask, mask_line, mask_context

logger = logging.getLogger(__name__)


class ManagedScanner:
    # ... существующий __init__ ...

    def _execute_task(self, task: dict) -> dict:
        """Выполняет задание, возвращает результаты."""
        resource_path = task["path"]
        task_id = task["id"]

        # 1. Сканирование (построчно)
        findings: list[Finding] = self.connector.scan_file(resource_path)
        logger.info("Found %d raw findings in %s", len(findings), resource_path)

        if not findings:
            return {
                "files_scanned": 1,
                "findings": [],
                "files_failed": 0,
            }

        # 2. Шифрование + маскирование
        enc = get_encryption()
        serialized = []

        for f in findings:
            # Fingerprint (нужен открытый match_text)
            if enc:
                fp = enc.fingerprint(resource_path, f.line_number, f.match_text, f.category)
                match_enc = enc.encrypt(f.match_text)
                line_enc = enc.encrypt(f.line_text)
                key_id = enc.key_id
            else:
                # Legacy: без шифрования (Manager зашифрует)
                fp = self._legacy_fingerprint(resource_path, f.line_number, f.match_text, f.category)
                match_enc = None
                line_enc = None
                key_id = None

            # Маскирование
            match_masked = mask(f.match_text, f.category)
            line_masked = mask_line(
                f.line_text,
                [(f.start_pos, f.end_pos, f.category)]
            )
            context_before_masked = mask_context(f.context_before, f.category)
            context_after_masked = mask_context(f.context_after, f.category)

            serialized.append({
                "line_number": f.line_number,
                "fragment_type": f.fragment_type,
                "finding_type": f.finding_type,
                "category": f.category,
                "severity": f.severity,
                "match_text_masked": match_masked,
                "match_text_encrypted": match_enc,
                "line_text_masked": line_masked,
                "line_text_encrypted": line_enc,
                "context_before_masked": context_before_masked,
                "context_after_masked": context_after_masked,
                "fingerprint": fp,
                "encryption_key_id": key_id,
                "confidence": f.confidence,
                "detector": f.detector,
                "fragment_path": f.fragment_path,
                "bounding_box": f.bounding_box,
                "byte_offset": f.byte_offset,
                "byte_length": f.byte_length,
                "hex_preview": f.hex_preview,
            })

        # 3. FP-фильтр (batch-проверка)
        serialized = self._filter_false_positives(serialized)
        logger.info("After FP-filter: %d findings", len(serialized))

        return {
            "files_scanned": 1,
            "findings": serialized,
            "files_failed": 0,
        }

    def _filter_false_positives(self, findings: list[dict]) -> list[dict]:
        """
        Проверяет fingerprints в Manager, убирает FP.
        Если Manager не поддерживает — возвращает всё как есть.
        """
        if not findings:
            return findings

        fingerprints = [f["fingerprint"] for f in findings]

        try:
            r = self.client.post(
                "/api/findings/check-fingerprints",
                json={"fingerprints": fingerprints},
                timeout=30,
            )
            if r.status_code == 404:
                # Manager старый — нет эндпоинта
                logger.warning("check-fingerprints not available (old Manager?)")
                return findings

            if r.status_code != 200:
                logger.warning("check-fingerprints failed: %s", r.status_code)
                return findings

            data = r.json()
            fp_set = set(data.get("false_positives", []))

            if fp_set:
                logger.info("Filtered %d false positives", len(fp_set))

            return [f for f in findings if f["fingerprint"] not in fp_set]

        except Exception as e:
            logger.warning("FP-filter failed: %s", e)
            return findings

    def _legacy_fingerprint(self, file_path: str, line: int, match: str, category: str) -> str:
        """Fingerprint без HMAC (для legacy-режима)."""
        import hashlib
        msg = f"{file_path}|{line}|{match}|{category}".encode()
        return hashlib.md5(msg).hexdigest()
5.2. Отправка результатов
MODIFIED: scanner/src/managed_scanner.py — метод отправки результатов:

python
def _submit_results(self, task_id: int, results: dict):
    """Отправляет результаты в Manager."""
    payload = {
        "task_id": task_id,
        "files_scanned": results["files_scanned"],
        "findings": results["findings"],
        "files_failed": results.get("files_failed", 0),
    }

    r = self.client.post(
        f"/api/scanner/tasks/{task_id}/results",
        json=payload,
        timeout=60,
    )

    if r.status_code not in (200, 201, 202):
        logger.error("Failed to submit results: %s %s", r.status_code, r.text)
        raise RuntimeError(f"Submit failed: {r.status_code}")

    logger.info("Submitted %d findings for task %d", len(results["findings"]), task_id)
📦 Часть 6. Manager — приём нового формата + дедупликация
6.1. Обновление manager/src/api/scanner.py
MODIFIED: manager/src/api/scanner.py — метод submit_results:

python
"""
Приём результатов от сканера: новый формат + дедупликация.
"""
import logging
from datetime import datetime

from manager.src.db.models import Finding, ScanTask, Resource
from manager.src.core.encryption import get_encryption, mask

logger = logging.getLogger(__name__)


@router.post("/tasks/{task_id}/results")
def submit_results(
    task_id: int,
    results: dict,
    db: Session = Depends(get_db),
):
    """
    Принимает результаты сканирования.
    Поддерживает новый формат (findings с line_number) и legacy (file-level).
    """
    task = db.query(ScanTask).filter(ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")

    enc = get_encryption()
    findings_data = results.get("findings", [])
    created = 0
    skipped_fp = 0
    updated = 0

    for f_data in findings_data:
        # 1. Проверяем fingerprint
        fp = f_data.get("fingerprint")
        if not fp:
            # Legacy-формат без fingerprint — вычисляем
            fp = enc.fingerprint(
                task.resource.path if task.resource else "",
                f_data.get("line_number", 0),
                f_data.get("match_text", f_data.get("value", "")),
                f_data.get("category", "unknown"),
            )

        existing = db.query(Finding).filter(Finding.fingerprint == fp).first()

        if existing:
            if existing.status == "false_positive":
                # FP — НЕ создавать повторно
                skipped_fp += 1
                continue
            # Обновляем last_seen_at
            existing.last_seen_at = datetime.utcnow()
            updated += 1
            continue

        # 2. Создаём новую находку
        try:
            finding = _create_finding_from_data(
                db, task, f_data, fp, enc
            )
            db.add(finding)
            created += 1
        except Exception as e:
            logger.error("Failed to create finding: %s", e)
            continue

    db.commit()

    # Обновляем задание
    task.status = "completed"
    task.files_scanned = results.get("files_scanned", 0)
    task.findings_count = created
    task.files_failed = results.get("files_failed", 0)
    task.completed_at = datetime.utcnow()
    db.commit()

    return {
        "task_id": task_id,
        "created": created,
        "updated": updated,
        "skipped_false_positives": skipped_fp,
        "status": "completed",
    }


def _create_finding_from_data(db, task, f_data: dict, fp: str, enc):
    """Создаёт Finding из данных сканера."""
    # Определяем, зашифровано ли (новый формат) или открытый текст (legacy)
    match_enc = f_data.get("match_text_encrypted")
    match_masked = f_data.get("match_text_masked")
    line_enc = f_data.get("line_text_encrypted")
    line_masked = f_data.get("line_text_masked")
    key_id = f_data.get("encryption_key_id")

    # Legacy: сканер прислал открытый текст — шифруем сами
    if not match_enc and f_data.get("match_text"):
        match_enc = enc.encrypt(f_data["match_text"])
        match_masked = f_data.get("match_text_masked") or mask(
            f_data["match_text"], f_data.get("category", "unknown")
        )
        key_id = enc.key_id

    if not line_enc and f_data.get("line_text"):
        line_enc = enc.encrypt(f_data["line_text"])
        line_masked = f_data.get("line_text_masked") or mask(
            f_data["line_text"], f_data.get("category", "unknown")
        )

    return Finding(
        resource_id=task.resource_id,
        task_id=task.id,
        finding_type=f_data.get("finding_type", "unknown"),
        category=f_data.get("category", "unknown"),
        severity=f_data.get("severity", "medium"),
        fragment_type=f_data.get("fragment_type", "text_line"),
        line_number=f_data.get("line_number"),
        match_text_masked=match_masked,
        match_text_encrypted=match_enc,
        line_text_masked=line_masked,
        line_text_encrypted=line_enc,
        context_before_masked=f_data.get("context_before_masked"),
        context_after_masked=f_data.get("context_after_masked"),
        fragment_path=f_data.get("fragment_path"),
        bounding_box=f_data.get("bounding_box"),
        byte_offset=f_data.get("byte_offset"),
        byte_length=f_data.get("byte_length"),
        hex_preview=f_data.get("hex_preview"),
        fingerprint=fp,
        encryption_key_id=key_id or enc.key_id,
        confidence=f_data.get("confidence"),
        detector=f_data.get("detector", "legacy"),
        status="new",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
6.2. check-fingerprints — уже есть (День 40.1)
Проверить, что эндпоинт работает. Если нет — восстановить из ТЗ Дня 40.1.

📦 Часть 7. Тесты
7.1. Unit-тесты сканера
NEW: tests/unit/test_scanner_findings.py

python
"""Unit-тесты сканера: Finding, маскирование, fingerprint."""
import os
import pytest
from scanner.src.finding import Finding
from scanner.src.encryption import (
    ScannerEncryption, mask, mask_line, get_encryption, reset_encryption
)


def test_finding_to_dict():
    f = Finding(
        line_number=42,
        line_text="Иван Иванов, +7-999-123-45-67",
        match_text="+7-999-123-45-67",
        start_pos=13,
        end_pos=29,
        finding_type="pii",
        category="phone",
        confidence=0.95,
        detector="regex",
    )
    d = f.to_dict()
    assert d["line_number"] == 42
    assert d["category"] == "phone"
    assert d["fragment_type"] == "text_line"


def test_mask_phone():
    assert mask("+7-999-123-45-67", "phone") == "+7***123-45-67"


def test_mask_line_scanner():
    line = "Иван Иванов, +7-999-123-45-67, ivan@example.com"
    matches = [(13, 29, "phone"), (31, 47, "email")]
    result = mask_line(line, matches)
    assert "+7-999-123-45-67" not in result
    assert "ivan@example.com" not in result


def test_scanner_encryption_roundtrip():
    enc = ScannerEncryption(os.urandom(32), os.urandom(32), "test")
    plain = "secret_value"
    cipher = enc.encrypt(plain)
    assert cipher != plain
    # decrypt только на Manager (здесь нет метода decrypt)


def test_scanner_fingerprint_deterministic():
    enc = ScannerEncryption(os.urandom(32), os.urandom(32), "test")
    fp1 = enc.fingerprint("/path/file.txt", 42, "+7-999-123-45-67", "phone")
    fp2 = enc.fingerprint("/path/file.txt", 42, "+7-999-123-45-67", "phone")
    assert fp1 == fp2


def test_scanner_no_keys_returns_none(monkeypatch):
    monkeypatch.delenv("FINDINGS_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("FINDINGS_HMAC_KEY", raising=False)
    reset_encryption()
    assert get_encryption() is None
7.2. E2E-тесты сканера
NEW: tests/e2e/test_scanner_findings.py

python
"""E2E-тесты: сканер → Manager → findings построчно."""
import pytest
import time
import requests


@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_scan_creates_line_findings(api_client, manager_url, tmp_path, cleanup_tasks):
    """Сканирование создаёт находки с line_number."""
    # 1. Создать тестовый файл
    test_dir = tmp_path / "scan_test"
    test_dir.mkdir()
    (test_dir / "pii.txt").write_text(
        "Контакты:\n"
        "Иван Иванов, +7-999-123-45-67\n"
        "ivan@example.com\n",
        encoding="utf-8"
    )

    # 2. Создать задание
    r = api_client.post(f"{manager_url}/api/tasks/create", json={
        "resource_path": str(test_dir),
        "resource_type": "FILESYSTEM",
    })
    task_id = r.json()["task_id"]
    cleanup_tasks.append(task_id)

    # 3. Ждать завершения
    deadline = time.time() + 300
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id}")
        status = r.json().get("status")
        if status == "completed":
            break
        if status == "failed":
            pytest.fail(f"Task failed: {r.json()}")
        time.sleep(2)
    assert status == "completed"

    # 4. Проверить находки (построчно!)
    r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id})
    assert r.status_code == 200
    findings = r.json()

    assert len(findings) > 0, "No findings"

    # Проверяем, что есть line_number
    lines = [f.get("line_number") for f in findings if f.get("line_number")]
    assert len(lines) > 0, "No line_number in findings"

    # Проверяем, что phone найден на строке 2
    phone_findings = [f for f in findings if f.get("category") == "phone"]
    if phone_findings:
        assert phone_findings[0]["line_number"] == 2

    # 5. Проверить, что match_text маскирован
    for f in findings:
        if f.get("category") == "phone":
            assert "+7-999-123-45-67" not in (f.get("match_text") or ""), \
                "Phone not masked!"


@pytest.mark.e2e
@pytest.mark.requires_manager
@pytest.mark.requires_scanner
def test_false_positive_not_recreated(api_client, manager_url, tmp_path, cleanup_tasks):
    """
    FP не создаётся повторно при повторном сканировании.
    """
    test_dir = tmp_path / "fp_test"
    test_dir.mkdir()
    (test_dir / "creds.env").write_text("TEST_KEY=AKIAIOSFODNN7EXAMPLE\n")

    # 1. Первое сканирование
    r = api_client.post(f"{manager_url}/api/tasks/create", json={
        "resource_path": str(test_dir),
        "resource_type": "FILESYSTEM",
    })
    task_id = r.json()["task_id"]
    cleanup_tasks.append(task_id)

    # Ждать завершения
    deadline = time.time() + 300
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id}")
        if r.json().get("status") == "completed":
            break
        time.sleep(2)

    # 2. Получить находки
    r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id})
    findings = r.json()
    if not findings:
        pytest.skip("No findings to mark as FP")
    finding_id = findings[0]["id"]

    # 3. Пометить как FP (нужен auditor token)
    auditor_token = _login(manager_url, "auditor", "auditor123")
    if not auditor_token:
        pytest.skip("auditor user not available")

    r = requests.patch(
        f"{manager_url}/api/findings/{finding_id}",
        json={"status": "false_positive", "comment": "test"},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert r.status_code == 200

    # 4. Повторное сканирование
    r = api_client.post(f"{manager_url}/api/tasks/create", json={
        "resource_path": str(test_dir),
        "resource_type": "FILESYSTEM",
    })
    task_id2 = r.json()["task_id"]
    cleanup_tasks.append(task_id2)

    # Ждать
    deadline = time.time() + 300
    while time.time() < deadline:
        r = api_client.get(f"{manager_url}/api/tasks/{task_id2}")
        if r.json().get("status") == "completed":
            break
        time.sleep(2)

    # 5. Проверить: находка НЕ создана повторно
    r = api_client.get(f"{manager_url}/api/findings", params={"task_id": task_id2})
    findings2 = r.json()
    assert len(findings2) == 0, f"FP recreated: {findings2}"


def _login(manager_url, username, password):
    r = requests.post(f"{manager_url}/api/auth/login",
                      json={"username": username, "password": password})
    return r.json().get("access_token") if r.status_code == 200 else None
📦 Часть 8. Документация и обновления
8.1. STATE.md (кодер обновит в конце)
Версия → v3.10.0

Текущий день → 40.3

Последний отчёт → day_40.2_report.md

8.2. ROADMAP.md
День 40.2 ✅

BACKLOG-053, 054, 055 ✅

8.3. docs/deployment.md
Добавить раздел про env-переменные сканера:

markdown
### Ключи шифрования сканера

Для шифрования находок **на стороне сканера** (рекомендуется):

```bash
export FINDINGS_ENCRYPTION_KEY=<base64 32 bytes>  # тот же, что у Manager
export FINDINGS_HMAC_KEY=<base64 32 bytes>
export FINDINGS_KEY_ID=key-2026-09
Если не заданы — сканер работает в legacy-режиме (открытый текст → Manager шифрует сам).

text

### 8.4. `scanner/config/scanner_config.json`

Добавить `context_lines`, `text_extensions` (см. выше).

---

## ✅ Критерии приёмки Дня 40.2

1. **`Finding` dataclass** в сканере (`scanner/src/finding.py`)
2. **Шифрование** (`scanner/src/encryption.py`) — AES-256-GCM + HMAC + маскирование
3. **Классификаторы** возвращают `Finding` с позициями (`scan_line`)
4. **Filesystem connector** — построчное чтение + контекст (N строк до/после)
5. **FP-фильтр** — batch-проверка `check-fingerprints` перед отправкой
6. **Отправка нового формата** — `match_text_encrypted`, `fingerprint`, `line_number`
7. **Manager: дедупликация** — FP не создаются повторно, confirmed обновляют `last_seen_at`
8. **Backward compatibility** — старый Manager (без check-fingerprints) → legacy-режим
9. **Тесты** — unit (Finding, mask, encryption) + e2e (построчные находки, FP)
10. **`STATE.md` обновлён** (v3.10.0)
11. **`ROADMAP.md`** — День 40.2 ✅

---

## 📁 Артефакты (итог)

**NEW:**
- `scanner/src/finding.py`
- `scanner/src/encryption.py`
- `tests/unit/test_scanner_findings.py`
- `tests/e2e/test_scanner_findings.py`
- `prompts/reports/day_40.2_report.md` (после выполнения)

**MODIFIED:**
- `scanner/classifiers/pii_classifier.py` (`scan_line`)
- `scanner/classifiers/credentials_classifier.py` (`scan_line`)
- `scanner/classifiers/code_classifier.py` (`scan_line`)
- `scanner/connectors/filesystem.py` (построчное чтение + контекст)
- `scanner/src/managed_scanner.py` (FP-фильтр, шифрование, отправка)
- `manager/src/api/scanner.py` (`submit_results`: новый формат + дедупликация)
- `scanner/config/scanner_config.json` (`context_lines`, `text_extensions`)
- `docs/deployment.md` (env сканера)
- `STATE.md` (v3.10.0)
- `ROADMAP.md` (День 40.2 ✅)

**DELETED:** —

---

## 🚀 Команда коммита

```bash
git checkout -b feature/day_40.2_scanner_findings
git add -A
git commit -m "feat: День 40.2 — Findings Refactor: сканер (построчно + FP + дедуп) (v3.10.0)

Модель находки в сканере (BACKLOG-053):
- scanner/src/finding.py: Finding dataclass (line_number, match_text,
  start_pos, end_pos, category, confidence, detector, контекст)
- scanner/src/encryption.py: AES-256-GCM + HMAC-fingerprint + маскирование
- Классификаторы: scan_line(line, line_num) → list[Finding]
  (pii, credentials, code)
- Filesystem connector: построчное чтение + контекст (N строк до/после)
- Конфиг: context_lines, text_extensions

FP-фильтр + дедупликация (BACKLOG-054/055):
- scanner/src/managed_scanner.py: batch-проверка check-fingerprints
- Фильтрация FP перед отправкой
- Отправка нового формата (match_text_encrypted, fingerprint, line_number)
- Legacy-режим (если ключи не заданы)

Manager:
- manager/src/api/scanner.py: submit_results поддерживает новый формат
- Дедупликация: FP не создаются повторно, confirmed обновляют last_seen_at
- Legacy-формат конвертируется в новый

Тесты:
- tests/unit/test_scanner_findings.py: Finding, mask, encryption, fingerprint
- tests/e2e/test_scanner_findings.py: построчные находки, FP не дублируются

Docs:
- STATE.md → v3.10.0, следующий — День 40.3
- ROADMAP.md: День 40.2 ✅
- docs/deployment.md: env сканера (FINDINGS_*)"
📝 Обратная связь архитектору (шаблон)
После выполнения — заполнить:

Что заработало / что нет

Отклонения от ТЗ (Presidio, entropy, code classifier)

Проблемы с legacy-режимом

Производительность (скорость сканирования)

Готовность к Дню 40.3 (WebUI)

⚠️ Важные замечания
Ключи должны совпадать у сканера и Manager (один FINDINGS_ENCRYPTION_KEY). Иначе Manager не расшифрует.

Legacy-режим — если ключи не заданы у сканера, он шлёт открытый текст. Manager шифрует сам. Менее безопасно — открытый текст идёт по сети.

Presidio может быть медленным на больших файлах. Построчное сканирование — ок, но если файл 100k строк, может быть долго.

Context — 3 строки до/после. Настраивается.

Code-классификатор — может не возвращать построчные находки (он про язык/фреймворк). Если так — scan_line возвращает [].