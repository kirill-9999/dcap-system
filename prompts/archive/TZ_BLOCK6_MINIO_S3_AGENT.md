Файл 3 — TZ_BLOCK6_MINIO_S3_AGENT.md
markdown
📋 ТЗ — БЛОК 6.3: MINIO + S3-АГЕНТ (ФИКС BUG-120)
Файл: prompts/tz/TZ_BLOCK6_MINIO_S3_AGENT.md
Дата: 03.10.2026
Версия: v3.13.28
Статус: ✏️ Готово к разработке
Оценка: ~40 мин
Приоритет: 🔴 критично (BUG-120 — S3-аудит не работает вообще)
Обнаружено: 03.10.2026, Блок 6.3

🎯 ЦЕЛЬ
1. Поднять MinIO в Docker.
2. Создать bucket `dcap-audit-logs`, заполнить тестовыми логами.
3. Переключить S3-агент на MinIO (фикс BUG-120).
4. Проверить сквозной поток: S3 → агент → Manager → audit_logs.

📌 ПРОБЛЕМА (BUG-120)
S3-агент (`dcap-s3-agent`) не работает:
- `events_sent: 0` за 3 недели работы.
- Логи каждые 5 минут: `ERROR - SSL validation failed for https://s3.amazonaws.com/dcap-logs [Errno 2] No such file or directory`.

Причина:
- В `.env` задано `S3_ENDPOINT=https://s3.amazonaws.com` (default AWS).
- `S3_ACCESS_KEY=""`, `S3_SECRET_KEY=""` — пустые.
- Bucket `dcap-logs` не существует ни на AWS, ни локально.
- MinIO не запущен (только пустая директория `~/.minio/certs`).
- boto3 ищет `~/.aws/credentials` → не находит → `[Errno 2]`.

📌 ПРЕДУСЛОВИЯ
- ✅ Docker Desktop запущен
- ✅ Основной стек Manager/Celery/PG/Redis — работает (v3.13.28)
- ✅ `docker-compose.s3.yml` — существует
- ✅ Сеть `dcap-network` — существует (external)
- ⏸️ S3-агент `dcap-s3-agent` — остановлен (Exited)
- ⏸️ MinIO — не установлен
- ⏸️ Порты 9000/9001 — проверить, свободны

📁 ФАЙЛЫ (создаются / изменяются)

Создаются:
- `docker-compose.minio.yml` — MinIO в Docker
- `scripts/minio-seed/access-logs/*.json` — тестовые логи
- `scripts/minio-seed/access-logs/*.csv` — тестовые CSV
- `scripts/seed_minio.sh` (или PowerShell) — загрузка в MinIO

Изменяются:
- `.env` — S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY
- `.env.example` — аналогично
- `docker-compose.s3.yml` — опционально (может не потребоваться)

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-097 — Проверка предусловий

Проверить, что S3-агент остановлен:
```powershell
docker ps -a --filter "name=dcap-s3-agent" --format "table {{.Names}}\t{{.Status}}"
Ожидание: Exited.

Проверить, что порты 9000/9001 свободны:

powershell
netstat -ano | Select-String ":9000|:9001"
Ожидание: пусто. Если занято — использовать 9002/9003.

Проверить сеть:

powershell
docker network ls | Select-String "dcap"
Ожидание: dcap-network есть.

TASK-098 — Поднять MinIO

Создать docker-compose.minio.yml:

yaml
version: '3.8'

services:
  minio:
    image: minio/minio:latest
    container_name: dcap-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - dcap-minio-data:/data
    networks:
      - dcap-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  dcap-minio-data:
    name: dcap-minio-data

networks:
  dcap-network:
    external: true
Запустить:

powershell
docker compose -f docker-compose.minio.yml up -d
Start-Sleep 15
docker ps --filter "name=dcap-minio"
curl.exe -s -o NUL -w "MinIO API → HTTP %{http_code}\n" http://localhost:9000/minio/health/live
curl.exe -s -o NUL -w "MinIO Console → HTTP %{http_code}\n" http://localhost:9001
Ожидание: HTTP 200 на обоих.

TASK-099 — Создать bucket и заполнить тестовыми логами

Создать директорию scripts\minio-seed\access-logs\ с файлами:

2026-10-03T10-00-00.json:

json
[
  {"eventTime": "2026-10-03T10:00:01Z", "eventName": "GetObject", "userIdentity": {"type": "IAMUser", "userName": "alice"}, "sourceIPAddress": "10.0.0.5", "requestParameters": {"bucketName": "dcap-audit-logs", "key": "docs/report.pdf"}, "responseElements": {"x-amz-request-id": "REQ001"}},
  {"eventTime": "2026-10-03T10:00:05Z", "eventName": "PutObject", "userIdentity": {"type": "IAMUser", "userName": "bob"}, "sourceIPAddress": "10.0.0.7", "requestParameters": {"bucketName": "dcap-audit-logs", "key": "uploads/data.csv"}, "responseElements": {"x-amz-request-id": "REQ002"}},
  {"eventTime": "2026-10-03T10:00:15Z", "eventName": "DeleteObject", "userIdentity": {"type": "IAMUser", "userName": "alice"}, "sourceIPAddress": "10.0.0.5", "requestParameters": {"bucketName": "dcap-audit-logs", "key": "old/temp.txt"}, "responseElements": {"x-amz-request-id": "REQ003"}}
]
2026-10-03T11-00-00.json:

json
[
  {"eventTime": "2026-10-03T11:00:01Z", "eventName": "ListBucket", "userIdentity": {"type": "IAMUser", "userName": "charlie"}, "sourceIPAddress": "10.0.0.9", "requestParameters": {"bucketName": "dcap-audit-logs"}, "responseElements": {"x-amz-request-id": "REQ004"}},
  {"eventTime": "2026-10-03T11:00:30Z", "eventName": "GetObject", "userIdentity": {"type": "IAMUser", "userName": "bob"}, "sourceIPAddress": "10.0.0.7", "requestParameters": {"bucketName": "dcap-audit-logs", "key": "images/photo.jpg"}, "responseElements": {"x-amz-request-id": "REQ005"}}
]
2026-10-03T12-00-00.csv:

csv
eventTime,eventName,userIdentity.userName,sourceIPAddress,requestParameters.bucketName,requestParameters.key
2026-10-03T12:00:01Z,GetObject,dave,10.0.0.11,dcap-audit-logs,backup/archive.zip
2026-10-03T12:00:10Z,PutObject,eve,10.0.0.13,dcap-audit-logs,logs/app.log
Создать bucket + загрузить:

powershell
docker run --rm --network dcap-network `
  -v "${PWD}\scripts\minio-seed:/seed:ro" `
  minio/mc:latest `
  sh -c "
    mc alias set dcap http://minio:9000 minioadmin minioadmin &&
    mc mb --ignore-existing dcap/dcap-audit-logs &&
    mc cp --recursive /seed/access-logs/ dcap/dcap-audit-logs/access-logs/ &&
    mc ls --recursive dcap/dcap-audit-logs
  "
Проверка (в браузере): http://localhost:9001 → minioadmin/minioadmin → bucket dcap-audit-logs → файлы есть.

TASK-100 — Обновить .env

Было:

text
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=dcap-logs
S3_ACCESS_KEY=
S3_SECRET_KEY=
Стало:

text
S3_ENDPOINT=http://minio:9000
S3_BUCKET=dcap-audit-logs
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_VERIFY_SSL=false
S3_PREFIX=access-logs/
S3_POLL_INTERVAL=15
MAX_ERROR_DELAY=60
Аналогично в .env.example (с placeholder'ами).

TASK-101 — Пересобрать и запустить S3-агент

powershell
docker compose -f docker-compose.s3.yml build s3-agent
docker compose -f docker-compose.s3.yml up -d s3-agent
Start-Sleep 20
docker logs dcap-s3-agent --tail 50
Ожидание в логах:

S3LogCollector initialized: bucket=dcap-audit-logs, prefix=access-logs/

Found N log files

Processing: access-logs/...

Collected N events

Sent N events

TASK-102 — Проверка сквозного потока

Логи S3-агента:

powershell
docker logs dcap-s3-agent --tail 100 | Select-String "Collected|Sent|Processing|ERROR"
Метрики:

powershell
curl.exe -s http://localhost:9103/metrics | Select-String "dcap_s3_"
Ожидание: dcap_s3_events_collected_total > 0, dcap_s3_events_sent_total > 0.

Через API Manager:

powershell
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

# Агент
Invoke-RestMethod -Method GET http://127.0.0.1:8000/api/audit/agents -Headers $headers |
    ConvertTo-Json -Depth 5 | Select-String "s3-agent-1" -Context 2,15

# События от s3_agent
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=s3_agent&limit=10" -Headers $headers |
    ConvertTo-Json -Depth 5
Ожидание:

events_sent > 0 для s3-agent-1.

Список событий от s3_agent.

В БД:

powershell
$sql = "SELECT event_source, COUNT(*) FROM audit_logs WHERE event_source='s3_agent' GROUP BY event_source;"
$sql | docker exec -i dcap-postgres psql -U dcap -d dcap
TASK-103 — Очистка мусорных агентов (опционально)

В Manager 12 агентов e2e-agent-* (артефакты E2E-тестов). Удалить:

powershell
2..13 | ForEach-Object {
  try {
    Invoke-RestMethod -Method DELETE "http://127.0.0.1:8000/api/audit/agents/$_" -Headers $headers
    "Deleted agent $_"
  } catch {
    "Failed to delete agent $_: $($_.Exception.Message)"
  }
}
🧪 КРИТЕРИИ ПРИЁМКИ
□ MinIO запущен (docker ps | grep minio)
□ Bucket dcap-audit-logs существует, содержит 3+ файла
□ .env обновлён (S3_ENDPOINT=http://minio:9000)
□ S3-агент запущен без ERROR-спама
□ Логи: Collected N events, Sent N events
□ dcap_s3_events_collected_total > 0
□ events_sent > 0 для s3-agent-1 в Manager
□ События от s3_agent появились в /api/audit
□ BUG-120 — ✅ закрыт

📊 LIVE-ПРОВЕРКА

powershell
# 1. MinIO
docker ps --filter "name=dcap-minio"

# 2. Bucket
docker run --rm --network dcap-network minio/mc:latest `
  sh -c "mc alias set dcap http://minio:9000 minioadmin minioadmin && mc ls --recursive dcap/dcap-audit-logs"

# 3. Логи S3-агента
docker logs dcap-s3-agent --tail 100

# 4. Метрики
curl.exe -s http://localhost:9103/metrics | Select-String "dcap_s3_"

# 5. События через API
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=s3_agent&limit=10" -Headers $headers
📝 СВОДКА ПРАВОК

#	Файл	Действие	Задача
1	docker-compose.minio.yml	Создан	TASK-098
2	scripts/minio-seed/access-logs/*	Созданы (JSON/CSV)	TASK-099
3	.env	Обновлён (S3_* → MinIO)	TASK-100
4	.env.example	Обновлён	TASK-100
5	dcap-s3-agent	Пересобран и запущен	TASK-101
6	audit-agent-s3/config/config.json	Возможно, нужен verify_ssl: false	TASK-100
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

MinIO credentials: minioadmin/minioadmin — для prod сменить.

S3_VERIFY_SSL=false для HTTP endpoint не критично.

Дополнительные форматы логов (CloudTrail native, S3 access log native) — тестировать отдельно.

📋 ОТКРЫТЫЕ ВОПРОСЫ

S3-агент в отдельном compose или в основном? → пока отдельный (docker-compose.s3.yml).

Нужны ли mTLS сертификаты для S3-агента? → в v3.1.0 (mTLS strict).

Очистка e2e-agent-* — обязательна? → нет, опционально.

⚠️ ЧТО НЕ ДЕЛАЕМ

Не настраиваем реальный AWS S3 (не наш сценарий).

Не разбираемся с CloudTrail-форматом (отдельная задача).

Не трогаем код S3-агента (BUG-120 — конфиг, не код).

Автор ТЗ: архитектор
Дата: 03.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: MinIO работает, S3-агент отправляет события в Manager, BUG-120 → ✅