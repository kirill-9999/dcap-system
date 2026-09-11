# Отчёт: День 38.5 — Scanner в Docker

**Дата:** 11.09.2026
**ТЗ:** `prompts/tz/day_38.5_scanner_containerization.md` (архив: `prompts/archive/day_38.5_scanner_containerization.md`)
**Роль:** Кодер
**Версия:** v3.6.1
**Ветка:** `feature/day_38.5_scanner_containerization` (создаётся при коммите)

---

## Резюме

Scanner (тяжёлый агент сканирования) контейнеризован и добавлен в общий Docker-стек:
`scanner/Dockerfile` (multi-stage: Tesseract + spaCy + Presidio), `.dockerignore`,
`requirements.txt`, сервис `scanner` в `docker-compose.yml` (profile `scanner`,
монтирование `${SCAN_PATH}:/scanned:ro`, volumes для данных/логов/состояния,
зависимость от Manager healthy), лимиты CPU/RAM в `docker-compose.prod.yml`,
раздел Scanner в `docs/deployment.md`, env-поддержка `MANAGER_URL`/`LOG_LEVEL` в
`scanner/src/config_loader.py`. Образ собран в Docker и прогонен smoke-тестом:
PII/Presidio/spaCy инициализируются, Tesseract (rus+eng) найден, все 3
классификатора загружаются, регистрация в Manager идёт.

---

## Ключевые решения (адаптации ТЗ)

> ТЗ давало «скелет» образца Dockerfile. При адаптации к реальной структуре
> кода внесены принципиальные отличия (зафиксированы ниже).

1. **Копирование кода**: ТЗ предлагало `COPY src/ ./src/` + `COPY config/ ./config/`.
   Реальный пакет сканера имеет **смешанные импорты** — `scanner.src.*`,
   `scanner.core.*` (абсолютные) и `core.*`/`utils.*`/`classifiers.*`
   (относительные, работают потому, что `managed_scanner.py` вставляет
   `scanner/` в `sys.path`). Поэтому в образ копируется **весь каталог `scanner/`**
   (`COPY scanner/ ./scanner/`) вместе с `run_scanner.py` (он живёт в корне репо).
   Именно так код работает локально через `python run_scanner.py`.

2. **spaCy-модели**: ТЗ загружало `ru_core_news_lg`/`en_core_web_lg`, но
   `scanner/classifiers/pii_classifier.py` (`_get_nlp_engine`) **жёстко использует
   `ru_core_news_sm`/`en_core_web_sm`**. Скачиваю модели **`sm` 3.8.0**
   (совместимы со spacy 3.8.x, URL публикуются в `explosion/spacy-models`,
   проверены 200/15MB+12MB) через `pip install --prefix=/opt/dcapdeps`
   (spacy download ставит модель в системный site-packages, т.е. мимо
   вендорного каталога и не попадает в `--prefix`).

3. **`requirements.txt`**: ТЗ-список содержал неиспользуемые пакеты
   (`fastapi`, `uvicorn`, `pdf2image`, `watchdog`, `presidio-anonymizer`).
   Реальный код импортирует: `pytesseract`, `PIL`, `pypdf`, `fitz`/PyMuPDF,
   `python-docx`, `openpyxl`, `xlrd`, `psutil`, `presidio-analyzer`, `spacy`,
   `requests`, `python-dotenv`. Список составлен именно по ним.

4. **`MANAGER_URL`/`LOG_LEVEL` env**: `config_loader.load_config` не имел
   поддержки окружения — в контейнере сканер обязательно должен стучаться на
   `http://manager:8000`, а не `localhost:8000`. Добавлен `_apply_env_overrides`,
   который подменяет `scanner.manager_url` и `scanner.log_level`.

5. **Runtime-каталоги**: ТЗ-тома `scanner_data:/app/data`, `scanner_logs:/app/logs`
   не совпадают с реальными путями сканера (всё считается от `WORKDIR /app`):
   state → `scanner/state`, offline/буфер → `scanner/data`, логи → `logs/`.
   Тома монтируются на реальные пути: `/app/scanner/state`, `/app/scanner/data`,
   `/app/logs`.

6. **`procps`**: healthcheck использует `pgrep`, а в `python:3.11-slim` пакета
   нет — добавлен в runtime-apt.

7. **`SCAN_PATH`** (env, `.env.example`): путь на хосте к сканируемым папкам,
   монтируется в `/scanned` (read-only). Дефолт `./data`.

---

## Выполненная работа

### NEW
- `scanner/Dockerfile` — multi-stage (builder: gcc/g++/libxml/libxslt + pip --prefix=/opt/dcapdeps; runtime: python:3.11-slim + tesseract(+rus,eng) + libgl1/libglib2/libxml2/libxslt1.1 + procps + curl), копирование `scanner/` + `run_scanner.py`, непривилегированный пользователь `dcap`, каталоги `/app/scanner/state`, `/app/scanner/data`, `/app/logs`, `/scanned`, HEALTHCHECK `pgrep -f run_scanner.py`, `VOLUME /scanned`, `CMD python run_scanner.py scanner/config/scanner_config.json`.
- `scanner/.dockerignore`
- `scanner/requirements.txt`
- `prompts/reports/day_38.5_report.md` (этот файл)

### Modified
- `scanner/src/config_loader.py` — `_apply_env_overrides(data)`: `MANAGER_URL`, `LOG_LEVEL`.
- `docker-compose.yml` — сервис `scanner` (profile `scanner`, container_name, env MANAGER_URL/LOG_LEVEL, volumes state/data/logs + `${SCAN_PATH:-./data}:/scanned:ro`, depends_on manager healthy, restart, logging, network) + volumes `scanner_state/scanner_data/scanner_logs`.
- `docker-compose.prod.yml` — `scanner.deploy.resources` (limits 2 CPU/4G, reservations 1 CPU/2G), комментарий про replicas.
- `.env.example` — секция `===== SCANNER =====` + `SCAN_PATH=./data`.
- `docs/deployment.md` — раздел Scanner (запуск, монтирование, ресурсы, troubleshooting), структура, build-контексты.
- `README.md` — раздел дня 38 (scanner/Dockerfile, profiles), версия v3.6.1.
- `AGENTS.md` — версия v3.6.1, статус (+Scanner в Docker), релиз v3.6.1, строка docker-compose (scanner profile), config_loader env.

---

## Тестирование

- `python -m py_compile scanner/src/config_loader.py` — ✅
- Конфиг сканера с env: `MANAGER_URL=http://manager:8000`, `LOG_LEVEL=DEBUG` → `cfg.scanner.manager_url='http://manager:8000'`, `log_level='DEBUG'` — ✅
- `docker compose config --quiet` — ✅ (base), ✅ (prod), ✅ (profile `scanner`), ✅ (scanner+agents)
- **Сборка** `docker compose --profile scanner build scanner` — ✅ (~15 мин; образ `dcap/scanner:3.5.0`, 1.4 GB — Tesseract + spaCy + Presidio)
- **Smoke-контейнер** (`dcap-smoke-scanner`, `MANAGER_URL=http://localhost:8000`):
  - `✅ Config loaded`, спаси-модели найдены/загружены, NLР движок создан (`en_core_web_sm`, `ru_core_news_sm`)
  - `✅ Presidio инициализирован`, кастомные распознаватели (PhoneRU, PassportRU, SnilsRU, InnRU, EmailRU)
  - Tesseract найден, языки `rus+eng`; OCRWorker запущен (PID)
  - `✅ Credentials/Code Classifier loaded` (3 классификатора)
  - Регистрация в Manager — `Connection refused` (ожидаемо: Manager отсутствует; `|| мэр` в проде — `depends_on: manager healthy`)
  - Status: `Up ... (healthy)`

---

## Запуск (ручное тестирование)

```powershell
# 1. Путь к сканируемым папкам
#    добавить в .env: SCAN_PATH=/data/shared  (Linux) или /mnt/c/Data/Shared (WSL)
Copy-Item .env.example .env

# 2. Только Scanner
docker compose --profile scanner build scanner
docker compose --profile scanner up -d scanner

# 3. Всё сразу (основной стек + Scanner + S3-агент)
docker compose --profile scanner --profile agents up -d

# 4. Проверка
docker compose ps
docker compose logs -f scanner            # регистрация, находки
docker compose exec scanner ls -la /scanned   # смонтированные папки
curl http://localhost:8000/api/scanners   # сканер зарегистрирован
curl http://localhost:8000/api/findings   # находки

# 5. Запустить задание сканирования через WebUI (Manager :8001) → Scanner его выполняет

# 6. Production (лимиты CPU/RAM)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile scanner up -d

# 7. Остановка
docker compose --profile scanner down
```

Ожидаемый результат: Scanner регистрируется в Manager (`/api/scanners`),
получает задания, сканирует `/scanned`, отправляет находки в Manager
(`/api/findings`). Без Manager (нет `manager:8000`) сканер живёт в цикле
heartbeat/retry (store&offline для результатов).

---

## Команда коммита

```powershell
git checkout -b feature/day_38.5_scanner_containerization
git add .
git commit -m "feat: День 38.5 — Scanner в Docker

Dockerfile:
- Multi-stage сборка (builder + runtime)
- Tesseract + языки (rus, eng)
- spaCy модели (ru_core_news_sm, en_core_web_sm)
- Presidio
- Непривилегированный пользователь
- Healthcheck
- Volume /scanned

docker-compose:
- Scanner в profile 'scanner'
- Монтирование SCAN_PATH:/scanned:ro
- Зависимость от Manager (healthy)
- Volumes для data/logs/state

Production:
- Лимиты CPU/RAM в docker-compose.prod.yml
- Возможность репликации

Код:
- scanner/config_loader.py: env MANAGER_URL/LOG_LEVEL
- scanner/requirements.txt по реальным импортам

Документация:
- docs/deployment.md — раздел Scanner
- .env.example — SCAN_PATH
- README.md / AGENTS.md обновлены (v3.6.1)"
```

---

## Обратная связь архитектору

- Все критерии приёмки выполнены; **спаси-модели должны быть `sm`, а не `lg`**
  (жёстко зашиты в `pii_classifier._get_nlp_engine`). `lg` (≈700MB/модель) —
  излишний вес и не используются. Если нужно `lg` — потребуется доработка
  классификатора (конфигурируемые модели).
- `presidio-anonymizer`, `pdf2image`, `fastapi`, `uvicorn`, `watchdog` из ТЗ
  не имеют импортов в сканере — не включал (приводит к лишним зависимостям и
  конфликтам numpy/opencv).
- Образ 1.4 GB — ожидаемый для Tesseract+spaCy+Presidio+OCR-моделей.
- `SCAN_PATH` в ТЗ имеет дефолт `./data`: в контейнере сканер получает путь
  задания от Manager (поле `task["path"]`) — реальный корень сканирования
  задаётся управляющей стороной, `/scanned` — точка монтирования.