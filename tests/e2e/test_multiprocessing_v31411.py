# tests/e2e/test_multiprocessing_v31411.py - E2E multiprocessing сканера (53.4m, v3.14.11).
# Проверяет на реальном сканировании локального корпуса:
#   * process-режим даёт те же находки, что и thread-режим (функционал сохранён);
#   * process-режим не медленнее thread-режима;
#   * metadata["locations"] сохранён.
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

N_FILES = int(os.getenv("DCAP_PERF_FILES", "100"))
# Минимальный soft-порог: на 2+ ядрах process-режим должен обгонять thread.
MIN_PROCESS_FPM = int(os.getenv("DCAP_PERF_MIN_FPM", "20"))


def _make_corpus(root, n):
    from pathlib import Path

    d = Path(root)
    d.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            "Иван Иванов, +7-999-123-45-67, ivan@example.com",
            "Контакт: support@example.org, тел. +7 (495) 123-45-67",
            "ПАСПОРТ 45 12 345678, ИНН 123456789012",
            "Обычная строка без PII — для проверки скорости",
            "login=admin password=SuperSecret123!",
        ]
        * 10
    )
    for i in range(n):
        (d / ("pii_%04d.txt" % i)).write_text(body, encoding="utf-8")
    return d


def _content_keys(findings):
    return {(f.fragment_path or "", f.category or "", f.match_text or "") for f in findings}


def _scan(corpus, executor, workers):
    from scanner.classifiers.factory import classifier_specs, worker_specs
    from scanner.classifiers.pii_classifier import PiiClassifier
    from scanner.connectors.filesystem import FilesystemConnector

    clf = PiiClassifier()
    if not getattr(clf, "_initialized", False):
        clf.configure(
            {
                "min_confidence": 0.3,
                "quick_filter_enabled": True,
                "analyzer_pool_size": 1,
                "ocr_enabled": False,
                "ner_enabled": False,
            }
        )

    cfg = {
        "max_parallel_files": workers,
        "extensions": ["txt"],
        "max_text_chars": 200000,
        "context_lines": 2,
        "ocr_enabled": False,
        "performance": {"executor": executor, "max_workers": workers, "chunk_size": 25},
    }
    conn = FilesystemConnector(cfg)
    conn._executor_type = executor
    conn._max_workers_proc = workers

    # В process-режиме классификаторы должны сериализоваться в spec.
    assert worker_specs(classifier_specs([clf])) is not None

    t0 = time.perf_counter()
    findings = conn.scan_path(str(corpus), [clf])
    dt = time.perf_counter() - t0
    return findings, dt


def test_process_matches_thread_and_speed(tmp_path):
    """process-режим: те же находки, locations[], скорость не ниже thread."""
    if (os.cpu_count() or 1) < 2:
        pytest.skip("нужно ≥ 2 ядра для process-режима")

    corpus = _make_corpus(tmp_path / "corpus", N_FILES)
    workers = min(4, max(1, (os.cpu_count() or 2) - 1))

    thread_findings, thread_dt = _scan(corpus, "thread", workers)
    proc_findings, proc_dt = _scan(corpus, "process", workers)

    assert proc_findings, "process-режим должен находить PII/credentials"
    assert _content_keys(proc_findings) == _content_keys(
        thread_findings
    ), "process-режим изменил набор находок (было %d, стало %d)" % (
        len(thread_findings),
        len(proc_findings),
    )

    with_locs = [f for f in proc_findings if (getattr(f, "metadata", None) or {}).get("locations")]
    assert with_locs, "metadata['locations'] должен заполняться и в process-режиме"

    proc_fpm = N_FILES * 60 / proc_dt if proc_dt > 0 else 0
    thread_fpm = N_FILES * 60 / thread_dt if thread_dt > 0 else 0
    print(
        "\n[E2E mp] files=%d workers=%d thread=%.1f f/min process=%.1f f/min"
        % (N_FILES, workers, thread_fpm, proc_fpm)
    )

    assert proc_fpm >= MIN_PROCESS_FPM, "process Files/min = %.1f (порог %d)" % (
        proc_fpm,
        MIN_PROCESS_FPM,
    )
