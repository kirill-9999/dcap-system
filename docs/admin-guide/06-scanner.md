# 06. Сканер

> **Руководство администратора DCAP.**
> Раздел «Сканер»: установка, настройка, ENV, ключи Findings, FP-фильтр.

**Обновлено:** 20.09.2026
**Версия:** v3.13.10

---

## 📖 Содержание

1. [Обзор](#1-обзор)
2. [Установка](#2-установка)
3. [Конфигурация](#3-конфигурация)
4. [ENV-переменные](#4-env-переменные)
5. [Ключи Findings (обязательно)](#5-ключи-findings-обязательно)
6. [Запуск](#6-запуск)
7. [Интеграция с Manager](#7-интеграция-с-manager)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Обзор

Scanner — тяжёлый агент сканирования файлов (Tesseract, spaCy, Presidio).

**Работает на хосте, не в Docker.** Причина: задания приходят с путями хоста
(`E:\...`, `/mnt/...`), а контейнер видит только заранее смонтированные тома.

**Ключевые функции:**
- Обход ФС, классификация PII / credentials / code.
- **Шифрование находок на стороне сканирующего хоста** (AES-256-GCM).
- **Маскирование** перед отправкой.
- **FP-фильтр** — проверка fingerprints до отправки.
- **Offline-буфер** — при недоступности Manager.

---

## 2. Установка

### Требования

- Python 3.11+
- Tesseract OCR
- spaCy модели (`ru_core_news_sm`, `en_core_web_sm`)
- Presidio
- RAM ≥ 4 GB, CPU ≥ 2

### Установка

```bash
cd scanner
python -m pip install -r requirements.txt
python -m spacy download ru_core_news_sm en_core_web_sm
Windows: Tesseract — отдельно, инструкция.

3. Конфигурация
Файл: scanner/config/scanner_config.json

Основные параметры:

json
{
  "scanner": {
    "manager_url": "http://localhost:8000",
    "heartbeat_interval": 30,
    "max_file_size_mb": 50,
    "extensions": ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
    "recursive": true
  }
}
Override через ENV:

MANAGER_URL — URL Manager.

LOG_LEVEL — уровень логирования.

4. ENV-переменные
Переменная	Обязательна	Назначение
FINDINGS_ENCRYPTION_KEY	✅	AES-256-GCM ключ (base64, 32 байта)
FINDINGS_HMAC_KEY	✅	HMAC-SHA256 ключ (base64, ≥32 байта)
FINDINGS_KEY_ID	⚠️ Рекомендуется	ID ключа (напр. key-2026-09)
MANAGER_URL	❌	URL Manager (override config)
LOG_LEVEL	❌	Уровень логов (DEBUG/INFO/WARNING)
DCAP_ALLOW_LEGACY_SCANNER	❌	Только для dev — разрешает запуск без ключей
⚠️ FINDINGS_* должны быть ИДЕНТИЧНЫ ключам Manager. Иначе Manager не расшифрует match_text.

5. Ключи Findings (обязательно)
С v3.13.9 (после фикса BUG-057) Scanner НЕ СТАРТУЕТ без ключей.

Почему: без ключей Scanner отправляет PII в открытом виде в Manager — нарушение модели безопасности (см. 05-security.md §3.2).

Получить ключи у администратора Manager
Значения — из secrets/ на Manager-хосте:

secrets/findings_encryption_key → FINDINGS_ENCRYPTION_KEY

secrets/findings_hmac_key → FINDINGS_HMAC_KEY

secrets/findings_key_id → FINDINGS_KEY_ID

Передача — только через защищённый канал (SSH, Ansible Vault).

Передача через ENV
Linux (systemd)
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
FINDINGS_ENCRYPTION_KEY=<base64>
FINDINGS_HMAC_KEY=<base64>
FINDINGS_KEY_ID=key-2026-09
MANAGER_URL=http://dcap-manager.corp:8000
LOG_LEVEL=INFO
Запуск:

bash
sudo systemctl daemon-reload
sudo systemctl enable --now dcap-scanner
Windows (NSSM)
powershell
nssm install DCAPScanner "C:\Python311\python.exe" "-X utf8 C:\dcap\run_scanner.py C:\dcap\scanner\config\scanner_config.json"
nssm set DCAPScanner AppEnvironmentExtra `
    "FINDINGS_ENCRYPTION_KEY=<base64>" `
    "FINDINGS_HMAC_KEY=<base64>" `
    "FINDINGS_KEY_ID=key-2026-09" `
    "MANAGER_URL=http://dcap-manager.corp:8000"
nssm start DCAPScanner
Windows (ручной запуск, dev)
powershell
$env:FINDINGS_ENCRYPTION_KEY = (Get-Content secrets\findings_encryption_key -Raw).Trim()
$env:FINDINGS_HMAC_KEY       = (Get-Content secrets\findings_hmac_key -Raw).Trim()
$env:FINDINGS_KEY_ID         = (Get-Content secrets\findings_key_id -Raw).Trim()
python -X utf8 run_scanner.py scanner/config/scanner_config.json
Проверка ключей
bash
python -c "
from scanner.src.encryption import get_encryption
e = get_encryption(fail_if_missing=True)
print('key_id:', e.key_id)
print('key len:', len(e.aes._key))
"
Ожидаем: key_id совпадает с Manager, key len: 32.

Fail-fast и legacy-режим
По умолчанию (DCAP_ALLOW_LEGACY_SCANNER не задан или false):

text
RuntimeError: FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY not set.
Scanner cannot start without encryption keys.
Legacy-режим (только dev):

bash
export DCAP_ALLOW_LEGACY_SCANNER=true   # ⚠️ PLAINTEXT УХОДИТ В MANAGER!
В production — категорически запрещено.

Полная процедура ключей
См. 05-security.md §3 — включая:

Инвентаризация сканеров (§3.7).

Ротация (§3.8).

Компрометация (§3.9).

Troubleshooting (§3.10).

6. Запуск
Порядок: сначала Manager (docker compose up -d), потом Scanner.

bash
# Linux
sudo systemctl start dcap-scanner

# Windows (служба)
Start-Service DCAPScanner

# Ручной запуск (dev)
python -X utf8 run_scanner.py scanner/config/scanner_config.json
7. Интеграция с Manager
Процесс:

Scanner регистрируется в Manager (POST /api/scanner/register).

Каждые 30 сек — heartbeat (POST /api/scanner/heartbeat).

Забирает задание из очереди (GET /api/scanner/tasks/pending).

Сканирует путь, шифрует находки на хосте.

Отправляет результаты (POST /api/scanner/tasks/{id}/results).

При недоступности Manager — сохраняет в scanner/data/offline/, досылает позже.

FP-фильтр: перед отправкой Scanner батчем проверяет fingerprints (POST /api/findings/check-fingerprints) — FP-находки не пересоздаются.

Батчинг: находки отправляются батчами по 500 (BUG-035 fix).

### Модель доступа к scanner-API (с v3.13.10)

Сканер и его machine-API работают **без JWT** (агент не хранит пользовательские учётки), но
middleware Manager'а теперь **всегда пытается извлечь JWT** из запроса на `/api/scanner/*`,
прежде чем пропустить его (BUG-048b). Итоговая модель доступа:

| Эндпоинт | Без JWT | С JWT (admin) | С JWT (viewer) |
|----------|---------|---------------|----------------|
| `POST /api/scanner/register` | 200 (machine) | 200 | 200 |
| `POST /api/scanner/heartbeat` | 200/400/404 (machine) | 200/400/404 | 200/400/404 |
| `GET /api/scanner` (список) | 200 (machine) | 200 | 200 |
| `GET /api/scanner/{id}`, `/ping` | 200/404 (machine) | 200/404 | 200/404 |
| `DELETE /api/scanner/{id}` | 401 | 200/404 (require_admin) | **403** |

Некорректный JWT (garbage) на любом записи → 401. `DELETE /api/scanner/{id}` — единственный
scanner-эндпоинт с ролью: только `admin`; viewer получает 403, не-аутентифицированный — 401.
Удаление сканера из WebUI/API идёт именно через этот эндпоинт.

8. Troubleshooting
Симптом	Причина	Fix
FINDINGS_ENCRYPTION_KEY not set	Ключи не заданы	Задать ENV (§5)
SCANNER IN LEGACY MODE в логах	DCAP_ALLOW_LEGACY_SCANNER=true	Убрать флаг в prod
Manager не расшифровывает match_text	Ключ Scanner ≠ Manager	Сверить base64, сверить key_id
Scanner не регистрируется	Manager недоступен	curl http://localhost:8000/api/health
Heartbeat timeout	STALE_THRESHOLD_MINUTES < 2	Проверить heartbeat_interval
Задание «зависло» в running	Scanner упал	Перезапустить Scanner; задача станет failed через 2 мин
Логи:

bash
tail -f logs/scanner.log
Метрики: http://localhost:9101/metrics (Prometheus).

📚 См. также
05-security.md — безопасность (ключи Findings, ENV)

docs/deployment.md — развёртывание

docs/monitoring.md — мониторинг

ARCHITECTURE.md — архитектура Scanner

Последнее обновление: 19.09.2026
Версия: v3.13.8