📋 ТЗ v3.14.9 — Scanner Performance Fix (53.4k)
Файл: prompts/tz/day_53_4k_scanner_perf_fix.md
Дата: 21.10.2026
Версия: v3.14.8 → v3.14.9
Приоритет: 🔴 Блокер v3.0.0 (сканер 19.6 ф/мин — нерабочая скорость)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 1 день (Фаза 3 — 0.5–1 день)

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Все находки, OCR, fragment_data в БД, fingerprint, S3/FS/MinIO — остаются. Любая оптимизация, которая урезает функционал (пропуск файлов, отключение OCR, «не отправлять fragment_data», «не считать fingerprint») — запрещена.

Замер — обязателен. Без «до/после» на одном и том же наборе (1000 файлов, реальные пропорции) — не принимаем отчёт.

📊 Контекст: что показала Фаза 2 (замеры)
Метрика	Факт (baseline)
Files/min	19.6 (100 файлов, 306.8 с)
ETA на 22 500	~19.2 ч
Разбивка	classify ~99%, read ~1%, discover ~0%, send O(findings), heartbeat ~0
Finding-взрыв	100 файлов → 60 916 находок (~609/файл)
cProfile топ	RecognizerResult.__eq__ 42 млн вызовов / 28 с (O(n²) дедуп), spaCy-лемматизация 37 с, phonenumbers 24 с
OCR-спам	3 subprocess на файл (where + --list-langs + tesseract), @lru_cache из 53.4j в linewise-путь не подключён
max_parallel_files 1/2/4/8	25.1 / 24.7 / 23.7 / 28.5 — шум (GIL), не корень
Корень найден:

Классификация Presidio (~99% CPU) — O(n²) дедуп результатов (contained_in), спам-лемматизация, phonenumbers.

Finding-взрыв (~609/файл) — умножает и классификацию, и send.

Пересоздание OCREngine/DocumentExtractor на каждый файл — 3 subprocess на файл, @lru_cache не подключён к linewise-пути.

🛠️ Фаза 3 — Фикс (согласовано)
Приоритет 1: безопасно, без потери находок
3.1. Singleton DocumentExtractor/OCREngine для linewise-пути
Файл: scanner/connectors/_text_scanner.py.

Проблема: _text_scanner.py:209 создаёт DocumentExtractor(...) на каждый файл, что создаёт новый OCREngine (с _find_tesseract() + _detect_languages() — 2 subprocess). OCR-worker — singleton, но в linewise-пути он вообще не используется.

Было:

python
def extract_document_text(content, ext, filename, ocr_enabled=False):
    ...
    extractor = DocumentExtractor(
        temp_dir=_P(_tf.gettempdir()),
        ocr_enabled=ocr_enabled,
    )  # ← НОВЫЙ на КАЖДЫЙ файл
    result, error = extractor.extract_text(content, ext, filename)
Стало:

python
import threading
_extractor_singleton = None
_extractor_lock = threading.Lock()

def _get_extractor(ocr_enabled: bool) -> DocumentExtractor:
    global _extractor_singleton
    if _extractor_singleton is None:
        with _extractor_lock:
            if _extractor_singleton is None:
                _extractor_singleton = DocumentExtractor(
                    temp_dir=_P(_tf.gettempdir()),
                    ocr_enabled=ocr_enabled,
                )
    return _extractor_singleton

def extract_document_text(content, ext, filename, ocr_enabled=False):
    ...
    extractor = _get_extractor(ocr_enabled)
    result, error = extractor.extract_text(content, ext, filename)
Ожидаемый эффект: минус ~2 subprocess на каждый doc/image файл.

Функционал: не меняется (тот же DocumentExtractor, тот же OCR).

3.2. Подключить @lru_cache-хелперы к OCREngine
Файл: scanner/utils/ocr_engine.py.

Проблема: OCREngine.__init__ вызывает self._find_tesseract() и self._detect_languages() — сырые subprocess, без @lru_cache. Модульные _get_tesseract_path/_get_tesseract_langs (из 53.4j) не используются.

Было (ocr_engine.py:79-80):

python
self._tesseract_cmd = self._find_tesseract()   # subprocess where
self._languages = self._detect_languages()     # subprocess --list-langs
Стало:

python
self._tesseract_cmd = _get_tesseract_path()   # @lru_cache(maxsize=1)
self._languages = _get_tesseract_langs()      # @lru_cache(maxsize=1)
Проверить: [OCR] Found via 'where' появляется 1 раз за скан (не 3000+).

Функционал: не меняется.

Приоритет 2: классификация (обязательно, но с regression-тестом)
3.3. Дешёвый префильтр до Presidio
Файл: scanner/classifiers/pii_classifier.py.

Проблема: Presidio analyze() вызывается на каждой строке каждого файла, даже если там нет ни одного PII-кандидата. Это 99% CPU.

Подход:

python
# до Presidio.analyze()
if not self._quick_regex.match(line):
    # нет ни одного быстрого кандидата — Presidio даст пусто
    continue
_quick_regex — уже существует (_quick_line_patterns в pii_classifier.py). Проверить, что он покрывает все категории PII (email, phone, passport, snils, inn, credit_card, person).

Критично: это не «отключить Presidio», а «не звать его на строках, где он и так выдаст 0 находок». При отсутствии _quick_regex-совпадений Presidio не найдёт ничего.

Regression-тест (обязателен):

Прогнать baseline (1000 файлов) до 3.3 — сохранить findings (count + fingerprint set).

Прогнать после 3.3 — сравнить.

Если хоть одна находка потеряна (count уменьшилось или fingerprint set не совпадает) — откат 3.3.

Ожидаемый эффект: снижение classify на «шумных» больших txt (например, very_large_100k.txt → 9 678 находок за 109 с только на классификации).

Приоритет 3: опционально (только с явным согласованием)
3.4. Оптимизация O(n²) дедупа RecognizerResult.__eq__/contained_in
Файл: scanner/classifiers/pii_classifier.py (или где Presidio-дедуп).

Проблема: RecognizerResult.__eq__ — 42 млн вызовов, contained_in — 42 млн вызовов, из-за O(n²) дедупа. При 609 находках/файл это квадратично.

Важно: это правка алгоритма Presidio-совместимого дедупа. Риск — потеря находки (дедуп слишком агрессивный). НЕ делать без:

Явного согласования с архитектором.

Regression-теста: все находки baseline присутствуют (fingerprint set).

Сравнения count.

Если риск не оправдан — оставить как BACKLOG-330 (v3.1.0). В 53.4k не делать.

🧪 Тесты
Unit — tests/unit/test_perf_v3149.py (new)
python
"""53.4k (v3.14.9): singleton extractor + lru_cache + prefilter."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_text_scanner_has_singleton():
    """3.1: _text_scanner.extract_document_text использует singleton extractor."""
    src = (ROOT / "scanner/connectors/_text_scanner.py").read_text(encoding="utf-8")
    assert "_extractor_singleton" in src or "_get_extractor" in src
    # Не должно быть DocumentExtractor(...) в extract_document_text без singleton
    body = src[src.find("def extract_document_text"):src.find("def extract_document_text") + 2000]
    assert "DocumentExtractor(" not in body or "_get_extractor" in body


def test_ocr_engine_uses_lru_cache_helpers():
    """3.2: OCREngine использует _get_tesseract_path/_get_tesseract_langs."""
    src = (ROOT / "scanner/utils/ocr_engine.py").read_text(encoding="utf-8")
    assert "_get_tesseract_path" in src
    assert "_get_tesseract_langs" in src
    # _find_tesseract/_detect_languages не должны вызываться в __init__ напрямую
    m = re.search(r"def __init__\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)", src, re.S)
    if m:
        body = m.group(1)
        assert "_find_tesseract" not in body or "_get_tesseract_path" in body


def test_pii_prefilter_exists():
    """3.3: pii_classifier использует префильтр до Presidio."""
    src = (ROOT / "scanner/classifiers/pii_classifier.py").read_text(encoding="utf-8")
    assert "_quick_regex" in src or "_quick_line_patterns" in src
Regression — tests/unit/test_perf_regression_v3149.py (new)
Обязательный: сравнение находок до/после 3.3.

python
"""53.4k (v3.14.9): regression — находки не теряются после префильтра (3.3)."""
from pathlib import Path
import json
import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests/fixtures/perf_baseline_findings.json"


@pytest.mark.skipif(not BASELINE.exists(), reason="Baseline не собран")
def test_no_finding_loss_after_prefilter():
    """Все находки baseline присутствуют после 3.3 (fingerprint set)."""
    with open(BASELINE) as f:
        baseline = json.load(f)
    # baseline: {"count": N, "fingerprints": [...]}
    # current: (собрать из актуального прогона)
    # ...
    assert True  # заменить на реальную проверку после 3.3
Baseline (tests/fixtures/perf_baseline_findings.json) — собрать до 3.3 на 1000 файлах, сохранить count + fingerprints.

E2E — tests/e2e/test_perf_v3149.py (new)
python
import pytest
import requests
import time


@pytest.mark.e2e
def test_scan_1000_files_speed(api_client, test_files_dir):
    """53.4k: скан 1000 файлов < X сек (после 3.1+3.2+3.3)."""
    # X = baseline * 0.5 (минимум в 2× быстрее)
    ...
📋 Ручная приёмка
#	Сценарий	Ожидание
1	Скан 1000 файлов (mixed: txt/docx/xlsx/png/pdf)	Files/min ≥ 50 (в 2× быстрее baseline 19.6). Идеально ≥ 100.
2	OCR-спам	[OCR] Found via 'where' = 1 раз за скан (не 3000+)
3	Функционал	Все находки baseline присутствуют (fingerprint set совпадает)
4	OCR	На .png/.pdf — находки есть, fragment_data в БД
5	S3-скан	Работает, находки > 0
6	Heartbeat	Продолжает идти, progress обновляется
7	max_parallel_files	Оставить 8 (не вредит, из отчёта Фазы 2)
✅ Definition of Done
Фаза 3 (фикс):

□ 3.1 — singleton DocumentExtractor/OCREngine для linewise-пути.
□ 3.2 — @lru_cache-хелперы подключены к OCREngine.__init__.
□ 3.3 — дешёвый префильтр до Presidio (с regression-тестом).
□ 3.4 — не делать (BACKLOG-330) или с явным согласованием.
□ Функционал сохранён (все находки baseline присутствуют).
□ Unit test_perf_v3149.py — passed.
□ Regression test_perf_regression_v3149.py — passed.
□ E2E test_perf_v3149.py — passed.
□ Замер «до/после» (1000 файлов) в отчёте: Files/min до/после, ETA on 22 500 до/после.
□ Логи: [OCR] Found via 'where' — 1 раз (не 3000+).
□ Ручная приёмка 7/7 ✅.
💾 Коммит
powershell
git add scanner/connectors/_text_scanner.py scanner/utils/ocr_engine.py `
        scanner/classifiers/pii_classifier.py `
        scanner/config/scanner_config.json `
        tests/unit/test_perf_v3149.py tests/unit/test_perf_regression_v3149.py `
        tests/e2e/test_perf_v3149.py `
        tests/fixtures/perf_baseline_findings.json `
        .env docker-compose.yml `
        ARCHITECTURE.md CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "perf: 53.4k scanner — singleton extractor + lru_cache + prefilter (v3.14.9)

Baseline: 19.6 ф/мин (ETA 19.2ч на 22 500).
Fix:
- 3.1: singleton DocumentExtractor/OCREngine для linewise (минус 2 subprocess/файл).
- 3.2: @lru_cache-хелперы подключены к OCREngine (Found via 'where' = 1 раз).
- 3.3: дешёвый префильтр до Presidio (regression-тест на baseline).
Результат: [N] ф/мин, ETA [M]ч на 22 500.

Функционал сохранён: все находки baseline, OCR работает, fragment_data в БД.

Tests: test_perf_v3149.py (unit), test_perf_regression_v3149.py (regression),
test_perf_v3149.py (e2e)."
📊 Отчёт (что прислать)
Замер «до» (1000 файлов): Files/min, ETA on 22 500, Time.

Замер «после» (1000 файлов): то же.

Разбивка по этапам (после): read / classify / ocr / send.

OCR-спам: Count (должно быть 1).

Regression: findings count до/после + fingerprint set совпадает (да/нет).

Функционал: OCR работает (на .png/.pdf), S3 работает.

Diff по 3 файлам (или описание).

docker inspect dcap-scanner (или версия) — обновлена.

⚠️ Побочный риск (из отчёта Фазы 2)
tempfile.gettempdir() == E:\Temp, и _cleanup_temp_files глоббит tmp*/ocr_* в E:\Temp. Тестовый набор в E:\Temp может быть удалён. Для приёмки:

Держать набор вне %TEMP% (например, E:\Temp\dcap_perf_* → перенести в E:\dcap_perf_*).

Или зафиксировать temp_dir сканера в конфиге.

Это не корень 53.4k, но важно для воспроизведения. Зафиксировать в docs/testing.md.

🎯 Что важно
3.1+3.2 — обязательно, безопасно (без потери находок, минус ~2 subprocess/файл).

3.3 — обязательно, но с regression-тестом (если хоть одна находка потеряна — откат).

3.4 — НЕ делать без явного согласования (BACKLOG-330, v3.1.0).

Замер — обязателен. Без «до/после» на одном наборе — не принимаем.

Побочный риск (temp_dir) — зафиксировать в docs/testing.md.