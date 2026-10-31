# 📄 Отчёт: День 47.7 — BUG-086: masking контекстов (TZ_FIX_BUG086_MASK_CONTEXT.md) → v3.13.21

**Дата:** 27.09.2026 (26.09 вечер)
**Версия:** v3.13.20 → **v3.13.21**
**Тип:** fix критического блокера v3.0.0
**Ветка:** `fix/scanner_deep`

---

## 🎯 Задача

**BUG-086 (TASK-053):** `mask_context` (`scanner/src/encryption.py`) маскировал только
**6 паттернов из 19** категорий `MASK_RULES`. В `context_before_masked`/`context_after_masked`
утекали сырые credentials и US-телефоны, и **Viewer+ видел их через API**:

- Finding 1439 (slack_token): `GITHUB_TOKEN=ghp_cleana…` (raw) в `context_before`,
  `BASIC_AUTH=Basic Y2xlYW51c2VyOmNsZWFucGFzcw==` (raw) + `API_KEY=sk-c…` в `context_after`.
- Finding 1461 (phone): `us: +1 415 555 0199` (raw) в `context_after`.

Это соответствовало критичности "🔴🔴 Критичные" (высокий приоритет).

---

## ✅ Сделано

### TASK-053 — `scanner/src/encryption.py` (mask_context → конвейер _CONTEXT_PATTERNS)

`mask_context` переписан полностью. Новая логика — конвейер `_CONTEXT_PATTERNS`:
список `(regex, category)` на ВСЕ категории `MASK_RULES`. Каждый паттерн по очереди
применяется к результату предыдущего. Ключевые решения:

- **Специфичные токены раньше generic** (иначе generic `token` съедал бы `ghp_`-префиксы
  и терялся маркер категории).
- **Generic `KEY=VALUE` маскирует только значение** — паттерны с 2 capture-группами
  `((?:password|passwd|pwd)\s*[:=]\s*)(\S+)`; в `_sub` по `m.lastindex >= 2` значение
  маскируется, префикс (ключ + разделитель) сохраняется. Без этого `GITHUB_TOKEN=ghp_***`
  превращалось бы в `GITHUB_TOKEN=***` (терялся `ghp_`-маркер).
- `person` и `high_entropy` в контексте НЕ маскируются (по решению ТЗ; high_entropy —
  сложный расчёт энтропии, отложен до v3.1.0 — в STATE не привязывал к BACKLOG-087,
  чтобы не путать с дедупликацией фрагментов).
- Сигнатура `mask_context(context, category=None)` сохранена — вызовы в
  `managed_scanner.py:762/763/770/771` не менялись.

### Тесты

- **`tests/unit/test_mask_context_v31321.py`** — 20 тестов (9 credentials + 3 phone +
  5 regressions + 3 edge). ТЗ давал 18; добавлены `test_password_masked` и
  `test_generic_token_masked` → итог **187 passed** (167 + 20).
- **`tests/e2e/test_mask_context_e2e.py`** — 1 тест: контексты **последнего скана**
  через API Manager (роль viewer) не содержат сырых паттернов. Фильтр по `max(task_id)`
  обязателен: исторические findings v≤3.13.19 сохраняют старые контексты и невалидны
  для проверки релиза.

### Live-подтверждение (linux/win dev-стек)

1. `DELETE FROM findings WHERE task_id=39` (по ТЗ).
2. Создан task (после конфликта со старыми процессами-сканерами фактически id **41**).
3. Найдены **4 осиротевших сканера** старых версий (`python run_scanner.py`) — конкурировали
   за задания и первыми выполнили task 40 СТАРЫМ кодом. Убиты все (`Stop-Process -Force`),
   стартовый скрипт через `subprocess.Popen` (Start-Process в shell-обёртке opencode падал),
   запущен единственный сканер → task 41 completed, 29 findings.
4. SQL: `context_before_masked ~ ghp_…|Basic …|xoxb-…|+1…|AKIA…|sk-…` → **0 совпадений**.
5. API (viewer/viewer123): findings 1496/1500/1503/1521/1522 → `raw_in_contexts=False`.
   Контексты теперь: `GITHUB_TOKEN=ghp_*****`, `BASIC_AUTH=Basic ***`,
   `DATABASE_URL=postgresql://***@cleandb.local:5432/…`, `us: 14***199`.
6. E2E против живого стека: `test_mask_context_e2e.py` → **1 passed**.
7. `/api/health` → `{"status":"healthy","version":"3.13.21"}`.

---

## 💻 Код

### TASK-053 — `scanner/src/encryption.py` (замена `mask_context` + новый конвейер)

```python
# BUG-086 (TASK-053, v3.13.21): универсальные regex для каждой категории
# MASK_RULES. Порядок важен — специфичные токены (ghp_, AKIA, xoxb-) раньше
# generic (token/api_key). high_entropy и person НЕ маскируются в контексте
# (high_entropy — сложный расчёт энтропии, отложено до v3.1.0).
_CONTEXT_PATTERNS = [
    # Credentials — специфичные токены (порядок важен: специфичные раньше generic)
    (r"ghp_[a-zA-Z0-9]{20,}",              "github_token"),
    (r"github_pat_[a-zA-Z0-9_]{20,}",      "github_token"),
    (r"xox[baprs]-[a-zA-Z0-9-]{10,}",      "slack_token"),
    (r"AKIA[A-Z0-9]{16}",                  "aws_key"),        # AWS Access Key ID
    (r"sk-[a-zA-Z0-9-]{20,}",              "api_key"),        # OpenAI-style
    (r"sk_live_[a-zA-Z0-9]{20,}",          "api_key"),        # Stripe
    (r"discord[a-zA-Z0-9_-]{20,}",         "discord_token"),  # Discord — упрощённо
    (r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "jwt_token"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----", "ssh_key"),
    (r"Basic [A-Za-z0-9+/=]{10,}",         "basic_auth"),
    (r"[a-z][a-z0-9+.\-]*://[^\s\"']+",    "database_url"),   # postgresql://..., mysql://...
    # Generic password/token в форме KEY=VALUE — две capture-группы:
    # (1) префикс (ключ + разделитель), (2) значение. Маскируется ТОЛЬКО значение.
    (r"(?i)((?:password|passwd|pwd)\s*[:=]\s*)(\S+)",  "password"),
    (r"(?i)((?:api[_-]?key|apikey)\s*[:=]\s*)(\S+)",   "api_key"),
    (r"(?i)((?:token|secret|access[_-]?key)\s*[:=]\s*)(\S+)", "token"),
    # PII
    (r"\S+@\S+\.\S+",                       "email"),
    # Phone: RU + международные
    (r"\+?7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", "phone"),  # RU
    (r"\+1[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}", "phone"),            # US
    (r"\+\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}", "phone"),            # generic intl
    # Passport / SNILS / INN / CC
    (r"\d{4}\s?\d{6}",                       "passport"),
    (r"\d{3}[\-\s]\d{3}[\-\s]\d{3}[\-\s]\d{2}", "snils"),
    (r"\d{12}",                              "inn"),
    (r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}", "credit_card"),
]


def mask_context(context: str, category: str = None) -> str:
    """Маскирует контекст (строки до/после).

    BUG-086 (TASK-053, v3.13.21): покрывает все категории из MASK_RULES
    (конвейер _CONTEXT_PATTERNS). Порядок паттернов важен — специфичные
    (github_token, aws_key) раньше generic (token/api_key). Параметр
    `category` сохранён для обратной совместимости (managed_scanner.py).
    high_entropy/person в контексте не маскируются (по решению).
    """
    if not context:
        return context
    result = context
    for pattern, cat in _CONTEXT_PATTERNS:
        def _sub(m, c=cat):
            # BUG-086: generic KEY=VALUE (2 capture-группы) маскирует только
            # значение; для одиночных паттернов маскируется весь match.
            if m.lastindex and m.lastindex >= 2:
                return m.group(1) + mask(m.group(2), c)
            return mask(m.group(), c)

        result = re.sub(pattern, _sub, result)
    return result
```

### `tests/unit/test_mask_context_v31321.py` (20 тестов)

```python
# tests/unit/test_mask_context_v31321.py — BUG-086 (TASK-053, v3.13.21)
# mask_context покрывает все категории MASK_RULES через _CONTEXT_PATTERNS
# (credentials: github/slack/aws/api_key/basic_auth/database_url/jwt/password/token;
#  телефоны RU/US/международные; регрессии PII; person не маскируется).
"""BUG-086 (TASK-053, v3.13.21): mask_context покрывает все категории."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.encryption import mask_context  # noqa: E402

pytestmark = [pytest.mark.unit]


class TestMaskContextCredentials:
    def test_github_token_masked(self):
        ctx = "GITHUB_TOKEN=ghp_cleanabcdefghijklmnopqrstuvwxyz012345"
        out = mask_context(ctx)
        assert "ghp_cleanabcdefghijklmnopqrstuvwxyz012345" not in out
        assert "ghp_" in out and "***" in out

    def test_slack_token_masked(self):
        ctx = "SLACK_TOKEN=xoxb-clean-1234567890-abcdef"
        out = mask_context(ctx)
        assert "xoxb-clean-1234567890-abcdef" not in out
        assert "xoxb-" in out and "***" in out

    def test_aws_key_masked(self):
        ctx = "AWS_KEY=AKIAIOSFODNN7EXAMPLE"
        out = mask_context(ctx)
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "AKIA" in out and "***" in out

    def test_api_key_masked(self):
        ctx = "API_KEY=sk-clean-1234567890abcdefghij"
        out = mask_context(ctx)
        assert "sk-clean-1234567890abcdefghij" not in out

    def test_basic_auth_masked(self):
        ctx = "BASIC_AUTH=Basic Y2xlYW51c2VyOmNsZWFucGFzcw=="
        out = mask_context(ctx)
        assert "Y2xlYW51c2VyOmNsZWFucGFzcw==" not in out
        assert "Basic ***" in out

    def test_database_url_masked(self):
        ctx = "DATABASE_URL=postgresql://cleanuser:cleanpass@cleandb.local:5432/cleandb"
        out = mask_context(ctx)
        assert "cleanpass" not in out
        assert "cleanuser" not in out

    def test_jwt_token_masked(self):
        ctx = "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdef"
        out = mask_context(ctx)
        assert "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdef" not in out

    def test_password_masked(self):
        ctx = "password=supersecret123"
        out = mask_context(ctx)
        assert "supersecret123" not in out

    def test_generic_token_masked(self):
        ctx = "secret=abcdefghijklmnopqrstuvwxyz"
        out = mask_context(ctx)
        assert "abcdefghijklmnopqrstuvwxyz" not in out


class TestMaskContextPhone:
    def test_ru_phone_masked(self):
        ctx = "office: +7 999 123-45-67"
        out = mask_context(ctx)
        assert "+7 999 123-45-67" not in out

    def test_us_phone_masked(self):
        """BUG-086: US-формат (не покрыт раньше)."""
        ctx = "us: +1 415 555 0199"
        out = mask_context(ctx)
        assert "+1 415 555 0199" not in out

    def test_us_phone_with_parens(self):
        ctx = "us: +1 (415) 555-0199"
        out = mask_context(ctx)
        assert "+1 (415) 555-0199" not in out


class TestMaskContextRegressions:
    """Старые категории (email, inn, snils, passport, credit_card) — не сломать."""

    def test_email_masked(self):
        ctx = "contact: user@example.com"
        out = mask_context(ctx)
        assert "user@example.com" not in out

    def test_inn_masked(self):
        ctx = "inn: 771234567890"
        out = mask_context(ctx)
        assert "771234567890" not in out

    def test_passport_masked(self):
        ctx = "passport: 4510 123456"
        out = mask_context(ctx)
        assert "4510 123456" not in out

    def test_credit_card_masked(self):
        ctx = "card: 4532 1234 5678 9010"
        out = mask_context(ctx)
        assert "4532 1234 5678 9010" not in out

    def test_person_not_masked(self):
        """person — не маскируется (по решению)."""
        ctx = "person: Ivan Ivanov"
        out = mask_context(ctx)
        assert "person: Ivan Ivanov" == out  # без изменений


class TestMaskContextEdge:
    def test_empty_context(self):
        assert mask_context("") == ""
        assert mask_context(None) is None

    def test_no_secrets(self):
        ctx = "plain text without secrets"
        assert mask_context(ctx) == ctx

    def test_multiple_secrets(self):
        ctx = "GITHUB_TOKEN=ghp_abc123456789012345678901234567890123\nBASIC_AUTH=Basic dXNlcjpwYXNz"
        out = mask_context(ctx)
        assert "ghp_abc123456789012345678901234567890123" not in out
        assert "dXNlcjpwYXNz" not in out
```

### `tests/e2e/test_mask_context_e2e.py` (1 тест)

```python
"""E2E-тест BUG-086 (v3.13.21): контексты findings не содержат сырых секретов.

Сценарий: через API Manager проверить, что context_before / context_after
(API отдаёт уже маскированные значения) находок не содержат сырых
credentials/US-phone (ghp_, Basic base64, xoxb-, sk-, AKIA, +1 …).
Требует пересканированных данных (см. task 40 в ТЗ).
"""
import re

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]

# Сырые паттерны, которые НЕ должны встречаться в контекстах
_RAW_PATTERNS = {
    "github_token": r"ghp_[a-zA-Z0-9]{20,}",
    "basic_auth": r"Basic [A-Za-z0-9+/=]{10,}",
    "slack_token": r"xox[baprs]-[a-zA-Z0-9-]{10,}",
    "aws_key": r"AKIA[A-Z0-9]{16}",
    "api_key": r"sk-[a-zA-Z0-9-]{20,}",
    "us_phone": r"\+1[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}",
}
_RAW_RE = {k: re.compile(v) for k, v in _RAW_PATTERNS.items()}

_SCOPE = ("github_token", "slack_token", "aws_key", "api_key", "basic_auth",
          "database_url", "jwt_token", "phone", "password", "token")


def test_contexts_have_no_raw_secrets(manager_url, api_client):
    """BUG-086: в контекстах findings последнего скана нет сырых credentials."""
    r = api_client.get(f"{manager_url}/api/findings", params={"limit": 1000}, timeout=15)
    assert r.status_code == 200
    findings = r.json() or []
    # Старые findings (v<=3.13.19) могут содержать raw — BUG-086 мог их покрыть;
    # проверяем только findings последнего (актуального) скана.
    task_ids = {f.get("task_id") for f in findings if f.get("task_id")}
    if not task_ids:
        pytest.skip("Нет findings в системе")
    latest = max(task_ids)
    latest_findings = [f for f in findings if f.get("task_id") == latest]
    scoped = [f for f in latest_findings if f.get("category") in _SCOPE]
    if len(scoped) < 2:
        pytest.skip("Недостаточно findings категорий BUG-086 (пересканируйте, см. task 40)")

    checked = 0
    for f in scoped:
        cat = f.get("category")
        for field in ("context_before", "context_after"):
            ctx = f.get(field)
            if not ctx:
                continue
            for raw_name, rx in _RAW_RE.items():
                assert not rx.search(ctx), (
                    f"finding {f['id']} ({cat}) field {field}: сырой паттерн {raw_name}: {ctx!r}"
                )
            checked += 1
    assert checked > 0, "нет контекстов для проверки"
```

---

## 📁 Файлы

| Файл | Изменение |
|------|-----------|
| `scanner/src/encryption.py` | TASK-053 (BUG-086): `_CONTEXT_PATTERNS` + конвейер `mask_context` |
| `tests/unit/test_mask_context_v31321.py` | NEW, 20 тестов |
| `tests/e2e/test_mask_context_e2e.py` | NEW, 1 тест |
| `docker-compose.yml` | manager/webui/celery → 3.13.21 |
| `STATE.md` | день 47.7, версия v3.13.21, ключевые решения, файлы |
| `ROADMAP.md` | строка 47.7, TASK-053, статистика (~88%), версия |
| `CHANGELOG.md` | секция [3.13.21] (Fixed/Changed/Tests/Verified live) |
| `docs/admin-guide/05-security.md` | §4.1 Маскирование контекстов (BUG-086) |
| `docs/admin-guide/10-troubleshooting.md` | §3.4 сырые credentials в контекстах |
| `prompts/reports/day_47.7_fix_bug086_mask_context_report.md` | этот отчёт |
| `prompts/archive/TZ_FIX_BUG086_MASK_CONTEXT.md` | ТЗ перемещено |

---

## 🧪 Результаты тестов

```
tests/unit/test_mask_context_v31321.py ............ 20 passed
tests/unit/ ........................................ 187 passed (61.47s)
tests/e2e/test_mask_context_e2e.py (live, MANAGER_URL) ... 1 passed
```

Полный прогон `pytest tests/unit/ -q` → **187 passed, 279 warnings**.

Прочие инструменты: `python -m py_compile scanner/src/encryption.py` → OK.
Баг, обнаруженный в процессе: у простого регекспа с generic `KEY=VALUE` маскировался весь
match (ключ вместе с значением) — исправлено второй capture-группой; тесты
`test_github_token_masked`/`test_slack_token_masked` это ловили (`ghp_`/`xoxb-` маркер обязателен).

---

## 🔴 Команда для коммита

```bash
# 1. Код
git add scanner/src/encryption.py tests/unit/test_mask_context_v31321.py tests/e2e/test_mask_context_e2e.py docker-compose.yml
git commit -F temp/commit_msg_31321_code.txt

# 2. Доки
git add STATE.md ROADMAP.md CHANGELOG.md docs/admin-guide/05-security.md docs/admin-guide/10-troubleshooting.md prompts/reports/day_47.7_fix_bug086_mask_context_report.md prompts/archive/TZ_FIX_BUG086_MASK_CONTEXT.md
git commit -F temp/commit_msg_31321_docs.txt
```

Сообщения (temp-файлы, т.к. PS ломает `-m`) — `temp/commit_msg_31321_code.txt`:

```text
feat: День 47.7 — BUG-086: masking контекстов (v3.13.21)

- сканер/src/encryption.py: mask_context → конвейер _CONTEXT_PATTERNS
- 21 паттерн на все категории MASK_RULES (было 6 из 19)
- специфичные токены (ghp_/AKIA/xoxb-) раньше generic; generic KEY=VALUE
- маскирует только значение (2 capture-группы); person/high_entropy в
- контексте не маскируются
- тесты: test_mask_context_v31321.py (20), test_mask_context_e2e.py (1)
- unit total 187 passed; live-проверка task 41 — 0 сырых контекстов
- docker-compose.yml → 3.13.21
```

`temp/commit_msg_31321_docs.txt`:

```text
docs: День 47.7 — обновлены STATE/ROADMAP/CHANGELOG/docs (v3.13.21)

- STATE.md: день 47.7, BUG-086 закрыт (TASK-053), ключевые решения
- ROADMAP.md: строка 47.7, закрытые TASK-053, статистика, версия
- CHANGELOG.md: секция [3.13.21] (Fixed/Changed/Tests/Verified live)
- docs/admin-guide/05-security.md: §4.1 маскирование контекстов
- docs/admin-guide/10-troubleshooting.md: §3.4 сырые credentials в контекстах
- отчёт day_47.7_fix_bug086_mask_context_report.md; ТЗ в prompts/archive/
```

---

## 🚀 Инструкция по запуску/проверке (ручное тестирование)

```powershell
# 1. Релиз
$env:VERSION="3.13.21"
docker compose build manager webui celery_worker celery_beat
docker compose up -d manager webui celery_worker celery_beat
Invoke-RestMethod http://127.0.0.1:8000/api/health   # {"version":"3.13.21"}

# 2. Регрессия (unit) — с корня репо
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
python -m pytest tests/unit/ -q     # 187 passed

# 3. E2E (живой стек)
$env:MANAGER_URL='http://127.0.0.1:8000'
python -m pytest tests/e2e/test_mask_context_e2e.py -v   # 1 passed

# 4. Live-проверка
# (а) убить осиротевшие старые сканеры, если есть:
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run_scanner.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# (б) заново запустить единственный сканер (env-ключи findings из secrets/):
#     python temp\launch_scanner.py  (или start_scanner.bat)

# (в) SQL-проверка (dev — SQLite manager/dcap.db; Docker — psql):
#     SELECT id FROM findings WHERE task_id=<latest>
#     AND (context_before_masked ~ 'ghp_…|Basic …|xoxb-…|\+1…|AKIA…|sk-…'
#          OR context_after_masked ~ '…')   → 0 строк

# (г) API-проверка (viewer):
$tok=(Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType 'application/json' -Body '{"username":"viewer","password":"viewer123"}').access_token
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/findings/<id>" -Headers @{Authorization="Bearer $tok"}
#    → context_before/context_after без сырых credentials/телефонов
```

---

## 📦 Следующий шаг

Блок 5 (WebUI) — продолжить с п.2.3 (фильтры). BUG-086 закрыт (TASK-053, v3.13.21).