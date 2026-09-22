Файл: TZ_FIX_SPRINT_7.md
Версия: v3.13.15 → v3.13.16
Оценка: ~1 ч
Дата: 22.09.2026
Контекст: после live-прогона v3.13.15 на C:\test\scanner_clean (task 34)

Цель
Устранить BUG-075 — Presidio URL recognizer ловит доменную часть email-адреса как отдельный url-finding. Из-за этого в task 34 появилось 5 url вместо 0.

Файл: scanner/classifiers/pii_classifier.py
Функция: _filter_url_over_email_finding

Доказательная база (task 34, C:\test\scanner_clean)
5 url — все из email-строк
id	line	файл	Гипотеза match_text	Источник
1328	1	mixed_clean.txt	corp.example	dave.clean@corp.example
1337	5	emails_clean.txt	company.example	carol.new@company.example
1338	1	emails_clean.txt	example.org	alice.new@example.org
1339	1	emails_clean.txt	example.org (дубль 1338)	alice.new@example.org
1340	3	emails_clean.txt	test.example	bob.new@test.example
Проблема: в этих строках нет ://, поэтому текущее условие "://" in line не срабатывает → url не отбрасывается.

Дополнительно: id 1338/1339 — дубликат url в одной строке (разные start_pos/end_pos → дедупликатор не схлопнул).

Что работает правильно
Email: 5 сохранены (4 presidio + 1 ocr), 3 шума из URL-логинов правильно отброшены ✅

organization = 0 ✅

uk_nhs = 0 ✅

date_time / person = 0 ✅

OCR image_region = 2, bounding_box = 2 ✅

Задача
TASK-040 (BUG-075) — расширить _filter_url_over_email_finding
Файл: scanner/classifiers/pii_classifier.py
Функция: _filter_url_over_email_finding (после правок ТЗ №6 — строка ~654+)

Текущая логика (v3.13.15):

Работает по line_text: если в строке есть :// и @/email-паттерн — отбрасывает все url/email из этой строки.

Проблема: carol.new@company.example — нет ://, но Presidio вернул и email, и url (company.example). Фильтр не срабатывает.

Требуемая логика:

Сохранить текущую логику (строки с :// + email → отбросить url/email).

Добавить: собирать все email-строки из findings (по match_text email-finding'ов) и email-паттерны из line_text.

Добавить: отбрасывать url, если его match_text целиком содержится в каком-либо email-значении (case-insensitive).

Новая реализация (заменить функцию целиком):

python
def _filter_url_over_email_finding(self, findings: List[Finding]) -> List[Finding]:
    """BUG-066b + BUG-071 + BUG-074 + BUG-075 (TASK-033/037/040, v3.13.16).

    Покрывает 3 случая:

    1. url-over-email: 'http://user@host/path'
       → Presidio обрезает url по '@', спаны url/email не пересекаются.
       Работаем по line_text: если строка содержит '://' И email-признак
       ('@' или email-паттерн) — отбрасываем все url/email этой строки.

    2. credentials-URL: 'postgresql://user:pass@host:port/db'
       → Presidio находит email в user:pass@host. Отбрасываем email
       из строк с '://' (уже покрыто п.1).

    3. BUG-075: Presidio URL recognizer ловит доменную часть email
       ('company.example' для 'carol.new@company.example'). В таких
       строках НЕТ '://', поэтому п.1 не срабатывает. Отбрасываем url,
       чей match_text целиком входит в какой-либо email (по match_text
       email-finding'ов или по email-паттернам из line_text).
    """
    import re

    EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")

    # 1. Строки с URL-схемой + email-признаком → все url/email отбросить
    skip_lines: set = set()
    for f in findings:
        line = f.line_text or ""
        if "://" in line and ("@" in line or EMAIL_RE.search(line)):
            skip_lines.add((f.line_number, f.fragment_path))

    # 2. Собрать все email-значения (match_text email-finding'ов
    #    + email-паттерны из line_text) — для BUG-075
    email_values: set = set()
    for f in findings:
        if f.category in ("email", "PII_EMAIL"):
            v = (f.match_text or "").strip().lower()
            if v:
                email_values.add(v)
        line = f.line_text or ""
        for m in EMAIL_RE.finditer(line):
            email_values.add(m.group(0).strip().lower())

    # 3. Фильтрация
    filtered: List[Finding] = []
    for f in findings:
        cat = f.category
        if cat in ("url", "PII_URL", "email", "PII_EMAIL"):
            # 3a. Строка с :// и email → пропустить (BUG-071/074)
            if (f.line_number, f.fragment_path) in skip_lines:
                continue
            # 3b. url, входящий в email → пропустить (BUG-075)
            if cat in ("url", "PII_URL"):
                url_val = (f.match_text or "").strip().lower()
                if url_val and any(url_val in em for em in email_values):
                    continue
        filtered.append(f)
    return filtered
Тесты (smoke-проверки)
Файл: tests/unit/test_pii_filters_v31316.py (создать)

python
"""Smoke-тесты фильтра url-over-email для v3.13.16 (TASK-040, BUG-075)."""

from scanner.src.finding import Finding
from scanner.classifiers.pii_classifier import PiiClassifier


def _f(category, line, match, line_text, start=0, end=10, fpath="C:/t.txt"):
    return Finding(
        line_number=line, line_text=line_text, match_text=match,
        start_pos=start, end_pos=end,
        finding_type="pii", category=category,
        fragment_path=fpath,
    )


class TestBug075UrlInEmail:
    """BUG-075: url = доменная часть email (без '://' в строке)."""

    def setup_method(self):
        self.c = PiiClassifier()

    def test_domain_of_email_removed(self):
        """carol.new@company.example → email ok, url 'company.example' отброшен."""
        line = "plain: carol.new@company.example"
        findings = [
            _f("email", 5, "carol.new@company.example", line, 7, 33),
            _f("url",   5, "company.example",           line, 18, 33),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        cats = [f.category for f in out]
        assert "url" not in cats
        assert "email" in cats

    def test_multiple_urls_same_line_removed(self):
        """Дубль url (1338/1339) в одной строке — оба отброшены."""
        line = "contact: alice.new@example.org"
        findings = [
            _f("email", 1, "alice.new@example.org", line, 9, 30),
            _f("url",   1, "example.org",           line, 19, 30),
            _f("url",   1, "example.org",           line, 18, 29),  # дубль
        ]
        out = self.c._filter_url_over_email_finding(findings)
        cats = [f.category for f in out]
        assert cats.count("url") == 0
        assert cats.count("email") == 1

    def test_real_url_kept(self):
        """URL без email в строке — сохраняется."""
        line = "visit https://example.com/page for details"
        findings = [
            _f("url", 1, "https://example.com/page", line, 6, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1
        assert out[0].category == "url"

    def test_email_without_url_kept(self):
        """Email без url-finding — сохраняется."""
        line = "contact: alice.new@example.org"
        findings = [
            _f("email", 1, "alice.new@example.org", line, 9, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1
        assert out[0].category == "email"


class TestRegressionPrevious:
    """Регрессия ТЗ №6 (BUG-071/074) — не должны сломаться."""

    def setup_method(self):
        self.c = PiiClassifier()

    def test_url_over_email_with_scheme_removed(self):
        """http://bob.new@test.example/x → url и email отброшены."""
        line = "url: http://bob.new@test.example/x"
        findings = [
            _f("email", 4, "bob.new@test.example", line, 15, 35),
            _f("url",   4, "http://bob.new",       line, 5, 20),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 0

    def test_credentials_url_email_removed(self):
        """postgresql://user:pass@host/db → email отброшен."""
        line = "DATABASE_URL=postgresql://cleanuser:cleanpass@cleandb.local:5432/cleandb"
        findings = [
            _f("email", 1, "cleanpass@cleandb.local", line, 35, 60),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 0

    def test_plain_email_no_scheme_kept(self):
        """contact: user@example.com (нет '://') → email сохранён."""
        line = "contact: alice.new@example.org"
        findings = [
            _f("email", 1, "alice.new@example.org", line, 9, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1
Запустить:

powershell
python -m pytest tests/unit/test_pii_filters_v31316.py -v
python -m pytest tests/unit/test_pii_filters_v31315.py -v
python -m pytest tests/unit/ -q
Ожидание:

Новые тесты — все зелёные (7 шт.)

Старые (v3.13.15) — все зелёные (7 шт.)

Все unit — 135 + 7 = 142 passed, регрессий нет

Пересборка и live-прогон
1. Обновить VERSION
powershell
$env:VERSION="3.13.16"
docker compose build
docker compose up -d
curl http://127.0.0.1:8000/api/health
# → {"status":"healthy","version":"3.13.16"}
2. Перезапустить сканер
powershell
# Ctrl+C в окне start_scanner.bat
cd E:\projects\dcap-system\scanner
.\start_scanner.bat
Дождаться:

text
[OK] Manager: healthy, version 3.13.16
...
[OK] Загружено 3 классификаторов
[X] Сканер scanner-1 запущен (ID: 1)
HeartbeatThread started (interval=30s)
(~35–60 с инициализации Presidio/spaCy)

3. Почистить findings task 32/33/34
sql
DELETE FROM findings WHERE task_id IN (32, 33, 34);
Проверка:

sql
SELECT task_id, COUNT(*) FROM findings WHERE resource_id = 16 GROUP BY task_id;
-- ожидание: 0 rows
4. Создать task 35
powershell
$login = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin123"}'
$token = $login.access_token

$body = @{
  resource_path = "C:\test\scanner_clean"
  name          = "scanner_clean_v3.13.16_final"
} | ConvertTo-Json

$task = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/tasks/create `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body

$task | ConvertTo-Json -Depth 5
Ожидаем task_id = 35.

5. Дождаться завершения
powershell
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/tasks/35" `
  -Headers @{ Authorization = "Bearer $token" } | ConvertTo-Json -Depth 5
Ожидание: status=completed, findings_count = 29 (было 34, минус 5 url).

Критерии приёмки ТЗ №7
SQL-проверки
sql
-- Общее
SELECT COUNT(*) FROM findings WHERE task_id = 35;
-- ожидание: ~29
sql
-- Разбивка
SELECT category, detector, COUNT(*)
FROM findings
WHERE task_id = 35
GROUP BY category, detector
ORDER BY category;
Ожидаемая таблица:

category	detector	count	Δ от task 34
aws_key	regex	1	—
basic_auth	regex	1	—
credit_card	presidio	4	—
database_url	regex	1	—
email	ocr	1	—
email	presidio	4	—
github_token	regex	1	—
high_entropy	entropy	2	—
inn	presidio	3	—
passport	presidio	2	—
phone	ocr	1	—
phone	presidio	4	—
slack_token	regex	1	—
snils	presidio	1	—
token	regex	2	—
url	—	0	было 5 ✅
Всего		~29	было 34
sql
-- Шум — все должны быть 0
SELECT category, COUNT(*) FROM findings
WHERE task_id = 35
  AND category IN ('url','uk_nhs','organization','date_time','person')
GROUP BY category;
-- ожидание: (0 rows)
sql
-- OCR (регрессия — должны сохраниться)
SELECT category, fragment_type, detector,
       bounding_box IS NOT NULL AS has_bbox
FROM findings
WHERE task_id = 35 AND fragment_type = 'image_region';
-- ожидание: 2 строки (email, phone), has_bbox=t
Лог сканера
Ожидаем:

text
[Scanner] Task 35 completed (linewise):
  - Total findings: 29
[SubmitResults] batch 1/1: 29 findings saved   ← N == M
Сводка правок
#	Функция	Действие
1	_filter_url_over_email_finding	Заменить на новую реализацию (~50 строк)
2	tests/unit/test_pii_filters_v31316.py	Создать (7 тестов)
3	docker-compose.yml, .env.example	VERSION → 3.13.16
4	STATE.md, ROADMAP.md, STATE_TEST_SESSION.md, CHANGELOG.md	Обновить
Критерии закрытия ТЗ №7
✅ pytest tests/unit/test_pii_filters_v31316.py -v — 7 passed

✅ pytest tests/unit/test_pii_filters_v31315.py -v — 7 passed (регрессия)

✅ pytest tests/unit/ -q — 142 passed

✅ python -m py_compile scanner/classifiers/pii_classifier.py — OK

✅ Manager /api/health → 3.13.16

✅ task 35 completed, findings_count = 29, url = 0

✅ Обновлены STATE.md, ROADMAP.md (BUG-075 → ✅), STATE_TEST_SESSION.md (Блок 3 → ✅)

✅ Блок 3 закрыт на 100%

После ТЗ №7
Блок 3 — 100% ✅ → переход к Блоку 8 (Мониторинг).

Оценка: 1-2 ч.

Автор ТЗ: архитектор
Дата: 22.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.16, Блок 3 — 100% ✅