📄 ТЗ: BUG-086 — Расширить mask_context (утечка credentials и US-phone)
Файл: TZ_FIX_BUG086_MASK_CONTEXT.md
Версия: v3.13.20 → v3.13.21
Оценка: ~3–5 ч
Дата: 26.09.2026
Контекст: найдено в Блоке 5 (WebUI deep, п.3 — детали finding)

🎯 Цель
Устранить BUG-086: функция mask_context (scanner/src/encryption.py:113) покрывает только 6 паттернов из 19 заявленных в MASK_RULES. В результате в context_before_masked / context_after_masked попадают незамаскированные credentials и US-телефоны.

Приоритет: 🔴 critical (блокер v3.0.0) — утечка credentials для всех ролей (Viewer+).

📌 Доказательная база
Finding 1439 (slack_token, строка 3 файла database_clean.env)
text
context_before_masked: DATABASE_URL=postgresql://cleanuser:cl***@cl***.local:5432/cleandb
                       GITHUB_TOKEN=ghp_cleanabcdefghijklmnopqrstuvwxyz012345   ← 🔴 СЫРОЙ
context_after_masked:  BASIC_AUTH=Basic Y2xlYW51c2VyOmNsZWFucGFzcw==            ← 🔴 СЫРОЙ
                       API_KEY=sk-clean-12** ******abcdefghijklmnop             ← 🟡 частично
Finding 1461 (phone, строка 2 файла phones_clean.txt)
text
context_before_masked: office: +7***123-45-67    ← ✅ маскировано
context_after_masked:  us: +1 415 555 0199       ← 🔴 СЫРОЙ (US-формат)
Проверки в БД
sql
SELECT id, category, match_text_masked, context_before_masked, context_after_masked
FROM findings WHERE id IN (1439, 1461);

  id  |  category   | match_text_masked |           context_before_masked            |        context_after_masked
------+-------------+-------------------+--------------------------------------------+------------------------------------
 1439 | slack_token | xoxb-***          | DATABASE_URL=...GITHUB_TOKEN=ghp_clean...  | BASIC_AUTH=Basic Y2xlYW51c2VyO...
 1461 | phone       | +7***987-65-43    | office: +7***123-45-67                     | us: +1 415 555 0199
В БД — сырое. Не только API-косметика. Проблема в сканере.

🔍 Корень
Файл: scanner/src/encryption.py

MASK_RULES (полный список, 19 категорий):

python
MASK_RULES = {
    "phone": lambda s: _mask_phone(s),
    "email": _mask_email,
    "api_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "aws_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "password": lambda s: "***",
    "token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "passport": lambda s: (s[:2] + "** ******") if len(s) >= 2 else "***",
    "snils": lambda s: "***-***-*** **",
    "inn": lambda s: (s[:2] + "**********") if len(s) >= 2 else "***",
    "credit_card": lambda s: "**** **** **** " + s[-4:] if len(s) >= 4 else "***",
    "jwt_token": lambda s: (s[:10] + "***") if len(s) > 10 else "***",
    "ssh_key": lambda s: "***ssh-private-key***",
    "github_token": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "slack_token": lambda s: (s[:5] + "***") if len(s) > 5 else "***",
    "discord_token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "database_url": lambda s: re.sub(r"//[^@/]+@", "//***@", s) if "@" in s else "***",
    "basic_auth": lambda s: "Basic ***",
    "high_entropy": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "person": lambda s: s,  # не маскируется
}
mask_context (текущая реализация, ~строка 113):

python
def mask_context(context: str, category: str = None) -> str:
    """Маскирует контекст (строки до/после)."""
    result = re.sub(r"\+?7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
                    lambda m: mask(m.group(), "phone"), result)   # ← только +7
    result = re.sub(r"\S+@\S+\.\S+", lambda m: mask(m.group(), "email"), result)
    result = re.sub(r"\d{4}\s?\d{6}", lambda m: mask(m.group(), "passport"), result)
    result = re.sub(r"\d{3}[\-\s]\d{3}[\-\s]\d{3}[\-\s]\d{2}",
                    lambda m: mask(m.group(), "snils"), result)
    result = re.sub(r"\d{12}", lambda m: mask(m.group(), "inn"), result)
    result = re.sub(r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}",
                    lambda m: mask(m.group(), "credit_card"), result)
    return result
Проблемы:

Хардкодит 6 паттернов, а не использует MASK_RULES.

Параметр category передаётся, но игнорируется.

Phone-regex — только +7. US, EU, другие — не покрыты.

Нет паттернов для: github_token, slack_token, aws_key, api_key, token, password, jwt_token, ssh_key, discord_token, database_url, basic_auth, high_entropy.

🔧 Задача
TASK-053 (BUG-086) — Расширить mask_context
Файл: scanner/src/encryption.py

Требование: mask_context должна покрывать все категории из MASK_RULES (кроме person).

Реализация (рекомендуемая):

python
# Универсальные regex для каждой категории
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
    # Generic password/token в форме KEY=VALUE
    (r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",  "password"),
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+",   "api_key"),
    (r"(?i)(token|secret|access[_-]?key)\s*[:=]\s*\S+", "token"),
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

    BUG-086 (TASK-053, v3.13.21): покрывает все категории из MASK_RULES.
    Порядок паттернов важен — специфичные (github_token, aws_key) раньше
    generic (token). Параметр `category` сохранён для обратной совместимости.
    """
    if not context:
        return context
    result = context
    for pattern, cat in _CONTEXT_PATTERNS:
        result = re.sub(pattern, lambda m, c=cat: mask(m.group(), c), result)
    return result
Важные моменты:

Порядок паттернов — специфичные (ghp_, AKIA, xoxb-) раньше generic (token, api_key).

Параметр category — оставить в сигнатуре (совместимость с managed_scanner.py:762,763,770,771).

high_entropy — сложно регулярить. Отложить (v3.1.0). Или — маскировать все значения [A-Za-z0-9+/=]{32,} (риск ложных срабатываний). Рекомендация: отложить, зафиксировать как BACKLOG-0XX.

person — не маскировать (по решению).

🧪 Тесты
Файл: tests/unit/test_mask_context_v31321.py
python
"""BUG-086 (TASK-053, v3.13.21): mask_context покрывает все категории."""

import pytest
from scanner.src.encryption import mask_context


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
        # Не должен быть "Ivan" в маскированном виде
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
Запуск:

powershell
python -m pytest tests/unit/test_mask_context_v31321.py -v
# ожидание: ~20 passed

python -m pytest tests/unit/ -q
# ожидание: 167 + 20 = 187 passed
📊 Live-проверка (task 40)
1. Обновить
powershell
$env:VERSION="3.13.21"
docker compose build manager webui celery_worker celery_beat
docker compose up -d
curl http://127.0.0.1:8000/api/health  # → 3.13.21
Перезапустить сканер (Ctrl+C → start_scanner.bat).

2. Очистить findings task 39
sql
DELETE FROM findings WHERE task_id = 39;
3. Создать task 40
powershell
$body = @{
  resource_path = "C:\test\scanner_clean"
  name          = "scanner_clean_v3.13.21_mask_fix"
} | ConvertTo-Json

$task = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/tasks/create `
  -Headers @{ Authorization = "Bearer $adminToken" } `
  -ContentType "application/json" -Body $body
$task.id
Дождаться completed.

4. Проверки в SQL
sql
-- Slack_token — контекст НЕ должен содержать сырой github_token
SELECT id, category,
       context_before_masked, context_after_masked
FROM findings
WHERE task_id = 40 AND fragment_path LIKE '%database_clean.env%'
  AND category IN ('slack_token', 'basic_auth', 'database_url')
ORDER BY line_number;
-- ожидание: context_before/after — с ***, без сырых токенов

-- Phone — контекст НЕ должен содержать сырой US-phone
SELECT id, category, context_after_masked
FROM findings
WHERE task_id = 40 AND category = 'phone'
ORDER BY id;
-- ожидание: us: +1 *** *** **** (или похожее с ***)

-- Проверка на сырые паттерны (должно быть 0 строк)
SELECT id, category, context_before_masked, context_after_masked
FROM findings
WHERE task_id = 40
  AND (
    context_before_masked ~ 'ghp_[a-zA-Z0-9]{20,}' OR
    context_after_masked  ~ 'ghp_[a-zA-Z0-9]{20,}' OR
    context_before_masked ~ 'Basic [A-Za-z0-9+/=]{10,}' OR
    context_after_masked  ~ 'Basic [A-Za-z0-9+/=]{10,}' OR
    context_before_masked ~ '\+1[\s\-]?\d{3}[\s\-]?\d{4}' OR
    context_after_masked  ~ '\+1[\s\-]?\d{3}[\s\-]?\d{4}'
  );
-- ожидание: 0 rows
5. Проверка по API
powershell
$base = "http://127.0.0.1:8000/api/findings"

# Найти slack_token
$slack = $null
foreach ($f in $findings) { if ($f.category -eq 'slack_token') { $slack = $f; break } }
$d = Invoke-RestMethod -Method GET "${base}/$($slack.id)" -Headers @{ Authorization = "Bearer $viewerToken" }
Write-Host "Slack context_before: $($d.context_before)"
Write-Host "Slack context_after:  $($d.context_after)"
# ожидание: без сырых github_token / basic_auth

# Найти phone
$phone = $null
foreach ($f in $findings) { if ($f.category -eq 'phone') { $phone = $f; break } }
$d2 = Invoke-RestMethod -Method GET "${base}/$($phone.id)" -Headers @{ Authorization = "Bearer $viewerToken" }
Write-Host "Phone context_after: $($d2.context_after)"
# ожидание: с ***
6. Критерии приёмки
□ pytest tests/unit/test_mask_context_v31321.py -v — ~20 passed
□ pytest tests/unit/ -q — 187 passed (167 + 20), регрессий нет
□ py_compile — OK
□ Manager /api/health → 3.13.21
□ Task 40: context_* не содержит сырых ghp_*, Basic *, xoxb-*, sk-*, +1 *
□ Task 40: context_* сохраняет маскирование email, inn, snils, passport, credit_card
□ E2E-тест добавлен (tests/e2e/test_mask_context_e2e.py): сканирование → проверка через API
□ Обновлены STATE.md, ROADMAP.md, CHANGELOG.md
📝 Сводка правок
#	Файл	Действие	Задача
1	scanner/src/encryption.py	Расширить mask_context — все категории через _CONTEXT_PATTERNS	TASK-053
2	tests/unit/test_mask_context_v31321.py	Создать (~20 тестов)	TASK-053
3	tests/e2e/test_mask_context_e2e.py	Создать (сканирование + API)	TASK-053
4	docker-compose.yml	VERSION → 3.13.21	релиз
5	STATE.md, ROADMAP.md, CHANGELOG.md	BUG-086 → ✅	док
6	docs/admin-guide/05-security.md	Обновить раздел «Маскирование контекста»	док
⚠️ Что НЕ делаем в этом ТЗ
high_entropy в контексте — сложно (нужен расчёт энтропии по подстрокам). Отложить → BACKLOG-087 (v3.1.0).

Пересканирование старых findings в БД — пользователь сам решает, когда пересканировать. В ТЗ — task 40 как пример.

📌 Замечание про существующие данные
Findings в БД (task 39 и раньше) содержат сырые context_*. После фикса кода они не изменятся — нужно пересканировать (task 40).

Рекомендация: после успешного фикса — удалить старые findings с сырыми context_* или пересканировать все активные задачи. Можно добавить в docs/admin-guide/10-troubleshooting.md: «После обновления до 3.13.21 — пересканируйте задачи, чтобы контекст был перемаскирован».

✅ Критерии закрытия ТЗ
□ Все пункты выше выполнены
□ Live-подтверждение: task 40 — context_* без сырых credentials/US-phone
□ STATE.md: BUG-086 → ✅
□ ROADMAP.md: BUG-086 → ✅; BACKLOG-087 (high_entropy в контексте) → 📋 v3.1.0
□ CHANGELOG.md: секция [3.13.21]
🚀 После закрытия
BUG-086 → ✅ (v3.13.21)

BACKLOG-087 → 📋 v3.1.0 — маскирование high_entropy в контексте

Продолжаем Блок 5 — п.4 (reveal + audit)

📋 Общий баг-лист Блока 5 (для фикс-спринта)
ID	Название	Приоритет	Оценка
BUG-082	detector/fragment_type не фильтруются	🟡 v3.1.0	30 мин
BUG-083	order_by=severity — лексикографический	🟢 v3.1.0	20 мин
BUG-084	limit<=0/offset<0 → 500	🟡 v3.0.0	20 мин
BUG-085	/fragment для text_line → 400	🟢 v3.1.0	15 мин
BUG-086	mask_context не покрывает credentials/US-phone	🔴 v3.0.0	3–5 ч
TEST-NOTE-5.2	ARCHITECTURE.md — фильтры	📋 док	—
TEST-NOTE-5.3	Export CSV BOM	🟢 v3.1.0	10 мин
TEST-NOTE-5.4	catalog_entries пуста	📋 док	—
Автор ТЗ: архитектор
Дата: 26.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.21, BUG-086 → ✅