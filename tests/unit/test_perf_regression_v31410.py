"""53.4l (v3.14.10): регрессия перф-оптимизации сканера.

Фикстуры (tests/fixtures/perf_{baseline,after}_1000.json) — сводные данные
замера на 1000 файлах (E:\\Temp\\dcap_perf_1000), снятые скриптом
temp/phase3/measure_1000.py.

Проверяем:
1. Ни одна «значимая» находка baseline не потеряна (content-key ⊆ after).
   Значимые = все категории, кроме NER-шума
   (person/location/organization/date_time/nrp — не маскируются, ARCHITECTURE.md).
2. Findings/файл ≤ 30 (было 609–666).
3. Files/min ≥ 50 (было 19.6–24.0).
4. locations[] присутствуют (дедуп не теряет вхождения).
"""
import json
import os

import pytest

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests", "fixtures")
BASE = os.path.join(FIXTURES, "perf_baseline_1000.json")
AFTER = os.path.join(FIXTURES, "perf_after_1000.json")

NER_CATEGORIES = {"person", "location", "organization", "date_time", "nrp"}


def _load(path):
    if not os.path.exists(path):
        pytest.skip(f"нет фикстуры {path} — запусти temp/phase3/measure_1000.py")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def base():
    return _load(BASE)


@pytest.fixture(scope="module")
def after():
    return _load(AFTER)


def test_baseline_ner_is_noise(base):
    """NER-категории — подавляющее большинство baseline-находок."""
    cats = base.get("categories", {})
    total = sum(cats.values()) or 1
    ner = sum(v for k, v in cats.items() if k in NER_CATEGORIES)
    assert ner / total > 0.9, f"ожидали >90% NER-шума, получили {ner}/{total}"


def test_no_significant_findings_lost(base, after):
    """Все значимые (не-NER) находки baseline присутствуют в after."""
    base_keys = set(base.get("significant_content_keys", []))
    after_keys = set(after.get("significant_content_keys", []))
    assert base_keys, "в фикстуре baseline нет значимых content-key"
    lost = base_keys - after_keys
    assert not lost, (
        f"потеряно {len(lost)} значимых находок (из {len(base_keys)}); примеры: "
        f"{list(lost)[:5]}"
    )


def test_findings_per_file_after(after):
    """После оптимизации — не больше 30 находок на файл."""
    fpf = after.get("findings_per_file", 0)
    assert fpf <= 30, f"findings/файл = {fpf} (лимит 30)"


def test_files_per_min_after(after):
    """Скорость сканирования — не меньше 50 файлов/мин."""
    fpm = after.get("files_per_min", 0)
    assert fpm >= 50, f"Files/min = {fpm} (порог 50)"


def test_speedup_vs_baseline(base, after):
    """Прирост скорости относительно baseline."""
    assert after.get("files_per_min", 0) > base.get("files_per_min", 0) * 1.5


def test_locations_present(after):
    """Дедуп сохраняет все вхождения в metadata['locations']."""
    assert after.get("total_locations", 0) > 0
    sample = after.get("sample_locations")
    assert sample, "в фикстуре нет примера locations[]"
    assert sample.get("locations_count", 0) >= 1
    assert sample.get("locations_head"), "locations[] пуст"
    head = sample["locations_head"][0]
    for key in ("line", "context_before", "context_after", "start_pos", "end_pos"):
        assert key in head, f"в locations[] нет поля {key}"
