📋 ТЗ v3.14.8 — Scanner Performance Research (53.4j)
Файл: prompts/tz/day_53_4j_scanner_performance.md
Дата: 20.10.2026
Версия: v3.14.7 → v3.14.8 (research) → v3.14.9 (fix)
Приоритет: 🔴 Блокер v3.0.0 (сканер 26 ф/мин — нерабочая скорость)
Тип: Research + Fix (две фазы, сначала замер, потом фикс)
Длительность: 1.5–2 дня (research — 0.5 дня, fix — 1–1.5 дня)

⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ
Функциональность НЕ сокращается.
Все функциональные возможности должны остаться:

Маскирование (MASK_RULES + _CONTEXT_PATTERNS) — все 22 паттерна.

Классификаторы: PII, Credentials, Code, OCR.

Встроенные OCR-фрагменты в БД (fragment_data, base64 + SHA-256).

Дедупликация (HMAC-SHA256 fingerprint).

Построчное чтение (_text_scanner.py).

S3/FS/MinIO коннекторы (factory.create_line_connector).

Heartbeat, progress, retry, offline-буфер.

Документы (PDF/DOCX) через DocumentExtractor.

OCR (Tesseract).

Любая оптимизация, которая урезает функционал (например, «выключить OCR для .txt», «не отправлять fragment_data», «не считать fingerprint») — ЗАПРЕЩЕНА.
Если оптимизация требует изменения контракта (payload, схемы БД, API) — согласовать с архитектором до реализации.

🎯 Цель
Сканер обрабатывает 22 500 файлов за ~8–9 часов (ETA), скорость ~26 ф/мин. Для v3.0.0 это нерабочая скорость (реальный скан директории с 100k файлов займёт недели).

Задача:

Фаза 1 (Research): профилировать сканер, прогнать каждый вариант оптимизации на одном и том же наборе файлов, замерить скорость, выбрать наилучший вариант (или комбинацию).

Фаза 2 (Fix): реализовать выбранный вариант без потери функционала, замерить до/после, обновить тесты и документацию.

📊 Фаза 1 — Research (0.5 дня)
1.1. Зафиксировать baseline (что есть сейчас)
Подготовить тестовый набор:

Директория с 1000 файлов, репрезентативная:

400 .txt (маленькие, 1–10 KB).

200 .log (средние, 10–100 KB).

100 .csv.

50 .pdf (для OCR/DocumentExtractor).

50 .png/.jpg (для OCR).

200 .py/.js/.json (code/credentials).

Общий размер: ~50–100 MB.

Замер baseline:

powershell
# Засечь время
Measure-Command {
    python run_scanner.py scanner/config/scanner_config.json
} | Select-Object TotalSeconds
Дополнительно — профилирование:

powershell
python -m cProfile -s cumtime run_scanner.py scanner/config/scanner_config.json > profile_baseline.txt
Прислать в отчёте:

Total time (sec).

Файлов/мин.

Топ-10 функций по cumtime (из profile_baseline.txt).

CPU % / RAM % (по Get-Process).

Лог-объём (сколько строк пишет сканер на 1000 файлов).

1.2. Проверить каждый вариант (изолированно)
Для каждого варианта — отдельная ветка / отдельный запуск, замер скорости на том же наборе 1000 файлов. Функционал не меняется.

Вариант A — os.scandir вместо os.walk
Файл: scanner/connectors/filesystem.py (или где обход).

Суть: заменить os.walk() на рекурсивный os.scandir(). На Windows это даёт ×2–×5 за счёт ленивого stat.

Функционал: не меняется (все файлы обходятся, симлинки как раньше).

Замер: Total time, файлов/мин, топ-функции.

Риск: если где-то os.walk использовал dirs[:] для prune (skip_dirs) — перенести логику.

Вариант B — Кэш OCR-инициализации (@lru_cache + singleton)
Файл: scanner/utils/ocr_engine.py, scanner/classifiers/pii_classifier.py.

Суть: get_tesseract_cmd(), get_available_languages(), get_ocr_worker() — с @lru_cache(maxsize=1) / singleton. pytesseract.tesseract_cmd — задать 1 раз.

Функционал: не меняется (OCR работает на всех файлах, где нужен).

Замер: Total time, лог-объём (должен упасть в ~100 раз), ETA.

Риск: если OCRWorker хранит состояние между файлами — проверить, что нет race condition (в однопоточном режиме — ок).

Вариант C — Параллелизм (N потоков на файлы)
Файл: scanner/connectors/filesystem.py (или _text_scanner.py), конфиг max_parallel_files.

Суть: concurrent.futures.ThreadPoolExecutor(max_workers=N) — файлы обрабатываются в N потоков. OCR (внешний процесс Tesseract) отпускает GIL — потоки эффективны.

Функционал: не меняется. Порядок находок может измениться (если важен — сортировать по line_number при отправке).

Замер: Total time, файлов/мин, топ-функции, CPU %.

Риск: race condition в finding_collector / adaptive_cache_manager. Проверить, что батч отправляется одним HTTP-запросом (как сейчас), а не N.

Важно: если max_parallel_files > 1 уже работает — замерить его с разными N (2, 4, 8, os.cpu_count()).

Вариант D — Prefilter (пропуск «скучных» файлов без чтения)
Файл: scanner/connectors/_text_scanner.py::file_pass_prefilter.

Суть: для .txt/.log — читать первые N KB (например, 4 KB), искать «горячие» маркеры (email-домены, AKIA, -----BEGIN, password=). Если маркеров нет — не читать остальное.

Функционал: НЕ МЕНЯЕТСЯ. Prefilter — только оптимизация чтения, а не пропуск файлов. Все файлы сканируются.

Замер: Total time, файлов/мин.

Риск: если prefilter ложно-отрицательный — пропустим находку. Нельзя! Поэтому prefilter должен быть очень широким (лучше пропустить оптимизацию, чем находку).

Вариант E — Разделить чтение и обработку (pipeline)
Файл: scanner/connectors/filesystem.py + scanner/handlers/finding_collector.py.

Суть: 1 поток читает файлы (I/O-bound), N потоков обрабатывают (CPU-bound: классификаторы, OCR). queue.Queue.

Функционал: не меняется.

Замер: Total time.

Риск: сложнее, чем C. Если C даёт тот же эффект — не нужно.

1.3. Комбинации
После изолированных замеров — проверить комбинации:

A + B (scandir + кэш OCR) — вероятно, самый большой прирост при минимальном риске.

A + B + C (scandir + кэш OCR + параллелизм) — максимум.

A + B + D (если prefilter безопасен).

1.4. Таблица результатов (обязательно в отчёте)
Вариант	Total time (sec)	Файлов/мин	Прирост vs baseline	Лог-объём (строк)	Риск	Функционал сохранён
Baseline	...	26	—	~100k	—	✅
A (scandir)	...	...	...	...	низкий	✅
B (OCR cache)	...	...	...	~1k	низкий	✅
C (parallel, N=4)	...	...	...	...	средний	✅
D (prefilter)	...	...	...	...	средний	⚠️ проверить
A + B	...	...	...	...	низкий	✅
A + B + C	...	...	...	...	средний	✅
Выбор варианта: по критериям:

Функционал сохранён (жёстко).

Максимальный прирост (файлов/мин).

Минимальный риск (стабильность, тесты).

Совместимость с S3/MinIO (те же оптимизации должны работать).

Итоговая рекомендация в отчёте: «Вариант X (или комбинация X+Y) — потому что ...».

🛠️ Фаза 2 — Fix (1–1.5 дня)
После согласования выбора (с архитектором) — реализовать.

2.1. Изменения
Применить выбранный вариант (A/B/C/D/E или комбинацию).

Не сокращать функционал (см. ГЛАВНОЕ ТРЕБОВАНИЕ выше).

Если меняется контракт (payload, схемы БД, API) — согласовать до реализации.

2.2. Тесты
Unit — tests/unit/test_perf_v3148.py:

os.scandir возвращает те же файлы, что os.walk (на тестовой директории).

get_ocr_worker() возвращает один и тот же инстанс при повторных вызовах.

Параллельная обработка (если выбрана) — находки те же, что при последовательной (порядок может отличаться, но состав — тот же).

Prefilter (если выбран) — не пропускает файлы с PII/credentials (тест на 10 файлах с известными находками).

E2E — tests/e2e/test_perf_v3148.py:

Скан тестовой директории (1000 файлов) за < X сек (порог из baseline × 0.5).

2.3. Замер «до/после»
Повторить тот же замер (1000 файлов) на той же машине.

Прислать в отчёте: baseline vs fix (файлов/мин, Total time, ETA на 22 500).

2.4. Обновить документацию
ARCHITECTURE.md §«Сканер: инстансы и параллелизм» — обновить, если меняется модель.

docs/admin-guide/06-scanner.md — если есть настройка max_parallel_files, описать.

CHANGELOG.md — [v3.14.8].

STATE.md / STATE_TEST_SESSION.md — обновить.

📋 Ручная приёмка (после fix)
#	Сценарий	Ожидание
1	Скан 1000 файлов	< X сек (по результатам research), файлов/мин > baseline
2	Находки	Все находки из baseline присутствуют (сравнить findings count + fingerprint set)
3	OCR	На .png/.pdf — находки есть, fragment_data в БД
4	S3-скан	Работает, находки > 0 (не только FS)
5	Heartbeat	Продолжает идти, progress обновляется
6	Лог	[OCR] Found via 'where' — 1 раз (если B применён)
7	ETA на 22 500 файлов	< 2 часов (цель)
✅ Definition of Done (Фаза 1 + Фаза 2)
Фаза 1 (Research):

□ Baseline замерен (Total time, файлов/мин, топ-функции cProfile, лог-объём).
□ 5 вариантов (A/B/C/D/E) изолированно замерены на 1000 файлах.
□ Комбинации (A+B, A+B+C, A+B+D) замерены.
□ Таблица результатов в отчёте.
□ Итоговая рекомендация с обоснованием.
□ Согласовано с архитектором (какой вариант выбран).
Фаза 2 (Fix):

□ Выбранный вариант реализован.
□ Функционал сохранён (все находки baseline присутствуют, OCR работает, fragment_data в БД).
□ Unit test_perf_v3148.py — passed.
□ E2E test_perf_v3148.py — passed.
□ Замер «до/после» в отчёте (файлов/мин, ETA на 22 500).
□ Документация обновлена (ARCHITECTURE, docs/admin-guide/06-scanner.md).
□ docker inspect dcap-scanner (или как собирается) — версия.
□ Ручная приёмка 7/7 ✅.
💾 Коммит (Фаза 2)
powershell
git add scanner/connectors/filesystem.py scanner/utils/ocr_engine.py `
        scanner/classifiers/pii_classifier.py scanner/connectors/_text_scanner.py `
        scanner/connectors/s3_line_connector.py `
        scanner/config/scanner_config.json `
        tests/unit/test_perf_v3148.py tests/e2e/test_perf_v3148.py `
        .env docker-compose.yml `
        ARCHITECTURE.md CHANGELOG.md STATE.md STATE_TEST_SESSION.md `
        docs/admin-guide/06-scanner.md
git commit -m "perf: 53.4j scanner — [вариант] (v3.14.8)

Baseline: 26 ф/мин (8-9ч на 22 500).
Fix: [вариант] — [кратко, что сделано].
Результат: [N] ф/мин, ETA [M]ч на 22 500.

Функционал сохранён: все находки baseline присутствуют, OCR работает,
fragment_data в БД, S3/FS/MinIO коннекторы.

Tests: test_perf_v3148.py (unit), test_perf_v3148.py (e2e)."
🎯 Что важно
Это research + fix, а не просто fix. Разработчик должен сначала замерить, потом выбрать, потом сделать. Без замеров — не поймём, куда копать.

Функционал — святое. Любая оптимизация, которая сокращает возможности (не считает fingerprint, не отправляет fragment_data, пропускает файлы, не делает OCR), запрещена.

Согласование с архитектором — до Фазы 2, если меняется контракт или схема БД.

Baseline фиксируется на одном наборе 1000 файлов — чтобы «до/после» было честным.