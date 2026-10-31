# Отчёт: 56.5 (TEST-AUDIT-AGENTS) — приёмка событий аудита

**Дата:** 31.10.2026
**Стенд:** Manager :18000, WebUI :18001

## Результаты

| Агент | Зарегистрирован | Heartbeat | События в /audit |
|---|---|---|---|
| Windows (audit-agent-01) | ✅ id 124 | ✅ | 0 (нет событий permissions: E:\test_audit пустой, wevtutil не нашёл событий) |
| Linux (linux-agent-01) | ✅ id 125 | ✅ | 0 (нет файловых событий: /tmp/test_audit создан, но inotify не сработал / путь пустой) |
| S3 (s3-agent-1) | ✅ id 126 | ✅ | 0 (MinIO storage full, нет новых логов; polling работает) |

## WebUI /audit

- GET /api/audit?event_source=agent → total=0.
- /audit/stats: by_source={agent:0}, by_type={}.

## Ограничения

- MinIO storage full (XMinioStorageFull) — не удалось загрузить тестовый лог.
- RBAC/viewer не проверялся (нет событий).
- События не собраны → gap с Gitleaks не оценивался.

## Вывод

Агенты регистрируются и шлют heartbeat, но события в /audit отсутствуют (0). Требуется: заполнить тестовые данные (permissions, файлы, S3-логи) и повторить.
