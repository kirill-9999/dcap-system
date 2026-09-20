# 🔐 05. Безопасность

> **Руководство администратора DCAP.**
> Раздел «Безопасность»: mTLS, шифрование находок, RBAC, ключи, инциденты.
> Общие принципы — в [SECURITY.md](../../SECURITY.md). Чеклист — в [docs/security_checklist.md](../security_checklist.md).

**Обновлено:** 20.09.2026
**Версия:** v3.13.10

---

## 📖 Содержание

1. [Обзор](#1-обзор)
2. [mTLS (взаимная аутентификация)](#2-mtls-взаимная-аутентификация)
3. [Управление ключами Findings (ENV)](#3-управление-ключами-findings-env)
   - 3.1 [Принцип: только ENV](#31-принцип-только-env)
   - 3.2 [**Зачем ключи на Scanner, если есть mTLS?**](#32-зачем-ключи-на-scanner-если-есть-mtls)
   - 3.3 [ENV-переменные](#33-env-переменные)
   - 3.4 [Первичная генерация](#34-первичная-генерация)
   - 3.5 [Manager: передача ключей через ENV](#35-manager-передача-ключей-через-env)
   - 3.6 [Scanner: передача ключей через ENV (N сканеров)](#36-scanner-передача-ключей-через-env-n-сканеров)
   - 3.7 [Инвентаризация сканеров](#37-инвентаризация-сканеров)
   - 3.8 [Ротация ключей](#38-ротация-ключей)
   - 3.9 [Компрометация ключа](#39-компрометация-ключа)
   - 3.10 [Troubleshooting](#310-troubleshooting)
4. [Маскирование и шифрование находок](#4-маскирование-и-шифрование-находок)
5. [Аутентификация и RBAC](#5-аутентификация-и-rbac)
6. [Rate-limit](#6-rate-limit)
7. [Хранение секретов](#7-хранение-секретов)
8. [Аудит и логирование](#8-аудит-и-логирование)
9. [Инцидент: что делать](#9-инцидент-что-делать)
10. [Чеклист production](#10-чеклист-production)

---

## 1. Обзор

DCAP защищает данные на нескольких уровнях:

| Уровень | Механизм |
|---------|----------|
| **Транспорт** | mTLS между компонентами |
| **Данные** | AES-256-GCM для находок, masked по умолчанию |
| **Доступ** | JWT + RBAC (admin/auditor/scanner/viewer) |
| **Секреты** | ENV (обязательно), rotation 90 дней |
| **Аудит** | `audit_logs` — все sensitive операции |
| **Rate-limit** | 300 req/min на IP (Redis) |

**Главный принцип:** открытый текст PII **не покидает** сканирующий хост. Scanner шифрует **на месте**, Manager хранит только зашифрованное + маскированное.

---

## 2. mTLS (взаимная аутентификация)

### Режимы

| Режим | Описание | Когда использовать |
|-------|----------|-------------------|
| `relaxed` | Работает на plain HTTP, если сертификатов нет | Dev, тестирование |
| `strict` | Manager **не стартует** без PKI | **Production** |

### Настройка

**`manager/config/config.json`:**

```json
{
    "security": {
        "mtls_enabled": true,
        "mtls_strict": false,
        "certs_dir": "certs"
    }
}
ENV (override):

ini
MTLS_ENABLED=true
MTLS_STRICT=true          # production
CERTS_DIR=/app/certs
Генерация сертификатов
bash
python scripts/generate_certs.py
Создаёт:

certs/ca.crt, certs/ca.key — корневой CA

certs/manager.crt, certs/manager.key

certs/scanner.crt, certs/scanner.key

certs/webui.crt, certs/webui.key

certs/agents/*.crt, certs/agents/*.key

Ротация сертификатов
Каждые 90 дней:

bash
python scripts/rotate_certs.py
docker compose restart manager webui
CRL (отзыв)
Файл certs/crl.pem — список отозванных сертификатов. Обновляется через rotate_certs.py --revoke <serial>.

Компоненты, поддерживающие mTLS:

Manager ↔ WebUI

Manager ↔ Scanner

Manager ↔ агенты (Windows, Linux, S3)

3. Управление ключами Findings (ENV)
3.1 Принцип: только ENV
Все ключи Findings передаются компонентам только через переменные окружения.

Компоненты, использующие ключи:

Manager — хранитель, шифрует/расшифровывает по запросу.

Scanner (N штук, на хостах) — потребитель, шифрует на стороне сканирующего хоста.

Агенты (Windows/Linux/S3) — не используют ключи Findings (аудиторские события не шифруются).

Почему ENV:

✅ Единый механизм для всех компонентов (Docker, systemd, Windows-службы).

✅ Простота развёртывания.

✅ Совместимость с CI/CD, Ansible, Kubernetes.

⚠️ Известное ограничение: ENV видны в ps, /proc/<pid>/environ, docker inspect. Митигация: доступ к хосту ограничен, ключи не логируются.

Не используются:

Docker Secrets — пока нет (см. STATE.md, v3.1.0+).

Файлы ключей — не передаются в открытом виде.

Vault — не интегрирован (v3.1.0+).

3.2 Зачем ключи на Scanner, если есть mTLS?
Короткий ответ: mTLS и шифрование находок — разные слои защиты. mTLS защищает канал, шифрование — данные в состоянии покоя.

Что защищает mTLS
Угроза	mTLS
Перехват трафика в сети	✅ защищает
MITM между Manager и Scanner	✅ защищает
Подмена Scanner (подложный агент)	✅ защищает (mutual auth)
Подмена Manager (фишинг сканера)	✅ защищает
Что mTLS НЕ защищает
Угроза	mTLS
Компромисс Manager (RAM, core dump, bash в контейнере)	❌ не защищает
Компромисс БД (кража диска, дамп, DBA)	❌ не защищает
Утечка бэкапа БД	❌ не защищает
Утечка логов Manager (PII в debug)	❌ не защищает
Компромисс хоста сканера (env, RAM, /proc)	❌ не защищает
Утечка offline-буфера сканера	❌ не защищает
Модель A — Scanner НЕ шифрует (только mTLS)
text
Scanner читает файл → plaintext
       ↓ (mTLS канал — защищён)
Manager получает plaintext → шифрует → БД
Что защищено: канал (mTLS).
Что НЕ защищено:

🔴 Manager видит plaintext всегда (в RAM, логах, трейсбэках, core dumps, swap).

🔴 Скомпрометированный Manager = все PII в plaintext.

🔴 Скомпрометированный хост сканера — вообще всё (файлы, RAM, env).

🔴 Offline-буфер сканера содержит plaintext.

🔴 Один баг в логировании Manager = утечка PII.

Модель B — Scanner шифрует до отправки (текущая, целевая)
text
Scanner читает файл → plaintext
       ↓ (шифрование на хосте сканера, ключ в ENV)
Scanner отправляет шифротекст → (mTLS канал — защищён)
Manager получает шифротекст → БД (шифротекст)
Что защищено:

✅ Канал (mTLS).

✅ Manager никогда не видит plaintext (кроме короткого момента reveal).

✅ Компромисс Manager без ключа → PII не читается.

✅ Компромисс хоста сканера → только этот хост (не вся система).

✅ Offline-буфер сканера = шифротекст.

✅ Бэкапы БД = шифротекст (если ключ не в дампе).

✅ Дампы памяти Manager = шифротекст.

✅ Логи Manager = шифротекст (в debug-режиме — маскированное).

Итог: defense in depth
Угроза	mTLS	Ключи на Scanner	Оба вместе
Перехват трафика	✅	✅	✅✅
Компромисс Manager (RAM)	❌	✅	✅
Компромисс БД (диск)	❌	✅	✅
Утечка бэкапа	❌	✅	✅
Компромисс одного Scanner	❌	⚠️ только этот	⚠️
Core dump Manager	❌	✅	✅
Debug-логи Manager	❌	✅	✅
mTLS — необходимый, но недостаточный слой. Для защиты данных в состоянии покоя нужны ключи на Scanner'е.

Комплаенс
Регуляторы (152-ФЗ, GDPR, PCI DSS) требуют:

Шифрование PII «на всём пути» — не только при передаче.

Минимизация доступа к plaintext.

Доказательство, что plaintext не хранится в открытом виде.

Модель B соответствует этим требованиям:

Единственный путь к plaintext — reveal (Auditor+, с аудитом).

Manager никогда не имеет plaintext постоянно.

Ограничение v3.0.0: единый ключ
v3.0.0: один FINDINGS_ENCRYPTION_KEY на всю инсталляцию.

Риск: компромисс одного Scanner = компромисс всех находок всех сканеров. mTLS не помогает (ключ уже на хосте сканера).

Митигация v3.0.0:

Ограниченный доступ к хостам сканеров.

Регулярная ротация ключа (§3.8).

Мониторинг аномалий (v3.1.0+).

v3.1.0+ (BACKLOG-068): планируется per-scanner key + mapping scanner_id → key_id в Manager. Тогда компромисс одного Scanner = только его находки.

3.3 ENV-переменные
Переменная	Обязательна	Формат	Пример
FINDINGS_ENCRYPTION_KEY	✅ Manager + Scanner	base64, 32 байта (AES-256)	q7Zx...== (44 символа)
FINDINGS_HMAC_KEY	✅ Manager + Scanner	base64, ≥32 байта	pLm3...==
FINDINGS_KEY_ID	⚠️ Рекомендуется	Строка	key-2026-09
DCAP_ALLOW_LEGACY_SCANNER	❌ Dev-only	true/false	false (в prod)
Правила:

Значения FINDINGS_ENCRYPTION_KEY, FINDINGS_HMAC_KEY, FINDINGS_KEY_ID должны БЫТЬ ИДЕНТИЧНЫ на Manager и всех сканерах.

FINDINGS_KEY_ID — не секрет, публичен, помогает сопоставить находку с ключом.

DCAP_ALLOW_LEGACY_SCANNER=true — только для dev. В prod — запрещено (сканер не стартует без ключей).

3.4 Первичная генерация
На Manager-хосте (в корне репозитория):

bash
python scripts/generate_findings_keys.py
Создаёт 3 файла в secrets/:

Файл	Содержимое	Использование
findings_encryption_key	base64 (44 символа)	→ env FINDINGS_ENCRYPTION_KEY
findings_hmac_key	base64 (44+ символов)	→ env FINDINGS_HMAC_KEY
findings_key_id	Строка, напр. key-2026-09	→ env FINDINGS_KEY_ID
Правила:

Генерируется только на Manager-хосте (не на сканере).

Не коммитится в git (secrets/ в .gitignore).

Резервная копия — в защищённое хранилище (Vault / offline).

Категорически нельзя передавать ключи через email/chat.

3.5 Manager: передача ключей через ENV
Вариант A — docker-compose.yml (prod, рекомендуется)
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
FINDINGS_ENCRYPTION_KEY=q7Zx...==
FINDINGS_HMAC_KEY=pLm3...==
FINDINGS_KEY_ID=key-2026-09
Запуск:

bash
docker compose up -d manager
Вариант B — systemd unit (Manager вне Docker)
/etc/systemd/system/dcap-manager.service:

ini
[Service]
EnvironmentFile=/etc/dcap/manager.env
ExecStart=/usr/bin/python /opt/dcap/run_manager.py
/etc/dcap/manager.env (chmod 600, owner root):

ini
FINDINGS_ENCRYPTION_KEY=q7Zx...==
FINDINGS_HMAC_KEY=pLm3...==
FINDINGS_KEY_ID=key-2026-09
Вариант C — Windows (Manager в службе)
powershell
[Environment]::SetEnvironmentVariable("FINDINGS_ENCRYPTION_KEY", "q7Zx...==", "Machine")
[Environment]::SetEnvironmentVariable("FINDINGS_HMAC_KEY", "pLm3...==", "Machine")
[Environment]::SetEnvironmentVariable("FINDINGS_KEY_ID", "key-2026-09", "Machine")
Restart-Service dcap-manager
Проверка Manager
bash
docker exec dcap-manager python -c "
from manager.src.core.encryption import get_encryption
e = get_encryption()
print('key_id:', e.key_id)
print('key len:', len(e.aes._key))
"
Ожидаем: key_id: key-2026-09, key len: 32.

3.6 Scanner: передача ключей через ENV (N сканеров)
⚠️ Ключи ИДЕНТИЧНЫ ключам Manager. Иначе Manager не расшифрует match_text.

Шаг 1 — Получить значения на Manager-хосте
bash
cat secrets/findings_encryption_key    # → base64
cat secrets/findings_hmac_key          # → base64
cat secrets/findings_key_id            # → строка
Передача — в защищённый канал (SSH, scp, Ansible Vault). НЕ через email/chat.

Шаг 2 — Передать на каждый сканер
Вариант A — Linux, systemd unit (рекомендуется)
/etc/systemd/system/dcap-scanner.service:

ini
[Unit]
Description=DCAP Scanner
After=network.target

[Service]
Type=simple
User=dcap
WorkingDirectory=/opt/dcap
EnvironmentFile=/etc/dcap/scanner.env
ExecStart=/usr/bin/python -X utf8 /opt/dcap/run_scanner.py /opt/dcap/scanner/config/scanner_config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
/etc/dcap/scanner.env (chmod 600, owner dcap):

ini
FINDINGS_ENCRYPTION_KEY=q7Zx...==
FINDINGS_HMAC_KEY=pLm3...==
FINDINGS_KEY_ID=key-2026-09
MANAGER_URL=http://dcap-manager.corp:8000
LOG_LEVEL=INFO
Запуск:

bash
sudo systemctl daemon-reload
sudo systemctl enable --now dcap-scanner
Вариант B — Windows, служба (NSSM)
powershell
nssm install DCAPScanner "C:\Python311\python.exe" "-X utf8 C:\dcap\run_scanner.py C:\dcap\scanner\config\scanner_config.json"
nssm set DCAPScanner AppEnvironmentExtra `
    "FINDINGS_ENCRYPTION_KEY=q7Zx...==" `
    "FINDINGS_HMAC_KEY=pLm3...==" `
    "FINDINGS_KEY_ID=key-2026-09" `
    "MANAGER_URL=http://dcap-manager.corp:8000"
nssm start DCAPScanner
Вариант C — ручной запуск (dev)
Linux/macOS:

bash
export FINDINGS_ENCRYPTION_KEY=$(cat secrets/findings_encryption_key)
export FINDINGS_HMAC_KEY=$(cat secrets/findings_hmac_key)
export FINDINGS_KEY_ID=$(cat secrets/findings_key_id)
python -X utf8 run_scanner.py scanner/config/scanner_config.json
Windows PowerShell:

powershell
$env:FINDINGS_ENCRYPTION_KEY = (Get-Content secrets\findings_encryption_key -Raw).Trim()
$env:FINDINGS_HMAC_KEY       = (Get-Content secrets\findings_hmac_key -Raw).Trim()
$env:FINDINGS_KEY_ID         = (Get-Content secrets\findings_key_id -Raw).Trim()
python -X utf8 run_scanner.py scanner/config/scanner_config.json
Шаг 3 — Проверка на сканере
bash
python -c "
from scanner.src.encryption import get_encryption
e = get_encryption(fail_if_missing=True)
print('scanner key_id:', e.key_id)
print('key len:', len(e.aes._key))
"
Ожидаем: тот же key_id, что у Manager.

Шаг 4 — E2E проверка
Запустить скан на сканере.

В Manager — POST /api/findings/{id}/reveal (auditor).

Ожидаем: match_text расшифрован.

Если match_text = "***" или ошибка decrypt → ключи не совпадают.

3.7 Инвентаризация сканеров
Обязательно вести таблицу (Excel / Confluence / Wiki):

Scanner ID	Host	key_id	Дата выдачи	Ответственный	Примечание
scanner-01	srv-scan-01.corp	key-2026-09	2026-09-19	И. Иванов	
scanner-02	srv-scan-02.corp	key-2026-09	2026-09-19	И. Иванов	
scanner-03	win-scan-01.corp	key-2026-09	2026-09-19	П. Петров	Windows
...	...	...	...	...	...
Зачем:

Ротация — знать, кому обновлять.

Инцидент — знать, у кого старый ключ.

Аудит — доказательство контроля.

Где взять Scanner ID: GET /api/scanners (WebUI-эндпоинт) → id + name.

3.8 Ротация ключей
Периодичность: 90 дней (совпадает с сертификатами) или при компрометации.

Модель: ENV содержит только текущий ключ. Ротация — с downtime (перешифровка + обновление ENV).

Почему без *_OLD: ключи привязаны к key_id в БД; при ротации все старые находки перешифровываются новым ключом. Хранить старый ключ в ENV не нужно (и вредно при компрометации).

Пошаговая процедура
Шаг 1 — Остановить сканеры:

bash
# На всех сканерах:
sudo systemctl stop dcap-scanner
Шаг 2 — Остановить Manager:

bash
docker compose stop manager
Шаг 3 — Сгенерировать новый ключ:

bash
python scripts/generate_findings_keys.py --key-id key-2026-12 --output secrets/new/
Шаг 4 — Перешифровать все находки:

bash
python scripts/reencrypt_findings.py \
    --old-key-file secrets/findings_encryption_key \
    --old-hmac-file secrets/findings_hmac_key \
    --new-key-file secrets/new/findings_encryption_key \
    --new-hmac-file secrets/new/findings_hmac_key \
    --new-key-id key-2026-12
Скрипт:

Читает каждую находку, расшифровывает старым ключом.

Шифрует новым ключом.

Обновляет findings.encryption_key_id = "key-2026-12".

Батчами по 500, транзакционно, с прогресс-баром.

Шаг 5 — Обновить ENV Manager:

ini
# В .env:
FINDINGS_ENCRYPTION_KEY=<new>
FINDINGS_HMAC_KEY=<new>
FINDINGS_KEY_ID=key-2026-12
Шаг 6 — Запустить Manager:

bash
docker compose up -d manager
Шаг 7 — Обновить ENV всех сканеров:

bash
# На каждом:
sudo sed -i 's/^FINDINGS_ENCRYPTION_KEY=.*/FINDINGS_ENCRYPTION_KEY=<new>/' /etc/dcap/scanner.env
sudo sed -i 's/^FINDINGS_HMAC_KEY=.*/FINDINGS_HMAC_KEY=<new>/' /etc/dcap/scanner.env
sudo sed -i 's/^FINDINGS_KEY_ID=.*/FINDINGS_KEY_ID=key-2026-12/' /etc/dcap/scanner.env
sudo systemctl start dcap-scanner
Шаг 8 — Проверка:

bash
docker exec dcap-manager python -c "
from manager.src.core.encryption import get_encryption
print('key_id:', get_encryption().key_id)
"
# → key-2026-12

docker exec dcap-postgres psql -U dcap -d dcap -c "
SELECT encryption_key_id, COUNT(*) FROM findings GROUP BY encryption_key_id;
"
# → все key-2026-12
Шаг 9 — Обновить инвентаризацию.

Шаг 10 — Удалить старый ключ (из offline-хранилища — когда уверены, что перешифровка прошла).

Окно downtime
Оценка:

100k находок ≈ 5-10 минут (в зависимости от CPU/IO).

Планировать maintenance window (например, ночью).

В v3.1.0+ планируется:

Multi-key режим (без downtime).

Фоновая перешифровка (Celery task).

3.9 Компрометация ключа
Сценарий: ключ утёк (уволен админ, взлом сканера, утечка docker inspect).

Немедленные действия
Ротация (§3.8) — срочно, без планового окна.

Аудит:

Кто имел доступ к ENV / .env / docker inspect.

Какие reveal были за последние N дней (audit_logs → finding_revealed).

Какие сканеры скомпрометированы.

Уведомление security-офицеру.

Инцидент-репорт.

Оценка ущерба
Утечка FINDINGS_ENCRYPTION_KEY → все зашифрованные находки этой инсталляции скомпрометированы.

Утечка FINDINGS_HMAC_KEY → возможен brute-force по fingerprint (если известен file_path).

Что НЕ делать
Не удалять старый ключ, пока все находки не перешифрованы (иначе — потеря данных).

Не передавать новый ключ по незащищённым каналам.

3.10 Troubleshooting
Симптом	Причина	Fix
Manager не расшифровывает match_text (reveal → маска/пусто)	FINDINGS_ENCRYPTION_KEY сканера ≠ Manager	Сверить base64, сверить key_id, перезапустить сканер
Сканер не стартует с ошибкой FINDINGS_ENCRYPTION_KEY not set	Fail-fast (BUG-057 fix)	Задать env
Логи сканера содержат "SCANNER IN LEGACY MODE"	DCAP_ALLOW_LEGACY_SCANNER=true (dev)	Убрать флаг в prod
После ротации новые находки не расшифровываются	Manager не знает новый ключ	Обновить ENV Manager до раздачи сканерам
docker inspect dcap-manager показывает ключ	ENV видны	Ограничить доступ к Docker-хосту
4. Маскирование и шифрование находок
Модель: гибрид — маскированное (по умолчанию) + зашифрованное (AES-256-GCM).

Что маскируется
Категория	Маска	Шифрование
phone	+7***123-45-67	✅
email	iv***@example.com	✅
api_key / aws_key	AKIA***	✅
password	***	✅
token / jwt_token	eyJ***	✅
ssh_key / github_token / slack_token	***	✅
database_url / basic_auth	***	✅
passport	12** ******	✅
snils / inn	***	✅
credit_card	**** **** **** 1234	✅
person	не маскируется	❌
Reveal (расшифровка)
Доступно: только Auditor или Admin.
Аудит: каждый reveal → запись в audit_logs (action="finding_revealed").

API:

http
POST /api/findings/{id}/reveal
Authorization: Bearer <auditor_token>
Ответ:

json
{
  "id": 1237,
  "match_text": "user1@example.com",
  "line_text": null,
  "context_before": "us***@example.com",
  "revealed_at": "2026-09-19T14:29:10.136318",
  "revealed_by": "auditor"
}
⚠️ Важно: context_before / context_after не расшифровываются — они хранятся только в masked-виде. Это by design.

5. Аутентификация и RBAC
Режимы
Режим	Описание
local	JWT + Bcrypt (разработка)
hybrid	SPNEGO → fallback JWT (тестирование)
windows_integrated	Только SPNEGO (production AD)
Роли
Роль	Права	AD группа
Admin	Полный доступ, удаление, CRUD users/roles	DCAP_Admins
Auditor	Аудит, reveal находок, FP, export	DCAP_Auditors
Scanner	Запуск сканирования	DCAP_Scanners
Viewer	Только чтение (маскированное)	все остальные
Рекомендации
Смените пароль admin/admin123 сразу после установки.

Сложные пароли (≥12 символов).

AD-интеграция в production.

Минимум Admin-пользователей.

Регулярный аудит списка пользователей (GET /api/auth/users).

JWT
TTL:

access: 24 часа

refresh: 7 дней

Cookie:

HttpOnly: True, SameSite=Lax, Path=/

Secure: True — при HTTPS (env COOKIE_SECURE=true или авто по request.url.scheme)

### 5.1 Machine-API и JWT (с v3.13.10)

Machine-эндпоинты агентов и сканера (зарегистрировать/опубликовать события) работают **без JWT** —
агенты не могут хранить пользовательские учётки. Однако с v3.13.10 (BUG-048b) middleware
Manager'а обрабатывает machine-запросы в **две стадии**:

1. Если в запросе есть валидный JWT — он **извлекается до** попадания в хендлер,
   `request.state.user` заполняется, и роль проверяется (например, `require_admin`)
   реальным пользователем, а не fallback-дефолтом.
2. Если JWT нет (или он невалидный) — запрос проходит как machine-доступ (без пользователя).

Это закрывает класс багов, когда защищённые эндпоинты, матчившиеся на machine-префикс
(например `DELETE /api/scanner/{id}`), получали 401 вместо 403/404: раньше middleware
пропускал `/api/scanner/*` публично и выходил из `dispatch` без извлечения JWT.

Практическое правило: **agent-facing** эндпоинты (`register`/`heartbeat`/`tasks`/`events`)
остаются публичными; **admin-facing** операцией на machine-префиксе (удаление сканера) —
RBAC-защищены. Отклики без JWT / с garbage-токеном на админ-операциях → 401.

```http
DELETE /api/scanner/999999          # без JWT            → 401
DELETE /api/scanner/999999          # Bearer <viewer>    → 403
DELETE /api/scanner/999999          # Bearer <admin>      → 404 (нет такого сканера)
POST   /api/scanner/heartbeat       # без JWT            → 200/400/404 (machine)
```

6. Rate-limit
RateLimitMiddleware защищает от брутфорса и DoS:

Параметр	Значение (по умолчанию)
Лимит	300 запросов/мин на IP
Исключение	/api/health
Хранилище	Redis (in-memory fallback)
Ответ	429 Too Many Requests
Настройка (redis.rate_limit в config.json):

json
{
    "redis": {
        "rate_limit": {
            "max_requests": 300,
            "window_seconds": 60
        }
    }
}
ENV: RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS

7. Хранение секретов
Правила:

Никогда не храните секреты в коде.

Production: ENV (Docker Compose / systemd / Kubernetes Secrets).

Dev: .env (не коммитить!).

Регулярная ротация (90 дней).

Секреты проекта:

Секрет	Назначение	ENV
JWT	Подпись JWT	JWT_SECRET_KEY
DB	Пароль PostgreSQL	POSTGRES_PASSWORD / DATABASE_URL
AD	Пароль AD-сервиса	AD_SERVICE_PASSWORD
Findings: encryption	AES-256-GCM	FINDINGS_ENCRYPTION_KEY
Findings: HMAC	HMAC-SHA256	FINDINGS_HMAC_KEY
Findings: key ID	Ротация	FINDINGS_KEY_ID
Redis	Пароль	REDIS_PASSWORD
.gitignore — обязательные записи:

text
secrets/
.env
*.key
*.crt
8. Аудит и логирование
Что логируется:

Вход/выход пользователей (auth_login, auth_logout)

Reveal находок (finding_revealed)

Изменения статусов находок (finding_status_changed)

Запуск сканирований (scan_started)

Изменения пользователей/ролей (user_created, role_changed)

Ошибки аутентификации (auth_failed)

Хранение:

audit_logs — партиционирована по месяцам

audit_logs_archive — TTL 90 дней, архив 365 дней

Рекомендации:

Не логируйте секреты (пароли, токены).

Маскируйте PII в логах.

Ротация логов (уже реализована в агентах).

Отправка в SIEM (v4.0.0).

9. Инцидент: что делать
При компрометации секретов
Остановить затронутые компоненты.

Отозвать сертификаты (CRL).

Сгенерировать новые секреты:

bash
python scripts/generate_certs.py
python scripts/generate_findings_keys.py
Перезапустить компоненты.

Проверить логи:

bash
grep "finding_revealed" audit_logs.log
grep "auth_failed" audit_logs.log
Уведомить пользователей (если PII скомпрометированы).

Задокументировать инцидент.

При компрометации ключа Findings
См. §3.9 — ротация срочно + аудит + уведомление.

10. Чеклист production
Перед вводом в production:

Аутентификация и доступ:

□ Пароль admin сменён (≥12 символов)
□ AUTH_MODE установлен корректно
□ JWT_SECRET_KEY — уникальный, ≥32 байт
□ AD-интеграция (если production)
□ Маппинг AD-групп на роли (DCAP_Admins и т.д.)
□ Минимум Admin-пользователей
mTLS:

□ MTLS_ENABLED=true, MTLS_STRICT=true
□ Сертификаты сгенерированы (generate_certs.py)
□ CRL настроен
Ключи Findings (ENV):

□ Ключи сгенерированы один раз на Manager-хосте
□ Manager имеет FINDINGS_* ENV
□ Все сканеры имеют идентичные FINDINGS_* ENV
□ key_id совпадает на Manager и всех сканерах
□ Fail-fast включён (DCAP_ALLOW_LEGACY_SCANNER=false)
□ Ведётся инвентаризация сканеров (Scanner ID → key_id)
□ Резервная копия ключей — отдельно от БД
□ Доступ к ENV ограничен (Docker-хост, systemd-файлы)
□ Ротация запланирована (90 дней)
Cookie:

□ HttpOnly: True (проверено)
□ SameSite=Lax (проверено)
□ Secure: True при HTTPS
Сеть:

□ Все компоненты — в изолированной сети
□ Firewall: открыты только необходимые порты
□ VPN для удалённого доступа
□ HTTPS для WebUI (reverse proxy)
База данных:

□ Отдельный пользователь (не postgres)
□ Пароль ≥20 символов
□ TLS включён (sslmode=require)
□ Слушает только внутреннюю сеть
□ Backup (pg_dump + cron)
Rate-limit:

□ Настроен (max_requests=300, window_seconds=60)
Мониторинг:

□ Prometheus собирает метрики
□ Grafana дашборды
□ Alertmanager + алерты
□ Логи ротация
□ Метрики /metrics защищены (BACKLOG-044)
Аудит:

□ audit_logs пишутся
□ Reveal логируется
□ Партиционирование работает
□ Архивация настроена
📚 См. также
SECURITY.md — политика безопасности

docs/security_checklist.md — чеклист production

docs/deployment.md — развёртывание

ARCHITECTURE.md — архитектура

04-authentication.md — аутентификация

06-scanner.md — сканер

10-troubleshooting.md — troubleshooting

Последнее обновление: 19.09.2026
Версия: v3.13.8