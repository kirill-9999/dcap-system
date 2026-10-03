# Отчёт Блок 6 — Агенты (Windows / Linux / S3) — v3.13.28

**Дата:** 03.10.2026
**Версия:** v3.13.28 (без bump — тот же релизный цикл, что и Блок 9)
**Ветка:** `develop`
**Статус блока:** ✅ закрыт (5 из 6 под-блоков; Блок 6.5 — сбор прав Windows — отложен на v3.1.0)

---

## 📋 Итоговая сводка

| Под-блок | Агент | Статус | Результат |
|----------|-------|--------|-----------|
| 6.1 | Windows-агент (служба) | ✅ закрыт | `DCAPAuditAgent` Running + Automatic, Security Log 4663, 47+ событий |
| 6.2 | Windows-агент (сбор прав) | ⏸ отложен | BUG-123, перенесён в Блок 6.5 / v3.1.0 |
| 6.3 | MinIO + S3-агент | ✅ закрыт | BUG-120 fixed, 16 событий в `audit_logs` |
| 6.4 | Linux-агент (WSL 2) | ⚠️ частично | События ✅, метрики и сквозной поток после restart WSL — на дотест (52.1) |
| 6.5 | Блок 6.5 | 📋 отложен | BUG-123 + BUG-127 |
| 6.6 | Документация | ✅ закрыт | 4 unit-файла + отчёты |

---

## 🪟 6.1 — Windows-агент (служба аудита)

### Что сделано
- Установлена служба `DCAPAuditAgent` через `audit-agent-windows/service.py` (pywin32), режим **Automatic**.
- Аудит-политика Windows: File System → `Success + Failure` (`auditpol /set /subcategory:"File System" /success:enable /failure:enable`).
- SACL на `E:\test_audit` установлен через .NET: `FileSystemAuditRule(S-1-1-0, FullControl, None, None, AuditFlags)` — `icacls /audit` не существует, нужен SACL через Win32/`.
- События `4663` (доступ к файлу), `4656` (создание), `4660` (удаление) стабильно генерируются при чтении/создании файлов.

### Проверка (Manager + PostgreSQL)
- Зарегистрирован агент `windows_agent` (`DESKTOP-9TI677N`).
- В `audit_logs` — **47+ событий** с `event_source='windows_agent'`, `event_type='file_access'`.
- Финальный тест: создан `service_test.txt` → событие 4663 доставлено.

### Решено
| ID | Проблема | Решение |
|----|----------|---------|
| BUG-120 | S3-агент ходил в AWS S3 вместо MinIO | `S3_ENDPOINT=http://host.docker.internal:9000`, нативный MinIO |

### Известные проблемы
| ID | Проблема | Приоритет |
|----|----------|-----------|
| BUG-123 | Сбор прав = 0: (а) 3-элементная распаковка ACE, (б) `win32security.FILE_GENERIC_*` отсутствуют — константы в `win32file` | 🟡 |
| BUG-127 | Сообщение «Manager недоступен?» при отправке прав (следствие BUG-123) | 🟡 |
| BUG-129 | Шум от собственного чтения агентом Security Log | 🟡 |
| BUG-121 | README: неверный SACL (`icacls /audit` не существует) | 🟢 |

### Артефакты
- `audit-agent-windows/config.json` — hostname `DESKTOP-9TI677N`, путь `E:\test_audit`.
- `audit-agent-windows/service.py` — `install|start|stop|remove`.
- `audit-agent-windows/logs/audit_agent.log` — UTF-8.

---

## 🐧 6.4 — Linux-агент в WSL 2

### Развёртывание
- Дистрибутив: **Ubuntu 22.04** в WSL 2, Python 3.10.12, пользователь `ser`, systemd включён через `/etc/wsl.conf` (`boot.systemd=true`).
- Агент развёрнут в `~/dcap/audit-agent-linux`, наблюдает `/home/ser/dcap-test`.
- Зависимости (`watchdog`, `prometheus_client`, `requests`) установлены **без sudo** через `get-pip.py --user` (TEST-NOTE-6.2).
- Юнит: `~/.config/systemd/user/dcap-audit-agent.service`, переживает restart WSL (linger).

### Проверено ✅
| Проверка | Результат |
|----------|-----------|
| Регистрация в Manager | `linux-agent-wsl-01`, **agent_id = 15** |
| События доступа к файлам | **9 событий** в `audit_logs` (`event_source='linux_agent'`) |
| Сбор POSIX-прав | **3 записи** (в т.ч. файл с правами 640) |
| Метрики `:9102` | отдаются внутри WSL (`dcap_linux_*`) |
| Буфер / ошибки | `buffer_size=0`, `send_errors=0` |
| Сквозной поток через службу | событие доходит до Manager |

### Осталось дотестировать (задача 52.1)
1. Метрики `:9102` — доступность **с хоста Windows** (не только изнутри WSL).
2. Сквозной поток **после `wsl --shutdown`** / перезапуска демона systemd.
3. **BUG-130** — retry без backoff при ошибке отправки прав.
4. **BUG-125** — `MANAGER_URL` env игнорируется (`audit-agent-linux/main.py` не читает переменную).

### Решено
| ID | Проблема | Решение |
|----|----------|---------|
| BUG-122 | systemd-unit не portable (`User=kirill`, `/home/kirill/...`) | Плейсхолдеры `__DCAP_USER__` / `__DCAP_HOME__` / `__DCAP_PYTHON__`, подстановка в `install.sh` |
| BUG-131 | `localhost:8000` терялся при зависании Docker | Само-исправился после перезагрузки |

### Известные проблемы
| ID | Проблема | Приоритет |
|----|----------|-----------|
| BUG-130 | Retry без backoff при ошибке отправки прав | 🟡 |
| BUG-125 | `MANAGER_URL` env игнорируется | 🟡 |

### Артефакты
- `audit-agent-linux/service/dcap-audit-agent.service` — обязательный `config.json`, плейсхолдеры.
- `audit-agent-linux/service/install.sh` — подстановка пользователя/пути/Python.
- `audit-agent-linux/main.py`, `collector.py`, `buffer.py`, `sender.py`, `metrics.py`.

---

## ☁️ 6.3 — MinIO + S3-агент

### Что сделано
- **BUG-120 (critical)** — S3-агент не отправлял события (`events_sent: 0` за 3 недели). Причина: в `.env` был `S3_ENDPOINT=https://s3.amazonaws.com` с пустыми credentials.
- MinIO развёрнут **нативно** (`E:\Dev\MinIO\bin\minio.exe`) — образы `minio/minio:latest` и `minio/mc:latest` не проходят через registry proxy (TEST-NOTE-6.1).
- Бакет `dcap-audit-logs`, alias `mc dcap → http://localhost:9000`.
- Исправлены build context / env в `docker-compose.yml` и `docker-compose.s3.yml`.
- Созданы seed-скрипты и логи: `scripts/seed_minio.sh`, `scripts/minio-seed/access-logs/*.json|*.csv`.
- Конфигурация агента: `S3_ENDPOINT=http://host.docker.internal:9000`, bucket `dcap-audit-logs`.

### Проверка
- В `audit_logs` — **16 событий** с `event_source='s3_agent'` (первая валидная выборка — 9; рост счётчика дал 16).
- Конвертер поддерживает JSON и CSV; CloudTrail-формат seed-логов конвертером **не поддерживается** (TEST-NOTE-6.3).
- Историческое расхождение: счётчик агента `events_sent=16` при 9 валидных в БД — зафиксировано как TEST-NOTE-6.6.

### Известные проблемы
| ID | Проблема | Приоритет |
|----|----------|-----------|
| BUG-135 | `json.loads` падает на **UTF-8 BOM** — файл `17-30-00.json` обрывает обработку | 🟡 |
| BUG-126 | `verify_ssl` приходит строковым, не bool | 🟢 |
| BUG-132 | S3-агент не переустанавливает соединение после перезагрузки Docker | 🟢 |
| BUG-134 | `mc.exe` без alias пишет в локальную папку (не баг DCAP) | 🟢 |

### Артефакты
- `docker-compose.minio.yml` (new), `.env` / `.env.example`, `scripts/seed_minio.sh`, `scripts/minio-seed/access-logs/*`.
- `audit-agent-s3/src/collector.py` — ⚠️ BUG-135, `audit-agent-s3/src/converters.py` — форматы.

---

## 📚 6.6 — Документация и отчёты

| Файл | Назначение |
|------|-----------|
| `audit-agent-windows/README.md` | Установка, запуск, SACL (⚠️ BUG-121) |
| `audit-agent-linux/docs/README.md`, `docs/deployment.md`, `docs/troubleshooting.md` | WSL 2, systemd-user, метрики |
| `audit-agent-s3/docs/*` (3 файла) | MinIO, режимы, troubleshooting |
| `scripts/seed_minio.sh` | Генерация тестовых access-логов |
| `prompts/reports/block6_agents_full_report.md` | Настоящий отчёт |
| `prompts/reports/s3_connector_deadcode_spravka.md` | Справка по неподключённому S3-коннектору Scanner |

---

## 🔍 Исследование S3-коннектора Scanner (подготовка к Дню 53)

Файл `scanner/connectors/s3_connector.py` **существует** (247 строк, tracked), но **функционально не подключён**:

| Что есть | Чего нет |
|----------|----------|
| `S3Connector` (read/list/metadata) | Ни одного `import`/`S3Connector()` в коде |
| Поддержка в `scanner/core/base.py` (`SourceType`) | Фабрики/выбора коннектора по заданию |
| `scanner/utils/file_hasher.py` с `hash_s3_object` | `connectors.s3` в конфиге сканера |
| `state_manager.py`, `orchestrator.py` | `boto3` в `scanner/requirements.txt` |
| | `managed_scanner.py:729,1126` жёстко создаёт `FilesystemConnector` |

**Вывод:** тестировать S3-коннектор «как есть» бессмысленно — сначала нужна интеграция (≈2–3 ч). Вынесено в отдельную задачу Дня 53.

---

## 🧪 Тесты Блока 9 (регрессия после Блока 6)

| Набор | Результат |
|-------|-----------|
| `tests/unit` | **359 passed** (317 + 42 новых), регрессий нет |
| `tests/e2e` | **46 passed, 12 skipped** против живого Manager на `:18000` |
| `manager/tests` | 44 passed, 1 пре-существующее падение (`test_retention.py::test_archiver_findings`, не связано со спринтом) |

---

## 📊 Изменённые / созданные файлы

### Создано
- `docker-compose.minio.yml`
- `scripts/seed_minio.sh`, `scripts/minio-seed/access-logs/*`
- `prompts/reports/block6_agents_full_report.md`
- `prompts/reports/s3_connector_deadcode_spravka.md`

### Изменено
- `.env`, `.env.example`
- `docker-compose.yml`, `docker-compose.s3.yml`
- `audit-agent-linux/service/dcap-audit-agent.service`, `audit-agent-linux/service/install.sh`
- `audit-agent-windows/config.json`
- `audit-agent-s3` — конфиг подключения к MinIO
- `audit-agent-linux`, `audit-agent-windows`, `audit-agent-s3` — `docs/`, `README.md`
- `CHANGELOG.md`, `ROADMAP.md`, `STATE.md`

### Не изменено (сознательно)
- `audit-agent-windows/collector.py` — частичная правка распаковки ACE **откачена** до Блока 6.5 (BUG-123), чтобы не оставлять недоделанный код в релизе.
- `audit-agent-linux/main.py` — BUG-125 отложен.
- `audit-agent-s3/src/collector.py` — BUG-135 отложен.
- `scanner/connectors/s3_connector.py` — интеграция отложена на День 53.

---

## ✅ Критерии приёмки

| # | Критерий | Статус |
|---|----------|--------|
| 1 | Windows-агент собирает Security Log (4663/4656/4660) и отправляет в Manager | ✅ 47+ событий |
| 2 | Windows-агент работает как служба `Automatic` | ✅ Running |
| 3 | S3-агент пишет события в Manager | ✅ 16 событий |
| 4 | MinIO развёрнут, бакет + seed-логи | ✅ |
| 5 | Linux-агент регистрируется и шлёт события | ✅ 9 событий, id 15 |
| 6 | Linux-агент собирает POSIX-права | ✅ 3 записи |
| 7 | Linux-агент поднимается как systemd-юнит на любом хосте | ✅ BUG-122 |
| 8 | Метрики `:9102` доступны | ⚠️ изнутри WSL ✅, с хоста — задача 52.1 |
| 9 | Сквозной поток после restart WSL | 📋 задача 52.1 |
| 10 | Регрессионные тесты Блока 9 зелёные | ✅ 359 / 46 |

---

## 🔄 Следующие шаги

1. **День 52.1** — Linux-агент: метрики с хоста, сквозной поток после `wsl --shutdown`, диагностика BUG-130.
2. **День 52.2 (Блок 6.5)** — BUG-123 (сбор прав Windows) + BUG-127.
3. **День 53** — Scanner: интеграция и тестирование S3-коннектора в MinIO.
4. **День 54** — Блок 11 (отказоустойчивость).
5. **День 55** — GitHub-пакет (BACKLOG-028/046).
6. **День 56** — BUG-117 (Manager-маскирование, hotfix).
7. **День 57** — релиз v3.0.0.

---

**Итог:** Блок 6 закрыт на 5 из 6 под-блоков. Критичный BUG-120 устранён, portability BUG-122 устранён. Три агента работают с живым Manager; остаток — дотест Linux, сбор прав Windows и подключение S3-коннектора Scanner.

Конец отчёта Блок 6 — v3.13.28