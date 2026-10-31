# Отчёт: Фикс-спринт Блок 9 (v3.13.28)

**Дата:** 03.10.2026
**Версия:** v3.13.27 → **v3.13.28**
**ТЗ:** `prompts/tz/TZ_FIX_BLOCK9_SECURITY.md`
**Ветка:** `develop`

---

## 1. Кратко

Закрыты **10 багов безопасности** из фикс-спринта Блока 9:
BUG-103, 105, 106, 107, 108, 110, 111, 114, 115, 116.

Попутно найден и исправлен **регресс зависимости**, из-за которого свежая сборка
образа не запускалась на PostgreSQL (`ModuleNotFoundError: No module named 'psycopg'`).

**Тесты:** unit `317 → 359` (+42 новых, регрессий нет), E2E `46 passed / 12 skipped`
против живого Manager, весь набор `408 passed / 17 skipped`.

Два бага из списка — **эшелонированная защита**, а не эксплуатируемые дыры
(BUG-115 и, частично, BUG-106): анонимный доступ к `/api/*` и раньше закрывал
`AuthMiddleware`. Подробности и доказательства — в §2 (BUG-115) и §4.1.

Обнаружен **предсуществующий баг вне scope** — потолок параллелизма 15 вместо 30
(§4.1); из-за него `tests/load` не проходит.

---

## 2. Исправленные баги

### BUG-115 🟡 medium — `/api/findings/count` без явного `require_auth`
**📁 `manager/src/api/findings.py`**

Маршрут не декларировал `Depends(require_auth)`, полагаясь только на
`AuthMiddleware`, закрывающий `/api/*`.

**Важное уточнение:** анонимный доступ фактически **уже блокировался**
middleware — проверено на работающем v3.13.27: анонимный запрос к `/count`
даёт `401` с заголовком `WWW-Authenticate: Negotiate`, то есть ответ приходит из
`AuthMiddleware._auth_required_headers()`, а не из роутера. Поэтому это
**эшелонированная защита, а не открытая утечка**: маршрут не имел собственной
проверки и зависел от того, что middleware нигде не будет ослаблен или пробрасывающую
цепочку (например, WebUI-прокси) не обойдут.

**Решение:** `Depends(require_auth)` на маршрут. E2E-тест фиксирует контракт
(аноним → 401, с JWT → 200), но как **регрессионный** тест на этот баг он
слабый: тот же 401 давал и старый код. Настоящая проверка — наличие
`Depends` в сигнатуре маршрута, она есть в unit-тесте.

### BUG-110 🔴 critical — reveal падал в 500 при недоступном ключе
**📁 `manager/src/api/findings.py`**

Ошибка `decrypt()` пробрасывалась наружу.

**Решение:** отлов `ValueError` → `409 Conflict` (не 500) + аудит-событие
`finding_reveal_failed`. Успешный reveal остался `200`.

### BUG-114 🟠 high — экспорт находок не аудировался
**📁 `manager/src/api/findings.py`**

Событие создавалось, но без `source_host` (источник выгрузки не установить),
`file_path` писался одним значением вместо списка.

**Решение:** `request` в сигнатуре, `source_host` из клиента, агрегация
`file_path` (до 10 путей, остальные сворачиваются в `...`).

### BUG-111 🟠 high — ошибка расшифровки роняла список находок
**📁 `manager/src/api/findings.py`**

`_resolve_text()` не перехватывал исключение: одна «битая» находка валила
весь `GET /api/findings`.

**Решение:** `except Exception` → masked-заглушка, листинг остаётся доступным.

### BUG-107 🟠 high — CRL не проверялся
**📁 `manager/src/core/security.py`, `manager/src/auth/middleware.py`**

CRL была сгенерирована, но не проверялась нигде — отозванный сертификат
считался валидным.

**Решение:**
- `ssl.VERIFY_CRL_CHECK_LEAF` в `get_server_ssl_context()`;
- `_check_mtls()`: `getpeercert(binary_form=True)` → `is_revoked(der)` → **401**;
- конвертация DER↔PEM (`_to_pem()`).

### BUG-108 🟠 high — `run_manager.py` игнорировал `CertificateManager`
**📁 `run_manager.py`**

Собственный `ssl.SSLContext` без проверки CRL и без единой точки конфигурации.

**Решение:** `get_server_ssl_context()`; strict → `CERT_REQUIRED`,
relaxed → `CERT_OPTIONAL`; `${VAR:-default}` через `_resolve_env`.

### BUG-106 🟡 medium — machine-эндпоинты не проходили mTLS
**📁 `manager/src/auth/middleware.py`**

`_is_public()` включал `/api/scanner*`, `/api/audit/agents/*`,
`/api/audit/events`, а `_check_mtls()` в `dispatch()` не вызывался.

**Решение:** machine-prefixes исключены из public, `_check_mtls()` вызывается
явно, CN клиента → `request.state.client_cert_cn`.

### BUG-105 🟡 medium — неверный каталог PKI в контейнере
**📁 `docker-compose.yml`**

`./manager/certs:/app/certs`, тогда как `scripts/generate_certs.py` пишет
в `./certs`. При `mtls_enabled=true` Manager не находил PKI.

**Решение:** `./certs:/app/certs:ro`.

### BUG-103 🟡 medium — метрики не видели 401 и раздували cardinality
**📁 `manager/src/metrics.py`, `manager/src/main.py`**

`MetricsMiddleware` стоял **внутри** `AuthMiddleware` — отказы авторизации не
попадали в `dcap_http_requests_total`. Метка `endpoint` бралась из сырого пути:
каждый `/api/findings/{id}` создавал новую серию.

**Решение:** middleware зарегистрирован последним (outermost); нормализация
через шаблон маршрута с regex-fallback (`{id}`, `{uuid}`, `{hash}`).

Порядок подтверждён вживую: `Metrics → RateLimit → Auth → CORS`.

### BUG-116 🟡 medium — reencrypt ломал дедупликацию
**📁 `scripts/reencrypt_findings.py`, `webui/templates/findings.html`, `webui/static/js/findings.js`**

После ротации `hmac_key` все fingerprint'ы пересчитывались, но дубликаты не
помечались; UI не знал о статусе `duplicate`.

**Решение:** пересчёт FP новым ключом (`Resource.path` + plaintext match +
line + finding_type), флаги `--dedup` / `--delete-duplicates`, статус
`duplicate` + фильтр и badge в WebUI. Plaintext захватывается **до** записи
нового ciphertext, иначе расшифровка была бы невозможна.

---

## 3. Регресс зависимости (вне scope, но блокировал E2E)

**📁 `manager/src/db/session.py`, `manager/src/db/migrations/env.py`**

Тестовый Manager падал при инициализации БД:

```
ModuleNotFoundError: No module named 'psycopg'
  .../sqlalchemy/dialects/postgresql/psycopg.py", line 497, in import_dbapi
```

**Причина.** `requirements.txt` не закрепляет SQLAlchemy. Рабочий образ
`dcap/manager:3.13.27` содержал SQLAlchemy **2.0.54**, где голая схема
`postgresql://` по умолчанию использует `psycopg2`. Свежая сборка подтянула
**2.1.3**, где дефолт — psycopg **v3**, которого в проекте нет (ставится
`psycopg2-binary`). Старый образ маскировал проблему.

**Решение:** `_normalize_url()` — явная схема `postgresql+psycopg2://`.
Используется в `session.py` и в Alembic `env.py`. Явно указанные драйверы
(`+psycopg`, `+pg8000`) не трогаются.

Проверено:

| Вход | Выход |
|------|-------|
| `postgresql://u:p@h:5432/db` | `postgresql+psycopg2://u:p@h:5432/db` |
| `postgresql+psycopg2://…` | без изменений |
| `postgresql+psycopg://…` | без изменений |
| `sqlite:///manager/dcap.db` | без изменений |

> 📌 **Рекомендация архитектору:** закрепить версию SQLAlchemy в
> `requirements.txt`, иначе проблема вернётся при следующем обновлении.

---

## 4. Тесты

### Новые файлы

| Файл | Тестов | Покрытие |
|------|--------|----------|
| `tests/unit/test_security_block9_v31328.py` | **42** | все 10 багов |
| `tests/e2e/test_security_block9_e2e_v31328.py` | **5** | BUG-103/110/114/115 против живого Manager |

### Результаты

| Набор | До | После | Комментарий |
|-------|-----|-------|-------------|
| `tests/unit` | 317 passed | **359 passed** | +42 новых, регрессий нет |
| `tests/e2e` | — | **46 passed, 12 skipped** | живой Manager `:18000` |
| `tests` (весь набор) | — | **408 passed, 17 skipped** | без `tests/load`, см. §4.1 |
| `tests/load` | 1 passed, 1 failed | 1 passed, **1 failed** | упирается в пул БД, см. §4.1 |
| `manager/tests` | 44 passed, 1 failed | 44 passed, **1 failed** | падение пре-существующее |
| `manager/tests/test_security.py` | 16 passed | 16 passed | без изменений |
| `tests/unit/test_reencrypt.py` | 4 passed | 4 passed | без изменений |

**Пре-существующее падение (не связано со спринтом):**
`manager/tests/test_retention.py::test_archiver_findings` —
`TypeError: 'file_path' is an invalid keyword argument for Finding`
(в модели поле называется `fragment_path`).

### 4.1 Открытый баг: потолок параллелизма 15 вместо 30

`tests/load/test_api_load.py::test_get_findings_load` (100 запросов, 20 потоков)
упирается в `sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20
reached, connection timed out, timeout 30.00` и падает на read-таймаутах.

**Механизм.** `AuthMiddleware.dispatch` (`manager/src/auth/middleware.py:225-234`)
открывает сессию для пользователя JWT и делает `return await call_next(request)`
**внутри** `try`, поэтому `finally: db.close()` срабатывает только после того, как
весь downstream-хендлер отработает. Это осознанное решение BUG-048b (иначе
`DetachedInstanceError` при чтении ролей). Итог: авторизованный запрос держит
**одновременно 2 соединения** — сессию middleware плюс сессию эндпоинта.

```
пул: pool_size=10 + max_overflow=20 = 30
потолок: 30 / 2 = 15 одновременных авторизованных запросов
```

**Подтверждено экспериментом** (свежий Manager, без других нагрузок):

| Потоков | Время | Ошибок |
|---------|-------|--------|
| 8 | 0.3 с | 0 |
| 12 | 0.4 с | 0 |
| 14 | 0.5 с | 0 |
| **15** | **0.6 с** | **0** |
| **16** | **30.6 с** | **1** |
| 18 | 30.6 с | 2 |

Порог ровно на 16 = `2 × 16 > 30`. Утечки соединений нет: `pg_stat_activity`
показывает `idle in transaction = 0` до и после каждого прогона; 200
последовательных запросов — 2.8 с без единой ошибки.

**Баг предсуществующий** и не связан со спринтом: `require_auth` сессию не
открывает (берёт пользователя из `request.state`), второй запрос соединения
приходит из самого middleware.

**Рекомендуемый фикс:** грузить роли eagerly (`selectinload(User.roles)`) внутри
сессии middleware и закрывать её **до** `call_next`. Тогда роли уже материализованы
и `DetachedInstanceError` не вернётся, а запрос будет держать одно соединение —
потолок станет 30. Занесено в `STATE.md` как 🔴 на v3.1.0.

**Почему не исправлено здесь:** спринт — безопасность (Блок 9), правка затрагивает
жизненный цикл сессии в auth-middleware и рискует регрессией BUG-048b. Требует
отдельного решения архитектора.

### Ручная проверка вживую

- BUG-115: аноним → **401**, с JWT → `{"count": 2}`.
- BUG-103: `dcap_http_requests_total{endpoint="/api/findings/count",method="GET",status="401"} 1.0` —
  отказы считаются; raw-ID в метках отсутствуют.
- BUG-114: событие `findings_exported` присутствует в `/api/audit` с непустым `source_host`.

---

## 5. Найдено попутно (вне scope)

### 5.1 Manager не маскирует контексты сам — доверяет суффиксу `_masked`

Проверено вручную: при отправке `context_before_masked` с сырым
`ghp_.../AKIA.../Basic ...` значение сохраняется в БД **дословно** и
отдаётся через API без изменений. То есть защита BUG-086 целиком зависит
от корректности сканера; компрометация сканера кладёт сырые секреты в БД.

Поле в БД: `Finding.context_before_masked` / `context_after_masked`
(`manager/src/db/models.py:138`). Ingest — `manager/src/api/scanner.py:515`.

**Рекомендация:** defensive-маскирование на стороне Manager (аналогично
`_resolve_text` из BUG-111). Занесено в `STATE.md` как открытая проблема.

### 5.2 Голый `pytest` не запускался вообще

`tests/unit/test_scanner_findings.py` и `tests/e2e/test_scanner_findings.py`
(а также `test_webui_block5_v31322.py`) имеют одинаковые базовые имена. В режиме
`prepend` pytest импортирует первый файл под общим именем модуля, и сборка
второго падает с `import file mismatch`. Так как в `pyproject.toml` задан
`testpaths = ["tests"]`, команда `pytest` без аргументов падала на сборе.

**Решение:** `addopts` дополнен `--import-mode=importlib` — каждый файл получает
собственное имя модуля. `sys.path` для `fixtures.*` уже добавляется в
`tests/conftest.py:9`, поэтому импорты не сломались. Сейчас собирается
**429 тестов** без ошибок, и unit + e2e можно гонять одной командой.

### 5.3 Эндпоинты-тесты зависят от наличия данных

`tests/e2e/test_webui_block5_v31322.py` и `test_mask_context_e2e.py` падают на
свежей БД: первый требует `X-Total-Count > 0`, второй — непустые контексты.
Это не регрессии (проверено: после наполнения данными проходят). Тесты
используют фикстуру `cleanup_tasks`, которая удаляет findings после каждого
кейса, поэтому опираются на данные, оставленные другим прогоном. Стоит
сделать их самодостаточными (seed внутри теста) — отдельная задача.

---

## 6. Изменённые файлы

### Код
| Файл | Изменения |
|------|-----------|
| `manager/src/auth/middleware.py` | BUG-106, 107: machine ≠ public, вызов `_check_mtls()`, CRL-проверка |
| `manager/src/core/security.py` | BUG-107, 108: CRL, `_to_pem`, `_apply_crl`, `_env_bool`, strict=`CERT_REQUIRED` |
| `run_manager.py` | BUG-108: `get_server_ssl_context()`, `_resolve_env` |
| `manager/src/api/findings.py` | BUG-110/111/114/115: reveal 409, masked fallback, аудит экспорта, `require_auth` |
| `manager/src/metrics.py` | BUG-103: нормализация метки `endpoint` |
| `manager/src/main.py` | BUG-103: `MetricsMiddleware` последним |
| `scripts/reencrypt_findings.py` | BUG-116: пересчёт FP, `--dedup`, `--delete-duplicates` |
| `manager/src/db/session.py` | `_normalize_url()` — фикс регресса psycopg |
| `manager/src/db/migrations/env.py` | `_normalize_url()` в Alembic |
| `webui/templates/findings.html` | BUG-116: фильтр статуса `duplicate` |
| `webui/static/js/findings.js` | BUG-116: badge `duplicate` |
| `docker-compose.yml` | BUG-105: `./certs` mount; VERSION 3.13.28 |
| `.env`, `.env.example` | VERSION 3.13.28 |

### Тесты
- `tests/unit/test_security_block9_v31328.py` (новый, 42)
- `tests/e2e/test_security_block9_e2e_v31328.py` (новый, 5)

### Документация
- `CHANGELOG.md` — раздел `[3.13.28]`
- `STATE.md` — версия, статус, таблица дней, открытые проблемы, файлы
- `ROADMAP.md` — Блок 9 закрыт, 10 BUG в «Закрытые», версия
- `ARCHITECTURE.md` — mTLS (CRL/BUG-105/106), метрики (порядок middleware)
- `SECURITY.md` — проверка CRL, machine-эндпоинты, путь PKI

---

## 7. Воспроизведение

```bash
# Тестовый стенд (изолированный проект dcap-test)
docker compose -p dcap-test -f docker-compose.test.yml up -d --build

# Unit
python -m pytest tests/unit -q

# E2E (нужен живой Manager на :18000)
python -m pytest tests/e2e -q

# Проверка метрик
curl http://localhost:18000/metrics | grep dcap_http_requests_total
```

⚠️ Не выполнять `docker compose -f docker-compose.test.yml down --remove-orphans` —
teardown должен явно указывать `-p dcap-test`, иначе сносится основной стек.

---

## 8. Статус

| Блок | Статус |
|------|--------|
| 1, 2, 3, 4, 5, 7, 8 | ✅ закрыты (ранее) |
| **9 (Безопасность)** | ✅ **закрыт (v3.13.28)** |
| 6 (Агенты) | 📋 следующий |
| 11 (Отказоустойчивость) | 📋 |
| GitHub-пакет / релиз v3.0.0 | 📋 |
