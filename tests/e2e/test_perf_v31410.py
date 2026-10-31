# tests/e2e/test_perf_v31410.py - E2E производительности сканера (53.4l, v3.14.10).
# Проверяет на реальном сканировании:
#   * дедуп 3.4.0: одно совпадение в N строках → 1 Finding + locations[];
#   * findings/файл ≤ 30 (было 609 — finding-взрыв);
#   * скорость скана (Files/min) — с soft-порогом, зависит от машины.
import os
import sys
import time

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCANNER_DIR = os.path.join(ROOT, "scanner")
for _p in (ROOT, SCANNER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

# Порог Files/min для E2E: набор из локальных файлов на dev-машине
MIN_FILES_PER_MIN = int(os.getenv("DCAP_PERF_MIN_FPM", "50"))
# Число файлов для замера (достаточно для оценки, но не час работы)
N_FILES = int(os.getenv("DCAP_PERF_FILES", "200"))


def _make_corpus(root, n):
    """Создаёт корпус файлов с PII (по 40 строк на файл)."""
    from pathlib import Path
    d = Path(root)
    d.mkdir(parents=True, exist_ok=True)
    body = "\n".join([
        "Иван Иванов, +7-999-123-45-67, ivan@example.com",
        "Контакт: support@example.org, тел. +7 (495) 123-45-67",
        "ПАСПОРТ 45 12 345678, ИНН 123456789012",
        "Обычная строка без PII — для проверки скорости",
    ] * 10)
    for i in range(n):
        (d / f"pii_{i:04d}.txt").write_text(body, encoding="utf-8")
    return d


def test_scan_speed_and_dedup(tmp_path):
    """Скан N файлов: Files/min ≥ порога, findings/файл ≤ 30, locations[] есть."""
    from scanner.classifiers.pii_classifier import PiiClassifier
    from scanner.connectors.filesystem import FilesystemConnector

    corpus = _make_corpus(tmp_path / "corpus", N_FILES)

    clf = PiiClassifier()
    clf.configure({
        "min_confidence": 0.3,
        "quick_filter_enabled": True,
        "analyzer_pool_size": 2,
        "ocr_enabled": False,
    })
    clf.config["min_confidence"] = 0.3

    conn = FilesystemConnector({
        "max_parallel_files": 4,
        "extensions": ["txt"],
        "max_text_chars": 200000,
        "context_lines": 2,
        "ocr_enabled": False,
    })

    t0 = time.perf_counter()
    findings = conn.scan_path(str(corpus), [clf])
    dt = time.perf_counter() - t0
    fpm = (N_FILES * 60 / dt) if dt > 0 else 0

    assert findings, "скан должен найти PII"
    per_file = len(findings) / float(N_FILES)
    assert per_file <= 30, "findings/файл = %.1f (лимит 30)" % per_file

    # locations[] — все вхождения одного совпадения
    with_locs = [f for f in findings if (getattr(f, "metadata", None) or {}).get("locations")]
    assert with_locs, "de-dup должен заполнять metadata['locations']"
    max_locs = max(len(f.metadata["locations"]) for f in with_locs)
    assert max_locs >= 10, "ожидаются повторы одного совпадения (locations ≥ 10)"

    print("\n[E2E perf] files=%d findings=%d per_file=%.1f f/min=%.1f"
          % (N_FILES, len(findings), per_file, fpm))
    assert fpm >= MIN_FILES_PER_MIN, (
        "Files/min = %.1f (порог %d) — замер на %s" % (fpm, MIN_FILES_PER_MIN, corpus))
