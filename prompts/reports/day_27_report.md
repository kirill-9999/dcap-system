# Отчет: День 27 — Релиз v2.1.0

**Дата:** 27.08.2026
**ТЗ:** `prompts/tz/day_27_release_v2.1.0.md`
**Статус:** Выполнено

---

## Результат

Оформление релиза v2.1.0 — документация, тестирование, тег, Release Notes.

---

## Проверка компонентов

| Компонент | Результат |
|-----------|-----------|
| WebUI статистика (`/api/stats`) | ✅ 585 findings, 10 completed tasks |
| WebUI аудит (`/api/audit`) | ✅ 688 events, filter=None |
| Audit stats (`/api/audit/stats`) | ✅ by_source: windows_agent=667, linux_agent=12 |
| Audit agents (`/api/audit/agents`) | ✅ 2 agents, 2 online |
| WebUI сканеры (`/api/scanners`) | ✅ 1 scanner (scanner-1, active) |

---

## Обновленные файлы

| Файл | Изменение |
|------|-----------|
| `project_context.md` | Версия → v2.1.0, статус → "Linux + Windows аудит", структура с audit-agent-linux, shared, API |
| `project_plan.md` | v2.1.0 → ✅, прогресс 66%, следующий шаг — v3.0.0 |
| `AGENTS.md` | Версия → v2.1.0, Linux-агент в секции структуры, shared/event_schema.py, запуск Linux |
| `README.md` | Создан: компоненты, запуск, архитектура, UnifiedEvent, версии |
| `backlog.txt` | BACKLOG-008/009/010 → ✅ (v2.1.0), дата обновлена |

---

## Созданные файлы

| Файл | Описание |
|------|----------|
| `README.md` | Документация проекта для GitHub |
| `prompts/reports/release_v2.1.0_notes.md` | Release Notes v2.1.0 |
| `prompts/reports/day_27_report.md` | Этот отчет |
| `prompts/archive/day_27_release_v2.1.0.md` | Архив ТЗ |

---

## Что включено в v2.1.0

| Компонент | Описание | Дни |
|-----------|----------|-----|
| `audit-agent-linux/` | Linux-агент (watchdog, SSH, systemd) | 23-24 |
| `shared/event_schema.py` | UnifiedEvent — единый формат | 25 |
| WebUI фильтр | По источнику (Windows/Linux) | 26 |
| WebUI управление | Удаление агентов/сканеров | 26.5 |
| Heartbeat fix | Авто-offline при >2 минут | 25 |

---

## Git

Тег `v2.1.0` создан на коммите `e4e8e26` (ветка `feature/day_25_unified_format`).

```bash
git tag -a v2.1.0 -m "v2.1.0 — Linux-агент аудита, унифицированный формат, WebUI фильтр"
```
