# Отчёт — День 53.4e-grafana (hotfix, v3.14.2)

**Дата:** 17.10.2026
**ТЗ:** «Диагностика Grafana» — хотфикс 7 багов по итогам тестирования Grafana/метрик.
**Версия:** v3.14.1 → **v3.14.2**
**Статус:** ✅ Выполнено (6 тестов passed, YAML/JSON провалидированы)

---

## Кратко

Закрыты 7 багов, найденных при тестировании Grafana (BACKLOG-307 / TEST-NOTE-8.x):
BUG-245, BUG-236, BUG-241, BUG-243, BUG-246, BUG-247, BUG-239.

Ключевая причина: `dcap_findings_total` был Counter'ом за сессию процесса
(credentials не появлялись), а Scanner-метрики могли отдавать пустой
`scanner_id=""`. Метрики переведены в корректную семантику:
`dcap_findings_total` — **Gauge из БД**, новый `dcap_findings_created_total` —
Counter за сессию.

---

## Изменённые / созданные файлы

| Файл | Изменение | Баг |
|------|-----------|-----|
| `manager/src/metrics.py` | `findings_total`: Counter → **Gauge** (значение из БД по типам, `_refresh_findings_gauges()`); добавлен Counter `findings_created_total` (`dcap_findings_created_total`); `track_findings` пишет в новый Counter; `_refresh_scanner_gauges()` — пер-строчная изоляция, пропуск falsy id, warning-лог, `+Inf` при `last_heartbeat=None`; `metrics_endpoint()` вызывает обе refresh | 245, 246, 247 |
| `monitoring/alertmanager/alertmanager.yml` | webhook → несуществующий `/api/alerts/webhook` закомментирован | 236 |
| `monitoring/prometheus/prometheus.yml` | job `s3-agent` закомментирован (DOWN без `--profile agents`) | 243 |
| `monitoring/grafana/provisioning/dashboards/dcap-overview.json` | панель 5xx → `... or vector(0)`; «Findings rate by type» → `rate(dcap_findings_created_total[5m])` | 241, 246 |
| `monitoring/grafana/provisioning/dashboards/dcap-scanner.json` | удалены 2 пустые панели (per-file duration p50/p95, OCR latency) | 239 |
| `manager/tests/test_metrics_v3142.py` | **новый**, 6 тестов | — |
| `docker-compose.yml` | все `3.14.1` → `3.14.2` (12 вхождений) | — |
| `CHANGELOG.md` | секция `## [v3.14.2]` | — |
| `ARCHITECTURE.md` | версия v3.14.2; метрики findings; targets 5/5; s3-agent закомментирован | — |
| `ROADMAP.md` | 53.4e-grafana-hotfix → ✅ v3.14.2 | — |
| `docs/monitoring.md` | семантика `dcap_findings_total` (Gauge), `dcap_findings_created_total` | — |
| `STATE.md` | версия/статус/day/баги/футер → v3.14.2 | — |

---

## Диагностика (факты, а не догадки)

- `GET :8000/metrics` (запущенный Manager) уже отдавал
  `dcap_scanner_heartbeat_age_seconds{scanner_id="1"} 2.31` — серии с `=""` **нет**.
  Модель `Scanner` имеет поле `last_heartbeat` — гипотеза об `AttributeError` не подтвердилась.
  Причина пустого лейбла — transient/stale-строка; фикс = hardening + warning-лог + тесты.
- `dcap_findings_created` — авто-метрика `<counter>_created` от `prometheus_client`
  (timestamp создания серии), а не кастомный счётчик. После перевода
  `findings_total` в Gauge авто-метрика исчезает (BUG-247 снят как false positive).
- В БД: `scanners` → `1`, `scanner-1`, `active`; findings: `pii=1458`, `credentials=51`.
- `scanner/src/metrics.py` определяет `dcap_scanner_file_duration_seconds` (Histogram),
  но **никогда не observes** → панель пустая (источник BUG-239).

---

## Тесты

```
python -m pytest manager/tests/test_metrics_v3142.py -q
6 passed, 13 warnings in 1.50s
```

Покрытие: `scanner_id="1"` (не `""`); `age=+Inf` без heartbeat; пустая БД не даёт
`scanner_id=""`; `dcap_findings_total` по типам из БД; тип `dcap_findings_total` — Gauge,
`dcap_findings_created_total` — Counter; инкремент `track_findings`.

YAML (`alertmanager.yml`, `prometheus.yml`) и оба JSON-дашборда — валидны.

---

## Ручная проверка (для пользователя)

1. Ребилд образов (метрики менялись):
   ```
   docker compose build manager webui
   docker compose up -d manager webui
   ```
2. Проверить `http://127.0.0.1:8000/metrics`:
   - `dcap_scanner_heartbeat_age_seconds{scanner_id="1"}` (нет `=""`)
   - `dcap_findings_total{type="pii"} 1458`, `{type="credentials"} 51`
   - нет метрики `dcap_findings_created`
- Grafana (http://localhost:3000): панель 5xx = 0 (не «No data»); «Findings by type» непустая;
  на `dcap-scanner` нет пустых панелей; Prometheus targets → 5/5 (без s3-agent).

---

## Коммит

```bash
git add manager/src/metrics.py manager/tests/test_metrics_v3142.py \
        monitoring/ docker-compose.yml CHANGELOG.md ARCHITECTURE.md \
        ROADMAP.md docs/monitoring.md STATE.md
git commit -m "fix: 53.4e-grafana hotfix — метрики findings/scanner + Grafana (v3.14.2)

* manager/src/metrics.py: dcap_findings_total → Gauge из БД (BUG-246),
  dcap_findings_created_total — Counter сессии; hardening scanner-gauges (BUG-245)
* monitoring: webhook Alertmanager убран (BUG-236), s3-agent target (BUG-243),
  5xx or vector(0) (BUG-241), удалены пустые панели (BUG-239)
* tests: test_metrics_v3142.py (6 passed)
* docs: CHANGELOG/ARCHITECTURE/ROADMAP/monitoring/STATE → v3.14.2"
```
