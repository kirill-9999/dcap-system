📋 ТЗ v3.14.11 — Scanner Multiprocessing (53.4m)
Файл: prompts/tz/day_53_4m_scanner_multiprocessing.md
Дата: 22.10.2026
Версия: v3.14.10 → v3.14.11
Приоритет: 🔴 Блокер v3.0.0 (скорость: 50 ф/мин → 2 000 000 файлов = 26 дней)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 1–2 дня
Зависимость: после 53.4l (v3.14.10, дедуп + NER off)

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Все находки baseline присутствуют (fingerprint set ⊆ after). Контекст (metadata["locations"]) сохранён. OCR, S3/FS/MinIO — работают.

Замер — обязателен. Без «до/после» на одном наборе (1000 файлов, dcap_perf_1000) — не принимаем.

Память — контролировать. Модели spaCy в каждом процессе — память ×N. Нужно лениво грузить (только при первом вызове в процессе).

📊 Контекст: почему multiprocessing
Факт из 53.4l: Files/min 65.8 на 1000 файлов (dcap_perf_1000), ~50 на 22 500 (much_of_test_files). ETA на 22 500 — 7 ч.

Проблема: max_parallel_files=8 — это потоки (ThreadPoolExecutor). GIL не даёт CPU-bound ускорения (Presidio/spaCy — Python, CPU-bound). На 8 ядрах — 0 ускорения (только I/O).

Решение: ProcessPoolExecutor (multiprocessing) — каждый процесс со своим GIL. На 8 ядрах — ×4–×8 (теоретически; на практике ×4–×6 из-за overhead на сериализацию).

Ожидаемый эффект: Files/min 50 → 200–400 (8 ядер). ETA на 2 000 000 — ~3–5 дней (вместо 26).

🛠️ Задача 53.4m — Multiprocessing
1. Замена ThreadPoolExecutor → ProcessPoolExecutor
Файлы:

scanner/connectors/filesystem.py (или _text_scanner.py, где max_parallel_files).

scanner/config/scanner_config.json (параметры).

scanner/src/config_loader.py (PerformanceConfig).

Проблема: сейчас (вероятно) ThreadPoolExecutor(max_workers=8) в _text_scanner.py или filesystem.py.

Решение:

python
from concurrent.futures import ProcessPoolExecutor

def _get_executor(executor_type: str, max_workers: int):
    if executor_type == "process":
        return ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,  # один раз на процесс
        )
    return ThreadPoolExecutor(max_workers=max_workers)

def _init_worker():
    """Инициализация в каждом процессе (лениво грузим модели)."""
    import logging
    logging.basicConfig(level=logging.INFO)
    # Модели spaCy — лениво (при первом вызове в процессе)
    # Не грузим здесь — грузим в _get_classifier() (кеш на процесс)
Важно: initializer= вызывается один раз на процесс (при старте). В нём:

logging.basicConfig (multiprocessing-safe).

os.environ (если нужно).

Не грузить spaCy/OCR — они лениво (в _get_classifier()), чтобы не тратить память на процессы, которые не обрабатывают файлы.

2. Ленивая инициализация классификаторов в каждом процессе
Файл: scanner/classifiers/__init__.py (или pii_classifier.py).

Проблема: если PiiClassifier() создаётся до ProcessPoolExecutor, модели spaCy грузятся в родительском процессе, а потом копируются (fork/spawn) в дочерние — память ×N.

Решение: ленивая инициализация — глобальный кеш на процесс:

python
# глобальный кеш (на процесс)
_classifier_cache = {}

def get_classifier(name: str):
    if name not in _classifier_cache:
        if name == "pii":
            from scanner.classifiers.pii_classifier import PiiClassifier
            _classifier_cache[name] = PiiClassifier(...)
        elif name == "credentials":
            ...
    return _classifier_cache[name]
В дочернем процессе (при первом вызове) — get_classifier("pii") создаёт PiiClassifier только в этом процессе (модели spaCy грузятся здесь, не копируются).

Ожидаемый эффект: память ×1 (не ×N) на процесс (каждый процесс грузит свои модели, но только при первом файле; если процесс не обрабатывает PII — модели не грузятся).

Риск: если все 8 процессов обрабатывают PII — память ×8 (spaCy модель ~500 MB ×8 = 4 GB). Нужно контролировать. Если памяти мало — max_workers=4 (не 8).

3. Picklable Finding
Файл: scanner/src/finding.py.

Проблема: ProcessPoolExecutor сериализует результаты (pickle). Finding должен быть picklable.

Решение: Finding — dataclass (уже). metadata (dict с locations[]) — picklable (dict/list). Проверить:

python
import pickle
from scanner.src.finding import Finding
f = Finding(category="email", match_text="test@example.com", metadata={"locations": [...]})
pickle.dumps(f)  # должно работать
Если Finding содержит не-picklable (например, threading.Lock) — убрать (перенести в отдельный класс).

4. temp_dir для каждого процесса
Файл: scanner/connectors/_text_scanner.py (или ocr_engine.py).

Проблема: если все процессы используют один temp_dir (E:\Temp), race condition на ocr_* файлах (один процесс удаляет файлы другого).

Решение: каждый процесс — свой temp_dir:

python
import os, tempfile
WORKER_TEMP_DIR = tempfile.mkdtemp(prefix=f"dcap_worker_{os.getpid()}_")

def _init_worker():
    global WORKER_TEMP_DIR
    WORKER_TEMP_DIR = tempfile.mkdtemp(prefix=f"dcap_worker_{os.getpid()}_")
И: _get_document_extractor(temp_dir=WORKER_TEMP_DIR, ...) — singleton на процесс (не глобальный).

Ожидаемый эффект: нет race condition, нет потери ocr_* файлов.

5. Graceful shutdown
Файл: scanner/src/managed_scanner.py.

Проблема: при Ctrl+C ProcessPoolExecutor может зависнуть (дочерние процессы не завершаются).

Решение:

python
try:
    with ProcessPoolExecutor(...) as executor:
        futures = [executor.submit(scan_file, path) for path in paths]
        for future in as_completed(futures):
            if stop_event.is_set():
                # отменить оставшиеся
                for f in futures:
                    f.cancel()
                break
            result = future.result()
            ...
except KeyboardInterrupt:
    logger.info("[Scan] Ctrl+C — graceful shutdown")
    # ProcessPoolExecutor.__exit__ → shutdown(wait=True)
Важно: ProcessPoolExecutor.shutdown(wait=True) — ждёт завершения текущих задач. Если задачи долгие (OCR на большом PDF) — Ctrl+C ждёт до 30–60 сек. Это приемлемо (лучше, чем потеря данных).

Опционально: shutdown(wait=False, cancel_futures=True) — но тогда потеряем результаты текущих задач (не отправятся в Manager). Не делать (функционал).

6. Конфиг
Файл: scanner/config/scanner_config.json.

Добавить секцию performance:

json
{
  "performance": {
    "max_parallel_files": 8,
    "executor": "process",
    "max_workers": 8,
    "chunk_size": 100
  }
}
Описание:

max_parallel_files — устаревшее (для совместимости). executor="process" — использовать max_workers.

executor — "process" (multiprocessing) или "thread" (ThreadPool, fallback).

max_workers — число процессов (по умолчанию os.cpu_count() // 2, чтобы не грузить машину на 100%).

chunk_size — размер чанка для executor.map (100 файлов — баланс между overhead и parallelism).

Файл: scanner/src/config_loader.py — PerformanceConfig:

python
class PerformanceConfig:
    max_parallel_files: int = 8
    executor: str = "process"  # "thread" | "process"
    max_workers: int = 4  # os.cpu_count() // 2
    chunk_size: int = 100
🧪 Тесты
Unit — tests/unit/test_multiprocessing_v31411.py (new)
python
"""53.4m (v3.14.11): multiprocessing — ProcessPoolExecutor, picklable Finding."""
import pickle
from scanner.src.finding import Finding


def test_finding_picklable():
    """Finding с metadata.locations[] — picklable."""
    f = Finding(
        category="email",
        match_text="test@example.com",
        metadata={"locations": [{"line": 1, "start_pos": 0, "end_pos": 16}]},
    )
    data = pickle.dumps(f)
    f2 = pickle.loads(data)
    assert f2.category == "email"
    assert len(f2.metadata["locations"]) == 1


def test_performance_config():
    """PerformanceConfig — executor, max_workers, chunk_size."""
    from scanner.src.config_loader import PerformanceConfig
    cfg = PerformanceConfig()
    assert cfg.executor in ("process", "thread")
    assert cfg.max_workers >= 1
    assert cfg.chunk_size >= 1


def test_executor_factory():
    """_get_executor('process') → ProcessPoolExecutor."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from scanner.connectors._text_scanner import _get_executor
    ex = _get_executor("process", 2)
    assert isinstance(ex, ProcessPoolExecutor)
    ex.shutdown(wait=True)
    ex = _get_executor("thread", 2)
    assert isinstance(ex, ThreadPoolExecutor)
    ex.shutdown(wait=True)
Regression — tests/unit/test_perf_regression_v31411.py (new)
python
"""53.4m (v3.14.11): regression — baseline fingerprints ⊆ after."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests/fixtures/perf_baseline_1000.json"  # v3.14.9
AFTER = ROOT / "tests/fixtures/perf_after_1000.json"  # v3.14.10 (53.4l)


@pytest.mark.skipif(not BASELINE.exists() or not AFTER.exists(),
                    reason="Baseline/after не собраны")
def test_no_baseline_finding_loss():
    with open(BASELINE) as f: baseline = json.load(f)
    with open(AFTER) as f: after = json.load(f)
    lost = set(baseline["fingerprints"]) - set(after["fingerprints"])
    assert not lost, f"Потеряны: {len(lost)}"
E2E — tests/e2e/test_multiprocessing_v31411.py (new)
python
import pytest


@pytest.mark.e2e
def test_scan_1000_files_speed(api_client, test_files_dir):
    """53.4m: скан 1000 файлов — Files/min ≥ 200."""
    # X = baseline * 4 (в 4× быстрее 50)
    ...
📋 Ручная приёмка
#	Сценарий	Ожидание
1	Скан 1000 файлов (dcap_perf_1000, 8 ядер)	Files/min ≥ 200 (×4 от 50)
2	ETA на 2 000 000	≤ 7 дней (было 26)
3	Regression	baseline fingerprints ⊆ after (0 lost)
4	Память	Не более ×2 от baseline (модели лениво)
5	Ctrl+C	Graceful shutdown (процессы завершаются, findings отправлены)
6	OCR (.png/.pdf)	находки есть, fragment_data в БД
7	S3-скан	Работает
8	executor="thread" (fallback)	Работает (если процесс не нужен)
✅ Definition of Done
□ _get_executor(executor_type, max_workers) — ProcessPoolExecutor / ThreadPoolExecutor.
□ initializer=_init_worker — logging + WORKER_TEMP_DIR (на процесс).
□ Ленивая инициализация классификаторов (get_classifier с кешем на процесс).
□ Finding — picklable (unit-тест).
□ temp_dir — свой на процесс (WORKER_TEMP_DIR).
□ PerformanceConfig — executor, max_workers, chunk_size.
□ scanner_config.json — секция performance.
□ Graceful shutdown (Ctrl+C → shutdown(wait=True), findings отправлены).
□ Unit test_multiprocessing_v31411.py — passed.
□ Regression test_perf_regression_v31411.py — passed.
□ E2E test_multiprocessing_v31411.py — passed.
□ Замер «до/после» (1000 файлов): Files/min до/после, ETA на 2 000 000.
□ Память: не более ×2 от baseline.
□ Ручная приёмка 8/8 ✅.
💾 Коммит
powershell
git add scanner/connectors/_text_scanner.py `
        scanner/connectors/filesystem.py `
        scanner/src/finding.py `
        scanner/src/config_loader.py `
        scanner/config/scanner_config.json `
        tests/unit/test_multiprocessing_v31411.py `
        tests/unit/test_perf_regression_v31411.py `
        tests/e2e/test_multiprocessing_v31411.py `
        ARCHITECTURE.md CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "perf: 53.4m scanner multiprocessing — ProcessPoolExecutor (v3.14.11)

Baseline: 50 ф/мин (ETA 2 000 000 = 26 дней).
Fix: ProcessPoolExecutor (×4–×8 на 8 ядрах).
Ленивая инициализация spaCy/OCR (память ×1, не ×N).
temp_dir на процесс (нет race condition).
Graceful shutdown (Ctrl+C → shutdown(wait=True)).
Результат: [N] ф/мин, ETA 2 000 000 = [M] дней.

Функционал сохранён: все находки baseline, контекст, OCR, S3.

Tests: test_multiprocessing_v31411.py (unit), test_perf_regression_v31411.py (regression),
test_multiprocessing_v31411.py (e2e)."
📊 Отчёт (что прислать)
Замер «до» (1000 файлов, v3.14.10): Files/min, ETA на 2 000 000.

Замер «после» (1000 файлов, v3.14.11): Files/min, ETA на 2 000 000.

Regression: baseline fingerprints ⊆ after? (да/нет), lost count.

Память: peak RSS до/после (GB).

Ctrl+C: graceful shutdown (лог: процессы завершены, findings отправлены).

executor: "process" / "thread" (в конфиге).

Diff по _text_scanner.py (или описание).

docker inspect dcap-scanner (или версия).

🎯 Что важно
Ленивая инициализация — критично для памяти. Модели spaCy — только при первом PII-файле в процессе.

temp_dir на процесс — иначе race condition на ocr_* файлах.

Picklable Finding — иначе ProcessPoolExecutor упадёт на сериализации.

Graceful shutdown — Ctrl+C не должен вешать процессы.

Regression — baseline fingerprints ⊆ after (0 lost).

Память — не более ×2. Если больше — max_workers=4 (не 8).

⚠️ Побочный риск (из Фазы 2)
tempfile.gettempdir() == E:\Temp, _cleanup_temp_files глоббит tmp*/ocr_*. Тестовый набор — вне %TEMP%. Зафиксировать в docs/testing.md.