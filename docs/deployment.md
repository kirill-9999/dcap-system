# Развертывание DCAP System (День 38)

Полная контейнеризация компонентов: Manager, WebUI, Celery (worker/beat/flower),
PostgreSQL 16, Redis 7, S3/MinIO аудит-агент. Стек поднимается одной командой.

**Сканер в Docker не запускается** (День 38.5+): задания приходят с путями хоста
(`E:\...`, `/mnt/...`), а контейнер может видеть только заранее смонтированные
тома и не может сам примонтировать папку из задания. Сканер работает **на хосте**
через `python run_scanner.py scanner/config/scanner_config.json` — так он видит
любые пути напрямую (см. раздел «Сканер» ниже).

## Требования

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM (минимум), 16 GB (рекомендуется)
- 2 CPU (минимум), 8 CPU (рекомендуется)
- 20 GB дискового пространства

## Структура
dcap-system/
├── Dockerfile # (нет) — Dockerfile для каждого компонента:
├── manager/Dockerfile # Manager + Celery worker/beat
├── webui/Dockerfile # WebUI
├── audit-agent-s3/Dockerfile # S3/MinIO аудит-агент
├── audit-agent-linux/Dockerfile# Linux аудит-агент
├── scanner/ # Scanner (НЕ в Docker, запуск на хосте)
├── .dockerignore # корневой (для сборки из корня репо)
├── docker-compose.yml # полный стек
├── docker-compose.prod.yml # production overrides
├── scripts/
│ ├── deploy.sh # полный деплой
│ ├── stop.sh # остановка
│ ├── logs.sh # логи
│ ├── status.sh # статус + health
│ └── healthcheck.sh # проверка здоровья
└── docs/deployment.md # этот файл

text

## Быстрый старт

```bash
# 1. Клонирование
git clone https://github.com/yourusername/dcap-system.git
cd dcap-system

# 2. Настройка
cp .env.example .env
# Отредактируйте .env (пароли PostgreSQL/Redis, JWT_SECRET_KEY, S3 ключи)

# 3. Генерация сертификатов (опционально, для mTLS)
python scripts/generate_certs.py

# 4. Генерация ключей Findings (обязательно)
python scripts/generate_findings_keys.py

# 5. Прописать ключи Findings в .env
#    (FINDINGS_ENCRYPTION_KEY, FINDINGS_HMAC_KEY, FINDINGS_KEY_ID)

# 6. Деплой
./scripts/deploy.sh
Примечание: build-контекст для Manager/S3-агента — корень репо
(компоненты используют пакет shared/ и/или корневой код импортов),
webui/Dockerfile — контекст ./webui.

Проверка
bash
# Статус
./scripts/status.sh

# Healthcheck
./scripts/healthcheck.sh

# Логи
./scripts/logs.sh -f
S3/MinIO аудит-агент (profile)
Агент не входит в базовый стек — запускается через profile agents:

bash
docker compose --profile agents up -d
Для него в .env заполните S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY.

Active Directory (Samba AD DC, profile ad)
Собираются в основной docker-compose.yml как сервис samba-ad-dc с профилем
ad. Вне профиля не запускается и не влияет на основной стек (redis, manager,
s3-агент остаются).

bash
# Без AD (обычный стек)
docker compose up -d

# С AD-контроллером домена — включается ТОЛЬКО сервис dcap-ad-dc
docker compose --profile ad up -d
Параметр	Значение
Образ	diegogslomp/samba-ad-dc
Контейнер	dcap-ad-dc
Realm / Domain	SAMDOM.EXAMPLE.COM / SAMDOM (env-переменные)
Пароль админа	Passw0rd
Host-порты	LDAP 389, LDAPS 636, DNS 1353→53, SMB 1445→445 и др.
Порт 53 на host занят → DNS наружу на 1353; внутри docker-сети — 53	
Сеть	dcap-network
Интеграция: Manager резолвит AD-контроллер по имени dcap.local (network alias
сервиса samba-ad-dc), аутентификация — режим hybrid / windows_integrated
(см. docs/admin-guide/04-authentication.md, раздел «Active Directory / hybrid»).

Примечание. Старый отдельный файл docker-compose.ad.yml удалён
(v3.13.8): его содержимое встроено в основной compose через profile ad.
Справочная копия — docker-compose.ad.yml.example (не используется compose).
Перед обновлением остановите ранее запущенный docker compose -f docker-compose.ad.yml ...,
иначе контейнер dcap-ad-dc будет orphan-ом.

Тестовые данные AD
bash
python scripts/init_ad_test_data.py
Scanner (тяжёлый агент сканирования)
Scanner — агент сканирования файлов (Tesseract, spaCy, Presidio), управляется через
Manager (REST-задания). Работает на хосте, не в Docker.

Причина: задания приходят с путями хоста (E:\shared, /mnt/data, UNC и т.д.).
Docker-контейнер видит только тома, смонтированные при его создании, и не может
сам примонтировать папку из задания. Сканер на хосте видит любые пути напрямую.

Требования окружения (на хосте)
bash
python -m pip install -r scanner/requirements.txt
# spaCy модели: python -m spacy download ru_core_news_sm en_core_web_sm
# Windows: apt отсутствует — Tesseract ставится отдельно (см. scanner/README)
Запуск
⚠️ Сканер требует ENV-ключи Findings (см. раздел «Ключи шифрования Scanner» ниже).

bash
export FINDINGS_ENCRYPTION_KEY=<base64 из secrets/findings_encryption_key>
export FINDINGS_HMAC_KEY=<base64 из secrets/findings_hmac_key>
export FINDINGS_KEY_ID=key-2026-09
python run_scanner.py scanner/config/scanner_config.json
Manager URL задаётся в scanner/config/scanner_config.json → scanner.manager_url
(по умолчанию http://localhost:8000; поддержан env-override MANAGER_URL,
LOG_LEVEL — см. scanner/src/config_loader.py).

Сканер регистрируется в Manager (/api/scanner/register), каждые N сек берёт
задание из очереди (/api/scanner/tasks/pending), сканирует путь из задания
(доступен напрямую на хосте), отправляет результаты
(/api/scanner/tasks/{id}/results). При недоступности Manager результаты
сохраняются в scanner/data/offline/ и автоматически досылаются.

Ресурсы
Параметр	Минимум	Рекомендуется
CPU	2	4
RAM	4 GB	8 GB
Диск	10 GB	50 GB
Troubleshooting
Scanner не регистрируется:

bash
# Проверить, что Manager поднят и виден
curl http://localhost:8000/api/health

# Проверить логи сканера
tail -f logs/scanner.log
Scanner не стартует: FINDINGS_ENCRYPTION_KEY not set — задайте ENV (см. ниже).

Production
bash
# С production overrides (лимиты ресурсов, mTLS, репликация worker)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
Prod-надстройка добавляет:

ограничения CPU/RAM для manager/postgres/redis/webui/celery_worker;

лимиты для сервисов мониторинга (prometheus/grafana/alertmanager/exporters);

POSTGRES_INITDB_ARGS=--data-checksums;

--maxmemory 512mb --maxmemory-policy allkeys-lru для Redis;

replicas: 2 для celery_worker;

mTLS (при включенном MTLS_ENABLED=true и наличии certs/).

Мониторинг (День 39)
Стек мониторинга поднимается вместе с остальными сервисами:

bash
docker compose up -d prometheus grafana alertmanager \
  postgres_exporter redis_exporter celery_exporter
Grafana — http://localhost:3000 (admin / ${GRAFANA_PASSWORD}, дефолт admin);

Prometheus — http://localhost:9090;

Alertmanager — http://localhost:9093.

Scanner отдаёт метрики на :9101 с хоста (он не в Docker) — Prometheus
собирает через host.docker.internal:9101 (для Linux-хостов в compose
сервиса prometheus добавлен extra_hosts).

Полная документация мониторинга — docs/monitoring.md.

Тестирование (День 40-41)
Изолированный тестовый стек (docker-compose.test.yml, БД dcap_test, tmpfs,
Manager :18000, WebUI :18001) и набор pytest-тестов — E2E / Chaos / Load.

bash
pip install -r requirements-dev.txt
./scripts/test-up.sh       # поднять тестовый стек
pytest tests/              # все тесты
./scripts/run-tests.sh e2e # E2E (также: chaos, load, quick, all)
./scripts/test-down.sh     # остановить стек
Полная документация тестирования — docs/testing.md.

Ключи шифрования находок (День 40.1)
С v3.9.0 находки хранятся в зашифрованном виде (AES-256-GCM) + HMAC-fingerprint.

Передача ключей — только через ENV (Docker Secrets, файлы, Vault — не используются в v3.0.0).

Генерация ключей
Перед первым запуском:

bash
python scripts/generate_findings_keys.py   # создаёт secrets/findings_*
Сгенерированные файлы (в secrets/, не коммитятся):

findings_encryption_key — base64-кодированные 32 байта (AES-256);

findings_hmac_key — base64-кодированные 32 байта (HMAC-SHA256);

findings_key_id — идентификатор ключа (например, key-2026-09).

Передача ключей в Manager (ENV)
В docker-compose.yml (секция manager):

yaml
services:
  manager:
    environment:
      FINDINGS_ENCRYPTION_KEY: ${FINDINGS_ENCRYPTION_KEY}
      FINDINGS_HMAC_KEY: ${FINDINGS_HMAC_KEY}
      FINDINGS_KEY_ID: ${FINDINGS_KEY_ID:-key-2026-09}
В .env (рядом с compose, не коммитится):

ini
FINDINGS_ENCRYPTION_KEY=<base64>
FINDINGS_HMAC_KEY=<base64>
FINDINGS_KEY_ID=key-2026-09
Ротация ключей
См. docs/admin-guide/05-security.md §3.8.

Кратко: ротация с downtime (перешифровка + обновление ENV), без *_OLD.

bash
# 1. Остановить сканеры и Manager
# 2. Сгенерировать новый ключ
python scripts/generate_findings_keys.py --key-id key-2026-12 --output secrets/new/

# 3. Перешифровать все находки
python scripts/reencrypt_findings.py \
    --old-key-file secrets/findings_encryption_key \
    --old-hmac-file secrets/findings_hmac_key \
    --new-key-file secrets/new/findings_encryption_key \
    --new-hmac-file secrets/new/findings_hmac_key \
    --new-key-id key-2026-12

# 4. Обновить .env + перезапустить Manager и Scanner'ы
Ключи шифрования Scanner (ENV)
С v3.10.0 Scanner шифрует и маскирует находки на стороне сканирующего хоста —
открытый текст не покидает хост. Ключи должны СОВПАДАТЬ с ключами Manager
(тот же FINDINGS_ENCRYPTION_KEY), иначе Manager не расшифрует match_text.

Передача ключей Scanner'у (только ENV):

bash
# Linux (systemd unit)
export FINDINGS_ENCRYPTION_KEY=<base64 из secrets/findings_encryption_key>
export FINDINGS_HMAC_KEY=<base64 из secrets/findings_hmac_key>
export FINDINGS_KEY_ID=key-2026-09                 # должно совпадать с key_id у Manager
python run_scanner.py scanner/config/scanner_config.json
Windows (PowerShell, ручной запуск):

powershell
$env:FINDINGS_ENCRYPTION_KEY = (Get-Content secrets\findings_encryption_key -Raw).Trim()
$env:FINDINGS_HMAC_KEY       = (Get-Content secrets\findings_hmac_key -Raw).Trim()
$env:FINDINGS_KEY_ID         = (Get-Content secrets\findings_key_id -Raw).Trim()
python -X utf8 run_scanner.py scanner/config/scanner_config.json
Windows (NSSM, служба):

powershell
nssm set DCAPScanner AppEnvironmentExtra `
    "FINDINGS_ENCRYPTION_KEY=<base64>" `
    "FINDINGS_HMAC_KEY=<base64>" `
    "FINDINGS_KEY_ID=key-2026-09" `
    "MANAGER_URL=http://dcap-manager.corp:8000"
Fail-fast: Scanner без ключей не стартует
С v3.13.9 (после фикса BUG-057) Scanner не стартует без FINDINGS_ENCRYPTION_KEY
и FINDINGS_HMAC_KEY. Это сделано намеренно — иначе PII уходит plaintext в Manager.

Только для dev можно включить legacy-режим:

bash
export DCAP_ALLOW_LEGACY_SCANNER=true   # ⚠️ PLAINTEXT УХОДИТ В MANAGER!
В production — категорически запрещено.

WebUI: находки и каталог (День 40.3)
WebUI переведён на строчную модель находок (v3.10+). Все данные — через прокси
на Manager (webui/api/routes.py, catch-all /api/*), прямого доступа к БД нет.

/findings — список находок (webui/templates/findings.html,
webui/static/js/findings.js): фильтры по статусу/типу/категории/severity/задаче,
bulk-действия (подтвердить/ложное), пагинация prev/next, экспорт отфильтрованного
списка в JSON.

/findings/{id} (40.3.2) — детальная карточка
(finding_detail.html, finding_detail.js): фрагмент кода, контекст, reveal
(POST /api/findings/{id}/reveal, доступен auditor/admin, действие логируется),
кнопки «Подтвердить» и «Ложное срабатывание» с комментарием.

/catalog (40.3.3) — каталог находок по файлам (catalog.js): дерево
папка → файл → найденные строки, поиск и фильтр по типу.

/false-positives — журнал ложных срабатываний.

Прогресс сканера на дашборде: карточка «Сканеры» показывает
current_task.progress (files_scanned/total/percent) из heartbeat.

Фрагменты и экспорт находок (День 40.4)
GET /api/findings/{id}/fragment — фрагмент находки (Viewer+):

image_region → PNG

?format=hex (byte_range) → hex-дамп

text_line/text_context → 400

category=person → 403 для не-Auditor

GET /api/findings/export?format=csv|json — экспорт находок (Auditor+):

По умолчанию маскированное; ?reveal=true — расшифровка (Auditor+), с аудитом

CSV: BOM для Excel, защита от CSV injection

GET /api/findings возвращает заголовок X-Total-Count

Остановка
bash
# Обычная остановка
./scripts/stop.sh

# С удалением volumes (все данные БД и логи удаляются!)
./scripts/stop.sh --volumes
Обновление
bash
git pull
docker compose build
docker compose up -d
Linux аудит-агент (docker)
Образ: cd audit-agent-linux && docker build -f Dockerfile -t dcap/linux-agent:3.5.0 .

Запуск: docker run -d --name dcap-linux-agent -v /path/to/watch:/watched \ -e MANAGER_URL=http://manager:8000 dcap/linux-agent:3.5.0

Внимание: дефолтный config.json агента указывает watch_paths: ["/home/kirill/test_audit"] —
замените его на свой (монтируйте поверх /app/config.json), либо используйте
docker run -v ./audit-agent-linux/config.json:/app/config.json:ro ....

Troubleshooting
Manager не запускается
bash
docker compose logs manager
PostgreSQL не готов
bash
docker compose exec postgres pg_isready -U dcap
Redis недоступен
bash
docker compose exec redis redis-cli ping
Alembic-миграции при первом старте
:8000/api/health отвечает 500? Manager при старте выполняет
alembic upgrade head. Проверьте логи:

bash
docker compose logs manager | grep -i alembic
При необходимости выполните вручную:
docker compose exec manager alembic upgrade head

text