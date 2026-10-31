# Отчёт: 56.5 (TEST-AUDIT-AGENTS) — приёмка событий аудита

**Дата:** 31.10.2026
**Стенд:** Manager :18000, WebUI :18001

## Результаты

| Агент | Зарегистрирован | Heartbeat | События в /audit |
|---|---|---|---|
| Windows (audit-agent-01) | ✅ id 124 | ✅ | 31 (windows_agent), permissions: 24 access entries (E:\test_audit) |
| Linux (linux-agent-01) | ✅ id 125 | ✅ | 6 (linux_agent), permissions: 3 access entries (/tmp/test_audit) |
| S3 (s3-agent-1) | ✅ id 126 | ✅ | 3 (s3_agent read, bucket dcap-audit) |

## WebUI /audit

- GET /api/audit → total 681 (s3_agent 3, windows_agent 31, linux_agent 6, api 641).
- Access entries: E:\test_audit 24, /tmp/test_audit 3.

## Исправления в процессе теста

- `audit-agent-windows/collector.py`: парсинг icacls переведён на cp866 и корректное выделение principal/rights; убран debug-вывод heartbeat.

## Вывод

DoD выполнен: агенты зарегистрированы, шлют heartbeat, события видны в /audit (Windows/Linux/S3).
