# День 53.3 — E2E на MinIO + форма S3/MinIO в WebUI — отчёт

**Версия:** v3.13.32
**Дата:** 04.10.2026
**Ветка:** `feature/day_53_3_s3_e2e_webui`
**ТЗ:** `prompts/tz/day_53_3_s3_e2e_webui.md` → `prompts/archive/day_53_3_s3_e2e_webui.md`
**Часть BACKLOG-097:** ч.4 (тесты E2E на MinIO + WebUI-форма S3)

---

## 1. Что сделано

### 1.1 `tests/e2e/test_s3_e2e.py` (новый)

Полный живой цикл S3/MinIO-сканирования против поднятого стенда:

| Шаг | Проверка |
|-----|----------|
| 1 | `POST /api/resources` с `type=s3`, `path=s3://dcap-audit-logs/access-logs/`, `endpoint=…` → 200 |
| 2 | `POST /api/resources/{id}/scan` → `task_id` |
| 3 | опрос `GET /api/tasks/{id}` до `completed` (таймаут 240 с) |
| 4 | `GET /api/findings?task_id=…` — находки есть, у всех `file_path` начинается с `s3://dcap-audit-logs/access-logs/` |
| 5 | `DELETE /api/resources/{id}` — каскадная проверка: findings для `resource_id` пусты |

Особенности:

- маркеры `e2e`, `requires_manager`, `requires_minio` (последний — новый, `pyproject.toml`);
- авто-skip: MinIO не отвечает на `/minio/health/live` или нет активного сканера (задача всё равно не будет обработана);
- endpoint передаётся **явно в query**, а не через `S3_DEFAULT_ENDPOINT` на хосте Manager — тест не зависит от окружения;
- `client` — module-scoped (через `fixtures.auth.login`): `/api/auth/login` ограничен 5 попытками в минуту, function-scoped фикстура ловила бы 429;
- `s3_resource` перед созданием подчищает возможный остаток прошлого прогона (уникальность по `(path, type)`), teardown удаляет ресурс каскадно.

### 1.2 `pyproject.toml`

Добавлен маркер:

```toml
requires_minio: Требует запущенный MinIO (S3-совместимое хранилище)
```

### 1.3 `manager/src/api/resources.py` — вариант B

Было: endpoint для `s3`/`minio` неявно зашит как `host.docker.internal:9000` — MinIO на другом хосте/порту был бы недостижим, и проверку нельзя было провести.

Стало (`manager/src/api/resources.py:126`):

```
endpoint (query) → S3_DEFAULT_ENDPOINT (ENV) → 400
```

Ответ при отсутствии обоих:

```json
{"detail":"endpoint is required for S3/MinIO resources (or set S3_DEFAULT_ENDPOINT in env)"}
```

### 1.4 `webui/templates/resources.html`

- селектор типа ресурса: `filesystem` / `s3` / `minio`;
- блок `#s3-fields` (`#resource-endpoint`, `#resource-region`, `#resource-secure`, `#resource-path-style`) показывается только для S3/MinIO, с авто-подсказкой `host.docker.internal:9000` для MinIO;
- отправка через **REST** `POST /api/resources` (query-параметры) вместо legacy `/api/resources/create`;
- предупреждение: секреты в форму **не вводятся** — только `S3_ACCESS_KEY` / `S3_SECRET_KEY` в ENV сканера (TASK-018, Manager их не хранит);
- поле «расширения» отключено и помечено как справочное (реализация расширений — вне scope 53.3).

### 1.5 `.env.example`

Секция `SCANNER: S3/MinIO`: `S3_DEFAULT_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` + пояснения (сканер на хосте, приоритет ENV над config, `minioadmin` для локального MinIO).

### 1.6 `docs/admin-guide/06-scanner.md`

- новый раздел «8. S3/MinIO-сканирование»: endpoint, формат пути `s3://bucket/prefix/`, разбор bucket/prefix, секреты, параметры `secure`/`use_path_style`, MinIO-настройка;
- S3-переменные в ENV-таблице;
- S3-строки в Troubleshooting (`Task status is completed…`, «задача висит pending», MinIO недоступен).

### 1.7 `tests/unit/test_s3_resource_v31329.py`

Autouse-фикстура `S3_DEFAULT_ENDPOINT`, переписаны дефолты и добавлены тесты: `400` без endpoint для `s3` и `minio`, ENV-endpoint, приоритет явного query endpoint. Итого по файлу — **22 passed**.

---

## 2. Тесты

| Набор | Результат |
|-------|-----------|
| `tests/unit` (все) | **427 passed**, 1030 warnings, 94.89 с |
| `tests/unit/test_s3_resource_v31329.py` | 22 passed |
| `tests/e2e/test_s3_e2e.py` (стенд :18000) | **2 passed**, 16.20 с |
| `tests/e2e` (все, стенд :18000) | **53 passed, 7 skipped**, 144.16 с |
| Ранее падавшие 4 теста (full_scan_cycle, scanner_findings, scanner_heartbeat) | 12 passed, 1 skipped после очистки БД |

### 2.1 Стенд

```
docker compose -f docker-compose.test.yml up -d      # Manager :18000, WebUI :18001
pythonw temp/launch_scanner_test.py                   # Scanner на хосте → :18000
pytest tests/e2e -p no:randomly -q
```

Scanner регистрируется как `scanner-1` (`id=1`) после ~100 с (cold start spaCy/Presidio, 1.7 ГБ RSS).

### 2.2 Smoke WebUI-формы (live)

```
GET  :18001/resources                       -> 200, есть #s3-fields и опции s3/minio
POST :18001/api/resources  type=s3          -> 200 {"id":22,…}
POST :18001/api/resources  type=minio       -> 200 {"id":23,…}
DELETE :18001/api/resources/{id}            -> 200
POST :18001/api/resources  type=minio, без endpoint
                                        -> 400 {"detail":"endpoint is required …"}
```

---

## 3. Разбор падений (важно для повторов)

Первый полный прогон на стенде дал `6 failed`. Причина — **не код**, а состояние окружения:

1. `docker-compose.test.yml` использует персистентный том `postgres_test_data`. В накопленной БД было ~2000 pending-задач и десятки «мёртвых» сканеров.
2. Сканер разбирал эту очередь FIFO: S3-задача, созданная последней, ждала >240 с и оставалась `pending` → `test_s3_scan_full_cycle` падал по таймауту.
3. Из-за занятости сканера отвалились `test_full_scan_cycle`, `test_scanner_findings`, `test_scanner_heartbeat`.

После `docker compose -f docker-compose.test.yml down -v` (чистая БД) эти 4 теста прошли.

Оставшиеся 2 (`test_proxy_forwards_total_count`, `test_findings_filters_csv_and_empty`) — **legacy-зависимость от наполненной БД**: они требуют `X-Total-Count != "0"`. На пустой БД падают, при наличии хотя бы одной находки проходят (проверено отдельно: 2 passed). Это не регрессия 53.3; для стабильного прогона набора findings должны существовать. В финальном прогоне findings предварительно засеяны FS-ресурсом, поэтому набор зелёный целиком.

Замечание по стенду: manager_test поднимается раньше готовности PostgreSQL и падает (`the database system is starting up`) — нужен `docker compose -f docker-compose.test.yml restart manager_test`. Стоит учесть при автоматизации стенда.

---

## 4. Что НЕ сделано (вне scope по ТЗ)

- 53.4 — docs по масштабированию S3-сканирования;
- BACKLOG-100 (параллельное сканирование S3) и BACKLOG-099 (`skip_prefixes`) — оба в v3.1.0;
- `recursive` для S3 (в коннекторе рекурсия всегда — намеренно, см. §8.1 admin-guide);
- `scanner/README.md` (нужен после 53.4 — риск конфликта);
- фильтрация по расширениям в WebUI-форме;
- вынос `S3_DEFAULT_ENDPOINT` в compose (`env_file: .env`) — не входило в ТЗ.

---

## 5. Известные замечания (из аудита 53.2, не менялись)

- `S3LineConnector`: `env_value or config.get(...)` — при отсутствии ENV ключи всё же берутся из config (fallback сохранён намеренно, чтобы не сломать существующие конфиги; в логе — WARNING). Политика TASK-018 требует «только ENV» — решение нужно от архитектора.
- `s3://bucket/prefix/` в UI: bucket фактически берётся из конфига коннектора, из `path` используется только префикс — предупреждение в коде сейчас неточно.

---

## 6. Файлы

Изменены: `pyproject.toml`, `manager/src/api/resources.py`, `tests/unit/test_s3_resource_v31329.py`,
`webui/templates/resources.html`, `.env.example`, `docs/admin-guide/06-scanner.md`,
`CHANGELOG.md`, `ROADMAP.md`, `STATE.md`.
Добавлен: `tests/e2e/test_s3_e2e.py`.
Перемещено: `prompts/tz/day_53_3_s3_e2e_webui.md` → `prompts/archive/day_53_3_s3_e2e_webui.md`.
