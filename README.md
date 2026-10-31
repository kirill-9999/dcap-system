# DCAP — Data Classification & Audit Platform

[![Version](https://img.shields.io/badge/version-3.0.0-blue)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Docker](https://img.shields.io/badge/docker-compose-blue)](docker-compose.yml)
[![Tests](https://img.shields.io/badge/tests-544%20passed-brightgreen)](tests/)

> **DCAP** — платформа аудита данных на предмет конфиденциальной информации (PII, credentials,
> code secrets) и разрешений на файловых хранилищах и S3/MinIO. Enterprise-ready: RBAC, mTLS,
> соответствие регуляторам (152-ФЗ / GDPR / PCI DSS), retention, Prometheus/Grafana.

## ✨ Возможности

- **Сканер** — PII (ФИО, email, телефоны, паспорта, СНИЛС, ИНН, банковские карты), credentials
  (API-ключи, пароли, SSH, токены), code secrets. OCR для изображений/PDF.
- **Аудит разрешений** — файловые хранилища (Windows/Linux), S3/MinIO (streaming, multipart).
- **Шифрование** — AES-256-GCM; расшифровка только Auditor, с аудитом.
  HMAC-SHA256 fingerprint (защита от brute-force). Маскирование контекстов
  на стороне Manager (BUG-117).
- **Дашборд** — фильтры по findings, статистика, экспорт; аудит Windows/Linux/S3.
- **RBAC** — admin / auditor / scanner / viewer; AD-интеграция; mTLS relaxed/strict.
- **Retention** — политики TTL, очистка, архивирование, Celery Beat.
- **Мониторинг** — Prometheus /metrics, Grafana (2 дашборда, 4 алерта).
- **WebUI** — Dovetail dark, RBAC-гейты, responsive.

## ⚙️ Требования

- Docker + Docker Compose v2 (`--wait`)
- Python 3.10+ (для сканера на хосте)
- 16 ГБ RAM (сканер: `max_workers=2`; 32 ГБ → 4; 128 ГБ → 8)

### 1. Клонировать и настроить

```bash
git clone https://github.com/kirill-9999/dcap-system.git
cd dcap-system
cp .env.example .env
# Заполнить: FINDINGS_ENCRYPTION_KEY, FINDINGS_HMAC_KEY (base64, 32 bytes),
#           S3_ACCESS_KEY, S3_SECRET_KEY (если S3), POSTGRES_PASSWORD
```
Генерация ключей findings:

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
# повторить дважды — для FINDINGS_ENCRYPTION_KEY и FINDINGS_HMAC_KEY
```
2. Поднять стек
```bash
docker compose up -d --build --wait
# Manager :8000, WebUI :8001, Grafana :3000, Prometheus :9090
```
3. Первый вход
WebUI: http://localhost:8001

Логин: admin / admin123 — сменить при первом запуске (Settings → Password).

4. Запустить сканер (на хосте)
```bash
export FINDINGS_ENCRYPTION_KEY="<base64>"
export FINDINGS_HMAC_KEY="<base64>"
export MANAGER_URL="http://127.0.0.1:8000"
python run_scanner.py scanner/config/scanner_config.json
```
⚠️ В production сканер без ключей не стартует (fail-fast).
DCAP_ALLOW_LEGACY_SCANNER=true — только dev.

5. Создать ресурс и запустить скан
WebUI → Resources → New (filesystem path или s3://bucket/prefix).

Или API: POST /api/resources?path=...&type=filesystem → POST /api/resources/{id}/scan.

🏗️ Архитектура
docs/architecture-overview.png

Общая схема взаимодействия компонентов DCAP (Manager, Scanner, агенты, хранилища).

Подробное описание (модели данных, API, SIEM) — в ARCHITECTURE.md и docs/architecture.mermaid.

🧪 Тестирование
```bash
# Unit (544 passed)
pytest tests/unit -q
# E2E (тестовый стенд :18000/:18001)
scripts/test-up.sh
scripts/run-tests.sh e2e
# Security (53.5)
scripts/security_scan.ps1   # Bandit, Semgrep, Gitleaks, pip-audit, Trivy, ZAP
```
Подробнее — docs/testing.md.
📚 Документация
ARCHITECTURE.md — архитектура, модели, API, SIEM.

ROADMAP.md — план и бэклог.

CHANGELOG.md — история изменений.

docs/admin-guide/ — 04-authentication, 05-security, 06-scanner, 10-troubleshooting.

docs/DESIGN.md — WebUI style reference (Dovetail).

SECURITY.md — политика безопасности.

docs/security_checklist.md.

🔒 Безопасность
Findings: AES-256-GCM + HMAC-SHA256 fingerprint; маскирование по умолчанию.
Расшифровка — только Auditor, с аудитом (finding_reveal).
mTLS relaxed/strict + CRL; machine-эндпоинты проверяют сертификат в strict.
Аудит: findings, auth, роли, retention — в audit_logs (партиционирование).
53.5: Bandit 0 HIGH, Semgrep 0, Gitleaks 0, pip-audit 0, Trivy 0 CRITICAL,
ZAP 0 HIGH, CapDrop=[ALL], non-root.
⚠️ /metrics публичный (BACKLOG-044) — закрыть в production.
⚠️ admin/admin123 — сменить при первом запуске.
Найденные уязвимости — см. SECURITY.md.
🤝 Contributing
Fork → branch → PR.

Тесты: pytest tests/unit -q + scripts/run-tests.sh e2e (при предусловиях).

Стиль: PEP 8, type hints, logger вместо print.

Security-правки — с # nosemgrep + комментарием (если осознанно).

CI — GitHub Actions (BACKLOG-046, день 55).

📄 Лицензия
Apache License 2.0. Сторонние компоненты — см. NOTICE.md.

🙏 Acknowledgements
Inter (rsms/inter) — SIL OFL 1.1

JetBrains Mono — SIL OFL 1.1

Bootstrap, Chart.js, Font Awesome — MIT / BSD (см. NOTICE.md)

📬 Контакты
Issues: https://github.com/kirill-9999/dcap-system/issues

Security: см. SECURITY.md
