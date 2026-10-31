# 🔧 ТЗ №3: Fix-спринт по итогам Блока 3 (Scanner deep) + BUG-061

**Дата:** 20.09.2026
**Версия:** v3.13.10 → **v3.13.11** (или v3.14.0, если критично)
**Ветка:** `fix/scanner_deep`
**Приоритет:** 🔴 важно (блокеры v3.0.0: BUG-067, 067b, 063, 066)
**Источник:** `STATE_TEST_SESSION.md` (Блок 3)
**Оценка:** ~6 часов

---

## 🎯 Контекст

**По итогам Блока 3 (Scanner deep) найдено:**

- 🔴 **BUG-067** — изображения **не обрабатываются** (stub в `scan_file`) — критично.
- 🔴 **BUG-067b** — PDF-сканы **не обрабатываются** (`ocr_enabled=False`).
- 🔴 **BUG-063** — `credit_card` **не детектируется** (критично для PCI DSS).
- 🔴 **BUG-066** — `url`-детектор **ложно срабатывает** на email-домены (дубликаты).
- 🟡 **BUG-061** — сканер **не восстанавливает** HTTP после падения Manager.
- 🟡 **BUG-065** — `database_url`/`basic_auth`/`github_token`/`slack_token` falls back на `high_entropy`.
- 🟢 **BUG-062** — избыточные логи.

**Что работает (не трогать):**
- PII: email, phone, passport, snils, inn.
- Credentials: aws_key, token, high_entropy.
- Presidio + кастомные RU-распознаватели.
- Entropy-детектор.
- Маскирование (BUG-044 закрыт).
- AES-256-GCM + HMAC-fingerprint.
- Дедупликация, FP-фильтр, батчинг.

---

## 📋 Задачи

### TASK-022 — BUG-067: OCR для изображений

**Приоритет:** 🔴 **критично**

**Компонент:** `scanner/src/connectors/filesystem.py::scan_file`, новый метод `_scan_image`.

**Проблема:**

```python
# filesystem.py::scan_file (текущий код)
if ext in _IMAGE_EXTENSIONS:
    return []   # ← stub, «не сканируем построчно (день 40.2)»
Изображения (png, jpg, jpeg, gif, bmp, tiff, webp) явно пропускаются. OCR не вызывается. Findings image_region не создаются.

Fix:

Реализовать _scan_image через Pillow + Tesseract:

python
def scan_file(self, file_path: str, classifiers: List[Any]) -> List[Finding]:
    p = Path(file_path)
    if not p.exists():
        return []
    ext = p.suffix.lower().lstrip('.')

    if ext in self._text_extensions or p.name.lower() in self._cred_filenames:
        text = self._read_text(str(p))
        if text is None:
            return []
        return self._scan_text(text, classifiers, str(p))

    if ext in _DOCUMENT_EXTENSIONS:
        text = self._extract_document(str(p), ext)
        if not text:
            return []
        return self._scan_text(text, classifiers, str(p))

    # BUG-067 fix: изображения — OCR + image_region findings
    if ext in _IMAGE_EXTENSIONS:
        return self._scan_image(str(p), classifiers)

    return []

def _scan_image(self, file_path: str, classifiers: List[Any]) -> List[Finding]:
    """OCR изображения через Tesseract.
    
    Возвращает findings с fragment_type="image_region", detector="ocr".
    Для bounding_box — использует image_to_data (word-level координаты).
    """
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        logger.warning("PIL/pytesseract not installed — image scan skipped")
        return []
    
    findings: List[Finding] = []
    try:
        img = Image.open(file_path)
        # Получаем текст + координаты по словам
        data = pytesseract.image_to_data(
            img, lang="rus+eng", output_type=pytesseract.Output.DICT
        )
        # Собираем строку с координатами слов
        # Простой подход: OCR всего текста → scan_text
        full_text = pytesseract.image_to_string(img, lang="rus+eng")
        if not full_text.strip():
            return []
        
        # Сканируем текст теми же классификаторами
        text_findings = self._scan_text(full_text, classifiers, file_path)
        
        # Преобразуем в image_region
        for f in text_findings:
            f.fragment_type = "image_region"
            f.detector = "ocr"
            # bounding_box: найти позицию finding в OCR-данных (упрощённо)
            # На первом этапе — общий bounding box картинки
            f.bounding_box = {
                "x": 0,
                "y": 0,
                "width": img.width,
                "height": img.height,
            }
            f.fragment_path = file_path
            findings.append(f)
        
        logger.info("[OCR] %s: %d findings", file_path, len(findings))
    except Exception as e:
        logger.error("[OCR] Failed for %s: %s", file_path, e)
    
    return findings
Тесты:

test_scan_image_finds_pii — PNG с email/phone → finding image_region.

test_scan_image_empty — PNG без текста → 0 findings.

test_scan_image_ocr_disabled — ocr_enabled=False → 0 findings.

Verify (ручной):

Создать screenshot.png с email/phone.

Запустить скан → finding с fragment_type = image_region, detector = ocr.

GET /api/findings/{id}/fragment → PNG-фрагмент.

Оценка: 2-3 часа.

TASK-023 — BUG-067b: OCR для PDF-сканов
Приоритет: 🔴 важно

Компонент: scanner/src/connectors/filesystem.py::_extract_document.

Проблема:

python
def _extract_document(self, file_path: str, ext: str) -> Optional[str]:
    ...
    extractor = DocumentExtractor(
        temp_dir=Path(_tf.gettempdir()),
        ocr_enabled=False,   # ← 🔴 OCR отключён
    )
PDF-сканы (без текстового слоя) не обрабатываются.

Fix:

Включить OCR опционально — через конфиг:

python
def _extract_document(self, file_path: str, ext: str) -> Optional[str]:
    try:
        from utils.document_extractor import DocumentExtractor
        import tempfile as _tf
        with open(file_path, 'rb') as f:
            content = f.read()
        # BUG-067b: OCR для PDF/изображений внутри документов
        ocr_enabled = self.config.get("ocr_enabled", True)
        extractor = DocumentExtractor(
            temp_dir=Path(_tf.gettempdir()),
            ocr_enabled=ocr_enabled,
        )
        result, error = extractor.extract_text(
            content, ext, Path(file_path).name
        )
        return result
    except Exception as e:
        print(f"[FS] Не удалось извлечь текст из {file_path}: {e}")
        return None
Плюс — новый finding type для PDF-сканов:

Если _extract_document вернул текст из OCR (без текстового слоя), findings должны иметь:

fragment_type = "text_context" (или image_region).

detector = "ocr".

Проверить, как DocumentExtractor различает текстовый слой vs OCR.

Тесты:

test_pdf_with_text_layer — PDF с текстом → findings.

test_pdf_scan_ocr — PDF-скан → findings через OCR.

Оценка: 30 мин.

TASK-024 — BUG-063: credit_card не детектируется
Приоритет: 🔴 важно (PCI DSS)

Компонент: scanner/src/classifiers/pii_classifier.py.

Проблема: cards.txt с 4111 1111 1111 1111 и 5555-5555-5555-4444 → 0 findings. Presidio не имеет CREDIT_CARD распознавателя по умолчанию.

Fix: добавить кастомный распознаватель CreditCardRU:

python
# В pii_classifier.py, рядом с PhoneRU/PassportRU/SnilsRU/InnRU/EmailRU

class CreditCardRecognizer(EntityRecognizer):
    """Распознаватель кредитных карт (BUG-063, PCI DSS)."""
    
    PATTERNS = [
        # 4xxx, 5[1-5]xx, 3[47]xx, 6xxx — с разделителями и без
        Pattern(
            "CREDIT_CARD",
            r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
            r"[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
            0.85,
        ),
    ]
    
    CONTEXT = ["card", "credit", "visa", "mastercard", "amex", "cc", "карта"]
    
    def __init__(self):
        super().__init__(
            supported_entities=["CREDIT_CARD"],
            name="CreditCardRecognizer",
            supported_language="en",
        )
    
    def load(self):
        pass
    
    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        for pattern in self.PATTERNS:
            for match in pattern.compiled_regex.finditer(text):
                # Luhn-проверка
                digits = re.sub(r"\D", "", match.group())
                if self._luhn_check(digits):
                    results.append(
                        RecognizerResult(
                            entity_type="CREDIT_CARD",
                            start=match.start(),
                            end=match.end(),
                            score=pattern.score,
                        )
                    )
        return results
    
    @staticmethod
    def _luhn_check(number: str) -> bool:
        """Алгоритм Луна для валидации карт."""
        if not number.isdigit() or len(number) < 13:
            return False
        digits = [int(d) for d in number]
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        return checksum % 10 == 0
Регистрация в PiiClassifier._init_analyzers:

python
self.analyzer.registry.add_recognizer(CreditCardRecognizer())
Маскирование — уже есть в MASK_RULES["credit_card"] (**** **** **** 1234).

Тесты:

test_credit_card_visa — 4111 1111 1111 1111 → finding.

test_credit_card_mastercard — 5555-5555-5555-4444 → finding.

test_credit_card_luhn_invalid — 1234 5678 9012 3456 (невалидная) → 0 findings.

Оценка: 30 мин.

TASK-025 — BUG-066: url-дубликаты email
Приоритет: 🔴 важно

Компонент: scanner/src/classifiers/pii_classifier.py::scan_text (или scan_line).

Проблема: Presidio распознаёт example.com (домен внутри email) как URL. Создаёт дубликаты с category=url на тех же строках, где уже есть email.

Fix: фильтрация пересечений после получения findings:

python
def _filter_url_over_email(self, findings: List[Finding]) -> List[Finding]:
    """BUG-066: исключить url-findings, пересекающиеся с email."""
    email_positions = [
        (f.start_pos, f.end_pos) for f in findings if f.category == "email"
    ]
    if not email_positions:
        return findings
    
    filtered = []
    for f in findings:
        if f.category == "url" and f.start_pos is not None:
            # Пересекается с email?
            is_dup = any(
                e_start <= f.start_pos and f.end_pos <= e_end
                for e_start, e_end in email_positions
                if e_start is not None and e_end is not None
            )
            if is_dup:
                continue
        filtered.append(f)
    return filtered
Применить в scan_text/scan_line после получения всех findings.

Тесты:

test_url_not_duplicated_by_email — email + domain → только email.

test_url_standalone — https://example.com (без email) → url finding.

Оценка: 30 мин.

TASK-026 — BUG-061: HTTP retry в сканере
Приоритет: 🟡 важно (отказоустойчивость)

Компоненты:

scanner/src/managed_scanner.py::ManagerClient

scanner/src/heartbeat.py::HeartbeatThread

Проблема: при падении Manager — stale connections → RemoteDisconnected циклично после подъёма.

Fix:

1. ManagerClient — HTTPAdapter с Retry:

python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class ManagerClient:
    def __init__(self, base_url: str, scanner_id=None, config=None):
        ...
        self.session = requests.Session()
        self.session.headers.update({...})
        
        # BUG-061: retry при stale connections (RemoteDisconnected, ConnectionError)
        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=10,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        ...
2. HeartbeatThread — общий session:

python
class HeartbeatThread(threading.Thread):
    def __init__(self, manager_url, scanner_id, interval=30, session=None):
        ...
        self.session = session or requests.Session()
    
    def run(self):
        while not self._stop.wait(self.interval):
            try:
                resp = self.session.post(   # ← было requests.post
                    f"{self.manager_url}/api/scanner/heartbeat",
                    json=self._build_payload(),
                    timeout=5,
                )
                ...
В managed_scanner.py::run_loop:

python
self.heartbeat_thread = HeartbeatThread(
    manager_url=self.manager_url,
    scanner_id=self.scanner_id,
    interval=30,
    session=self.client.session,   # ← общий session с retry
)
Тесты:

test_session_has_retry_adapter — проверить session.adapters["http://"].max_retries.total == 5.

test_heartbeat_uses_shared_session — HeartbeatThread.session is ManagerClient.session.

E2E: остановить Manager, поднять → сканер восстанавливается.

Оценка: 30 мин.

TASK-027 — BUG-065: расширенные credentials-паттерны
Приоритет: 🟡

Компонент: scanner/src/classifiers/credentials_classifier.py.

Проблема: DATABASE_URL, BASIC_AUTH, GITHUB_TOKEN, SLACK_TOKEN не детектируются как именованные категории (falls back на high_entropy).

Fix: добавить regex:

python
CREDENTIAL_PATTERNS = {
    ...
    "database_url": re.compile(
        r"(?:postgresql|postgres|mysql|mongodb|redis|amqp|mssql|oracle)://"
        r"[^:\s]+:[^@\s]+@[^\s]+",
        re.IGNORECASE,
    ),
    "basic_auth": re.compile(
        r"Basic\s+[A-Za-z0-9+/=]{20,}",
        re.IGNORECASE,
    ),
    "github_token": re.compile(
        r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    ),
    "slack_token": re.compile(
        r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    ),
    ...
}
Использовать их до high_entropy (приоритет).

Тесты:

test_database_url_pattern — postgresql://user:pass@host/db → database_url.

test_basic_auth_pattern — Basic dXNlcjpwYXNz → basic_auth.

test_github_token_pattern — ghp_... → github_token.

test_slack_token_pattern — xoxb-... → slack_token.

Оценка: 1 час.

TASK-028 — BUG-062: логи сканера (nice-to-have)
Приоритет: 🟢

Компоненты:

scanner/src/managed_scanner.py

scanner/src/pii_classifier.py

run_scanner.py

Проблема: ~40 строк при старте, дубли [PII] ×6, pymorphy3 шум.

Fix:

logging.getLogger("pymorphy3").setLevel(logging.WARNING).

logging.getLogger("numexpr").setLevel(logging.WARNING).

[PII]-логи — только для первого воркера, остальные → DEBUG.

Убрать дубль [X] DCAP SCANNER (оставить [X] DCAP MANAGED SCANNER).

Объединить [OK] PII Classifier + Credentials + Code в одну строку.

Оценка: 30 мин.

📊 Сводка задач
ID	Название	Приоритет	Оценка
TASK-022	BUG-067: OCR для изображений	🔴	2-3 ч
TASK-023	BUG-067b: OCR для PDF-сканов	🔴	30 мин
TASK-024	BUG-063: credit_card	🔴	30 мин
TASK-025	BUG-066: url-дубликаты	🔴	30 мин
TASK-026	BUG-061: HTTP retry	🟡	30 мин
TASK-027	BUG-065: credentials-паттерны	🟡	1 ч
TASK-028	BUG-062: логи	🟢	30 мин
Итого: ~6 часов.

🚦 Порядок выполнения
TASK-025 (BUG-066) — 30 мин, быстрый, чистит findings.

TASK-024 (BUG-063) — 30 мин, credit_card (PCI DSS).

TASK-023 (BUG-067b) — 30 мин, OCR для PDF (проще, чем PNG).

TASK-022 (BUG-067) — 2-3 ч, OCR для PNG (главная задача).

TASK-026 (BUG-061) — 30 мин, retry.

TASK-027 (BUG-065) — 1 ч, credentials.

TASK-028 (BUG-062) — 30 мин, логи (nice-to-have).

✅ Критерии приёмки
□ screenshot.png с email/phone → findings с fragment_type = image_region, detector = ocr.
□ PDF-скан → findings через OCR.
□ cards.txt (4111 1111 1111 1111, 5555-5555-5555-4444) → credit_card findings.
□ emails.txt → нет дублирующих url findings.
□ database.env → database_url, basic_auth, github_token, slack_token — именованные категории.
□ Остановка Manager + подъём → сканер восстанавливается (heartbeat, задачи) без ручного перезапуска.
□ Логи сканера — ≤ 20 строк при старте.
□ Все unit-тесты — зелёные.
📌 Коммиты
text
fix: BUG-066 — url-дубликаты email (фильтр пересечений) [v3.13.11]
fix: BUG-063 — credit_card распознаватель (Luhn) [v3.13.11]
fix: BUG-067b — OCR для PDF-сканов [v3.13.11]
fix: BUG-067 — OCR для изображений (PNG/JPG) [v3.13.11]
fix: BUG-061 — HTTP retry в сканере (ManagerClient + HeartbeatThread) [v3.13.11]
fix: BUG-065 — credentials-паттерны (database_url, basic_auth, github_token, slack_token) [v3.13.11]
fix: BUG-062 — логи сканера (шум pymorphy3, дубли PII) [v3.13.11]
docs: CHANGELOG v3.13.11 — fix-спринт №3 (Scanner deep)
📚 Ссылки
STATE_TEST_SESSION.md — Блок 3 (Scanner deep).

scanner/src/connectors/filesystem.py — BUG-067 (stub).

scanner/src/classifiers/pii_classifier.py — BUG-063, 066.

scanner/src/classifiers/credentials_classifier.py — BUG-065.

scanner/src/managed_scanner.py — BUG-061.

scanner/src/heartbeat.py — BUG-061.

Конец ТЗ №3. Приступай в порядке: TASK-025 → 024 → 023 → 022 → 026 → 027 → 028.

text

---

## 🎯 Итог

**Файл `TZ_FIX_SPRINT_3.md` — готов к передаче.**

**Что охвачено:**

| Категория | Багов |
|-----------|-------|
| 🔴 Критичные | 4 (BUG-063, 066, 067, 067b) |
| 🟡 Средние | 2 (BUG-061, 065) |
| 🟢 Nice-to-have | 1 (BUG-062) |

**Оценка:** ~6 часов работы разработчика.

**После выполнения:** **v3.13.11** → повторная проверка Блока 3 → финализация v3.0.0.