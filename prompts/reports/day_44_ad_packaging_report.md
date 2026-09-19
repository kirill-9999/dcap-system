# Отчёт — BUG-AD: Корректная упаковка AD-контейнера (v3.13.8)

**Дата:** 19.09.2026
**Версия:** v3.13.8
**Ветка:** `fix/docker_compose_ad_packaging`
**Коммит:** см. раздел 6
**Предыдущая версия:** v3.13.7
**Приоритет:** 🟡 важный (для тестирования AD/hybrid)

---

## 1. Проблема

### Симптом

Запуск `docker compose -f docker-compose.ad.yml up -d` ломал основной стек:

- `dcap-redis` перезапускался (сервис `redis` был продублирован в обоих compose);
- `dcap-manager`, `dcap-celery-beat`, `dcap-system-celery_worker-1` → unhealthy
  (потеря redis после рестарта);
- `dcap-s3-agent` останавливался — Docker видел его как orphan;
- Docker выводил warning про 13 orphan-контейнеров.

### Причина

Оба compose-файла (`docker-compose.yml` и `docker-compose.ad.yml`) используют один
project name (`dcap-system`, по умолчанию от имени каталога) и пересекающиеся
сервисы (`redis`). Redis в AD-compose задавал контейнер `dcap-redis` с другой
конфигурацией (без пароля/healthcheck) → при `up -d` контейнер пересоздавался,
ломая всех зависящих.

Фактическое состояние машины на момент фикса: `dcap-ad-dc` Up 9 min (запущен
старым способом), redis перезапущен 11:11, manager/worker/beat unhealthy.

---

## 2. Решение — выбран подход: **профиль `ad`** (Задача 3)

Рекомендация ТЗ: один compose, один project, нет orphan-контейнеров, нет
пересечений. Реализовано:

1. **Сервис `samba-ad-dc` перенесён в основной `docker-compose.yml`** с
   `profiles: ["ad"]` — запускается только с `--profile ad`.
2. **`docker-compose.ad.yml` переименован в `docker-compose.ad.yml.example`**;
   из старого AD-compose **убран сервис `redis`** (в основном compose он есть,
   дубликат не нужен).
3. **Network aliases** `dcap.local` / `dc1.dcap.local` для сервиса `samba-ad-dc` —
   Manager резолвит AD по DNS без extra_hosts.
4. Тома `samba_data`/`samba_logs` добавлены в основной compose.

### Запуск

```bash
# Основной стек (без AD)
docker compose up -d

# С AD-контроллером
docker compose --profile ad up -d

# Всё вместе с агентами
docker compose --profile agents --profile ad up -d
```

---

## 3. Изменения

### 3.1 `docker-compose.yml` — добавлен сервис

```yaml
  # ===== SAMBA AD DC (профиль ad, День 33 + v3.13.8) =====
  samba-ad-dc:
    image: diegogslomp/samba-ad-dc
    container_name: dcap-ad-dc
    privileged: true
    profiles:
      - ad
    environment:
      REALM: 'SAMDOM.EXAMPLE.COM'
      DOMAIN: 'SAMDOM'
      ADMIN_PASS: 'Passw0rd'
      DNS_FORWARDER: '8.8.8.8'
    hostname: DC1
    command: ["/bin/bash", "-c", "samba-domain-provision && sed -i 's/eth0@if[0-9]*/eth0/' /usr/local/samba/etc/smb.conf 2>/dev/null || true && samba -F"]
    ports:
      - "1353:53"
      - "1353:53/udp"
      - "88:88"
      - "464:464"
      - "1135:135"
      - "1139:139"
      - "389:389"
      - "1445:445"
      - "636:636"
      - "3268:3268"
      - "3269:3269"
    volumes:
      - samba_data:/var/lib/samba
      - samba_logs:/var/log/samba
    networks:
      dcap-network:
        aliases:
          - dcap.local
          - dc1.dcap.local
    <<: *default-restart
    logging: *default-logging
```

Тома:

```yaml
  samba_data:
    name: dcap-samba-data
  samba_logs:
    name: dcap-samba-logs
```

### 3.2 `docker-compose.ad.yml.example` (был `docker-compose.ad.yml`)

`git mv` + переписано: **redis удалён**, заголовок объясняет новый профильный
способ запуска, сервис `samba-ad-dc` и тома `samba_data`/`samba_logs` сохранены
как справка.

Проверка (критерий ТЗ «redis не упоминается»):

```
> Select-String -Path docker-compose.ad.yml.example -Pattern "redis"
(нет совпадений)
```

### 3.3 Документация

- **`docs/deployment.md`** — новая секция «Active Directory (Samba AD DC,
  profile `ad`)»: запуск, таблица параметров, DNS через aliases, миграция со
  старой схемы, тестовые данные.
- **`docs/admin-guide/04-authentication.md`** — создан (раздел админ-руководства):
  режимы auth, запуск AD через профиль, DNS `dcap.local`, подключение Manager
  к AD (`ad`-секция config + env), RBAC-страницы, проверка и troubleshooting.
- **`ARCHITECTURE.md`** — в дереве проекта `docker-compose.ad.yml` →
  `docker-compose.ad.yml.example` (с пометкой profile 'ad').

---

## 4. Проверка — критерии приёмки

| # | Критерий | Результат |
|---|----------|-----------|
| 1 | `docker compose up -d` — основной стек, без AD → 13 healthy | ✅ 13 сервисов (postgres, redis, manager, worker, beat, flower, webui, prometheus, grafana, alertmanager, 3 экспортера), все healthy |
| 2 | `--profile ad up -d` — с AD → все healthy | ✅ 14 сервисов, `dcap-ad-dc` Up (healthy) |
| 3 | `dcap-redis` не перезапускается | ✅ `Started: 2026-09-19T11:21:39Z` не менялся при каждом `up -d` (в т.ч. с AD) |
| 4 | `dcap-s3-agent` не пропадает | ✅ `Up 5 minutes`, в `--profile agents --profile ad ps` присутствует, не orphan |
| 5 | Manager healthy после AD | ✅ `dcap-manager` Up (healthy), `/api/health` → `{"status":"healthy","version":"3.13.8"}` |
| 6 | DNS: Manager резолвит `dcap.local` | ✅ `docker exec dcap-manager getent hosts dcap.local` → `172.19.0.15 dcap.local` |
| 7 | Нет warning про orphan | ✅ `docker compose up -d` — вывод без `orphan`/`warning`, exit 0 |
| 8 | Документация обновлена | ✅ deployment.md, admin-guide/04-authentication.md, ARCHITECTURE.md |

> Примечание по #2: `bcakend` linux-агент (`audit_agent_linux`, profile `agents`)
> имеет предсуществующую проблему сборки (`COPY config.json` с контекстом корня
> вместо `audit-agent-linux/`) — падает на `docker compose --profile agents
> up -d` сборкой **всех** агентов. `s3_agent` собран и поднят отдельно
> (`docker compose --profile agents up -d s3_agent`). К AD-задаче отношения
> не имеет, зафиксировано в §7.

---

## 5. Отчёт — версия и пересборка

- Версия 3.13.8 установлена: `.env`, `.env.example`, `webui/config.py`,
  `docker-compose.yml` (14 дефолтов `${VERSION:-3.13.8}`).
- Пересобраны образы `dcap/manager:3.13.8`, `dcap/webui:3.13.8`
  (manager/worker/beat — единый Dockerfile).
- Стек перезапущен: `/api/health` → v3.13.8.

---

## 6. Коммит

```powershell
git add -A
git commit -m "fix: AD-контейнер — корректная упаковка (v3.13.8)

Docker:
- AD-сервисы через profile 'ad' (docker compose --profile ad up -d)
- docker-compose.ad.yml → docker-compose.ad.yml.example (redis удалён)
- network aliases dcap.local/dc1.dcap.local для samba-ad-dc
- томы samba_data/samba_logs в основном compose

Docs:
- docs/deployment.md — запуск с AD
- docs/admin-guide/04-authentication.md — AD/hybrid (новый)
- ARCHITECTURE.md — docker-compose.ad.yml → .example

Отчёт: prompts/reports/day_44_ad_packaging_report.md"
```

---

## 7. Открытые проблемы

- **audit_agent_linux build fail** (предсуществующее, не связано с AD):
  `docker compose --profile agents up -d` падает на сборке linux-агента —
  `COPY config.json` из контекста `.` (корень репо) не находит
  `audit-agent-linux/config.json`. Образ не тегирован; до фикса linux-агент
  собирается только из `audit-agent-linux/` (заголовок Dockerfile). Отдельная
  задача — указать `context: ./audit-agent-linux` в compose.
- Старые контейнеры/тома от `docker-compose.ad.yml` (до v3.13.8) нужно удалить
  вручную: `docker rm -f dcap-ad-dc` (тома `samba_data` сохраняются и
  переиспользуются новым сервисом).