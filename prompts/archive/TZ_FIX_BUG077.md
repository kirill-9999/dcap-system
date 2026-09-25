📄 ТЗ: BUG-077 (Вариант C) — финальная версия v2
Файл: TZ_FIX_BUG077.md
Версия: v3.13.16 → v3.13.17
Оценка: ~40 мин
Дата: 24.09.2026
Контекст: найдено в Блоке 5 (WebUI deep) при проверке OCR-finding'ов

🎯 Цель
Устранить BUG-077: OCR-finding'и получают захардкоженный bounding_box = {x:0, y:0, width:0, height:0}, что вводит в заблуждение API/WebUI/аудит — они считают, что координаты есть, но вырезать нечего.

Минимальный фикс (Вариант C): заменить {0,0,0,0} на None — честно отражает отсутствие координат. Полный OCR-пайплайн с реальным bbox — отдельная задача BACKLOG-085 (v3.1.0).

Endpoint /fragment: зафиксирован Вариант 1 — для image_region без bbox возвращать весь PNG-файл с заголовком X-Fragment-Mode: full-image.

Дополнительно (косметика): синхронизировать дефолтные VERSION в docker-compose.yml для агентов (s3_agent, audit_agent_linux).

📌 Доказательная база
SQL (task 35)
sql
SELECT id, category, fragment_type, detector, bounding_box
FROM findings
WHERE task_id = 35 AND fragment_type = 'image_region';
text
  id  | category | fragment_type | detector |               bounding_box
------+----------+---------------+----------+-------------------------------------------
 1357 | email    | image_region  | ocr      | {"x": 0, "y": 0, "width": 0, "height": 0}
 1358 | phone    | image_region  | ocr      | {"x": 0, "y": 0, "width": 0, "height": 0}
Код — источник бага
Файл: scanner/connectors/filesystem.py, строки 331–335

python
for f in findings:
    f.fragment_type = "image_region"
    f.detector = "ocr"
    f.bounding_box = {"x": 0, "y": 0, "width": 0, "height": 0}
Причина: OCR-пайплайн (OCREngine.ocr_image, OCRWorker._perform_ocr) вызывает Tesseract CLI без tsv, возвращает только текст. Координаты никогда не вычислялись.

Ключевой факт из аудита Manager
manager/src/api/findings.py:75:

python
"has_fragment": bool(finding.fragment_path),
→ Условие по fragment_path, не по bounding_box/fragment_type. У OCR-находок fragment_path уже выставляется (filesystem.py:328 → _scan_text → строки 380/408). Значит:

has_fragment = True у OCR уже сейчас — и это корректно: fragment = сам PNG-файл.

BUG-078 не нужен — условие fragment_path покрывает OCR.

Endpoint /fragment (findings.py:464, 479) для image_region режет по bounding_box. После фикса bbox = None → требуется fallback (TASK-042).

🔧 Задача
TASK-041 (BUG-077) — bounding_box = None вместо {0,0,0,0}
Файл: scanner/connectors/filesystem.py, функция scan_file, блок OCR-изображений (строки ~323–335)

Было:

python
# Изображения — OCR (TASK-022, BUG-067): извлекаем текст через OCR
if ext in _IMAGE_EXTENSIONS:
    text = self._extract_document(str(p), ext)
    if not text:
        return []
    findings = self._scan_text(text, classifiers, str(p))
    # BUG-067d (TASK-034, день 46.8): findings из OCR-изображения
    # помечаем как image_region + detector=ocr + bounding_box.
    for f in findings:
        f.fragment_type = "image_region"
        f.detector = "ocr"
        f.bounding_box = {"x": 0, "y": 0, "width": 0, "height": 0}
    return findings
Стало:

python
# Изображения — OCR (TASK-022, BUG-067): извлекаем текст через OCR
if ext in _IMAGE_EXTENSIONS:
    text = self._extract_document(str(p), ext)
    if not text:
        return []
    findings = self._scan_text(text, classifiers, str(p))
    # BUG-067d (TASK-034, день 46.8): findings из OCR-изображения
    # помечаем как image_region + detector=ocr.
    # BUG-077 (TASK-041, v3.13.17): реальные координаты OCR не вычисляются
    # (Tesseract вызывается без --psm/tsv, только текст). Ставим None,
    # чтобы API/WebUI не пытались вырезать несуществующий регион.
    # Полный OCR-пайплайн с bbox — BACKLOG-085 (v3.1.0).
    for f in findings:
        f.fragment_type = "image_region"
        f.detector = "ocr"
        f.bounding_box = None
    return findings
TASK-042 (BUG-077) — fallback в endpoint /fragment (Вариант 1)
Файл: manager/src/api/findings.py, роут GET /api/findings/{id}/fragment (строки ~464, 479)

Требование: если fragment_type = "image_region" и bounding_box IS NULL — вернуть весь PNG-файл (не обрезанный), с заголовком X-Fragment-Mode: full-image. Если файл недоступен — 404.

Скелет (уточнить по факту кода):

python
if finding.fragment_type == "image_region":
    # BUG-077 (TASK-041): bbox может быть None, если OCR не вычислял
    # координаты. В этом случае отдаём весь файл (Вариант 1 ТЗ №8).
    if not finding.bounding_box:
        if not finding.fragment_path or not Path(finding.fragment_path).exists():
            raise HTTPException(404, "Fragment file not found")
        return FileResponse(
            finding.fragment_path,
            media_type="image/png",
            headers={"X-Fragment-Mode": "full-image"},
        )
    # ... существующая логика с bbox
Важно:

Путь к файлу — из fragment_path (не file_path — уточнить в API-модели, оба поля могут совпадать).

media_type — определить по расширению (png/jpg/jpeg/gif/bmp/tiff/webp) или всегда image/png (если файл — png).

Если файл недоступен (удалён, нет прав) — 404 Not Found.

TASK-043 (косметика) — синхронизация VERSION для агентов
Файл: docker-compose.yml

Проблема: дефолты VERSION у агентов остались на 3.13.12, manager/webui уже 3.13.16:

Сервис	Строка	Текущее	Должно быть
s3_agent	203	${VERSION:-3.13.12}	${VERSION:-3.13.16}
audit_agent_linux	231	${VERSION:-3.13.12}	${VERSION:-3.13.16}
Замечание: образы агентов не несут версии в /api/health — это чисто косметика, чтобы избежать случайного запуска устаревших образов при отсутствии VERSION в .env.

.env.example — не трогать (там уже VERSION=3.13.16).

🧪 Проверки после фикса
1. Unit-тест — tests/unit/test_ocr_bbox_v31317.py (создать)
Имя свободно, конфликтов с существующими 142 нет.

python
"""Smoke-тесты BUG-077 (TASK-041, v3.13.17): bounding_box=None для OCR."""

from unittest.mock import patch
from scanner.connectors.filesystem import FileSystemConnector
from scanner.src.finding import Finding


def _fake_finding():
    return Finding(
        line_number=1,
        line_text="email: test@example.com",
        match_text="test@example.com",
        start_pos=7, end_pos=23,
        finding_type="pii",
        category="email",
        detector="presidio",   # filesystem перезапишет на ocr для .png
    )


class TestOcrBoundingBox:
    """BUG-077: image_region без реальных координат → bounding_box=None."""

    def test_ocr_finding_bbox_is_none(self):
        """OCR-finding для .png: fragment_type=image_region, detector=ocr, bbox=None."""
        connector = FileSystemConnector()
        with patch.object(connector, "_extract_document", return_value="email: test@example.com"):
            with patch.object(connector, "_scan_text", return_value=[_fake_finding()]):
                findings = connector.scan_file("dummy.png", classifiers=[])
        assert len(findings) == 1
        f = findings[0]
        assert f.fragment_type == "image_region"
        assert f.detector == "ocr"
        assert f.bounding_box is None

    def test_text_finding_bbox_stays_none(self):
        """Обычный текстовый finding — bbox=None (не image_region)."""
        connector = FileSystemConnector()
        with patch.object(connector, "_read_text", return_value="email: test@example.com"):
            with patch.object(connector, "_scan_text", return_value=[_fake_finding()]):
                findings = connector.scan_file("dummy.txt", classifiers=[])
        assert len(findings) == 1
        assert findings[0].fragment_type == "text_line"
        assert findings[0].bounding_box is None
Запуск:

powershell
python -m pytest tests/unit/test_ocr_bbox_v31317.py -v
# ожидание: 2 passed

python -m pytest tests/unit/ -q
# ожидание: 144 passed (142 + 2), регрессий нет
2. Live-прогон (v3.13.17)
powershell
$env:VERSION="3.13.17"
docker compose build
docker compose up -d
curl http://127.0.0.1:8000/api/health
# → {"status":"healthy","version":"3.13.17"}
Перезапустить сканер (Ctrl+C → start_scanner.bat).

sql
DELETE FROM findings WHERE task_id = 35;
powershell
$login = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin123"}'
$token = $login.access_token

$body = @{
  resource_path = "C:\test\scanner_clean"
  name          = "scanner_clean_v3.13.17"
} | ConvertTo-Json

$task = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/tasks/create `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body
$task | ConvertTo-Json -Depth 5
Ожидаем task_id = 36, дождаться completed.

3. Критерии приёмки — SQL
sql
-- 1. OCR-finding'и — bbox = NULL
SELECT id, category, fragment_type, detector, bounding_box
FROM findings
WHERE task_id = 36 AND fragment_type = 'image_region';
-- ожидание: 2 строки, bounding_box = NULL

-- 2. Всего findings
SELECT COUNT(*) FROM findings WHERE task_id = 36;
-- ожидание: 29

-- 3. Разбивка без регрессий
SELECT category, detector, COUNT(*)
FROM findings WHERE task_id = 36
GROUP BY category, detector ORDER BY category;
-- ожидание: идентично task 35 (15 категорий, 29 findings)
4. Критерии приёмки — API
powershell
# 4.1. Список OCR-finding'ов
$r = Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/findings?task_id=36&fragment_type=image_region" `
  -Headers @{ Authorization = "Bearer $token" }
$r | Select-Object id, category, fragment_type, detector, bounding_box, has_fragment | Format-Table
# ожидание: bounding_box пусто, has_fragment=True

# 4.2. Детали одного OCR-finding
$ocrId = $r[0].id
$detail = Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/findings/$ocrId" `
  -Headers @{ Authorization = "Bearer $token" }
Write-Host "bounding_box: $($detail.bounding_box)"
Write-Host "has_fragment: $($detail.has_fragment)"
Write-Host "file_path: $($detail.file_path)"

# 4.3. Endpoint /fragment — fallback на весь файл (Вариант 1)
$frag = Invoke-WebRequest -Method GET "http://127.0.0.1:8000/api/findings/$ocrId/fragment" `
  -Headers @{ Authorization = "Bearer $token" }
Write-Host "Status: $($frag.StatusCode)"
Write-Host "Content-Type: $($frag.Headers['Content-Type'])"
Write-Host "Content-Length: $($frag.Headers['Content-Length'])"
Write-Host "X-Fragment-Mode: $($frag.Headers['X-Fragment-Mode'])"
Ожидание:

bounding_box = null (пусто)

has_fragment = True

file_path = путь к PNG

/fragment — 200 OK, Content-Type: image/png, X-Fragment-Mode: full-image ✅

5. WebUI smoke
Открыть http://localhost:8001/findings/{ocr_id}:

□ Страница открывается без ошибок
□ Не рисуется пустой/битый bbox
□ Кнопка «Показать фрагмент» работает — открывает весь PNG
□ Нет JS-ошибок в консоли браузера
📝 Сводка правок
#	Файл	Действие	Задача
1	scanner/connectors/filesystem.py	{"x":0,...} → None (строки ~331–335)	TASK-041
2	manager/src/api/findings.py	Fallback для /fragment при image_region + bbox=NULL → отдать весь файл (X-Fragment-Mode: full-image), строки ~464, 479	TASK-042
3	docker-compose.yml	VERSION агентов: 3.13.12 → 3.13.16 (строки 203, 231)	TASK-043
4	tests/unit/test_ocr_bbox_v31317.py	Создать (2 теста)	TASK-041
5	.env.example	НЕ трогать (уже 3.13.16)	—
6	docker-compose.yml	VERSION manager/webui → 3.13.17	релиз
7	STATE.md	BUG-077 → ✅ в закрытых	док
8	ROADMAP.md	BUG-077 → ✅; добавить BACKLOG-085 (v3.1.0)	док
9	ARCHITECTURE.md	Уточнить: image_region bbox может быть None до v3.1.0; endpoint /fragment возвращает весь файл	док
10	STATE_TEST_SESSION.md	Блок 5 (WebUI) — BUG-077	док
✅ Критерии закрытия ТЗ
□ python -m py_compile scanner/connectors/filesystem.py — OK
□ python -m py_compile manager/src/api/findings.py — OK
□ pytest tests/unit/test_ocr_bbox_v31317.py -v — 2 passed
□ pytest tests/unit/ -q — 144 passed (142 + 2), регрессий нет
□ Manager /api/health → 3.13.17
□ Пересоздан task 36 → 29 findings
□ SQL: bounding_box IS NULL для обоих OCR-finding'ов
□ SQL: разбивка идентична task 35 (15 категорий)
□ API: bounding_box = null, has_fragment = True для OCR
□ API: /fragment для OCR → 200 OK, X-Fragment-Mode: full-image
□ WebUI: страница OCR-finding'а открывается корректно, кнопка «Показать фрагмент» отдаёт весь PNG
□ docker-compose.yml агентов → 3.13.16
□ Обновлены STATE.md, ROADMAP.md, ARCHITECTURE.md, STATE_TEST_SESSION.md
🚀 После закрытия
BUG-077 → ✅ (Вариант C, endpoint — Вариант 1)

BACKLOG-085 → 📋 v3.1.0 — полный OCR-пайплайн с bbox (tesseract tsv)

TASK-043 → ✅ — VERSION агентов синхронизирован

BUG-078 → не создаётся (аудит показал: has_fragment через fragment_path уже покрывает OCR)

Блок 5 (WebUI) → продолжить с п.2.3 (фильтры)

Автор ТЗ: архитектор
Дата: 24.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.17, BUG-077 → ✅, TASK-043 → ✅