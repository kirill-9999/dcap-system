 ТЗ v3.14.10 — Scanner Performance Fix Phase 2 (53.4l)
Файл: prompts/tz/day_53_4l_scanner_perf_phase2.md
Дата: 21.10.2026
Версия: v3.14.9 → v3.14.10
Приоритет: 🔴 Блокер v3.0.0 (скорость критична)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 1–1.5 дня

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Все находки baseline присутствуют. Контекст сохранён (context_before / context_after). Построчный анализ остаётся (он нужен для контекста). Новые находки допустимы (граничные), но только если они реальные (FP-тест). Если FP > 5% — откат.

Замер — обязателен. Без «до/после» на одном наборе (1000 файлов) + regression (baseline fingerprints ⊆ after) — не принимаем.

📊 Контекст: finding-взрыв (корень №1)
Факт из Фазы 2: 100 файлов → 60 916 находок (~609/файл).

Почему это ненормально: типичный файл с PII — 5–30 находок. 609 — в 20× больше.

Причина: построчный анализ (analyze() на каждой строке) — правильный (контекст), но без дедупа он плодит дубликаты:

Один test@example.com в 100 строках → 100 находок (line 1, line 2, …, line 100).

10 email × 60 строк = 600 находок.

Следствия:

Presidio O(n²) дедуп (RecognizerResult.__eq__ — 42 млн вызовов / 28 с) — потому что 609 находок на файл → O(n²).

send в Manager — O(findings) = 60 916 записей на 100 файлов.

Корень: нет дедупа по (category, match_text) в рамках файла.

🛠️ Задача 3.4.0 — Дедупликация находок в рамках файла (ГЛАВНОЕ)
3.4.0.1. Алгоритм
Файл: scanner/classifiers/pii_classifier.py (и credentials_classifier.py, code_classifier.py — если там аналогично).

Проблема: построчный анализ создаёт дубликат на каждое вхождение. Один email в 100 строках = 100 Finding.

Подход: собрать все вхождения, схлопнуть по (category, match_text), создать одну Finding с массивом locations[].

Было (псевдокод):

python
findings = []
for line_num, line in enumerate(lines, start=1):
    for r in analyzer.analyze(text=line, language=lang):
        findings.append(Finding(
            line_number=line_num,
            match_text=r.entity_value,
            context_before=prev_line,
            context_after=next_line,
            category=r.entity_type,
        ))
Стало:

python
from collections import defaultdict

by_key = defaultdict(list)  # (category, match_text) → [locations]
for line_num, line in enumerate(lines, start=1):
    for r in analyzer.analyze(text=line, language=lang):
        key = (r.entity_type, r.entity_value)
        by_key[key].append({
            "line": line_num,
            "context_before": prev_line,
            "context_after": next_line,
        })

findings = []
for (category, match_text), locations in by_key.items():
    first = locations[0]
    findings.append(Finding(
        category=category,
        match_text=match_text,
        line_number=first["line"],
        context_before=first["context_before"],
        context_after=first["context_after"],
        metadata={"locations": locations},  # ← все вхождения
    ))
3.4.0.2. Модель Finding — НЕ меняется
line_number — первое вхождение (как сейчас).

context_before / context_after — первого вхождения (как сейчас).

metadata["locations"] — новое поле (все вхождения). Если metadata_json уже есть в модели — использовать. Если нет — добавить в metadata_json (не в схему БД).

WebUI: показывает первое вхождение (как сейчас). Drill-down по locations[] — BACKLOG-331 (v3.1.0).

3.4.0.3. fingerprint — оставить как есть
fingerprint = HMAC(file_path|line|match|category) — не меняется. Дедуп между сканами работает (как сейчас). Дедуп внутри файла — через by_key[(category, match_text)] (новый код).

Почему не менять fingerprint: если убрать line из fingerprint — дедуп между сканами схлопнет все вхождения одного email, но потеряется line (нужен для контекста). Оставить как есть.

3.4.0.4. PERSON (NER) — проверить и отключить (если доминирует)
Проблема: NER может находить «имена» в каждом слове (FP-взрыв). Если PERSON > 80% находок — это FP, не finding-взрыв.

Проверить (SQL):

sql
SELECT category, count(*) FROM findings GROUP BY category ORDER BY count DESC;
Если PERSON > 80% — отключить в Presidio:

python
# в PiiClassifier.__init__ / configure
# Не включать 'PERSON' в entities (или filter post-analyze)
Причина: по ARCHITECTURE.md — person не маскируется (по решению). Если он не маскируется, но попадает в находки — это FP-шум. Отключить.

3.4.0.5. Тест (обязателен)
Regression:

Baseline (1000 файлов, до 3.4.0): findings (count + fingerprint set).

После 3.4.0: fingerprint set baseline ⊆ after (все baseline-находки присутствуют).

count after ≤ count baseline (finding-взрыв устранён).

locations[] в metadata — все вхождения (проверить на 1 файле с известным дубликатом).

Unit:

python
# tests/unit/test_dedup_v31410.py
def test_dedup_same_email_in_multiple_lines():
    """3.4.0: один email в 100 строках → 1 Finding с 100 locations."""
    lines = ["test@example.com"] * 100
    findings = classify_text("\n".join(lines))
    emails = [f for f in findings if f.category == "email"]
    assert len(emails) == 1
    assert len(emails[0].metadata["locations"]) == 100
    assert emails[0].line_number == 1
🛠️ Задача 3.4 — Line-windowed Presidio (после 3.4.0)
Файл: scanner/classifiers/pii_classifier.py.

Когда: после дедупа. Если после 3.4.0 Files/min ≥ 50 — line-windowed не нужен. Если < 50 — line-windowed для оставшихся больших текстов.

3.4.1. Алгоритм
python
WINDOW_SIZE = 10_000
OVERLAP = 500

def _analyze_windowed(self, text, language):
    results = []
    if len(text) <= WINDOW_SIZE:
        return self._analyzer.analyze(text=text, language=language, ...)
    step = WINDOW_SIZE - OVERLAP
    for offset in range(0, len(text), step):
        window = text[offset:offset + WINDOW_SIZE]
        for r in self._analyzer.analyze(text=window, language=language, ...):
            r.start += offset
            r.end += offset
            results.append(r)
        if offset + WINDOW_SIZE >= len(text):
            break
    return results
3.4.2. Параметры (конфиг)
json
{
  "pii": {
    "window_size": 10000,
    "overlap": 500,
    "score_threshold": 0.5
  }
}
3.4.3. Regression (обязателен)
После 3.4.0 + 3.4:

fingerprint set baseline ⊆ after.

count after ≥ count baseline (граничные — плюс).

FP-тест (100 доп. находок → ≤ 5% FP).

📋 Порядок работ
3.4.0 — дедуп (главное). Замер Files/min. Если ≥ 50 — стоп, 3.4 не нужен.

3.4 — line-windowed (если < 50). Замер.

PERSON off — если доминирует (> 80%).

Важно: 3.4.0 — обязательно. 3.4 — опционально (по результатам 3.4.0). PERSON off — по результатам SQL.

🧪 Тесты
Unit — tests/unit/test_dedup_v31410.py (new)
python
"""53.4l (v3.14.10): дедуп в рамках файла (3.4.0)."""
def test_dedup_same_email_in_multiple_lines():
    lines = ["test@example.com"] * 100
    findings = classify_text("\n".join(lines))
    emails = [f for f in findings if f.category == "email"]
    assert len(emails) == 1
    assert len(emails[0].metadata["locations"]) == 100
    assert emails[0].line_number == 1


def test_dedup_different_emails_kept():
    lines = ["a@x.com", "b@x.com", "c@x.com"]
    findings = classify_text("\n".join(lines))
    emails = [f for f in findings if f.category == "email"]
    assert len(emails) == 3  # разные email — 3 находки


def test_dedup_context_preserved():
    lines = ["test@example.com"] * 10
    findings = classify_text("\n".join(lines))
    email = [f for f in findings if f.category == "email"][0]
    assert email.context_before is not None or email.context_after is not None
    assert len(email.metadata["locations"]) == 10
Regression — tests/unit/test_perf_regression_v31410.py (new)
python
"""53.4l (v3.14.10): regression — baseline fingerprints ⊆ after."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests/fixtures/perf_baseline_1000.json"
AFTER = ROOT / "tests/fixtures/perf_after_1000.json"


@pytest.mark.skipif(not BASELINE.exists() or not AFTER.exists(),
                    reason="Baseline/after не собраны")
def test_no_baseline_finding_loss():
    with open(BASELINE) as f: baseline = json.load(f)
    with open(AFTER) as f: after = json.load(f)
    lost = set(baseline["fingerprints"]) - set(after["fingerprints"])
    assert not lost, f"Потеряны: {len(lost)}"
E2E — tests/e2e/test_perf_v31410.py (new)
python
import pytest


@pytest.mark.e2e
def test_scan_1000_files_speed(api_client, test_files_dir):
    """53.4l: скан 1000 файлов — Files/min ≥ 50."""
    ...
📋 Ручная приёмка
#	Сценарий	Ожидание
1	Скан 1000 файлов (после 3.4.0)	Files/min ≥ 50
2	Findings/файл	≤ 30 (было 609)
3	Regression	baseline fingerprints ⊆ after (0 lost)
4	locations[] в metadata	Для дубликатов — все вхождения
5	Контекст	context_before / context_after — сохранены
6	OCR	.png / .pdf — находки есть, fragment_data в БД
7	S3-скан	Работает
8	OCR-спам	[OCR] Found via 'where' = 1 раз
9	Если 3.4 нужен — FP-тест	100 доп. находок → ≤ 5% FP
✅ Definition of Done
3.4.0 (обязательно):

□ Дедуп по (category, match_text) в pii_classifier.py (и credentials/code).
□ metadata["locations"] = все вхождения.
□ line_number / context_* — первого вхождения.
□ fingerprint — не меняется (по line).
□ PERSON off (если > 80% — SQL-проверка).
□ Unit test_dedup_v31410.py — passed.
□ Regression — baseline fingerprints ⊆ after (0 lost).
□ Замер Files/min (1000 файлов): ≥ 50 (если да — 3.4 не нужен).
□ Findings/файл: ≤ 30 (было 609).
3.4 (опционально, если 3.4.0 < 50 ф/мин):

□ Line-windowed Presidio (window_size=10000, overlap=500).
□ Регрессия + FP-тест.
□ Замер Files/min — ≥ 50.
E2E:

□ test_perf_v31410.py — passed.
💾 Коммит
powershell
git add scanner/classifiers/pii_classifier.py `
        scanner/classifiers/credentials_classifier.py `
        scanner/classifiers/code_classifier.py `
        scanner/config/scanner_config.json `
        tests/unit/test_dedup_v31410.py `
        tests/unit/test_perf_regression_v31410.py `
        tests/e2e/test_perf_v31410.py `
        tests/fixtures/perf_baseline_1000.json `
        tests/fixtures/perf_after_1000.json `
        ARCHITECTURE.md CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "perf: 53.4l scanner — dedup + windowed Presidio (v3.14.10)

Finding-взрыв (609/файл) — из-за отсутствия дедупа в рамках файла.
3.4.0: дедуп по (category, match_text), metadata[locations] = все вхождения.
line_number/context — первого вхождения. fingerprint — не меняется.
3.4: line-windowed Presidio (если 3.4.0 < 50 ф/мин).
PERSON off (если > 80%).

Baseline: 22-25 ф/мин. После: [N] ф/мин.
Findings/файл: 609 → [M].
Regression: baseline fingerprints ⊆ after (0 lost).

Функционал сохранён: контекст, locations[], fingerprint.

Tests: test_dedup_v31410.py (unit), test_perf_regression_v31410.py (regression),
test_perf_v31410.py (e2e)."
📊 Отчёт (что прислать)
SQL распределения находок по category (до 3.4.0) — PERSON > 80%?

Замер «до» (1000 файлов, v3.14.9): Files/min, findings count, findings/файл.

Замер «после 3.4.0»: Files/min, findings count, findings/файл.

Замер «после 3.4» (если нужен): Files/min.

Regression: baseline fingerprints ⊆ after? (да/нет), lost count.

locations[] — пример на 1 файле с дубликатом (email в 10 строках → 1 Finding, 10 locations).

Diff по pii_classifier.py (или описание).

Параметры window_size / overlap (если 3.4).

docker inspect dcap-scanner (или версия).

🎯 Что важно
3.4.0 — обязательно. Это главный фикс finding-взрыва. Если после 3.4.0 Files/min ≥ 50 — 3.4 не нужен, экономим время.

Контекст — сохранить. line_number / context_before / context_after — первого вхождения. metadata["locations"] — все. Модель Finding не меняется.

fingerprint — не менять. Дедуп между сканами работает. Дедуп внутри файла — через by_key.

PERSON — SQL-проверка. Если > 80% — отключить (FP, не PII).

Regression — обязателен. baseline fingerprints ⊆ after — единственный способ убедиться, что не потеряли находки.

FP-тест (если 3.4) — 100 доп. находок → ≤ 5% FP.

⚠️ Побочный риск (из Фазы 2)
tempfile.gettempdir() == E:\Temp, _cleanup_temp_files глоббит tmp*/ocr_*. Тестовый набор — вне %TEMP% (или зафиксировать temp_dir). Зафиксировать в docs/testing.md.

