📋 ТЗ — ДЕНЬ 32: S3-АГЕНТ (ЗАВЕРШЕНИЕ)
Файл: prompts/tz/day_32_s3_agent_finish.md
Дата: 01.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Завершить разработку S3-агента и подготовить его к промышленному использованию:

Нагрузочное тестирование — проверка производительности при больших объемах

Обработка ошибок и восстановление — улучшение отказоустойчивости

Документация — инструкции по развертыванию и эксплуатации

Интеграция в Docker Compose — единый стек

Полировка — улучшение логирования, обработка крайних случаев

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ / СОЗДАНИЯ
НОВЫЕ ФАЙЛЫ (СОЗДАТЬ)
Файл	Назначение
audit-agent-s3/tests/load/test_load.py	Нагрузочное тестирование агента
audit-agent-s3/docs/README.md	Документация по S3-агенту
audit-agent-s3/docs/deployment.md	Инструкции по развертыванию
audit-agent-s3/docs/troubleshooting.md	Устранение неисправностей
docker-compose.s3.yml	Docker Compose с S3-агентом
ИЗМЕНИТЬ
Файл	Изменение
audit-agent-s3/src/main.py	Улучшенная обработка ошибок, паузы при ошибках
audit-agent-s3/src/collector.py	Обработка throttling, улучшенные логи
audit-agent-s3/src/sender.py	Экспоненциальная задержка, улучшенный retry
audit-agent-s3/src/buffer.py	Оптимизация запросов, индексы
audit-agent-s3/config/config.json	Добавлены параметры для нагрузочного режима
AGENTS.md	Обновлена информация о S3-агенте
README.md	Обновлена документация
project_plan.md	Статус Дня 32
📋 ДЕТАЛЬНОЕ ТЗ
1. Нагрузочное тестирование
1.1. Тест: Обработка 10 000 событий
python
# audit-agent-s3/tests/load/test_load.py
import unittest
import time
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.buffer import BufferManager
from src.collector import S3LogCollector
from src.converters import s3_log_to_unified

class TestLoad(unittest.TestCase):
    """Нагрузочное тестирование"""
    
    def test_buffer_performance(self):
        """Тест производительности буфера"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": f"{tmpdir}/buffer.db",
                "max_events": 100000,
                "cleanup_days": 7
            }
            buffer = BufferManager(config)
            
            # Создание 10 000 событий
            events = []
            for i in range(10000):
                event = Mock()
                event.json.return_value = json.dumps({
                    "event_type": "read",
                    "event_source": "s3_agent",
                    "user": f"user{i}",
                    "file_path": f"s3://bucket/key{i}.txt",
                    "created_at": "2026-09-01T00:00:00.000Z"
                })
                events.append(event)
            
            # Измерение времени записи
            start = time.time()
            for event in events:
                buffer.store_event(event)
            write_time = time.time() - start
            
            # Измерение времени чтения
            start = time.time()
            unsent = buffer.get_unsent(limit=10000)
            read_time = time.time() - start
            
            print(f"Write 10 000 events: {write_time:.2f}s ({10000/write_time:.0f} events/sec)")
            print(f"Read 10 000 events: {read_time:.2f}s ({10000/read_time:.0f} events/sec)")
            
            self.assertLess(write_time, 5.0)  # < 5 секунд
            self.assertLess(read_time, 2.0)   # < 2 секунды
            self.assertEqual(len(unsent), 10000)
1.2. Тест: Обработка больших CSV файлов
python
def test_large_csv_parsing(self):
    """Тест парсинга большого CSV файла"""
    import csv
    import io
    
    # Генерация CSV с 10 000 строк
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'bucket', 'key', 'operation', 'requester', 'remote_ip', 
        'object_size', 'http_status', 'time'
    ])
    writer.writeheader()
    
    for i in range(10000):
        writer.writerow({
            'bucket': f'bucket{i%10}',
            'key': f'key{i}.txt',
            'operation': 'REST.GET.OBJECT' if i % 2 == 0 else 'REST.PUT.OBJECT',
            'requester': f'user{i%100}',
            'remote_ip': f'10.0.0.{i%255}',
            'object_size': str(i * 1024),
            'http_status': '200',
            'time': f'2026-09-01T{i%86400:06d}Z'
        })
    
    content = output.getvalue()
    
    # Измерение времени парсинга
    start = time.time()
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    parse_time = time.time() - start
    
    print(f"Parse 10 000 CSV rows: {parse_time:.2f}s ({10000/parse_time:.0f} rows/sec)")
    
    self.assertEqual(len(rows), 10000)
    self.assertLess(parse_time, 1.0)  # < 1 секунда
1.3. Тест: Отправка пакета 1000 событий
python
def test_batch_send_performance(self):
    """Тест производительности отправки"""
    from src.sender import Sender
    
    config = {
        "manager": {
            "url": "http://localhost:8000",
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1
        }
    }
    
    sender = Sender(config)
    
    # Создание 1000 событий
    events = []
    for i in range(1000):
        event = UnifiedEvent(
            event_type="read",
            event_source="s3_agent",
            user=f"user{i}",
            file_path=f"s3://bucket/file{i}.txt",
            created_at=datetime.utcnow().isoformat()
        )
        events.append(event)
    
    # Измерение времени сериализации
    start = time.time()
    data = [e.dict() for e in events]
    serialize_time = time.time() - start
    
    print(f"Serialize 1000 events: {serialize_time:.3f}s")
    self.assertLess(serialize_time, 0.5)
2. Улучшенная обработка ошибок
2.1. main.py — экспоненциальная задержка при ошибках
python
# audit-agent-s3/src/main.py (дополнение)

def main():
    # ... инициализация ...
    
    # Параметры для экспоненциальной задержки
    error_delay = 1
    max_error_delay = 300  # 5 минут
    
    while running:
        try:
            # 1. Сбор событий
            events = collector.poll()
            if events:
                logger.info(f"Collected {len(events)} events")
                error_delay = 1  # Сброс задержки при успехе
            
            # 2. Буферизация
            for event in events:
                buffer.store_event(event)
            
            # 3. Отправка
            unsent = buffer.get_unsent()
            if unsent:
                event_ids = [e[0] for e in unsent]
                events_to_send = [e[1] for e in unsent]
                
                if sender.send_events_batch(events_to_send):
                    buffer.mark_sent(event_ids)
                    logger.info(f"Sent {len(event_ids)} events")
                    error_delay = 1  # Сброс при успехе
                else:
                    logger.warning(f"Failed to send {len(event_ids)} events")
                    # Не сбрасываем delay
            
            # 4. Очистка старых событий
            buffer.cleanup_old_events()
            
            if args.once:
                break
            
            # 5. Ожидание с экспоненциальной задержкой
            delay = config["s3"].get("poll_interval", 60)
            if error_delay > 1:
                delay = min(delay, error_delay)
            
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            error_delay = min(error_delay * 2, max_error_delay)
            time.sleep(error_delay)
2.2. collector.py — обработка throttling
python
# audit-agent-s3/src/collector.py (дополнение)

def poll(self) -> List[UnifiedEvent]:
    """Опрос новых логов с обработкой throttling"""
    events = []
    
    try:
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=self.prefix,
            StartAfter=self.last_processed if self.last_processed else ""
        )
        
        # Проверка на throttling
        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 503:
            logger.warning("S3 throttling detected, waiting...")
            time.sleep(30)
            return []
        
        objects = response.get("Contents", [])
        logger.debug(f"Found {len(objects)} log files")
        
        # Ограничение количества обрабатываемых файлов за одну итерацию
        max_files_per_poll = 100
        if len(objects) > max_files_per_poll:
            logger.warning(f"Too many files ({len(objects)}), limiting to {max_files_per_poll}")
            objects = objects[:max_files_per_poll]
        
        # ... остальная логика ...
        
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'SlowDown':
            logger.warning("S3 SlowDown error, waiting...")
            time.sleep(60)
        elif e.response['Error']['Code'] == 'NoSuchBucket':
            logger.error(f"Bucket {self.bucket} does not exist")
            raise
        else:
            logger.error(f"S3 error: {e}")
            raise
    
    return events
2.3. sender.py — экспоненциальная задержка
python
# audit-agent-s3/src/sender.py (дополнение)

def _send_request(self, endpoint: str, data: dict) -> bool:
    """Выполнение запроса с экспоненциальной задержкой"""
    url = f"{self.manager_url}{endpoint}"
    retries = 0
    delay = self.retry_delay
    
    while retries < self.max_retries:
        try:
            response = self.session.post(url, json=data, timeout=self.timeout)
            
            if response.status_code in [200, 201, 202]:
                return True
            elif response.status_code == 429:
                # Rate limiting
                retry_after = int(response.headers.get("Retry-After", delay))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                retries += 1
                delay = min(delay * 2, 60)
            elif response.status_code in [500, 502, 503, 504]:
                # Server errors - retry
                logger.warning(f"Server error {response.status_code}, retrying...")
                time.sleep(delay)
                retries += 1
                delay = min(delay * 2, 60)
            elif response.status_code == 401:
                logger.error("Authentication failed")
                return False
            else:
                logger.error(f"Request failed: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout, retrying... ({retries+1}/{self.max_retries})")
            time.sleep(delay)
            retries += 1
            delay = min(delay * 2, 60)
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error: {e}, retrying... ({retries+1}/{self.max_retries})")
            time.sleep(delay)
            retries += 1
            delay = min(delay * 2, 60)
    
    return False
3. Документация
3.1. docs/README.md
markdown
# S3/MinIO Audit Agent

Агент для аудита S3-совместимых объектных хранилищ (Amazon S3, MinIO, Wasabi, etc.).

## Возможности

- **Polling-режим** — периодический опрос Server Access Logs
- **Поддержка форматов** — S3 Access Logs (CSV), MinIO webhook (JSON)
- **Буферизация** — SQLite с автоматической очисткой
- **Отказоустойчивость** — retry, экспоненциальная задержка, graceful shutdown
- **Безопасность** — JWT аутентификация (mTLS в разработке)
- **Контейнеризация** — Docker + Docker Compose

## Требования

- Python 3.11+
- Доступ к S3/MinIO (ключи доступа)
- Доступ к Manager API

## Установка

```bash
# Клонирование
cd dcap-system/audit-agent-s3

# Установка зависимостей
pip install -r requirements.txt

# Настройка
cp .env.example .env
# Отредактировать .env (S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET)
Конфигурация
Основные параметры:

Параметр	Описание	Обязательный
s3.bucket	Имя бакета	✅
s3.access_key	Access Key	✅
s3.secret_key	Secret Key	✅
s3.poll_interval	Интервал опроса (сек)	❌ (60)
manager.url	URL Manager API	✅
Полный пример: config/config.json.example

Запуск
bash
# Console режим
python -m src.main --config config/config.json

# Daemon режим
./scripts/start.sh --daemon

# Проверка статуса
./scripts/status.sh

# Остановка
./scripts/stop.sh
Мониторинг
Логи: logs/s3_agent.log

Состояние: data/state/

Буфер: data/buffer/buffer.db

Устранение неисправностей
См. troubleshooting.md

text

#### 3.2. docs/deployment.md

```markdown
# Развертывание S3-агента

## Docker

```bash
# Сборка
docker build -t dcap-s3-agent .

# Запуск
docker run -d \
  --name dcap-s3-agent \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e S3_BUCKET=my-logs \
  -e S3_ACCESS_KEY=xxx \
  -e S3_SECRET_KEY=xxx \
  dcap-s3-agent
Docker Compose
yaml
# docker-compose.s3.yml
services:
  s3-agent:
    build: ./audit-agent-s3
    environment:
      S3_BUCKET: my-logs
      S3_ACCESS_KEY: ${S3_ACCESS_KEY}
      S3_SECRET_KEY: ${S3_SECRET_KEY}
      MANAGER_URL: http://manager:8000
    volumes:
      - ./audit-agent-s3/config:/app/config
      - s3_data:/app/data
      - s3_logs:/app/logs
    restart: unless-stopped
Несколько бакетов
Запустите несколько экземпляров с разными переменными:

bash
docker run -d --name s3-agent-prod -e S3_BUCKET=logs-prod ...
docker run -d --name s3-agent-staging -e S3_BUCKET=logs-staging ...
Мониторинг в production
Логи: централизованный сбор (ELK / Loki)

Метрики: Prometheus (экспортер в разработке)

Алерты: при падении агента / переполнении буфера

text

#### 3.3. docs/troubleshooting.md

```markdown
# Устранение неисправностей S3-агента

## Агент не регистрируется

**Причина:** Manager недоступен или неправильный URL.

**Решение:**
1. Проверьте `manager.url` в конфиге
2. Проверьте доступность Manager: `curl http://manager:8000/health`
3. Проверьте логи: `tail -f logs/s3_agent.log`

## События не отправляются

**Причина:** Проблемы с аутентификацией или сетью.

**Решение:**
1. Проверьте JWT токен
2. Проверьте сетевые соединения
3. Проверьте буфер: `sqlite3 data/buffer/buffer.db "SELECT COUNT(*) FROM events WHERE sent=0"`

## S3 ошибка "AccessDenied"

**Причина:** Неправильные ключи доступа.

**Решение:**
1. Проверьте `S3_ACCESS_KEY` и `S3_SECRET_KEY`
2. Проверьте политики доступа к бакету
3. Проверьте, что бакет существует

## Буфер переполняется

**Причина:** Manager недоступен длительное время.

**Решение:**
1. Восстановите Manager
2. Увеличьте `buffer.max_events`
3. Уменьшите `s3.poll_interval`

## Высокая загрузка памяти

**Решение:**
1. Уменьшите `get_unsent` лимит (по умолчанию 100)
2. Увеличьте `cleanup_days` для очистки старых событий
3. Перезапустите агент
4. Интеграция в Docker Compose
4.1. docker-compose.s3.yml
yaml
# docker-compose.s3.yml
version: '3.8'

services:
  s3-agent:
    build:
      context: ./audit-agent-s3
      dockerfile: Dockerfile
    container_name: dcap-s3-agent
    environment:
      S3_ENDPOINT: ${S3_ENDPOINT:-https://s3.amazonaws.com}
      S3_BUCKET: ${S3_BUCKET}
      S3_PREFIX: ${S3_PREFIX:-access-logs/}
      S3_ACCESS_KEY: ${S3_ACCESS_KEY}
      S3_SECRET_KEY: ${S3_SECRET_KEY}
      S3_POLL_INTERVAL: ${S3_POLL_INTERVAL:-60}
      MANAGER_URL: ${MANAGER_URL:-http://manager:8000}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    volumes:
      - ./audit-agent-s3/config:/app/config
      - s3_data:/app/data
      - s3_logs:/app/logs
    networks:
      - dcap-network
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

volumes:
  s3_data:
    name: dcap-s3-data
  s3_logs:
    name: dcap-s3-logs

networks:
  dcap-network:
    external: true
4.2. docker-compose.yml — объединенный
yaml
# docker-compose.yml (обновленный)
version: '3.8'

services:
  manager:
    # ... существующая конфигурация ...

  webui:
    # ... существующая конфигурация ...

  s3-agent:
    extends:
      file: docker-compose.s3.yml
      service: s3-agent
5. Полировка
5.1. Улучшение логирования
python
# audit-agent-s3/src/main.py (дополнение)

import logging
from logging.handlers import RotatingFileHandler

def setup_logging(config: dict):
    """Настройка логирования с ротацией"""
    log_level = config.get("logging", {}).get("level", "INFO")
    log_format = config.get("logging", {}).get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Создание директории
    Path("logs").mkdir(exist_ok=True)
    
    # Настройка root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console)
    
    # File handler с ротацией
    file_handler = RotatingFileHandler(
        "logs/s3_agent.log",
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)
    
    return logging.getLogger(__name__)
5.2. Healthcheck эндпоинт
python
# audit-agent-s3/src/main.py (дополнение)

def print_status(state: StateManager, buffer: BufferManager, collector: S3LogCollector):
    """Вывод статуса агента"""
    logger.info("=" * 60)
    logger.info(f"Agent ID: {state.get_agent_id()}")
    logger.info(f"Last processed: {state.get_last_processed()}")
    logger.info(f"Buffer stats: {buffer.get_stats()}")
    logger.info(f"Collector: bucket={collector.bucket}, prefix={collector.prefix}")
    logger.info("=" * 60)
5.3. Обработка специальных случаев
python
# audit-agent-s3/src/collector.py (дополнение)

def poll(self) -> List[UnifiedEvent]:
    """Опрос новых логов с обработкой специальных случаев"""
    
    # Проверка существования бакета
    if not self._bucket_exists():
        logger.error(f"Bucket {self.bucket} does not exist")
        return []
    
    # Проверка прав доступа
    if not self._has_read_access():
        logger.error(f"No read access to bucket {self.bucket}")
        return []
    
    # ... остальная логика ...

def _bucket_exists(self) -> bool:
    """Проверка существования бакета"""
    try:
        self.s3_client.head_bucket(Bucket=self.bucket)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise

def _has_read_access(self) -> bool:
    """Проверка прав на чтение"""
    try:
        self.s3_client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            return False
        raise
📋 КРИТЕРИИ ПРИЕМКИ
Нагрузочное тестирование
□ Тест буфера: 10 000 событий за < 5 секунд
□ Тест парсинга: 10 000 CSV строк за < 1 секунда
□ Тест отправки: 1000 событий сериализация < 0.5 секунд
Обработка ошибок
□ Экспоненциальная задержка при ошибках
□ Обработка throttling S3
□ Обработка server errors (500+)
□ Обработка таймаутов
□ Проверка существования бакета
Документация
□ docs/README.md — описание агента
□ docs/deployment.md — инструкции по развертыванию
□ docs/troubleshooting.md — устранение неисправностей
Docker Compose
□ docker-compose.s3.yml — отдельный сервис
□ Интеграция с основным docker-compose.yml
Полировка
□ Ротация логов
□ Статус в логах
□ Обработка крайних случаев
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Нагрузочное тестирование
cd audit-agent-s3
python -m pytest tests/load/ -v

# 2. Проверка обработки ошибок
# (имитация недоступности Manager)
docker stop dcap-manager
# Агент должен продолжать работу с экспоненциальной задержкой

# 3. Проверка Docker Compose
docker-compose -f docker-compose.s3.yml up -d
docker-compose -f docker-compose.s3.yml logs s3-agent
docker-compose -f docker-compose.s3.yml down
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_32_s3_agent_finish
git add .
git commit -m "feat: День 32 — S3-агент (завершение)

- Нагрузочное тестирование (буфер, парсинг, отправка)
- Улучшенная обработка ошибок (экспоненциальная задержка, throttling)
- Документация (README, deployment, troubleshooting)
- Docker Compose интеграция (docker-compose.s3.yml)
- Ротация логов
- Healthcheck и статус
- Обработка крайних случаев (бакет не существует, нет прав)"
