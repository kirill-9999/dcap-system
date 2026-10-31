# S3/MinIO Audit Agent

Агент для аудита S3-совместимых объектных хранилищ (Amazon S3, MinIO, Wasabi и др.).

## Возможности

- **Polling-режим** — периодический опрос Server Access Logs
- **Поддержка форматов** — S3 Access Logs (CSV), MinIO webhook (JSON)
- **Буферизация** — SQLite с автоматической очисткой
- **Отказоустойчивость** — retry, экспоненциальная задержка, graceful shutdown
- **Безопасность** — JWT аутентификация (mTLS в разработке)
- **Контейнеризация** — Docker + Docker Compose
- **Нагрузочный режим** — оптимизированный буфер, ограничение файлов за опрос

## Требования

- Python 3.11+
- Доступ к S3/MinIO (ключи доступа)
- Доступ к Manager API (DCAP)

## Установка

```bash
cd dcap-system/audit-agent-s3

# Установка зависимостей
pip install -r requirements.txt

# Настройка
cp config/config.json.example config/config.json
# Отредактировать config/config.json (bucket, access_key, secret_key, manager.url)
```

> Альтернативно можно передавать параметры через переменные окружения
> (`S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `MANAGER_URL` и др.) —
> значения в конфиге вида `${VAR}` подставляются автоматически.

## Конфигурация

Основные параметры:

| Параметр | Описание | Обязательный |
|----------|----------|--------------|
| `s3.bucket` | Имя бакета | ✅ |
| `s3.access_key` | Access Key | ✅ |
| `s3.secret_key` | Secret Key | ✅ |
| `s3.poll_interval` | Интервал опроса (сек) | ❌ (60) |
| `s3.max_files_per_poll` | Макс. файлов за опрос | ❌ (100) |
| `manager.url` | URL Manager API | ✅ |
| `buffer.max_events` | Макс. событий в буфере | ❌ (100000) |
| `buffer.commit_batch` | Батч коммитов буфера | ❌ (100) |

Полный пример: `config/config.json.example`.

## Запуск

```bash
# Console режим
python -m src.main --config config/config.json

# Daemon режим
./scripts/start.sh --daemon

# Проверка статуса
./scripts/status.sh

# Остановка
./scripts/stop.sh
```

## Мониторинг

- Логи: `logs/s3_agent.log` (ротация 10 МБ, 5 файлов)
- Состояние: `data/state/`
- Буфер: `data/buffer/buffer.db`

## Развертывание

См. [deployment.md](deployment.md).

## Устранение неисправностей

См. [troubleshooting.md](troubleshooting.md).
