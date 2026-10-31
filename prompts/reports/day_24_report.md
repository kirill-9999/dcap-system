# Отчет: День 24 — Системная интеграция Linux-агента

**Дата:** 26.08.2026
**ТЗ:** `prompts/tz/day_24_linux_agent_service.md`
**Статус:** Выполнено

---

## Результат

Linux-агент интегрирован как управляемый сервис. Два режима установки: systemd (Linux-серверы) и crontab (WSL). Управление через start/stop/status.

---

## Созданные файлы

```
audit-agent-linux/service/
├── dcap-audit-agent.service   # systemd unit
├── install.sh                 # установка systemd-сервиса
├── uninstall.sh               # удаление systemd-сервиса
├── install_cron.sh            # установка через crontab (WSL)
└── uninstall_cron.sh          # удаление из crontab
```

## Измененные файлы

| Файл | Изменение |
|------|-----------|
| `start.sh` | + `--daemon` флаг для фонового запуска |
| `stop.sh` | + pgrep fallback если нет PID-файла |
| `status.sh` | Новый: PID + unsent буфер |
| `README.md` | Документация по сервисному режиму |

---

## Критерии приемки

| Критерий | Статус |
|----------|--------|
| systemd unit-файл создан | Да |
| Установка/удаление systemd-сервиса | Да |
| Crontab-установка (WSL) | Да |
| `start.sh --daemon` | Да |
| `stop.sh` корректно останавливает | Да |
| `status.sh` показывает статус | Да |
| README обновлен | Да |

---

## Режимы

| Режим | Сервис | Установка | Управление |
|-------|--------|-----------|------------|
| systemd | dcap-audit-agent.service | `service/install.sh` | `systemctl start/stop/status` |
| WSL | crontab @reboot | `service/install_cron.sh` | `./start.sh/stop.sh/status.sh` |

---

## systemd unit

```ini
[Service]
Type=simple
User=kirill
WorkingDirectory=/home/kirill/dcap-system/audit-agent-linux
ExecStart=.../venv/bin/python .../main.py
Restart=on-failure
RestartSec=10
```

Ключевые моменты:
- Python из venv, не системный (решает PEP 668)
- `Restart=on-failure` — автоперезапуск при сбоях
- `journalctl -u dcap-audit-agent -f` — логи в systemd journal

---

## Команда для коммита (уже выполнен)

```bash
git checkout -b feature/day_24_linux_service
git add audit-agent-linux/service/ audit-agent-linux/start.sh \
       audit-agent-linux/stop.sh audit-agent-linux/status.sh audit-agent-linux/README.md
git commit -m "feat: День 24 — системная интеграция Linux-агента (systemd + crontab)"
```
