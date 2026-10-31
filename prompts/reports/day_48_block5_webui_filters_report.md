# 📄 Отчёт: День 48 — Блок 5 (WebUI), п.2.3: фильтры, пагинация, аудит, экспорт → v3.13.22

**Дата:** 27.09.2026
**Версия:** v3.13.21 → **v3.13.22**
**Блок:** 5 — WebUI (п.2.3)
**Задачи:** TASK-054…059 (BUG-087…093)
**ТЗ:** отдельного файла в `prompts/tz/` нет — scope выведен из `STATE.md` («Блок 5, п.2.3 — фильтры»)
и подтверждён диагностикой живого стека (все 7 проблем воспроизведены на v3.13.21).

---

## 🎯 Итог

| ID | Проблема | Где | Статус |
|----|----------|-----|--------|
| TASK-054 / BUG-087 | Прокси WebUI ронял заголовки ответа (`X-Total-Count`, `X-Fragment-*`, `Content-Disposition`) | `webui/api/routes.py` | ✅ |
| TASK-055 / BUG-088 | Фрагмент `<img>` без Bearer → 401 | `webui/static/js/finding_detail.js` | ✅ |
| TASK-056 / BUG-089 | `/api/access/*` 500 на PostgreSQL (`is_active == 1`) | `manager/src/api/webui.py` | ✅ |
| TASK-057 / BUG-090 | CSV-категории давали 0, пустые параметры → 422 | `manager/src/api/findings.py` + `webui/templates/findings.html` | ✅ |
| TASK-058 / BUG-091 | `event_source` игнорировался, фильтры аудита статические | `manager/src/api/audit.py` + `webui/templates/audit.html` | ✅ |
| TASK-059 / BUG-093 | Экспорт findings 401 (`window.location.href`) | `webui/static/js/findings.js` | ✅ |

**Тесты:** 33 unit (`tests/unit/test_webui_block5_v31322.py`) + 8 E2E (`tests/e2e/test_webui_block5_v31322.py`).
**Регрессии:** 220 unit passed (187 + 33).

---

## 🔍 Диагностика (v3.13.21, живой стек)

| # | Проверка | Результат |
|---|----------|-----------|
| 1 | `GET :8000/api/findings?limit=5` | 200, `X-Total-Count: 667` |
| 2 | `GET :8001/api/findings?limit=5` | 200, **заголовка нет** → пагинация сломана |
| 3 | `?category=phone` / `?category=phone,email` | 11 / **0** (UI подсказывает формат «через запятую») |
| 4 | `?task_id=` / `?task_id=abc` | 422 / 422 (пустой фильтр ≠ «без фильтра») |
| 5 | `:8000/api/findings/{id}/fragment` без токена / с Bearer | 401 / 200 `image/png` 8255 B |
| 6 | `:8001/.../fragment` без токена | 401 → картинка в UI не грузилась |
| 7 | `/api/access/resources` | **500** (`boolean = integer`) |
| 8 | `/api/audit?event_source=api` и `=scanner` | 47 и 47 → фильтр игнорировался |
| 9 | `/api/findings/export` без токена / с Bearer | 401 / 200 |
| 10 | Login WebUI | Нет `Set-Cookie` → JWT только через Bearer-заголовок |

Не воспроизвелось (ложные «баги»): `/dashboard` — дашборд это `/`; `/api/scanners` — массив,
singleton в PowerShell был артефактом unrolling.

---

## 🔧 Исправления

### TASK-054 / BUG-087 — заголовки прокси (`webui/api/routes.py`)

```python
# Заголовки hop-by-hop не пробрасываем (связь обрывается, body пересчитывается)
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
    "content-length", "content-encoding",
}


def forwarded_headers(upstream: dict) -> dict:
    """Заголовки ответа Manager → ответ WebUI (регистронезависимо).

    Проксируем всё, кроме hop-by-hop и set-cookie:
      * X-Total-Count — пагинация findings;
      * X-Fragment-Mode/X-Fragment-Hash/X-Bounding-Box — метаданные фрагмента;
      * Content-Disposition — имя файла экспорта.
    Cookie Manager'а не пробрасываются намеренно: WebUI авторизуется
    заголовком Authorization (JWT в localStorage), иначе прокси
    подменял бы куки браузера.
    """
    out = {}
    for key, value in upstream.items():
        low = key.lower()
        if low in HOP_BY_HOP or low == "set-cookie":
            continue
        out[key] = value
    return out
```

Применено в ветках `Response` и `StreamingResponse` (бинарные ответы: fragment, экспорт).

### TASK-055 / BUG-088 — фрагмент с Bearer (`webui/static/js/finding_detail.js`)

`<img src="/api/findings/1/fragment?format=png">` заменён на:

```javascript
const r = await fetch(`/api/findings/${id}/fragment?format=${fmt}`, {
    headers: api._headers(),
});
if (r.status === 401) { /* → /login */ }
const blob = await r.blob();
img.src = URL.createObjectURL(blob);
metaEl.textContent = `${r.headers.get('X-Fragment-Mode') || '—'}` +
    ` · sha256 ${(r.headers.get('X-Fragment-Hash') || '').slice(0, 12)}…`;
```

`innerHTML` для метаданных заменён на `textContent` (значения приходят от Manager).

### TASK-056 / BUG-089 — Boolean-колонка (`manager/src/api/webui.py`)

`AccessEntry.is_active == 1` → `== True` (2 места: `/api/access/resources`,
`/api/access/resources/{id}/entries`).

### TASK-057 / BUG-090 — фильтры findings (`manager/src/api/findings.py`)

```python
def _parse_categories(raw):  # "phone, email" -> ["phone", "email"]
    return [c.strip() for c in raw.split(",") if c.strip()]


def _apply_category_filter(query, raw):
    """Legacy-категории (pii/credentials/code) -> finding_type, остальные -> category.
    Объединение через ИЛИ: «credentials,phone» находит и то, и другое."""
    cats = _parse_categories(raw)
    if not cats:
        return query
    legacy = [c for c in cats if c in ("pii", "credentials", "code")]
    real = [c for c in cats if c not in ("pii", "credentials", "code")]
    clauses = []
    if real:
        clauses.append(Finding.category.in_(real))
    if legacy:
        clauses.append(Finding.finding_type.in_(legacy))
    return query.filter(or_(*clauses)) if clauses else query
```

Пустые числовые параметры:

```python
def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


OptInt = Annotated[Optional[int], BeforeValidator(_blank_to_none), Query()]


def _clamp_int(value, default, lo, hi):
    if value is None:
        return default
    return max(lo, min(hi, value))
```

> **FastAPI 0.137 gotcha (обнаружено тестами):** `BeforeValidator` в `Annotated` **теряется**,
> если `Query(...)` указан в default — `create_model_field` берёт `annotation` из `field_info`
> и отбрасывает метаданные `Annotated` (проверено на fastapi 0.137.2 / pydantic 2.10.3).
> Поэтому `Query()` объявлен **внутри** `Annotated`, а дефолт — через `=`.
> Вторая находка: `le`/`ge` на `Optional[int]` падают с `TypeError` на `None`
> («Unable to apply constraint 'le' to supplied value None») — границы задаёт `_clamp_int`.

Новые фильтры в `list_findings` (и те же правила в `/count` и `/export`):
`detector`, `fragment_type`, `search` (`fragment_path`/`match_text_masked`/`line_text_masked`, ILIKE),
`order_by=id`; `has_fragment` учитывает `fragment_data`.

UI (`webui/templates/findings.html`): две строки фильтров — поиск, «Категория (через запятую)»,
«Детектор», «Фрагмент», «Задание», статус/тип/severity + «Применить» и **«Сброс»**
(`resetFilters()` чистит 8 контролов и перезагружает список).

### TASK-058 / BUG-091 — аудит (`manager/src/api/audit.py`, `webui/templates/audit.html`)

В `get_audit_events` добавлен параметр `event_source` и SQL-фильтр. В шаблоне статические
опции «Источник/Тип» заменены на данные `/api/audit/stats`:

```javascript
async function loadFilterOptions() {
    const st = await api.get('/api/audit/stats', {days: 30});
    fillSelect('a-source', (st.by_source || []).map((x) => x.source));
    fillSelect('a-type', (st.by_type || []).map((x) => x.type));
}
```

Также `d.total ?? events.length` вместо `d.total || events.length` (0 событий не показывался как N).

### TASK-059 / BUG-093 — экспорт (`webui/static/js/findings.js`)

```javascript
const r = await fetch(`/api/findings/export?${params}`, { headers: api._headers() });
if (r.status === 401) { /* → /login */ }
const blob = await r.blob();
const name = /filename="?([^"]+)"?/.exec(r.headers.get('Content-Disposition') || '')?.[1];
const a = document.createElement('a');
a.href = URL.createObjectURL(blob);
a.download = name || `findings.${fmt}`;
a.click();
setTimeout(() => URL.revokeObjectURL(a.href), 5000);
```

---

## 🧪 Тесты

### `tests/unit/test_webui_block5_v31322.py` (33)

| Группа | Тестов | Что проверяет |
|--------|--------|---------------|
| `TestProxyHeaders` | 4 | проброс `X-Total-Count`/`X-Fragment-*`/`X-Bounding-Box`, отбрасывание hop-by-hop и `Set-Cookie`, регистронезависимость |
| `TestFindingsFilters` | 18 | одиночная/CSV-категория, пробелы и хвостовая запятая, legacy-микс, `detector`, `fragment_type`, `search`, комбинация, `order_by=id`, 4× пустые числовые параметры, `/count`, `/export` CSV+JSON, `has_fragment` из `fragment_data` |
| `TestAccessResources` | 3 | `/api/access/resources` и `/entries` без 500 (Boolean) |
| `TestAuditFilters` | 5 | `event_source`, `event_type`, комбинация, пустой фильтр, `user` |

> Тесты нашли 3 бага в первой версии реализации: AND вместо OR в `_apply_category_filter`
> и 422 на `?limit=` (валидатор терялся из-за `Query()` в default) — исправлено до коммита.

### `tests/e2e/test_webui_block5_v31322.py` (8)

Против живого стека (`MANAGER_URL=http://127.0.0.1:8000`, `WEBUI_URL=http://127.0.0.1:8001`):
`X-Total-Count` через прокси, CSV-категории и пустые параметры, новые фильтры,
export 200/401 + `Content-Disposition`, fragment 200/401, `/api/access/*`,
`event_source` (в ответе только запрошенный источник), рендер `/findings` и `/audit`.

Логин — **один на модуль** (фикстура `client`): `/api/auth/login` ограничен
5 попытками в минуту (`AUTH_LOGIN_MAX_ATTEMPTS`), фикстура `api_client` (function scope)
логинится на каждый тест и при полном прогоне даёт 429.

---

## ✅ Проверено live (v3.13.22)

```
$env:VERSION="3.13.22"; docker compose build manager webui
$env:VERSION="3.13.22"; docker compose up -d manager webui celery_worker celery_beat
```

| Проверка | Результат |
|----------|-----------|
| `/api/health` | `{"status":"healthy","version":"3.13.22"}` (Manager и WebUI) |
| BUG-087 | Manager `X-Total-Count: 667` → WebUI `X-Total-Count: 667` |
| BUG-088 | `:8001/.../fragment?format=png` → 200 `image/png` 8255 B, `X-Fragment-Mode: embedded`, `X-Fragment-Hash: 9ecadc2f…`; без токена 401 |
| BUG-089 | `/api/access/resources` → 200 (7 ресурсов), `/entries` → 200 |
| BUG-090 | `category=phone` → 11, `category=phone,email` → 623, `?task_id=`/`?limit=`/`?offset=` → 200 (667), `/count?category=phone,email` → `{"count":623}`, `detector`/`fragment_type`/`search`/`order_by=id` → 200 |
| BUG-091 | `/api/audit` — 48 событий, `event_source=api` → 44, `event_type=finding_reveal` → 25 |
| BUG-093 | export CSV 200 (99 907 B, `Content-Disposition: attachment; filename="findings_20260927_002857.csv"`), JSON 200, `?task_id=&resource_id=&limit=` → 200, без токена 401 |
| E2E | `8 passed` |
| Unit | `220 passed` |

---

## 📁 Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `webui/api/routes.py` | `HOP_BY_HOP`, `forwarded_headers()`, проброс заголовков (Response + StreamingResponse) |
| `webui/static/js/finding_detail.js` | fragment через fetch+blob, метаданные `X-Fragment-*`, безопасный textContent |
| `webui/static/js/findings.js` | `showExportDialog` (async fetch+blob), `collectFilters` (detector/fragment_type/search), `resetFilters`, Enter в поиске |
| `webui/templates/findings.html` | фильтры в 2 строки + кнопка «Сброс», подпись «Категория (через запятую)» |
| `webui/templates/audit.html` | `loadFilterOptions`/`fillSelect` из `/api/audit/stats`, `d.total ?? events.length` |
| `manager/src/api/findings.py` | `_blank_to_none`, `OptInt`, `_clamp_int`, `_parse_categories`, `_apply_category_filter` (OR), фильтры в list/count/export, `has_fragment` |
| `manager/src/api/audit.py` | параметр и SQL-фильтр `event_source` |
| `manager/src/api/webui.py` | `AccessEntry.is_active == True` (2 места) |
| `tests/unit/test_webui_block5_v31322.py` | новый — 33 теста |
| `tests/e2e/test_webui_block5_v31322.py` | новый — 8 тестов |
| `docker-compose.yml` | manager/webui/celery → 3.13.22 |
| `STATE.md`, `ROADMAP.md`, `CHANGELOG.md` | день 48, версия, задачи, live-результаты |

---

## 📌 Замечания

1. **FastAPI 0.137** теряет `BeforeValidator` из `Annotated` при `Query()` в default — при
   добавлении новых числовых query-параметров использовать схему `OptInt` (или помнить про gotcha).
2. **Rate limit логина** (5/мин, in-memory) срабатывает при массовых E2E-прогонах: держать
   один логин на модуль/сессию либо поднимать `AUTH_LOGIN_MAX_ATTEMPTS` на тестовом стеке.
3. Ложные «баги», которые не воспроизвелись: `/dashboard` (дашборд = `/`), «один сканер»
   в PowerShell (unrolling массива). Запланировано в бэклог на отдельный UI-проход.
4. Следующий шаг — Блок 5, п.2.4 (отчёты/архив в WebUI).

---

## 🔧 Команда коммита

```powershell
git add webui/api/routes.py `
        webui/static/js/finding_detail.js `
        webui/static/js/findings.js `
        webui/templates/findings.html `
        webui/templates/audit.html `
        manager/src/api/findings.py `
        manager/src/api/audit.py `
        manager/src/api/webui.py `
        tests/unit/test_webui_block5_v31322.py `
        tests/e2e/test_webui_block5_v31322.py `
        docker-compose.yml

git commit -m "feat: День 48 (Блок 5, п.2.3) — фильтры/пагинация/аудит/экспорт WebUI (v3.13.22)

TASK-054 (BUG-087): прокси WebUI ронял заголовки ответа Manager — пагинация
  (X-Total-Count), метаданные фрагмента (X-Fragment-Mode/Hash, X-Bounding-Box)
  и Content-Disposition экспорта. Добавлены HOP_BY_HOP и forwarded_headers();
  set-cookie не пробрасывается (WebUI авторизуется Bearer-заголовком).

TASK-055 (BUG-088): фрагмент грузился через <img src> без Authorization -> 401.
  Теперь fetch + Blob + objectURL с Bearer, метаданные через textContent.

TASK-056 (BUG-089): /api/access/resources и /entries отдавали 500 на PostgreSQL —
  AccessEntry.is_active == 1 вместо == True (boolean = integer).

TASK-057 (BUG-090): фильтр Категория принимает CSV («phone, email»), раньше давал 0.
  Legacy-категории (pii/credentials/code) -> finding_type, остальные -> category,
  объединение через ИЛИ. Пустые числовые параметры больше не 422. Добавлены
  detector, fragment_type, search, order_by=id (list/count/export).
  FastAPI 0.137: BeforeValidator в Annotated теряется при Query() в default —
  Query() перенесён внутрь Annotated, le/ge заменены на _clamp_int.

TASK-058 (BUG-091): event_source не попадал в SQL-фильтр /api/audit — фильтр
  Источник игнорировался. Опции Источник/Тип в UI берутся из /api/audit/stats.

TASK-059 (BUG-093): экспорт findings через window.location.href давал 401 —
  переведён на fetch + Blob + download с именем из Content-Disposition.

Тесты: 33 unit (tests/unit/test_webui_block5_v31322.py) + 8 E2E; 220 unit passed.
Live: v3.13.22, X-Total-Count 667 через прокси, CSV-категории 11/623,
  /api/access/resources 200, event_source=api 44 из 48, export 200 (99 907 B)."
```

```powershell
git add STATE.md ROADMAP.md CHANGELOG.md prompts/reports/day_48_block5_webui_filters_report.md
git commit -m "docs: День 48 — обновлены STATE/ROADMAP/CHANGELOG (v3.13.22)

- STATE.md: день 48 (Блок 5, п.2.3), версия v3.13.22, ключевые решения WebUI,
  FastAPI 0.137 gotcha, список файлов; следующий шаг — п.2.4 (отчёты/архив)
- ROADMAP.md: день 48 ✅, TASK-054…059, статистика v3.0.0 ~89%
- CHANGELOG.md: секция [3.13.22] (Fixed/Changed/Tests/Verified live)
- prompts/reports/day_48_block5_webui_filters_report.md: отчёт дня"
```

---

## ▶️ Инструкция для ручного тестирования

```powershell
# 1. Стек (или текущий: docker compose ps)
$env:VERSION="3.13.22"
docker compose build manager webui
docker compose up -d manager webui
Start-Sleep 20
Invoke-RestMethod http://127.0.0.1:8000/api/health   # version 3.13.22

# 2. UI (http://127.0.0.1:8001, admin/admin123)
#    - «Находки»: пагинация вниз (счётчик «Найдено: N» не обнуляется),
#      Категория «phone, email» -> находки обоих типов, Поиск «secret»,
#      Детектор/Фрагмент, кнопка «Сброс»
#    - Карточка находки с картинкой: фрагмент открывается, подпись
#      «embedded · sha256 9ecadc2f…», hex-дамп справа
#    - «Экспорт» -> csv: файл скачивается (не JSON с 401)
#    - «Аудит»: списки «Источник/Тип» заполнены реальными значениями,
#      фильтр «Источник = api» сокращает выборку
#    - «Ресурсы»/«Права доступа»: страница открывается (было 500)
```

```powershell
# 3. Автотесты
python -m pytest tests/unit/test_webui_block5_v31322.py -v
$env:MANAGER_URL="http://127.0.0.1:8000"; $env:WEBUI_URL="http://127.0.0.1:8001"
python -m pytest tests/e2e/test_webui_block5_v31322.py -v
python -m pytest tests/unit -q          # регрессии: 220 passed
```
