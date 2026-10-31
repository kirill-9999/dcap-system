📋 ТЗ — ДЕНЬ 38.5: SCANNER В DOCKER
Файл: prompts/tz/day_38.5_scanner_containerization.md
Дата: 11.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Контейнеризовать Scanner (тяжелый агент сканирования) и добавить его в общий стек Docker:

Dockerfile для Scanner (multi-stage, Tesseract, spaCy, Presidio)

Scanner в docker-compose.yml — профиль scanner

Монтирование сканируемых папок — volume /scanned

Ресурсы — лимиты CPU/RAM в prod-override

Документация — инструкции по развертыванию Scanner

📁 СТРУКТУРА ИЗМЕНЕНИЙ
text
scanner/
├── Dockerfile               # НОВЫЙ: multi-stage
├── .dockerignore            # НОВЫЙ
└── requirements.txt         # ОБНОВИТЬ: точные версии

docker-compose.yml           # ОБНОВИТЬ: + scanner (profile)
docker-compose.prod.yml      # ОБНОВИТЬ: + лимиты для scanner
.env.example                 # ОБНОВИТЬ: + SCAN_PATH
docs/deployment.md           # ОБНОВИТЬ: + Scanner
🔧 ДЕТАЛЬНОЕ ТЗ
1. Scanner Dockerfile
dockerfile
# scanner/Dockerfile
# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build

# Системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/opt/dcapdeps -r requirements.txt

# Загрузка spaCy моделей
RUN PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages \
    python -m spacy download ru_core_news_lg || true
RUN PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages \
    python -m spacy download en_core_web_lg || true

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

WORKDIR /app

# Runtime зависимости: Tesseract + языки + OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование Python пакетов
COPY --from=builder /opt/dcapdeps /opt/dcapdeps
ENV PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages:$PYTHONPATH
ENV PATH=/opt/dcapdeps/bin:$PATH

# Копирование кода
COPY src/ ./src/
COPY config/ ./config/
COPY run_scanner.py .

# Создание пользователя
RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs /scanned \
    && chown -R dcap:dcap /app

USER dcap

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO
ENV MANAGER_URL=http://manager:8000

# Healthcheck (проверка процесса)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "run_scanner.py" || exit 1

# Сканируемые папки монтируются сюда
VOLUME ["/scanned"]

CMD ["python", "run_scanner.py", "config/scanner_config.json"]
2. scanner/.dockerignore
gitignore
__pycache__/
*.py[cod]
*.so
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.git/
.gitignore
.env
.env.*
*.db
*.sqlite
*.log
logs/
data/
certs/
secrets/
tests/
temp/
prompts/
docs/
*.md
!README.md
3. scanner/requirements.txt
txt
# scanner/requirements.txt
# Основные
fastapi>=0.104.0
uvicorn>=0.24.0
requests>=2.31.0
pydantic>=2.0.0
python-dotenv>=1.0.0

# Классификаторы
presidio-analyzer>=2.2.0
presidio-anonymizer>=2.2.0
spacy>=3.7.0
pytesseract>=0.3.10
Pillow>=10.0.0
pdf2image>=1.16.0
python-docx>=1.1.0
openpyxl>=3.1.0

# Утилиты
watchdog>=3.0.0
4. docker-compose.yml (дополнение)
yaml
# docker-compose.yml (дополнение)

services:
  # ... существующие сервисы ...

  # ===== SCANNER =====
  scanner:
    build:
      context: .
      dockerfile: scanner/Dockerfile
    image: dcap/scanner:${VERSION:-3.5.0}
    container_name: dcap-scanner
    environment:
      MANAGER_URL: http://manager:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      SCAN_PATH: /scanned
    volumes:
      - scanner_data:/app/data
      - scanner_logs:/app/logs
      # Монтирование сканируемых папок (read-only)
      - ${SCAN_PATH:-./data}:/scanned:ro
    depends_on:
      manager:
        condition: service_healthy
    profiles:
      - scanner
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
    networks:
      - dcap-network

volumes:
  # ... существующие volumes ...
  scanner_data:
    name: dcap-scanner-data
  scanner_logs:
    name: dcap-scanner-logs
5. docker-compose.prod.yml (дополнение)
yaml
# docker-compose.prod.yml (дополнение)

services:
  scanner:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    # Для больших объемов — несколько реплик
    # deploy:
    #   replicas: 2
    environment:
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
6. .env.example (дополнение)
bash
# .env.example (дополнение)

# ===== SCANNER =====
# Путь к сканируемым папкам на хосте
# Примеры:
#   Linux: /data/shared или /mnt/smb-share
#   Windows: C:\Data\Shared (WSL путь: /mnt/c/Data/Shared)
SCAN_PATH=/data/shared
7. docs/deployment.md (дополнение)
markdown
## Scanner

Scanner — тяжелый агент сканирования (Tesseract, spaCy, Presidio).

### Запуск

```bash
# Только Scanner
docker compose --profile scanner up -d scanner

# Всё сразу (Scanner + агенты)
docker compose --profile scanner --profile agents up -d
Монтирование папок
По умолчанию Scanner монтирует ${SCAN_PATH} в /scanned (read-only).

Примеры:

bash
# Linux
SCAN_PATH=/data/shared

# Windows (WSL)
SCAN_PATH=/mnt/c/Data/Shared

# Сетевые папки (сначала монтировать на хосте)
SCAN_PATH=/mnt/smb-share
Ресурсы
Параметр	Минимум	Рекомендуется
CPU	2	4
RAM	4 GB	8 GB
Диск	10 GB	50 GB
Размер образа
~1.5 GB (Tesseract + spaCy + Presidio).

Troubleshooting
Scanner не видит файлы:

bash
# Проверить монтирование
docker compose exec scanner ls -la /scanned

# Проверить SCAN_PATH
grep SCAN_PATH .env
Scanner не регистрируется:

bash
# Проверить Manager
docker compose logs manager | grep scanner

# Проверить логи Scanner
docker compose logs scanner
text

---

## ✅ КРИТЕРИИ ПРИЕМКИ

### Dockerfile
- [ ] Multi-stage сборка
- [ ] Tesseract + языки (rus, eng)
- [ ] spaCy модели (ru_core_news_lg, en_core_web_lg)
- [ ] Presidio
- [ ] Непривилегированный пользователь (dcap)
- [ ] Healthcheck
- [ ] Volume /scanned

### docker-compose
- [ ] Scanner в profile `scanner`
- [ ] Монтирование `${SCAN_PATH}:/scanned:ro`
- [ ] Зависимость от Manager (healthy)
- [ ] Volumes для data/logs
- [ ] Логирование с ротацией

### Production
- [ ] Лимиты CPU/RAM в prod-override
- [ ] Возможность репликации

### Документация
- [ ] docs/deployment.md — раздел Scanner
- [ ] .env.example — SCAN_PATH
- [ ] README обновлен

### Тестирование
- [ ] Образ собирается
- [ ] Scanner регистрируется в Manager
- [ ] Scanner сканирует смонтированные папки
- [ ] Находки отправляются в Manager

---

## 🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

```bash
# 1. Сборка образа
docker compose --profile scanner build scanner

# 2. Запуск
export SCAN_PATH=/tmp/test_scan
mkdir -p /tmp/test_scan
echo "password=test123" > /tmp/test_scan/test.env

docker compose --profile scanner up -d

# 3. Проверка
docker compose logs scanner
docker compose exec scanner ls -la /scanned

# 4. Проверка в Manager
curl http://localhost:8000/api/scanners

# 5. Проверка находок
curl http://localhost:8000/api/findings

# 6. Остановка
docker compose --profile scanner down
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_38.5_scanner_containerization
git add .
git commit -m "feat: День 38.5 — Scanner в Docker

Dockerfile:
- Multi-stage сборка (builder + runtime)
- Tesseract + языки (rus, eng)
- spaCy модели (ru_core_news_lg, en_core_web_lg)
- Presidio
- Непривилегированный пользователь
- Healthcheck
- Volume /scanned

docker-compose:
- Scanner в profile 'scanner'
- Монтирование SCAN_PATH:/scanned:ro
- Зависимость от Manager (healthy)
- Volumes для data/logs

Production:
- Лимиты CPU/RAM в docker-compose.prod.yml
- Возможность репликации

Документация:
- docs/deployment.md — раздел Scanner
- .env.example — SCAN_PATH"
📋 ОБНОВЛЕНИЕ ПЛАНА
День	Задача	Статус
36-37	Масштабирование	✅
38	Контейнеризация	✅
38.5	Scanner в Docker	📋 Ожидает
39	Мониторинг	📋
40-41	Тестирование	📋
42	GitHub	📋
43	Релиз	📋