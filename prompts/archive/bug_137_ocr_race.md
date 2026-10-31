ТЗ: BUG-137 — OCRWorker: потеря ответов при параллельном сканировании
Файл: prompts/tz/bug_137_ocr_race.md
Дата: 09.10.2026
Версия: v3.13.35 → v3.13.36
Статус: ✏️ Готово к разработке
Оценка: ~2–3 ч (фикс + тесты)
Приоритет: 🔴 критично (блокер релиза v3.0.0; тихая потеря OCR-находок)
Родитель: 53.3-fs-regress-ocr-diag

🎯 ЦЕЛЬ
Починить гонку в OCRWorker, из-за которой при параллельном сканировании (max_parallel_files > 1) PNG-файлы молча теряют OCR-находки.

Симптом (D3): PNG + 10 других файлов, 8 потоков → 0 находок image_region/detector=ocr (одиночный прогон — 4).

📌 ПРЕДУСЛОВИЯ
✅ BUG-137 воспроизведён на живом стенде (Manager :8000 + Scanner на хосте).

✅ analyzer_pool_size=4, max_parallel_files=8, ocr_enabled=true.

✅ pii_screenshot.png (19929 байт) — 4 находки при одиночном прогоне.

✅ v3.13.35.

🔧 ДЕТАЛЬНОЕ ТЗ
TASK-BUG137-1 — Диагностика места потери
Файлы для изучения:

scanner/classifiers/ocr_worker.py — как устроен request_queue и как возвращаются ответы.

scanner/classifiers/pii_classifier.py — как вызывается OCRWorker из scan_text.

Что искать:

Очередь запросов/ответов. Если OCRWorker получает (request_id, image_bytes) и возвращает (request_id, text) через общую очередь — при параллельных вызовах возможна путаница ответов (ответ не тому клиенту) или потеря (клиент не дождался ответа и ушёл).

Timeout. Если стоит timeout (например, 30 с), а при параллелизме ответ приходит позже — запрос молча отбрасывается. ocr_timeout=60 в конфиге — проверить, применяется ли.

Синхронизация по pool_size. Если analyzer_pool_size=4 и max_parallel_files=8 — 8 потоков конкурируют за 4 процесса. Если нет корректной блокировки/пула, часть потоков не дожидается ответа.

Прислать в отчёте:

Ключевые фрагменты ocr_worker.py (request_queue, response_queue, worker-loop, отправка ответа) — что именно теряется.

Ключевые фрагменты pii_classifier.py (scan_text → OCR-вызов) — как формируется запрос и как ожидается ответ.

Одну фразу «где корень» (гонка / timeout / неверный pool).

TASK-BUG137-2 — Фикс
Конкретный фикс — за кодером, потому что зависит от того, что найдётся в TASK-1. Но направления:

Если ответы теряются из-за timeout: увеличить/убрать таймаут, или логировать потерю (WARNING), чтобы не молча.

Если ответы путаются (не тому клиенту): использовать request_id (UUID) и сопоставлять клиент ↔ ответ; либо у каждого клиента — своя очередь.

Если пул меньше параллелизма: синхронизировать max_parallel_files с analyzer_pool_size, либо блокировать до свободного слота (semaphore).

Обязательные требования к фиксу:

Никакой тихой потери. Если OCR-ответ не пришёл — WARNING в лог с file_path и pool_size/active.

Не ломать одиночный прогон. pii_screenshot.png в одиночку по-прежнему даёт 4 находки.

Не менять публичный интерфейс PiiClassifier.scan_text / scan_line.

TASK-BUG137-3 — Воспроизводимый тест
Файл: tests/unit/test_ocr_worker_race_v31336.py (новый).

Тест должен:

Создать PNG с текстом (Pillow, латиница — Phone:, Email:).

Запустить PiiClassifier.scan_text на одном файле — 4 находки.

Запустить параллельно (ThreadPoolExecutor, 8 потоков) на 11 файлах (PNG + 10 пустых txt) — все PNG должны дать находки.

Регресс на стабильность: 3 повтора подряд — каждый раз одинаковый результат.

Если OCR недоступен в unit-окружении (нет Tesseract) — тест skip с явной причиной, а воспроизведение — на живом стенде (ручной прогон D3 при критерии приёмки).

TASK-BUG137-4 — Live-проверка
Повторить D3 (PNG + 10 других файлов, 8 потоков) на живом стенде — PNG должен дать 4 находки image_region стабильно, 3 прогона подряд.

🧪 КРИТЕРИИ ПРИЁМКИ
#	Критерий	Проверка
1	Корень найден и описан в отчёте	TASK-BUG137-1
2	Фикс не ломает одиночный прогон	D2/D4 по-прежнему 4 находки
3	Параллельный прогон D3 даёт 4 находки	Live, 3 повтора
4	Никакой тихой потери — при неудаче OCR → WARNING	grep в pii_classifier.py
5	Unit-тест test_ocr_worker_race_v31336.py создан	pytest tests/unit/test_ocr_worker_race_v31336.py -v
6	Полный unit-набор зелёный	pytest tests/unit/ -q — 430+ passed
7	E2E зелёный	pytest tests/e2e/ -q — 53+ passed
⚠️ ЧТО НЕ ДЕЛАЕМ
Не переписываем OCR-пайплайн с нуля (точечный фикс).

Не меняем Tesseract / Presidio.

Не трогаем S3-коннектор.

Не трогаем WebUI-редизайн (это следующий день).

Не уменьшаем max_parallel_files (это «замаскировать» проблему, а не починить).

📋 ОТКРЫТЫЕ ВОПРОСЫ
Где корень — путаница ответов / timeout / pool < parallel? Ответ — после TASK-1.

ocr_timeout=60 — применяется ли в ocr_worker.py? Если нет — часть фикса.

💾 КОММИТ
bash
git checkout -b fix/bug_137_ocr_race

git add scanner/classifiers/ocr_worker.py \
        scanner/classifiers/pii_classifier.py \
        tests/unit/test_ocr_worker_race_v31336.py \
        ROADMAP.md STATE.md CHANGELOG.md \
        prompts/reports/bug_137_ocr_race_report.md

git commit -m "fix: BUG-137 — OCRWorker: гонка при параллельном сканировании (v3.13.36)

- scanner/classifiers/ocr_worker.py — <конкретный фикс по TASK-BUG137-2>
- scanner/classifiers/pii_classifier.py — WARNING при потере OCR-ответа
  (не молчаливая потеря)
- tests/unit/test_ocr_worker_race_v31336.py — воспроизводимый тест
  (одиночный vs параллельный прогон, 3 повтора)

BUG-137 (блокер v3.0.0; воспроизведён в 53.3-fs-regress-ocr-diag)
docs: обновлены STATE.md (v3.13.36), CHANGELOG.md, ROADMAP.md"
📌 ПОСЛЕ ВЫПОЛНЕНИЯ
Обновить STATE.md — версия v3.13.36, BUG-137 → ✅ fixed.

Обновить CHANGELOG.md — секция [3.13.36].

Обновить ROADMAP.md — BUG-137 закрыт, 53.3-fs-regress-ocr-diag отмечен.

Переместить ТЗ в prompts/archive/bug_137_ocr_race.md.

Отчёт — prompts/reports/bug_137_ocr_race_report.md.