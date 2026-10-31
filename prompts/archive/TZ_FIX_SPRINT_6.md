ТЗ №6 — Fix-спринт №6 (v3.13.15)
Файл: TZ_FIX_SPRINT_6.md
Версия: v3.13.14 → v3.13.15
Оценка: ~1 ч
Дата: 22.09.2026
Контекст: после live-прогона v3.13.14 на C:\test\scanner_clean (task 32)

Цель
Устранить 4 остаточных бага, выявленных в live-прогоне task 32:

ID	Название	Где	Приоритет
BUG-071	url-over-email не фильтруется (2 случая)	pii_classifier.py	🔴
BUG-072	organization = "INN" (аббревиатура как организация)	pii_classifier.py	🟡
BUG-073	uk_nhs на US-телефоне (ложное срабатывание)	pii_classifier.py	🟡
BUG-074	email из URL-логина (postgresql://...@...)	pii_classifier.py	🔴
Все правки — в одном файле: scanner/classifiers/pii_classifier.py.

Доказательная база (task 32, C:\test\scanner_clean)
BUG-071 — url-over-email
id	line	match (revealed)	line_text
1297	4	http://bob.new	url: http://bob.new@test.example/x
1300	2	example.org/path	site: https://alice.new@example.org/path
Проблема: Presidio обрезает url по @ (http://bob.new) или отрезает логин (example.org/path). Спаны url и email не пересекаются → текущий фильтр не работает.

BUG-072 — organization = "INN"
id	line	match	line_text
1289	3	INN	INN: 7712345678
Проблема: Presidio (en-проход) классифицирует аббревиатуру INN (3 заглавные латинские) как organization. Текущий _filter_spacy_noise не отбрасывает (нет _: =, 0% цифр, len=3 не <3).

BUG-073 — uk_nhs на US-телефоне
id	line	match	line_text
1307	3	415 555 0199	us: +1 415 555 0199
Проблема: Presidio UkNhsRecognizer ловит 10 цифр → US-телефон +1 415 555 0199 проходит как UK NHS.

BUG-074 — email из URL-логина
id	line	match	line_text
1272	1	cleanpass@cleandb.local	DATABASE_URL=postgresql://cleanuser:cleanpass@cleandb.local:5432/cleandb
Проблема: Presidio находит email в user:password@host части URL. database_url — credentials-классификатор, email — PII, межклассификаторной координации нет.

Задачи
TASK-037 (BUG-071 + BUG-074) — переписать _filter_url_over_email_finding
Файл: scanner/classifiers/pii_classifier.py
Текущие строки: 654–676

Текущая логика:

python
def _filter_url_over_email_finding(self, findings):
    email_spans = {(f.start_pos, f.end_pos) for f in findings
                   if f.category in ("email", "PII_EMAIL")}
    if not email_spans:
        return findings
    filtered = []
    for f in findings:
        if f.category in ("url", "PII_URL"):
            if any(e_start <= f.start_pos and f.end_pos <= e_end
                   for e_start, e_end in email_spans):
                continue
        filtered.append(f)
    return filtered
Проблема: работает по спанам, но спаны url/email не пересекаются (Presidio режет).

Требуемая логика: работать по line_text. Если в строке есть и URL-схема (://), и email-признак (@ или email-паттерн) — отбрасывать все url и email findings этой строки.

Новая реализация:

python
def _filter_url_over_email_finding(self, findings: List[Finding]) -> List[Finding]:
    """BUG-066b + BUG-071 + BUG-074 (TASK-033, расширено TASK-037, v3.13.15).

    Presidio обрезает url по '@' ('http://bob.new' для
    'http://bob.new@test.example/x'), поэтому спаны url и email
    НЕ пересекаются — фильтр по спанам не работает.

    Работаем по line_text: если строка содержит URL-схему ('://')
    И email-признак ('@' или email-паттерн) — отбрасываем все
    url/email-findings этой строки. Покрывает:
      - url-over-email:       http://user@host/path
      - credentials-URL:      postgresql://user:pass@host:port/db

    НЕ трогает обычные email-строки без '://':
      - 'contact: user@example.com'  →  email сохраняется
    """
    import re
    EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")

    # Номера строк с URL-схемой + email-признаком
    skip_lines: set = set()
    for f in findings:
        line = f.line_text or ""
        if "://" in line and ("@" in line or EMAIL_RE.search(line)):
            skip_lines.add((f.line_number, f.fragment_path))

    if not skip_lines:
        return findings

    filtered = []
    for f in findings:
        if f.category in ("url", "PII_URL", "email", "PII_EMAIL"):
            if (f.line_number, f.fragment_path) in skip_lines:
                continue
        filtered.append(f)
    return filtered
TASK-038 (BUG-072) — дополнить _filter_spacy_noise
Файл: scanner/classifiers/pii_classifier.py
Текущие строки: 678–703

Текущие условия:

python
if (any(c in val for c in "_:=")
        or "://" in val
        or sum(c.isdigit() for c in val) > len(val) / 2
        or len(val) < 3
        or "card " in val.lower()):
    continue
Требуется добавить условие:

python
        # BUG-072 (TASK-038, v3.13.15): аббревиатуры INN/SSN/DOB/URL/API —
        # шум spaCy en-прохода. Отбрасываем все заглавные латинские ≤5 симв.
        or (len(val) <= 5 and val.isupper() and val.isascii() and val.isalpha())
Итоговый блок:

python
if (any(c in val for c in "_:=")
        or "://" in val
        or sum(c.isdigit() for c in val) > len(val) / 2
        or len(val) < 3
        or "card " in val.lower()
        # BUG-072 (TASK-038, v3.13.15): аббревиатуры INN/SSN/DOB/URL/API
        or (len(val) <= 5 and val.isupper() and val.isascii() and val.isalpha())):
    continue
То же условие добавить в _filter_spacy_noise_classification (строки 705–727):

python
if (any(c in val for c in "_:=")
        or "://" in val
        or sum(c.isdigit() for c in val) > len(val) / 2
        or len(val) < 3
        or "card " in val.lower()
        # BUG-072 (TASK-038, v3.13.15)
        or (len(val) <= 5 and val.isupper() and val.isascii() and val.isalpha())):
    continue
TASK-039 (BUG-073) — новый фильтр _filter_uk_nhs_with_phone
Файл: scanner/classifiers/pii_classifier.py
Разместить после _filter_spacy_noise_classification (примерно строка 728).

Новая функция:

python
def _filter_uk_nhs_with_phone(self, findings: List[Finding]) -> List[Finding]:
    """BUG-073 (TASK-039, v3.13.15): UK NHS — ложное срабатывание
    на US-телефонах.

    Presidio's UkNhsRecognizer ловит 10 цифр — US-телефон
    '+1 415 555 0199' проходит как UK NHS. Отбрасываем uk_nhs,
    если в той же строке уже есть phone.
    """
    phone_lines = {
        (f.line_number, f.fragment_path)
        for f in findings
        if f.category in ("phone", "PII_PHONE")
    }
    if not phone_lines:
        return findings

    filtered = []
    for f in findings:
        if f.category in ("uk_nhs", "UK_NHS"):
            if (f.line_number, f.fragment_path) in phone_lines:
                continue
        filtered.append(f)
    return filtered
Подключить в scan_line (после строки 454) и scan_text (после строки 545):

python
# scan_line (строка ~454):
findings = self._filter_url_over_email_finding(findings)
findings = self._filter_spacy_noise(findings)
findings = self._filter_uk_nhs_with_phone(findings)   # ← NEW (TASK-039)
return self._deduplicate(findings)

# scan_text (строка ~545):
findings = self._filter_url_over_email_finding(findings)
findings = self._filter_spacy_noise(findings)
findings = self._filter_uk_nhs_with_phone(findings)   # ← NEW (TASK-039)

# BUG-022.9: дедупликация по позиции с приоритетом категорий
by_pos = {}
...
Сводка правок
#	Функция	Действие	Строки
1	_filter_url_over_email_finding	Переписать	654–676
2	_filter_spacy_noise	Добавить 1 условие	696–700
3	_filter_spacy_noise_classification	Добавить 1 условие	720–724
4	_filter_uk_nhs_with_phone	Новая функция	после 727
5	scan_line	+1 строка вызова	~454
6	scan_text	+1 строка вызова	~545
Тесты (smoke-проверки)
Файл: tests/unit/test_pii_filters_v31315.py (создать)

python
"""Smoke-тесты фильтров PII для v3.13.15 (TASK-037..039)."""

from scanner.src.finding import Finding
from scanner.classifiers.pii_classifier import PiiClassifier


def _f(category, line, match, line_text, start=0, end=10, fpath="C:/t.txt"):
    return Finding(
        line_number=line, line_text=line_text, match_text=match,
        start_pos=start, end_pos=end,
        finding_type="pii", category=category,
        fragment_path=fpath,
    )


class TestUrlOverEmail:
    def setup_method(self):
        self.c = PiiClassifier()

    def test_url_over_email_removed(self):
        """http://bob.new@test.example/x → url и email отброшены."""
        findings = [
            _f("email", 4, "bob.new@test.example",
               "url: http://bob.new@test.example/x", 15, 35),
            _f("url",   4, "http://bob.new",
               "url: http://bob.new@test.example/x", 5, 15),
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

    def test_plain_email_kept(self):
        """contact: user@example.com → email СОХРАНЯЕТСЯ (нет ://)."""
        findings = [
            _f("email", 1, "alice.new@example.org",
               "contact: alice.new@example.org", 9, 30),
        ]
        out = self.c._filter_url_over_email_finding(findings)
        assert len(out) == 1


class TestSpacyNoise:
    def setup_method(self):
        self.c = PiiClassifier()

    def test_inn_abbrev_removed(self):
        """organization='INN' отброшен."""
        findings = [
            _f("organization", 3, "INN", "INN: 7712345678"),
        ]
        out = self.c._filter_spacy_noise(findings)
        assert len(out) == 0

    def test_real_org_kept(self):
        """organization='Apple Inc' НЕ отброшен."""
        findings = [
            _f("organization", 1, "Apple Inc", "at Apple Inc office"),
        ]
        out = self.c._filter_spacy_noise(findings)
        assert len(out) == 1


class TestUkNhsWithPhone:
    def setup_method(self):
        self.c = PiiClassifier()

    def test_uk_nhs_removed_when_phone(self):
        """uk_nhs отброшен, если phone в той же строке."""
        findings = [
            _f("phone",  3, "415 555 0199", "us: +1 415 555 0199"),
            _f("uk_nhs", 3, "415 555 0199", "us: +1 415 555 0199"),
        ]
        out = self.c._filter_uk_nhs_with_phone(findings)
        assert len(out) == 1
        assert out[0].category == "phone"

    def test_uk_nhs_kept_without_phone(self):
        """uk_nhs сохранён, если phone нет в строке."""
        findings = [
            _f("uk_nhs", 1, "123 456 7890", "NHS: 123 456 7890"),
        ]
        out = self.c._filter_uk_nhs_with_phone(findings)
        assert len(out) == 1
Запустить:

powershell
python -m pytest tests/unit/test_pii_filters_v31315.py -v
Ожидание: все тесты зелёные.

Пересборка и live-прогон
1. Пересборка Manager (не затрагивается) + перезапуск сканера
Manager не менялся — пересборка нужна только если меняются контейнеры. Сканер — на хосте.

powershell
# Остановить сканер (Ctrl+C в окне start_scanner.bat)
# Запустить заново:
cd E:\projects\dcap-system\scanner
.\start_scanner.bat
2. Обновить VERSION (опционально)
Если Manager/WebUI не менялись — версия не меняется. Но docker-compose.yml / .env.example можно поднять до 3.13.15 для единообразия (опционально).

3. Live-прогон — task 33
Сначала почистить task 32 (опционально):

sql
DELETE FROM findings WHERE task_id = 32;
Создать новую задачу:

powershell
$body = @{
  resource_path = "C:\test\scanner_clean"
  name          = "scanner_clean_v3.13.15"
} | ConvertTo-Json

$task = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/tasks/create `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body

$task | ConvertTo-Json -Depth 5
Ожидаем task_id = 33.

Критерии приёмки
После task 33 = completed:

sql
SELECT category, detector, COUNT(*)
FROM findings
WHERE task_id = 33
GROUP BY category, detector
ORDER BY category;
Критерий	Ожидание	Проверка
url	0	было 2 (BUG-071)
organization	0	было 1 (BUG-072)
uk_nhs	0	было 1 (BUG-073)
email	7	было 8 (−1 из URL-логина, BUG-074)
phone	5	без изменений
credit_card	4	без изменений
inn	3	без изменений
passport	2	без изменений
snils	1	без изменений
aws_key, basic_auth, database_url, github_token, slack_token, token, high_entropy	≥1 каждый	без изменений
Всего	~32	было 36
OCR-проверка:

sql
SELECT category, fragment_type, detector,
       bounding_box IS NOT NULL AS has_bbox
FROM findings
WHERE task_id = 33 AND fragment_type = 'image_region';
Ожидание: 2 строки (email, phone), detector=ocr, has_bbox=t.

date_time / person:

sql
SELECT COUNT(*) FROM findings
WHERE task_id = 33 AND category IN ('date_time','person');
Ожидание: 0 (регрессия BUG-069/070).

Критерии закрытия ТЗ №6
✅ pytest tests/unit/test_pii_filters_v31315.py — все тесты зелёные

✅ python -m py_compile scanner/classifiers/pii_classifier.py — OK

✅ task 33 completed, все критерии приёмки выполнены

✅ Обновлён STATE.md (v3.13.15, Блок 3 — 100%)

✅ Обновлён ROADMAP.md (BUG-071…074 → ✅)

✅ Обновлён STATE_TEST_SESSION.md (Блок 3 — ✅)

Файлы к изменению
Файл	Действие
scanner/classifiers/pii_classifier.py	Правки TASK-037…039
tests/unit/test_pii_filters_v31315.py	Новый — smoke-тесты
docker-compose.yml, .env.example	(опционально) VERSION → 3.13.15
STATE.md	Обновить версию
ROADMAP.md	BUG-071…074 → ✅
STATE_TEST_SESSION.md	Блок 3 → ✅
Оценка
Этап	Время
Патч pii_classifier.py	25 мин
Smoke-тесты	10 мин
Перезапуск сканера	5 мин
Live-прогон task 33	10 мин
Верификация SQL	5 мин
Обновление STATE/ROADMAP	5 мин
Итого	~1 ч
Приоритет
🔴 Критично — блокирует 100%-ное закрытие Блока 3 и релиз v3.0.0.

После ТЗ №6
Переход к Блоку 8 (Мониторинг):

Метрики Prometheus/Grafana

Алерты Alertmanager

Heartbeat-thread

Логи

Оценка: 1-2 ч.

Автор ТЗ: архитектор
Дата: 22.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.15, Блок 3 — 100% ✅