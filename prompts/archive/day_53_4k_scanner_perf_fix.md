📋 ТЗ v3.14.9 — Scanner Performance (53.4k, фикс после провала 53.4j)
Файл: prompts/tz/day_53_4k_scanner_perf_fix.md
Дата: 21.10.2026
Версия: v3.14.8 → v3.14.9
Приоритет: 🔴 Блокер v3.0.0 (сканер 24.6 ф/мин — нерабочая скорость)
Исполнитель: Разработчик (ИИ-агент Open Code)
Длительность: 1–1.5 дня

⚠️ Контекст: 53.4j провалился
Отчёт 53.4j (601e348, 2b611e8) заявил ускорение discovery (2.5–2.8×), но в реальности:

Скорость сканера: 24.6 ф/мин (даже медленнее baseline 26).

Логи [OCR] Found via 'where' + tesseract --list-langs + [OCR] Languages: rus+eng — продолжают идти на каждый файл.

@lru_cache в ocr_engine.py не помогает — потому что OCRWorker запускается как отдельный процесс на каждый файл (или на каждую картинку), и кэш сбрасывается.

Причина: оптимизация A–D была не про то место. Discovery — не узкое место. Узкое место — перезапуск OCRWorker на каждый файл + повторная инициализация Tesseract.

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается. Все находки, OCR, fragment_data в БД, fingerprint, S3/FS/MinIO — остаются. Любая оптимизация, которая урезает функционал (пропуск файлов, отключение OCR, «не отправлять fragment_data»), запрещена.

Замер — обязателен. Без baseline и «после» — не принимаем отчёт. Доказательства: cProfile, логи сканера, цифры ф/мин до/после, ETA на 22 500.

🔍 Фаза 1 — Диагностика (0.5 дня)
Цель: найти, где именно вызывается find_tesseract / list-langs на каждый файл.

1.1. Найти источник логов
powershell
Get-ChildItem -Path scanner -Recurse -Filter *.py | Select-String -Pattern "Found via 'where'|Tesseract path|Available languages" | Select-Object Filename, LineNumber, Line
Прислать в отчёте: имя файла + номера строк. Скорее всего — scanner/utils/ocr_engine.py или scanner/classifiers/ocr_worker.py.

1.2. Понять жизненный цикл OCRWorker
powershell
# 1. Долгоживущий ли OCRWorker?
Get-Content scanner\classifiers\ocr_worker.py | Select-String -Pattern "__main__|while True|stdin|readline" -Context 0,3

# 2. Когда pii_classifier запускает OCRWorker?
Get-Content scanner\classifiers\pii_classifier.py | Select-String -Pattern "_ensure_worker|_start_ocr_worker|_ocr_process is None|Popen" -Context 3,3
Прислать в отчёте:

ocr_worker.py — while True (долгоживущий) или одноразовый (обработал 1 файл → умер)?

pii_classifier.py — _start_ocr_worker() вызывается один раз (singleton, if self._ocr_process is None) или на каждый файл (без условия)?

Это ключевой вопрос. Если _start_ocr_worker() — без условия, корень найден: OCRWorker перезапускается на каждый файл, @lru_cache бесполезен.

1.3. Замерить baseline (на 1000 файлов)
Подготовить набор (скрипт в ТЗ, скопировать):

powershell
$testDir = "E:\Temp\dcap_perf_test"
if (Test-Path $testDir) { Remove-Item $testDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $testDir | Out-Null
1..400 | ForEach-Object { "Test email test$_@example.com and phone +79991234$_ and AKIAIOSFODNN7EXAMPLE" | Out-File "$testDir\file$_.txt" }
1..200 | ForEach-Object { (1..100 | ForEach-Object { "log line $_ password=secret123" }) -join "`n" | Out-File "$testDir\file$_.log" }
1..200 | ForEach-Object { "def func$_():`n    password = 'secret$'`n    api_key = 'ghp_1234567890abcdefghij'" | Out-File "$testDir\file$_.py" }
1..200 | ForEach-Object { '{"api_key": "AKIAIOSFODNN7EXAMPLE"}' | Out-File "$testDir\file$_.json" }
# Итого 1000 файлов
Замерить baseline (через Manager API — ТЗ scripts/perf_measure.ps1, создать заново):

powershell
$base = "http://localhost:8000"
$login = Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }
$resource = Invoke-RestMethod -Method Post -Uri "$base/api/resources?path=$testDir&type=filesystem" -Headers $h
$task = Invoke-RestMethod -Method Post -Uri "$base/api/resources/$($resource.id)/scan" -Headers $h
$start = Get-Date
do {
    Start-Sleep -Seconds 3
    $status = Invoke-RestMethod "$base/api/scanner/tasks/$($task.id)" -Headers $h
} while ($status.status -notin @('completed', 'failed'))
$elapsed = (Get-Date) - $start
Write-Host "=== BASELINE ==="
Write-Host "Files: $($status.progress.files_scanned) / $($status.progress.total)"
Write-Host "Time: $($elapsed.TotalSeconds) sec"
Write-Host "Files/min: $([math]::Round($status.progress.files_scanned / $elapsed.TotalMinutes, 1))"
Write-Host "ETA on 22500: $([math]::Round($elapsed.TotalHours * (22500 / $status.progress.files_scanned), 1)) h"
Прислать в отчёте: Files/min baseline, ETA on 22500, Time.

1.4. Профилирование (обязательно)
powershell
python -m cProfile -s cumtime run_scanner.py scanner/config/scanner_config.json > profile_baseline.txt
Прислать в отчёте: топ-10 функций по cumtime (из profile_baseline.txt). Ожидание: find_tesseract / subprocess / pytesseract — в топе.

🛠️ Фаза 2 — Фикс (0.5–1 день)
Цель: устранить корень. Не «оптимизировать discovery» — он не был узким местом.

2.1. Если OCRWorker — на каждый файл (наиболее вероятно)
Фикс: сделать OCRWorker singleton (один процесс на весь скан).

Файл: scanner/classifiers/pii_classifier.py.

Было (вероятно):

python
def classify(self, line):
    worker = OCRWorker(...)   # ← на каждый файл
    result = worker.process(line)
Стало:

python
def __init__(self, ...):
    self._ocr_worker = None  # singleton

def _get_ocr_worker(self):
    if self._ocr_worker is None:
        self._ocr_worker = OCRWorker(...)
    return self._ocr_worker

def classify(self, line):
    worker = self._get_ocr_worker()  # singleton
    result = worker.process(line)
Плюс: OCRWorker.close() / __del__ — закрывать при завершении скана (не на каждый файл).

2.2. Если OCRWorker — singleton, но find_tesseract всё равно вызывается
Фикс: перенести find_tesseract / --list-langs в __init__ OCRWorker (один раз), а не в process().

Файл: scanner/classifiers/ocr_worker.py (или scanner/utils/ocr_engine.py).

Было:

python
def process(self, image):
    cmd = find_tesseract()  # ← на каждый вызов
    langs = get_available_languages(cmd)  # ← на каждый вызов
    ...
Стало:

python
def __init__(self):
    self._cmd = find_tesseract()  # 1 раз
    self._langs = get_available_languages(self._cmd)  # 1 раз
    logger.info("[OCR] Init: %s, langs=%s", self._cmd, self._langs)  # 1 строка

def process(self, image):
    # без find_tesseract / list-langs
    ...
2.3. Если pytesseract сам вызывает where tesseract на каждый image_to_string
Фикс: явно задать pytesseract.pytesseract.tesseract_cmd один раз при старте OCRWorker:

python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = get_tesseract_cmd()  # 1 раз в __init__
2.4. Параллелизм (если после 2.1–2.3 скорость всё ещё < 50)
Файл: scanner/connectors/filesystem.py.

Проверить: max_parallel_files в scanner_config.json — стоит ли 1? Если 1 → поставить os.cpu_count() (или половину). ThreadPoolExecutor уже есть (вариант C из 53.4j) — нужно включить.

🧪 Тесты
Unit — tests/unit/test_perf_v3149.py (new)
python
"""53.4k (v3.14.9): OCRWorker singleton + нет повторного find_tesseract."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def test_ocr_worker_singleton():
    """OCRWorker создаётся один раз (singleton), не на каждый файл."""
    src = (ROOT / "scanner/classifiers/pii_classifier.py").read_text(encoding="utf-8")
    # Должен быть singleton (self._ocr_worker / self._ocr_process)
    assert "self._ocr_worker" in src or "self._ocr_process" in src
    # И _get_ocr_worker() / _ensure_worker() с условием
    assert "_get_ocr_worker" in src or "_ensure_worker" in src


def test_no_find_tesseract_in_process():
    """find_tesseract / list-langs не вызываются в process() (только в __init__)."""
    src = (ROOT / "scanner/classifiers/ocr_worker.py").read_text(encoding="utf-8") \
        if (ROOT / "scanner/classifiers/ocr_worker.py").exists() else \
        (ROOT / "scanner/utils/ocr_engine.py").read_text(encoding="utf-8")
    # find_tesseract — только в __init__ / get_tesseract_cmd, не в process
    assert "find_tesseract" in src  # где-то есть
    # process() не содержит find_tesseract (эвристика)
    import re
    m = re.search(r"def process\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)", src, re.S)
    if m:
        body = m.group(1)
        assert "find_tesseract" not in body, "find_tesseract в process() — перезапуск на каждый файл"
E2E — tests/e2e/test_perf_v3149.py (new)
python
import pytest
import requests
import time

@pytest.mark.e2e
def test_scan_1000_files_speed(api_client, test_files_dir):
    """53.4k: скан 1000 файлов < X сек (после фикса)."""
    # Создать resource → scan → ждать → замерить
    # X = baseline * 0.5 (минимум в 2× быстрее)
    ...
Ручной замер (обязателен)
После фикса — повторить Фазу 1.3 (1000 файлов) и прислать цифры:

Files/min до/после.

ETA on 22500 до/после.

Скорость discovery (если менялось).

Логи: [OCR] Found via 'where' — 1 раз (не 1000).

📋 Ручная приёмка
#	Сценарий	Ожидание
1	Скан 1000 файлов (после фикса)	Files/min ≥ 50 (в 2× быстрее baseline 26). Идеально ≥ 100.
2	Логи сканера	[OCR] Found via 'where' — 1 раз (при старте), не на каждый файл
3	Находки	Все находки из baseline присутствуют (сравнить findings count + fingerprint set)
4	OCR	На .png/.pdf — находки есть, fragment_data в БД
5	S3-скан	Работает, находки > 0
6	Heartbeat	Продолжает идти, progress обновляется
7	max_parallel_files	Проверить в scanner_config.json — ≥ 2 (если CPU ≥ 2)
✅ Definition of Done
Фаза 1 (Диагностика):

□ Найден файл + строка, откуда идут [OCR] Found via 'where'.
□ Понято: OCRWorker — singleton или на каждый файл.
□ Baseline замерен (1000 файлов): Files/min, ETA on 22500.
□ cProfile — топ-10 функций по cumtime.
□ Причина сформулирована (например: «pii_classifier запускает OCRWorker на каждый файл, @lru_cache не работает между процессами»).
Фаза 2 (Фикс):

□ Корень устранён (2.1 / 2.2 / 2.3 / 2.4 — что применимо).
□ Функционал сохранён (все находки baseline присутствуют, OCR работает, fragment_data в БД).
□ Unit test_perf_v3149.py — passed.
□ E2E test_perf_v3149.py — passed.
□ Замер «до/после» (1000 файлов) — в отчёте: Files/min до/после, ETA on 22500 до/после.
□ Логи: [OCR] Found via 'where' — 1 раз (не 1000).
□ docker inspect dcap-scanner (или версия) — обновлена.
□ Ручная приёмка 7/7 ✅.
💾 Коммит
powershell
git add scanner/classifiers/pii_classifier.py scanner/classifiers/ocr_worker.py `
        scanner/utils/ocr_engine.py scanner/connectors/filesystem.py `
        scanner/config/scanner_config.json `
        tests/unit/test_perf_v3149.py tests/e2e/test_perf_v3149.py `
        .env docker-compose.yml `
        CHANGELOG.md STATE.md STATE_TEST_SESSION.md ROADMAP.md
git commit -m "perf: 53.4k scanner — OCRWorker singleton + no repeated find_tesseract (v3.14.9)

Baseline: 24.6 ф/мин (ETA 15ч на 22 500).
Fix: OCRWorker — singleton (один процесс на весь скан).
find_tesseract / --list-langs — только в __init__, не в process().
pytesseract.tesseract_cmd — задан 1 раз.
Результат: [N] ф/мин, ETA [M]ч на 22 500.

Функционал сохранён: все находки baseline, OCR работает, fragment_data в БД.

Tests: test_perf_v3149.py (unit), test_perf_v3149.py (e2e)."
📊 Отчёт (что прислать)
Файл + строки с [OCR] Found via 'where'.

OCRWorker — singleton или на каждый файл (вывод Select-String + кусок кода).

Baseline (1000 файлов): Files/min, ETA on 22500, Time.

cProfile — топ-10 функций по cumtime (из profile_baseline.txt).

Фикс — что именно изменено (diff или описание).

«После» (1000 файлов): Files/min, ETA on 22500, Time.

Логи после фикса: [OCR] Found via 'where' — сколько раз (должно быть 1, не 1000).

Функционал: все находки baseline присутствуют (сравнить count + fingerprint).

Скриншот ScanProgress после фикса (скорость ф/мин).

🎯 Что важно
Discovery — не узкое место. 53.4j уже это доказал (0.25s на 3100 файлов — не 8 часов). Корень — в OCR/классификации, а не в обходе.

@lru_cache не работает между процессами. Если OCRWorker — subprocess.Popen на каждый файл, кэш бесполезен. Нужен singleton.

Замер — обязателен. Без «до/после» (1000 файлов) — не принимаем отчёт. «Синтаксис валиден» — не доказательство.

Функционал не трогать. Если сомневаешься — не оптимизируй, спроси архитектора.