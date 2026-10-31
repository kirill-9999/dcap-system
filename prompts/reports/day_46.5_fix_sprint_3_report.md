# Отчёт — День 46.5: Fix-спринт №3 — OCR, HTTP-retry, Luhn (v3.13.12)

**Дата:** 21.09.2026
**Версия:** v3.13.11 → v3.13.12
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_SPRINT_3.md` (fix-спринт №3)
**Коммиты:** `509a0bc` (fix) + docs

---

## 1. Проблемы

По итогам прогона Дня 46 (ENV-ключи Findings) + live-теста сканера выявлены 5 багов
в глубоком сканировании (OCR / сеть / дедупликация) и инфраструктуре. Решение —
fix-спринт №3 в ветке `fix/scanner_deep`.

| ID | Баг | Суть |
|----|-----|------|
| BUG-067 | OCR | Изображения и PDF-сканы не сканировались: `ocr_enabled` жёстко `False`, изображения → `[]` |
| BUG-066 | url-over-email | Ломаный legacy-дубль фильтра (`List[Finding]`) шэдоуил корректный → AttributeError |
| BUG-063 | Luhn | Presidio `CREDIT_CARD` детектился без Luhn-валидации (маски под номера) |
| BUG-061 | HTTP-retry | Отсутствие ретраев на сетевые сбои и 5xx |
| BUG-065 | credentials | Возможные дубли категорий и вытеснение более приоритетной категории |

---

## 2. Решение

### TASK-023/022 — BUG-067 (OCR) — `scanner/connectors/filesystem.py`

- `_extract_document`: `ocr_enabled=False` (жёстко) → `ocr_enabled=self.config.get("ocr_enabled", False)` — OCR включается из конфига сканера.
- `scan_file`: изображения (`_IMAGE_EXTENSIONS`) вместо stub `return []` теперь
  извлекаются через `_extract_document` → OCR через `DocumentExtractor`.
- OCR-инфраструктура уже была в проекте (`DocumentExtractor`, `ocr_engine.py`) —
  теперь она реально задействована для PDF-сканов и изображений.

### TASK-025 — BUG-066 (url-over-email) — `scanner/classifiers/pii_classifier.py`

- Удалён ломаный legacy-дубль `_filter_url_over_email`, работавший со старой моделью
  `List[Finding]` (`category=="email"`, `start_pos`/`end_pos` — AttributeError).
- Остался единственный корректный метод (L600, `List[ClassificationFinding]`,
  поля `subcategory`/`position`/`len(value)`) и единственный вызов (L834) —
  до дедупликации, чтобы URL-находки внутри email не плодились.

### TASK-024 — BUG-063 (Luhn) — `scanner/classifiers/pii_classifier.py`

- Добавлен `_is_valid_luhn` (L628) + `_filter_credit_cards_by_luhn` (L642):
  отсекает находки категории `credit_card`, для которых номер НЕ проходит Luhn.
- Вызов после url-фильтра, до dedup (L835).

### TASK-026 — BUG-061 (HTTP-retry) — `scanner/src/managed_scanner.py`

- `ManagerClient`: `HTTPAdapter(max_retries=Retry(total=5, backoff_factor=0.5,
  status_forcelist=(500,502,503,504), allowed_methods=GET/POST))` монтируется для
  `http://`/`https://` — устойчивость к сетевым сбоям и 5xx.

### TASK-027 — BUG-065 (dedup credentials) — `scanner/classifiers/pii_classifier.py`

- Дедупликация по `(subcategory, value)` с приоритетом категорий
  (`CATEGORY_PRIORITY`, L596) — обнаружена уже реализованной, правок не потребовалось.

---

## 3. Файлы

- `scanner/connectors/filesystem.py` — OCR из конфига + OCR изображений (BUG-067)
- `scanner/classifiers/pii_classifier.py` — Luhn (BUG-063), url-over-email (BUG-066)
- `scanner/src/managed_scanner.py` — HTTPAdapter+Retry (BUG-061)
- `docker-compose.yml`, `.env.example` — тег `VERSION` 3.13.11 → 3.13.12

---

## 4. Тестирование

- `py_compile` всех изменённых файлов — OK (COMPILE_OK / SCANNER_COMPILE_OK).
- Stack пересобран: `docker compose up -d --build` → образы `dcap/manager:3.13.12`,
  `dcap/webui:3.13.12`, все сервисы healthy.
- `/api/health` → `{"status":"healthy","version":"3.13.12"}`.

---

## 5. Команды

```powershell
cd E:\projects\dcap-system
git add -A
git commit -m "fix: OCR из конфига + OCR изображений (BUG-067); retry (BUG-061); Luhn (BUG-063); url-over-email (BUG-066) — День 46.5, v3.13.12"
docker compose up -d --build
```

---

## 6. Следующий шаг

Live-прогон глубокого сканирования (Manager :8000 + сканер) с реальными PDF-сканами
и изображениями → подтверждение OCR-находок → релиз v3.0.0.
