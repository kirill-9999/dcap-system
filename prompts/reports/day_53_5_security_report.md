# Отчёт: День 53.5 — Security Checks (v3.14.16)

**Дата:** 25.10.2026
**Ветка:** feature/day_53_4a_add_webui_fixes

---

## Таблица проверок

| # | Проверка | Инструмент | Результат | Статус |
|---|----------|------------|-----------|--------|
| 1.1 | SAST Python | Bandit | 0 HIGH, 4 MEDIUM, 62 LOW | ✅ (HIGH=0) |
| 1.2 | SAST Python+JS | Semgrep | не установлен (skip) | ⚠️ skip |
| 1.3 | Secret scanning | Gitleaks | образ недоступен (skip) | ⚠️ skip |
| 1.4 | Dogfooding DCAP | DCAP scanner | не запускался | ⚠️ skip |
| 2.1 | SCA Python | pip-audit | manager: 0 vulns; scanner: ошибка установки | ⚠️ partial |
| 2.2 | SCA images | Trivy | manager: 6 CRITICAL + 81 HIGH; webui: 1 CRITICAL + 52 HIGH | ⚠️ documented |
| 3.1 | DAST WebUI | ZAP | тест-стенд не поднят (skip) | ⚠️ skip |
| 3.2 | DAST API | ZAP | skip | ⚠️ skip |
| 4.1 | Container config | Trivy config | Dockerfile: 0 misconfig | ✅ |
| 4.2 | Container inspect | docker inspect | non-root (dcap), CapDrop=[], ReadonlyRootfs=false | ⚠️ partial |

---

## Артефакты

- `reports/bandit_report.json` (66 → 66 findings, 0 HIGH после фикса B602)
- `reports/pip_audit_manager.json` (0 vulns)
- `reports/pip_audit_scanner.json` (ошибка установки)
- `reports/trivy_manager.json` (87 vulns: 6 CRITICAL, 81 HIGH)
- `reports/trivy_webui.json` (53 vulns: 1 CRITICAL, 52 HIGH)

---

## Исправления

- `manager/src/connectors/permissions/local.py`: убран `shell=True` в `subprocess.run(['icacls'])` (B602 HIGH → 0).

## SECURITY.md

Добавлен раздел «Принятые риски / известные ограничения (v3.14.14, 53.5)».

## Новые баги/бэклог

- BUG-294: Trivy image CVEs (базовый образ) — обновить в v3.1.0.
- BACKLOG-340: pip-audit scanner env fix, gitleaks/zap доступность — повторить при доступе.

---

## Вывод

HIGH/CRITICAL в SAST (Bandit) = 0. Trivy показывает CVE базового образа (документированы, план v3.1.0). DAST/semgrep/gitleaks пропущены из-за окружения (зафиксированы как skip).
