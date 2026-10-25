# 📋 ТЗ v3.14.16 — Security Checks (53.5)

**Файл:** `prompts/tz/day_53_5_security_checks.md`
**Дата:** 25.10.2026
**Версия:** v3.14.15 → v3.14.16
**Приоритет:** 🔴 Блокер v3.0.0 (продукт для ИБ — обязательная проверка безопасности)
**Исполнитель:** Разработчик (ИИ-агент Open Code)
**Длительность:** 0.5–1 день

---

## ⚠️ ГЛАВНОЕ ТРЕБОВАНИЕ

> **Функциональность НЕ сокращается.** Любая находка `HIGH`/`CRITICAL` — либо фикс, либо задокументированное принятие риска (с обоснованием и планом на v3.1.0). Находки `MEDIUM` — либо фикс, либо запись в `SECURITY.md` с оценкой риска.
>
> **DAST — на тестовом стенде** (`:18000/:18001`), не на основном (`:8000/:8001`) — DAST может изменить данные.

**Перед началом:** пересобрать `webui_test` с актуальной версией (тест-стенд отстаёт).

---

## 1. SAST — статический анализ кода

### 1.1. Bandit (Python)

**Установка:** `pip install bandit`

**Команда:**
```powershell
bandit -r manager/src scanner/src webui/ -f json -o reports/bandit_report.json
Конфигурация (.bandit):

ini
[bandit]
skips = B101,B601
confidence = HIGH
exclude = tests,test,fixtures,__pycache__
Что ищем: хардкод паролей/токенов (B105), eval/exec (B307), subprocess с shell=True (B602), небезопасный yaml.load (B506), слабая криптография (B303).

Критерий: HIGH severity + HIGH confidence — 0 находок. MEDIUM — триаж (фикс или обоснование).

1.2. Semgrep (Python + JS)
Установка: pip install semgrep

Команда:

powershell
semgrep --config=p/owasp-top-ten --config=p/python --config=p/javascript --json -o reports/semgrep_report.json manager/ scanner/ webui/
Что ищем: SQL-инъекции (A05:2025), XSS (A05:2025), broken access control (A01:2025), небезопасная десериализация.

Критерий: ERROR severity — 0 находок. WARNING — триаж.

1.3. Secret Scanning (Gitleaks)
Установка: Docker ghcr.io/gitleaks/gitleaks:latest

Команда (рабочее дерево + история):

powershell
docker run -v ${PWD}:/path ghcr.io/gitleaks/gitleaks:latest detect `
  --source=/path `
  --report-format=json `
  --report-path=/path/reports/gitleaks_report.json `
  --verbose
Конфигурация (.gitleaks.toml):

toml
[extend]
useDefault = true

[allowlist]
paths = [
  '''.*/test/.*''',
  '''.*/examples/.*''',
  '''.*\.md''',
]
regexes = [
  '''admin123''',  # init_db.py — by design, задокументировано
]
Критерий: 0 валидных секретов в рабочем дереве и истории.

1.4. Dogfooding: DCAP-сканер на собственном репозитории (опционально, 30 мин)
Цель: проверить, что DCAP находит секреты в реальном коде.

Шаги:

Запустить DCAP на E:\projects\dcap-system (FS, type=filesystem). Исключить: .git/, node_modules/, .venv/, __pycache__/, data/, logs/.

Сравнить с gitleaks_report.json.

Критерий: DCAP находит все валидные секреты, что и gitleaks (нет gap). FP ≤ 20%. Маскирование работает (FINDINGS_ENCRYPTION_KEY → eyJh***, не целиком).

2. SCA — анализ зависимостей
2.1. pip-audit (Python)
Установка: pip install pip-audit

Команда:

powershell
pip-audit -r requirements.txt --desc -f json -o reports/pip_audit_manager.json
pip-audit -r scanner/requirements.txt --desc -f json -o reports/pip_audit_scanner.json
Критерий: 0 HIGH/CRITICAL CVE с доступным фиксом. Если фикс недоступен — запись в SECURITY.md с оценкой reachable/unreachable.

2.2. Trivy (образы + файловая система)
Установка: Docker aquasec/trivy

Команда (образы):

powershell
docker run aquasec/trivy image dcap/manager:3.14.16 --severity HIGH,CRITICAL
docker run aquasec/trivy image dcap/webui:3.14.16 --severity HIGH,CRITICAL
Команда (файловая система):

powershell
docker run -v ${PWD}:/path aquasec/trivy fs `
  --scanners vuln,secret,misconfig `
  /path
Критерий: 0 CRITICAL CVE в базовых образах с доступным фиксом. HIGH — триаж.

3. DAST — динамический анализ (тест-стенд :18000/:18001)
3.1. OWASP ZAP Baseline (WebUI)
Команда:

powershell
docker run -v ${PWD}/reports:/zap/wrk/:rw -t zaproxy/zap-stable `
  zap-baseline.py `
  -t http://localhost:18001 `
  -r /zap/wrk/zap_baseline_webui.html `
  -J /zap/wrk/zap_baseline_webui.json
Что ищем: отсутствие security-заголовков (CSP, X-Frame-Options), information disclosure, небезопасные cookies.

Критерий: 0 HIGH. MEDIUM — триаж (например, CSP уже есть в webui/main.py — проверить, что ZAP видит его).

3.2. OWASP ZAP API Scan (Manager OpenAPI)
Команда:

powershell
docker run -v ${PWD}/reports:/zap/wrk/:rw -t zaproxy/zap-stable `
  zap-api-scan.py `
  -t http://localhost:18000/openapi.json `
  -f openapi `
  -r /zap/wrk/zap_api_manager.html
Что ищем: SQL-инъекции в query-параметрах, broken access control (например, /api/audit/* для viewer — должен быть 403), mass assignment.

Критерий: 0 HIGH. Если ZAP найдёт 403-обход — это блокер.

3.3. Ограничения DAST (честно)
ZAP не знает про RBAC-модель DCAP — нужно вручную проверить, что viewer/scanner не видят /api/audit/* (мы это уже сделали в 53.4h).

ZAP не тестирует mTLS — strict-режим не проверить автоматически.

ZAP не тестирует шифрование findings — reveal/decrypt нужно проверить вручную (Auditor only, аудит пишется).

4. Безопасная конфигурация контейнеров
4.1. Trivy config (Dockerfile + compose)
powershell
docker run -v ${PWD}:/path aquasec/trivy config /path/docker-compose.yml
docker run -v ${PWD}:/path aquasec/trivy config /path/manager/Dockerfile
docker run -v ${PWD}:/path aquasec/trivy config /path/webui/Dockerfile
Что ищем: USER root (должен быть non-root), отсутствие read_only, cap_add без необходимости, секреты в environment.

4.2. Ручная проверка (дополнительно к Trivy)
Проверка	Команда	Критерий
User в Dockerfile	Select-String -Path manager/Dockerfile,webui/Dockerfile -Pattern "USER"	USER dcap (не root)
Секреты в environment	docker inspect dcap-manager | Select-String "KEY|SECRET|PASSWORD"	Нет открытых значений
Capabilities	docker inspect dcap-manager --format '{{.HostConfig.CapDrop}}'	[ALL] + cap_add только нужные
Read-only rootfs	docker inspect dcap-manager --format '{{.HostConfig.ReadonlyRootfs}}'	true (если возможно)
Критерий: все контейнеры non-root (кроме сканера на хосте — by design). Секреты не в environment (или задокументировано как ограничение с планом на v3.1.0 — Docker Secrets / Vault).

5. Сводная таблица результатов
#	Проверка	Инструмент	Критерий	Результат	Действие
1.1	SAST Python	Bandit	0 HIGH+HIGH	⏳	
1.2	SAST Python+JS	Semgrep	0 ERROR	⏳	
1.3	Secret Scanning	Gitleaks	0 валидных	⏳	
1.4	Dogfooding DCAP	DCAP Scanner	gap=0, FP≤20%	⏳	
2.1	SCA Python	pip-audit	0 HIGH/CRITICAL	⏳	
2.2	SCA образы	Trivy	0 CRITICAL	⏳	
3.1	DAST WebUI	ZAP Baseline	0 HIGH	⏳	
3.2	DAST API	ZAP API Scan	0 HIGH	⏳	
4.1	Container config	Trivy config	0 HIGH	⏳	
4.2	Ручная проверка	Docker inspect	non-root, no secrets	⏳	
6. Definition of Done
□ Все 10 проверок выполнены, результаты в таблице.
□ HIGH/CRITICAL — 0 (или задокументированы с планом).
□ MEDIUM — триаж (фикс или запись в SECURITY.md).
□ Отчёт prompts/reports/day_53_5_security_report.md с таблицей и выводами.
□ SECURITY.md обновлён (известные ограничения, принятые риски).
□ Артефакты в reports/ (JSON/HTML от каждого инструмента).
□ Если найдены новые баги — заведены (BUG-294+, BACKLOG-340+) и переданы в бэклог.
7. Что делать с находками
Severity	Действие
CRITICAL	Блокер v3.0.0. Фикс обязателен.
HIGH	Блокер v3.0.0. Фикс или задокументированное принятие риска (с одобрением архитектора).
MEDIUM	Фикс если < 1 часа; иначе — SECURITY.md + план на v3.1.0.
LOW	SECURITY.md / бэклог.
8. Скрипт автоматизации
Файл: scripts/security_scan.ps1 (см. отдельно). Запуск:

powershell
.\scripts\security_scan.ps1 -SkipDast -SkipContainer
Собирает все артефакты, генерирует reports/security_summary.json + reports/security_summary.html.

9. Коммит
powershell
git add reports/ SECURITY.md prompts/reports/day_53_5_security_report.md
git commit -m "security: v3.0.0 security audit — SAST/SCA/DAST/secrets/containers

- Bandit: 0 HIGH+HIGH, N MEDIUM (триаж)
- Semgrep: 0 ERROR, N WARNING (триаж)
- Gitleaks: 0 валидных секретов (allowlist для admin123)
- pip-audit: 0 HIGH/CRITICAL (N MEDIUM задокументировано)
- Trivy image: 0 CRITICAL (N HIGH триаж)
- ZAP WebUI: 0 HIGH (N MEDIUM)
- ZAP API: 0 HIGH
- Trivy config: 0 HIGH
- Ручная проверка контейнеров: non-root ✅, secrets в env ⚠️ (v3.1.0)

Артефакты: reports/*.json, SECURITY.md"