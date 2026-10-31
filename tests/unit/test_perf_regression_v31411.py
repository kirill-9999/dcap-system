"""53.4m (v3.14.11): regression — baseline fingerprints ⊆ after.

Сравниваем значимые content-keys (без NER-категорий, которые отключены
в 53.4l) между зафиксированными эталонами и, если есть, свежим дампом
замера multiprocessing-режима (temp/phase3/*_findings.jsonl.gz).
"""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests/fixtures/perf_baseline_1000.json"
AFTER = ROOT / "tests/fixtures/perf_after_1000.json"
MP_DUMP = ROOT / "temp/phase3/mp_1000_w4_findings.jsonl.gz"


def _dump_keys(dump_path: Path) -> set:
    """content-key = sha256("file|category|match")[:16] (как в эталонах)."""
    keys = set()
    with gzip.open(str(dump_path), "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ck = row.get("ck") or ""
            keys.add(hashlib.sha256(ck.encode("utf-8")).hexdigest()[:16])
    return keys


@pytest.mark.skipif(
    not BASELINE.exists() or not AFTER.exists(),
    reason="Baseline/after не собраны",
)
def test_no_baseline_finding_loss():
    """Значимые находки baseline (v3.14.9) ⊆ after (v3.14.10+)."""
    with open(BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)
    with open(AFTER, encoding="utf-8") as f:
        after = json.load(f)

    base_keys = set(baseline.get("significant_content_keys") or [])
    after_keys = set(after.get("significant_content_keys") or [])
    assert base_keys, "в baseline нет significant_content_keys"
    assert after_keys, "в after нет significant_content_keys"

    lost = base_keys - after_keys
    assert not lost, "Потеряны находки baseline: %d (например, %s)" % (
        len(lost),
        sorted(lost)[:5],
    )


@pytest.mark.skipif(not AFTER.exists(), reason="After-эталон не собран")
@pytest.mark.skipif(not MP_DUMP.exists(), reason="Дамп замера v3.14.11 не собран")
def test_no_loss_vs_v31410():
    """После multiprocessing (v3.14.11) нет потерь относительно v3.14.10."""
    with open(AFTER, encoding="utf-8") as f:
        after = json.load(f)

    after_keys = set(after.get("significant_content_keys") or [])
    mp_keys = _dump_keys(MP_DUMP)

    lost = after_keys - mp_keys
    assert not lost, "Потеряны находки v3.14.10: %d (например, %s)" % (
        len(lost),
        sorted(lost)[:5],
    )
