ТЗ: День 53.3 — E2E на MinIO + WebUI-форма S3 + docs
Файл: prompts/tz/day_53_3_s3_e2e_webui.md
Дата: 04.10.2026
Версия: v3.13.31 → v3.13.32
Статус: ✏️ Готово к разработке
Оценка: ~2.5–3 ч
Приоритет: 🔴 критично (BACKLOG-097, часть 4: закрытие S3-интеграции в UI/E2E)
Родительская задача: BACKLOG-097 «S3-коннектор сканера: интеграция в ядро + пайплайн находок»

🎯 ЦЕЛЬ

1. **E2E-тесты на живом MinIO** (`tests/e2e/test_s3_e2e.py`) — полный цикл: создать S3-ресурс → запустить задачу → дождаться `completed` → проверить findings с `file_path LIKE 's3://%'` → cleanup.
2. **WebUI-форма добавления S3-ресурса** — единая форма с переключением типа (`filesystem` | `s3` | `minio`), при S3-типе появляются дополнительные поля (`endpoint`, `secure`, `use_path_style`, `region`). Форма переходит на **единый эндпоинт `POST /api/resources`** (REST).
3. **`manager/src/api/resources.py`** — убрать хардкод `host.docker.internal:9000` (вариант B: endpoint = query или `S3_DEFAULT_ENDPOINT`, иначе 400).
4. **`.env.example`** — отдельная секция «Scanner S3» с раскомментированным `S3_DEFAULT_ENDPOINT`.
5. **`docs/admin-guide/06-scanner.md`** — раздел «S3/MinIO-сканирование», обновление ENV-таблицы, версия `v3.13.32`.

Что НЕ входит в 53.3:
- Документация масштабирования сканера — **отдельный день (53.4)**.
- `BACKLOG-099` (`s3://*` — все bucket'ы одной задачей) — **не заводим** (решение: B).
- `recursive` для S3 — **не добавляем** (рекурсия всегда).
- `scanner/README.md` — **не трогаем** (единая документация в `docs/`).
- Параллелизм S3 (`max_parallel_files > 1`) — v3.1.0.
- `skip_prefixes` для S3 — v3.1.0.
- Расширение `POST /api/resources` (REST уже готов с 53.1a).

📌 ПРОБЛЕМА

После 53.2 сканер реально сканирует S3/MinIO, findings сохраняются с `file_path = s3://bucket/key`, `catalog_entries.path = s3://bucket/prefix`. Но:

- **E2E-тестов нет** — только ручной smoke в отчёте 53.2. Регрессия S3 не покрыта.
- **WebUI-форма** не даёт создать S3-ресурс — только через `curl`/Swagger. Форма в `webui/templates/resources.html` шлёт `POST /api/resources/create` (WebUI-совместимый эндпоинт) с полями `type` (только `FILESYSTEM`) и `path`.
- **`resources.py`** содержит хардкод `host.docker.internal:9000` как дефолт `endpoint` для S3-ресурсов — неявное поведение, не задокументировано.
- **`.env.example`** содержит `S3_*` переменные, но они относятся к **S3-аудиту** (профиль `agents`), не к сканеру. Пользователь запутается.
- **`docs/admin-guide/06-scanner.md`** не описывает S3-сканирование (v3.13.10, отстал от v3.13.31).

📌 ПРЕДУСЛОВИЯ

- ✅ 53.1a/53.1b/53.2 закрыты (v3.13.29, v3.13.30, v3.13.31).
- ✅ MinIO (нативный, `E:\Dev\MinIO`) поднят, bucket `dcap-audit-logs` наполнен seed-логами (`scripts/minio-seed/access-logs/*`).
- ✅ Manager healthy, сканер регистрируется и умеет S3 (проверено в 53.2).
- ✅ `pytest tests/unit/` — 424 passed.
- ✅ `pytest tests/e2e/` — 46 passed, 12 skipped.

📁 ФАЙЛЫ (создаются / изменяются)

Создаются

| Файл | Назначение |
|------|------------|
| `tests/e2e/test_s3_e2e.py` | E2E: полный цикл S3-сканирования |
| `prompts/reports/day_53_3_report.md` | Отчёт о выполнении |

Изменяются

| Файл | Что меняется |
|------|--------------|
| `webui/templates/resources.html` | Единая форма (3 типа), S3-поля, перевод на REST `POST /api/resources` |
| `manager/src/api/resources.py` | Убрать хардкод `endpoint`, вариант B |
| `tests/unit/test_s3_resource_v31329.py` | +3 теста, 1 переписать под вариант B |
| `.env.example` | Секция «Scanner S3», `S3_DEFAULT_ENDPOINT` раскомментирован |
| `docs/admin-guide/06-scanner.md` | §8 «S3/MinIO-сканирование», ENV-таблица, версия v3.13.32 |
| `pyproject.toml` | Маркер `requires_minio` (если ещё нет) |
| `STATE.md`, `CHANGELOG.md`, `ROADMAP.md` | Версия, отчёт |

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-129 — E2E-тесты на MinIO

Файл: `tests/e2e/test_s3_e2e.py` (создать)

Полный код:

```python
"""E2E: сканирование S3/MinIO (день 53.3, BACKLOG-097).

Полный цикл:
  создать S3-ресурс → запустить задачу → дождаться completed →
  проверить findings с file_path LIKE 's3://%' → cleanup.

Skip-условия:
  - MinIO недоступен (healthcheck не отвечает),
  - сканер не зарегистрирован как active.

Endpoint передаётся в query явно (не зависит от ENV S3_DEFAULT_ENDPOINT
на Manager-хосте) — чтобы тест был стабильным независимо от окружения.

Прогон: pytest tests/e2e/test_s3_e2e.py -v -m e2e
"""
import os
import time

import pytest
import requests

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_manager,
    pytest.mark.requires_minio,
]


MINIO_ENDPOINT = os.environ.get("S3_DEFAULT_ENDPOINT", "host.docker.internal:9000")
BUCKET = "dcap-audit-logs"
PREFIX = "access-logs/"


def _minio_available() -> bool:
    """Проверка доступности MinIO (healthcheck)."""
    try:
        r = requests.get(f"http://{MINIO_ENDPOINT}/minio/health/live", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _scanner_active(manager_url, client) -> bool:
    """Есть ли хотя бы один активный сканер."""
    try:
        r = client.get(f"{manager_url}/api/scanner", timeout=10)
        if r.status_code != 200:
            return False
        scanners = r.json()
        return any(s.get("status") in ("active", "ACTIVE") for s in scanners)
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def _skip_if_unavailable(manager_url, client):
    if not _minio_available():
        pytest.skip(f"MinIO недоступен на {MINIO_ENDPOINT}")
    if not _scanner_active(manager_url, client):
        pytest.skip("Нет активного сканера — S3-задача не будет обработана")


@pytest.fixture()
def s3_resource(manager_url, client):
    """Создать S3-ресурс на prefix access-logs/, удалить после теста."""
    path = f"s3://{BUCKET}/{PREFIX}"
    r = client.post(
        f"{manager_url}/api/resources",
        params={
            "path": path,
            "type": "s3",
            "endpoint": MINIO_ENDPOINT,
        },
        timeout=10,
    )
    assert r.status_code == 200, f"Create S3 resource: {r.status_code} {r.text}"
    res = r.json()
    yield res
    # cleanup: каскадно удаляет findings/tasks/catalog_entries
    client.delete(f"{manager_url}/api/resources/{res['id']}", timeout=10)


def test_s3_scan_full_cycle(manager_url, client, s3_resource):
    """S3-сканирование: задача проходит полный цикл, findings в БД."""
    res_id = s3_resource["id"]

    # 1. Запустить задачу
    r = client.post(f"{manager_url}/api/resources/{res_id}/scan", timeout=10)
    assert r.status_code == 200, f"Scan start: {r.text}"
    task_id = r.json()["task_id"]
    assert task_id > 0

    # 2. Дождаться завершения (до 240 с)
    deadline = time.time() + 240
    status = None
    while time.time() < deadline:
        r = client.get(f"{manager_url}/api/tasks/{task_id}", timeout=10)
        assert r.status_code == 200
        status = r.json()["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(5)
    assert status == "completed", f"Task не завершилась: status={status}"

    # 3. Findings содержат s3://
    r = client.get(
        f"{manager_url}/api/findings",
        params={"task_id": task_id, "limit": 200},
        timeout=15,
    )
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) > 0, "Нет findings от S3-сканирования"
    for f in findings:
        assert f["file_path"].startswith(f"s3://{BUCKET}/{PREFIX}"), (
            f"file_path не s3://: {f['file_path']}"
        )


def test_s3_resource_cleanup_removes_findings(manager_url, client):
    """DELETE resource каскадно удаляет findings/tasks/catalog_entries."""
    path = f"s3://{BUCKET}/{PREFIX}"
    r = client.post(
        f"{manager_url}/api/resources",
        params={
            "path": path,
            "type": "s3",
            "endpoint": MINIO_ENDPOINT,
        },
        timeout=10,
    )
    if r.status_code == 400:
        # Уже существует — cleanup проверится в основном тесте
        pytest.skip("S3-ресурс уже существует")
    assert r.status_code == 200
    res_id = r.json()["id"]

    # Сразу удаляем
    r = client.delete(f"{manager_url}/api/resources/{res_id}", timeout=10)
    assert r.status_code == 200

    # Findings с resource_id больше нет
    r = client.get(
        f"{manager_url}/api/findings",
        params={"resource_id": res_id},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json() == []
TASK-130 — WebUI-форма S3-ресурса

Файл: webui/templates/resources.html

Задача: заменить блок create-resource-modal и скрипт createResource.

Полный код модального окна (заменить <div class="modal" id="create-resource-modal">...</div>):

html
<div class="modal" id="create-resource-modal">
    <div class="modal-content">
        <div class="modal-header"><h3>Добавить ресурс</h3><button class="btn btn-sm" onclick="closeModal('create-resource-modal')">&times;</button></div>
        <div class="modal-body">
            <div class="mb-3">
                <label class="form-label">Тип</label>
                <select class="form-select" id="resource-type" onchange="onResourceTypeChange()">
                    <option value="filesystem">FILESYSTEM</option>
                    <option value="s3">S3</option>
                    <option value="minio">MINIO</option>
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Путь *</label>
                <input type="text" class="form-control" id="resource-path" placeholder="D:\data или /home/user/data">
                <div class="form-text" id="resource-path-hint"></div>
            </div>
            <div id="s3-fields" style="display:none;">
                <div class="mb-3">
                    <label class="form-label">Endpoint</label>
                    <input type="text" class="form-control" id="resource-endpoint" placeholder="host.docker.internal:9000">
                    <div class="form-text">Оставьте пустым, если на Manager-хосте задан <code>S3_DEFAULT_ENDPOINT</code></div>
                </div>
                <div class="mb-3">
                    <label class="form-label">Region</label>
                    <input type="text" class="form-control" id="resource-region" value="us-east-1">
                </div>
                <div class="form-check mb-2">
                    <input class="form-check-input" type="checkbox" id="resource-secure">
                    <label class="form-check-label" for="resource-secure">Secure (HTTPS)</label>
                </div>
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" id="resource-path-style" checked>
                    <label class="form-check-label" for="resource-path-style">Path-style addressing</label>
                </div>
                <div class="alert alert-info small">
                    Секреты S3 (<code>S3_ACCESS_KEY</code>, <code>S3_SECRET_KEY</code>) задаются на хосте сканера в ENV — в форму не вводятся.
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">Расширения</label>
                <input type="text" class="form-control" id="resource-extensions" value="txt,pdf,docx,xlsx,png,jpg,jpeg">
            </div>
            <div class="d-flex gap-2">
                <button class="btn btn-primary" onclick="createResource()">Создать</button>
                <button class="btn btn-outline-secondary" onclick="closeModal('create-resource-modal')">Отмена</button>
            </div>
        </div>
    </div>
</div>
Полный код функции createResource (заменить старую) и добавить onResourceTypeChange (в <script>):

javascript
function onResourceTypeChange() {
    var t = document.getElementById('resource-type').value;
    var s3 = document.getElementById('s3-fields');
    var hint = document.getElementById('resource-path-hint');
    var path = document.getElementById('resource-path');
    if (t === 's3' || t === 'minio') {
        s3.style.display = '';
        hint.innerHTML = 'Формат: <code>s3://bucket[/prefix]</code>';
        path.placeholder = 's3://bucket/prefix';
    } else {
        s3.style.display = 'none';
        hint.innerHTML = '';
        path.placeholder = 'D:\\data или /home/user/data';
    }
}

async function createResource() {
    var path = document.getElementById('resource-path')?.value?.trim();
    if (!path) { alert('Укажите путь'); return; }
    var type = document.getElementById('resource-type')?.value || 'filesystem';

    var params = new URLSearchParams({ path: path, type: type });
    if (type === 's3' || type === 'minio') {
        var endpoint = document.getElementById('resource-endpoint')?.value?.trim();
        if (endpoint) params.append('endpoint', endpoint);
        params.append('secure', document.getElementById('resource-secure')?.checked ? 'true' : 'false');
        params.append('use_path_style', document.getElementById('resource-path-style')?.checked ? 'true' : 'false');
        var region = document.getElementById('resource-region')?.value?.trim();
        if (region) params.append('region', region);
    }

    try {
        const r = await fetch('/api/resources?' + params.toString(), {
            method: 'POST',
            headers: api._headers(),
        });
        if (r.status === 401) {
            if (typeof Auth !== 'undefined') Auth.setToken(null);
            window.location.href = '/login';
            return;
        }
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText }));
            alert(err.detail || ('HTTP ' + r.status));
            return;
        }
        closeModal('create-resource-modal');
        loadResources();
    } catch (e) {
        alert('Ошибка: ' + e.message);
    }
}
Что убрать:

Существующий вызов api.post('/api/resources/create', {type: ..., path: ..., enabled: true, extensions: ...}) — удалить полностью.

Функцию rescanResource(id) и loadResources() — оставить без изменений.

Кнопку onclick="showModal('create-resource-modal')" — оставить.

TASK-131 — .env.example: секция «Scanner S3»

Файл: .env.example

Найти секцию:

text
# ===== SCANNER (НЕ в Docker, на хосте) =====
# Сканер запускается на хосте: python run_scanner.py scanner/config/scanner_config.json
# Он видит все пути хоста, поэтому НЕ требует монтирования в контейнер.
# MANAGER_URL (http://localhost:8000) задаётся в scanner/config/scanner_config.json
Заменить на:

text
# ===== SCANNER (НЕ в Docker, на хосте) =====
# Сканер запускается на хосте: python run_scanner.py scanner/config/scanner_config.json
# Он видит все пути хоста, поэтому НЕ требует монтирования в контейнер.
# MANAGER_URL (http://localhost:8000) задаётся в scanner/config/scanner_config.json

# ----- SCANNER: S3/MinIO (BACKLOG-097, v3.13.31) -----
# Секреты — только ENV (политика TASK-018). НЕ путать с секцией
# "S3/MinIO аудит-агент" выше — это разные процессы.
# Endpoint/bucket/prefix/secure/use_path_style/region приходят в payload
# задачи от Manager (scan_config.connector.s3). Bucket задаётся в path
# S3-ресурса (POST /api/resources?type=s3&path=s3://bucket/prefix).
# Дефолтный endpoint (вариант B): если не задан в query ресурса и не выставлен
# этот ENV → 400. Один раз на Manager-хосте — и все S3-ресурсы по умолчанию
# указывают на него.
S3_DEFAULT_ENDPOINT=host.docker.internal:9000

# Секреты S3-СКАНЕРА (не S3-аудита!). Идентичны на всех инстансах сканера,
# которые работают с одним и тем же S3-сервером.
S3_ACCESS_KEY=CHANGE_ME_MINIO_ACCESS_KEY
S3_SECRET_KEY=CHANGE_ME_MINIO_SECRET_KEY
Что НЕ трогаем: секция «S3/MinIO аудит-агент (profile agents)» (S3_ENDPOINT, S3_BUCKET, S3_PREFIX, S3_POLL_INTERVAL, MAX_ERROR_DELAY, MINIO_ROOT_*) — остаётся как есть, для S3-агента аудита.

TASK-131a — resources.py: убрать хардкод endpoint (вариант B)

Файл: manager/src/api/resources.py

Найти в create_resource:

python
        scan_config["connector"]["s3"] = {
            "endpoint": endpoint
            or os.environ.get("S3_DEFAULT_ENDPOINT", "host.docker.internal:9000"),
            "bucket": parsed.netloc,
            "prefix": parsed.path.lstrip("/"),
            "secure": secure,
            "use_path_style": use_path_style,
            "region": region,
        }
Заменить на:

python
        resolved_endpoint = endpoint or os.environ.get("S3_DEFAULT_ENDPOINT")
        if not resolved_endpoint:
            raise HTTPException(
                400,
                "endpoint is required for S3/MinIO resources "
                "(or set S3_DEFAULT_ENDPOINT in env)",
            )
        scan_config["connector"]["s3"] = {
            "endpoint": resolved_endpoint,
            "bucket": parsed.netloc,
            "prefix": parsed.path.lstrip("/"),
            "secure": secure,
            "use_path_style": use_path_style,
            "region": region,
        }
Файл: tests/unit/test_s3_resource_v31329.py

Переписать существующий тест test_create_s3_resource_with_defaults (он ожидал хардкод-дефолт):

python
def test_create_s3_resource_with_defaults(client, db, monkeypatch):
    """Ресурс создаётся; endpoint берётся из ENV, если не задан явно."""
    monkeypatch.setenv("S3_DEFAULT_ENDPOINT", "host.docker.internal:9000")
    r = client.post(
        "/api/resources",
        params={"path": "s3://dcap-audit-logs/", "type": "s3"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "s3"

    res = db.query(models.Resource).filter(models.Resource.id == body["id"]).first()
    s3 = (res.scan_config or {}).get("connector", {}).get("s3", {})
    assert s3["bucket"] == "dcap-audit-logs"
    assert s3["prefix"] == ""
    assert s3["secure"] is False
    assert s3["use_path_style"] is True
    assert s3["region"] == "us-east-1"
    assert s3["endpoint"] == "host.docker.internal:9000"
    # Секретов в scan_config быть не должно.
    assert "access_key" not in s3
    assert "secret_key" not in s3
Добавить три новых теста:

python
def test_create_s3_resource_without_endpoint_and_env_returns_400(
    client, monkeypatch,
):
    """Вариант B: без endpoint и без S3_DEFAULT_ENDPOINT → 400."""
    monkeypatch.delenv("S3_DEFAULT_ENDPOINT", raising=False)
    r = client.post(
        "/api/resources",
        params={"path": "s3://bucket/prefix", "type": "s3"},
    )
    assert r.status_code == 400
    assert "endpoint is required" in r.json()["detail"]


def test_create_s3_resource_endpoint_from_env_works(client, monkeypatch, db):
    """S3_DEFAULT_ENDPOINT в ENV → ресурс создаётся без явного endpoint."""
    monkeypatch.setenv("S3_DEFAULT_ENDPOINT", "minio.local:9000")
    r = client.post(
        "/api/resources",
        params={"path": "s3://bucket/prefix", "type": "s3"},
    )
    assert r.status_code == 200, r.text
    res = db.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    s3 = res.scan_config["connector"]["s3"]
    assert s3["endpoint"] == "minio.local:9000"


def test_create_s3_resource_explicit_endpoint_overrides_env(
    client, monkeypatch, db,
):
    """Явный endpoint в query имеет приоритет над S3_DEFAULT_ENDPOINT."""
    monkeypatch.setenv("S3_DEFAULT_ENDPOINT", "env.local:9000")
    r = client.post(
        "/api/resources",
        params={
            "path": "s3://bucket/prefix",
            "type": "s3",
            "endpoint": "explicit.local:9000",
        },
    )
    assert r.status_code == 200, r.text
    res = db.query(models.Resource).filter(models.Resource.id == r.json()["id"]).first()
    s3 = res.scan_config["connector"]["s3"]
    assert s3["endpoint"] == "explicit.local:9000"
Также проверить test_create_s3_resource_with_custom_endpoint — он передаёт endpoint явно, остаётся рабочим.

TASK-132 — docs/admin-guide/06-scanner.md: раздел S3

Файл: docs/admin-guide/06-scanner.md

Обновления:

Заголовок: **Обновлено:** 04.10.2026 + **Версия:** v3.13.32.

Содержание — добавить пункт (старый §8 сдвигается в §9):

text
8. [S3/MinIO-сканирование](#8-s3minio-сканирование)
9. [Troubleshooting](#9-troubleshooting)
§4 ENV-таблицы — добавить строки:

text
| `S3_ACCESS_KEY` | Для S3-ресурсов | Access key MinIO/S3 (политика TASK-018) |
| `S3_SECRET_KEY` | Для S3-ресурсов | Secret key MinIO/S3 (политика TASK-018) |
| `S3_DEFAULT_ENDPOINT` | ❌ | Дефолтный endpoint (вариант B: без query и без ENV → 400) |
Новый §8 «S3/MinIO-сканирование» (вставить перед Troubleshooting):

markdown
## 8. S3/MinIO-сканирование

> **С v3.13.31 (BACKLOG-097).** Сканер умеет сканировать S3-совместимые
> хранилища (MinIO, AWS S3, Wasabi и др.) построчно — так же, как файловую
> систему.

### 8.1. Как работает

- **Секреты — только ENV на хосте сканера:** `S3_ACCESS_KEY` / `S3_SECRET_KEY`.
- **Endpoint/bucket/prefix/secure/use_path_style** приходят в payload задачи
  от Manager (`scan_config.connector.s3`); регистрируются при создании ресурса:
  `POST /api/resources?type=s3&path=s3://bucket/prefix`.
- **Endpoint** (вариант B): если не задан в query при создании ресурса и не
  выставлен `S3_DEFAULT_ENDPOINT` на Manager-хосте → 400.
- **Формат пути:** `s3://bucket[/prefix]` (схема также `minio://`).
- **Рекурсия — всегда:** объекты обходятся по всему поддереву prefix
  (S3 — плоское хранилище, `list_objects_v2(Prefix=...)` возвращает всё
  поддерево). Опции `recursive=false` для S3 нет намеренно — чтобы не
  пропустить вложенные объекты при ошибке конфигурации.
- **Streaming:** объекты читаются по чанкам (`Body.iter_chunks`, 1 МБ),
  а не целиком в память.
- **Документы/изображения** — скачиваются во временный файл, извлекаются
  через `DocumentExtractor` (PDF/Office — текст; изображения — OCR).

### 8.2. Создание S3-ресурса

Через WebUI: **Ресурсы → Добавить ресурс → Тип: S3**, заполнить `path`
(`s3://bucket/prefix`), опционально `endpoint`, `secure`, `use_path_style`,
`region`.

Через API:

```bash
curl -X POST "http://localhost:8000/api/resources?path=s3://bucket/prefix&type=s3" \
     -H "Authorization: Bearer <TOKEN>"
8.3. Находки
file_path в findings = s3://bucket/key (не локальный путь).

catalog_entries.path = s3://bucket/prefix (без //, без s3:/bucket).

Fingerprint (дедупликация) считается от s3://bucket/key|line|match|type —
стабилен между сканами, если ключ не меняется.

8.4. Ограничения
Ограничение	Описание
secure=false = verify=False	При HTTP-endpoint сертификат не проверяется (TEST-NOTE-6.11). Для production — secure=true.
Секреты — per-host, не per-task	Разные credentials на разные S3 — отдельные инстансы сканера.
Параллелизм — последовательный	S3LineConnector.scan_path обрабатывает объекты по одному. max_parallel_files > 1 — v3.1.0.
s3_connector.py (ISourceConnector)	Существует отдельно (для Orchestrator), сканером не используется.
Все bucket'ы одной задачей	Не поддерживается — на каждый bucket создаётся отдельный Resource.
8.5. Масштабирование
Подробно — в отдельном дне документации. Кратко: один инстанс сканера =
одна задача за раз. Несколько bucket'ов — несколько Resource, сканер
обработает их последовательно. Для параллелизма — N инстансов сканера
(Manager разводит задачи между ними через /tasks/pending).

text

5. **Troubleshooting (было §8, стало §9)** — добавить строки в таблицу:
| S3-задача failed с «No files found» | _connector is None или source_type не распознан | Проверить логи сканера: должно быть Connector created: source_type=s3 |
| S3LineConnector: задайте S3_ACCESS_KEY / S3_SECRET_KEY в ENV | Секреты не заданы на хосте сканера | Задать ENV (§4) |
| endpoint is required for S3/MinIO resources при создании ресурса | Не задан endpoint в query и не выставлен S3_DEFAULT_ENDPOINT | Задать endpoint в форме или ENV на Manager-хосте |
| ClientError: NoSuchBucket | Bucket не существует или неверный endpoint | Проверить mc ls <alias>/<bucket> |
| secure=False — HTTPS-проверка сертификата отключена | Endpoint по HTTP, secure=false | Ожидаемо для MinIO dev; для production — secure=true |
| Кириллица в S3-объектах отображается мусором | Объект в не-UTF8 кодировке | С v3.13.31 поддерживается cp1251 (BUG-136 fix) |

text

6. **`📚 См. также`** — добавить ссылку на `ARCHITECTURE.md` (раздел S3).

7. **Финальная строка** — `Последнее обновление: 04.10.2026` / `Версия: v3.13.32`.

---

TASK-133 — Маркер `requires_minio` в pytest

Файл: `pyproject.toml` (секция `[tool.pytest.ini_options]`) — добавить:

```toml
markers = [
    "e2e: end-to-end тесты",
    "requires_manager: требует запущенный Manager",
    "requires_minio: требует запущенный MinIO",
]
Если секция уже есть — добавить requires_minio в существующий список.

🧪 КРИТЕРИИ ПРИЁМКИ

#	Критерий	Проверка
1	E2E test_s3_e2e.py создан, проходит на живом MinIO	pytest tests/e2e/test_s3_e2e.py -v
2	E2E: findings после S3-скана имеют file_path LIKE 's3://%'	test_s3_scan_full_cycle
3	E2E: cleanup удаляет resource + каскадно findings	test_s3_resource_cleanup_removes_findings
4	WebUI-форма: <select> с 3 типами, S3-поля показываются при s3/minio	ручная
5	WebUI-форма: создаёт S3-ресурс (endpoint из формы или из ENV)	ручная
6	resources.py: без endpoint и без ENV → 400; с ENV → 200; с query → 200 (приоритет query)	3 новых теста
7	.env.example: секция «Scanner S3» с S3_DEFAULT_ENDPOINT раскомментирован	grep
8	06-scanner.md: §8 S3, ENV-таблица обновлена, версия v3.13.32	grep
9	Полный unit-набор зелёный	pytest tests/unit/ -q — 427+ passed (было 424, +3 новых, 1 переписан)
10	Полный E2E не сломан	pytest tests/e2e/ -q — 48+ passed
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

Unit:

powershell
pytest tests/unit/test_s3_resource_v31329.py -v
pytest tests/unit/ -q
E2E (MinIO запущен, сканер активен):

powershell
$env:PYTHONUTF8 = '1'
$env:S3_ACCESS_KEY = "minioadmin"
$env:S3_SECRET_KEY = "minioadmin"
pytest tests/e2e/test_s3_e2e.py -v
WebUI (ручная):

powershell
Start-Process "http://localhost:8001/resources"
Открыть форму «Добавить ресурс».

Выбрать тип S3 → появились поля Endpoint/Region/Secure/Path-style.

Заполнить path = s3://dcap-audit-logs/access-logs/, endpoint оставить пустым (если ENV S3_DEFAULT_ENDPOINT задан) или указать host.docker.internal:9000.

Создать → ресурс появился в списке.

Нажать «▶ Сканировать» → задача создана.

Проверка варианта B (Manager без ENV и без endpoint):

powershell
# Если временно убрать S3_DEFAULT_ENDPOINT из docker-compose и перезапустить Manager:
curl.exe -X POST "http://127.0.0.1:8000/api/resources?path=s3://test-bucket/&type=s3" `
    -H "Authorization: Bearer $token"
# Ожидание: 400 endpoint is required for S3/MinIO resources
E2E-полный прогон:

powershell
pytest tests/e2e/ -q
📝 СВОДКА ПРАВОК

#	Файл	Действие	Задача
1	tests/e2e/test_s3_e2e.py	Создан	TASK-129
2	webui/templates/resources.html	Единая форма + S3-поля + REST	TASK-130
3	manager/src/api/resources.py	Убран хардкод endpoint (вариант B)	TASK-131a
4	tests/unit/test_s3_resource_v31329.py	+3 теста, 1 переписан	TASK-131a
5	.env.example	Секция «Scanner S3»	TASK-131
6	docs/admin-guide/06-scanner.md	§8 S3, ENV-таблица, версия	TASK-132
7	pyproject.toml	Маркер requires_minio	TASK-133
8	STATE.md, CHANGELOG.md, ROADMAP.md	Обновление	—
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

Форма не задаёт extensions — REST-эндпоинт берёт их из get_default_config(). Расширение функциональности — отдельная задача.

webui.py:create_resource остаётся как есть (легаси), но форма на него больше не ходит.

secure=false + verify=False — не правим в 53.3 (TEST-NOTE-6.11 → v3.1.0).

Разные credentials на разные S3 — требуют отдельных инстансов сканера, не решается в 53.3.

📋 ОТКРЫТЫЕ ВОПРОСЫ

WebUI-форма: единый REST-эндпоинт POST /api/resources — ✅ согласовано.

S3_DEFAULT_ENDPOINT — ✅ согласовано (вариант B: без ENV и без query → 400).

E2E: seed-логи — ✅ согласовано (используем access-logs/*.json).

⚠️ ЧТО НЕ ДЕЛАЕМ

Не трогаем manager/src/api/webui.py:create_resource (легаси, форма идёт в REST).

Не добавляем recursive для S3.

Не трогаем scanner/README.md.

Не создаём BACKLOG-099.

Не делаем документацию масштабирования — отдельный день.

Не расширяем POST /api/resources (REST уже готов с 53.1a).

Не трогаем секцию «S3-аудит-агент» в .env.example.

💾 КОМАНДА ДЛЯ КОММИТА

bash
git checkout -b feature/day_53_3_s3_e2e_webui

git add tests/e2e/test_s3_e2e.py \
        webui/templates/resources.html \
        manager/src/api/resources.py \
        tests/unit/test_s3_resource_v31329.py \
        .env.example \
        docs/admin-guide/06-scanner.md \
        pyproject.toml \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/reports/day_53_3_report.md

git commit -m "feat: День 53.3 — E2E на MinIO + WebUI-форма S3 + docs (v3.13.32)

- tests/e2e/test_s3_e2e.py — полный цикл S3-сканирования:
  create resource → scan → completed → findings с s3:// → cleanup;
  endpoint передаётся явно, независимо от ENV
- webui/templates/resources.html — единая форма с переключением типа
  (filesystem | s3 | minio); перевод с POST /api/resources/create
  на единый POST /api/resources (REST)
- manager/src/api/resources.py — убран хардкод endpoint
  (host.docker.internal:9000); вариант B: endpoint = query или
  S3_DEFAULT_ENDPOINT, иначе 400
- tests/unit/test_s3_resource_v31329.py — 3 новых теста (400 без endpoint,
  env, override), 1 переписан (defaults больше не хардкод)
- .env.example — секция «Scanner S3», S3_DEFAULT_ENDPOINT раскомментирован
- docs/admin-guide/06-scanner.md — §8 S3/MinIO-сканирование,
  ENV-таблица, troubleshooting, версия v3.13.32
- pyproject.toml — маркер requires_minio

BACKLOG-097 (часть 4: E2E + WebUI + docs) — закрыт полностью
docs: обновлены STATE.md (v3.13.32), CHANGELOG.md, ROADMAP.md"
📊 ОБНОВЛЕНИЕ ПЛАНА

День	Задача	Статус
53.1a	Manager: source_type + S3-ресурсы	✅ v3.13.29
53.1b	Scanner: фабрика + _text_scanner.py + boto3	✅ v3.13.30
53.2	Scanner: S3LineConnector	✅ v3.13.31
53.3	E2E на MinIO + WebUI-форма S3 + docs	🔄 В РАБОТЕ
53.4	Документация масштабирования сканера	📋 отдельный день
52.1	Linux-агент (дотест)	📋
52.2	Блок 6.5 (сбор прав Windows)	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ

Обновить STATE.md: версия v3.13.32, следующий шаг «53.4: Документация масштабирования» (или «52.1: Linux-агент» — по приоритету).

Обновить CHANGELOG.md — секция [3.13.32].

Обновить ROADMAP.md — 53.3 ✅, BACKLOG-097 закрыт полностью.

Переместить ТЗ в prompts/archive/day_53_3_s3_e2e_webui.md.

Отчёт — prompts/reports/day_53_3_report.md:

сводка по выполнению,

полный код изменённых/новых файлов,

результаты pytest (unit + E2E),

скриншот WebUI-формы (если возможно),

результаты ручной проверки варианта B (без ENV и без endpoint).

Автор ТЗ: архитектор
Дата: 04.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.32 — BACKLOG-097 закрыт полностью (Manager + Scanner + S3LineConnector + E2E + WebUI + docs).