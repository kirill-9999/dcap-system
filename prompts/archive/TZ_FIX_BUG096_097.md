📄 ТЗ: BUG-096 + BUG-096b + BUG-097
Файл: TZ_FIX_BUG096_097.md
Версия: v3.13.24 → v3.13.25
Оценка: ~1.5 ч (BUG-096: 30 мин + BUG-096b: 30 мин + диагностика BUG-097: 30 мин)
Дата: 27.09.2026
Приоритет: 🔴 critical (BUG-096 — блокер v3.0.0)
Обнаружено:

BUG-096 — День 48.2 (разработчик, E2E) + воспроизведён вручную 27.09.2026

BUG-096b — День 48.2 (разработчик, E2E)

BUG-097 — 27.09.2026, при диагностике BUG-096 (логи Manager)

🎯 BUG-096 — /false-positives → 500 при наличии FP
Приоритет: 🔴 critical (блокер v3.0.0)
Доказательная база
Traceback (live, 27.09.2026):

text
File "/app/manager/src/api/findings.py", line 324, in list_false_positives
    for u in db.query(_m.User).filter(_m.User.id.in_(set(reviewer_ids))).all():
                      ^^^^^^^
AttributeError: module 'manager.src.db.models' has no attribute 'User'
Воспроизведение (live):

powershell
# 1. FP = 0 → 200, items: 0
GET /api/findings/false-positives  → 200, items: 0  ✅

# 2. PATCH создаёт FP
PATCH /api/findings/1523 {"status": "false_positive"}  → 200  ✅

# 3. FP = 1 → 500
GET /api/findings/false-positives  → 500  🐛 (auditor)
GET /api/findings/false-positives  → 500  🐛 (admin)
Причина
_m = manager.src.db.models

User определён в manager.src.auth.models

В manager.src.db.models нет User → AttributeError при обогащении reviewed_by_username

Цикл выполняется только при FP > 0 — поэтому при пустом списке эндпоинт не падает

Файл
manager/src/api/findings.py:324 — функция list_false_positives.

Задача
TASK-064 (BUG-096) — фикс импорта
1. Добавить импорт в начало findings.py:

python
from manager.src.auth.models import User as AuthUser
2. Заменить _m.User → AuthUser в list_false_positives:

python
# Было (строка ~324):
for u in db.query(_m.User).filter(_m.User.id.in_(set(reviewer_ids))).all():
    reviewer_map[u.id] = u.username

# Стало:
for u in db.query(AuthUser).filter(AuthUser.id.in_(set(reviewer_ids))).all():
    reviewer_map[u.id] = u.username
3. Проверить все места _m.User в файле:

powershell
Select-String -Path "manager\src\api\findings.py" -Pattern "_m\.User" |
  Select-Object LineNumber, Line
Если есть ещё — исправить аналогично.

4. Проверить другие API-файлы:

powershell
Get-ChildItem -Path "manager\src\api" -Recurse -Filter *.py |
  Select-String -Pattern "_m\.User" |
  Select-Object Path, LineNumber, Line |
  Format-Table -AutoSize -Wrap
Если найден _m.User где-то ещё — тот же баг, исправить.

Unit-тест
Файл: tests/unit/test_false_positives_v31325.py

python
"""BUG-096 (TASK-064, v3.13.25): /false-positives возвращает 200 при FP > 0."""

class TestFalsePositives:
    def test_false_positives_with_data(self, client, auditor_token, finding_factory):
        """FP > 0 → 200, reviewed_by_username заполнен."""
        # 1. Создать finding
        # 2. PATCH → false_positive
        # 3. GET /api/findings/false-positives → 200
        # 4. items[0].reviewed_by_username == "auditor"
        pass

    def test_false_positives_empty(self, client, auditor_token):
        """FP = 0 → 200, items: []."""
        pass

    def test_false_positives_reviewed_by_username(self, client, auditor_token):
        """reviewed_by_username заполнен корректно."""
        pass
Ожидание: 3 passed.

🎯 BUG-096b — устаревшие E2E-тесты
Приоритет: 🟡 важно
Проблема 1: test_full_scan_cycle
Файл: tests/e2e/test_full_scan_cycle.py

Тест ждёт: finding_type in {pii, credentials}.
После v3.13.22: приходят гранулярные category: email, phone, aws_key, inn, snils, passport, credit_card, github_token, slack_token, token, basic_auth, database_url, high_entropy.

Фикс: обновить assertions на category:

python
# Было:
assert finding["finding_type"] in {"pii", "credentials"}

# Стало:
assert finding["category"] in {
    "email", "phone", "person", "aws_key", "inn", "snils", "passport",
    "credit_card", "github_token", "slack_token", "token", "basic_auth",
    "database_url", "high_entropy",
}
Или — если тест проверяет finding_type:

python
assert finding["finding_type"] in {"pii", "credentials"}  # остаётся валидным
Уточнить у разработчика: что именно ломается — обновить то поле, что проверяется.

Проблема 2: test_scanner_findings
Файл: tests/e2e/test_scanner_findings.py

Ошибка: RemoteDisconnected при опросе статуса задания.

Фикс: добавить retry:

python
import time
import requests
from requests.exceptions import ConnectionError, Timeout

def get_task_status_with_retry(url, headers, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return requests.get(url, headers=headers, timeout=10)
        except (ConnectionError, Timeout, RemoteDisconnected) as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
Или — pytest.skip при отсутствии активного сканера:

python
scanners = requests.get(f"{MANAGER_URL}/api/scanner", headers=headers).json()
if not scanners or not any(s.get("status") == "active" for s in scanners):
    pytest.skip("Нет активного сканера")
Ожидание: 2 passed.

🎯 BUG-097 — Scanner: POST /api/scanner/tasks/43/results → 404
Приоритет: 🟡 важно (диагностика)
Наблюдение (логи Manager, 27.09.2026)
text
INFO: 172.19.0.1:44698 - "POST /api/scanner/tasks/43/results?batch=1&total=1 HTTP/1.1" 404 Not Found
Возможные причины (диагностика)
A) Осиротевший сканер — старый процесс (v≤3.13.20) работает со старым task_id=43, который удалён из БД. Связано с TEST-NOTE-5.5 и BUG-081 (Ctrl+C).

B) Баг в Manager — endpoint /results не находит task, хотя он есть.

C) Race condition — task удалён в момент отправки результатов.

D) Реальная задача — task 43 существует, но сканер шлёт с неверным batch/total.

Задача — диагностика
Шаг 1. Проверить task 43 в БД:

sql
SELECT id, status, findings_count, scanner_id, source_path, created_at
FROM scan_tasks WHERE id IN (41, 42, 43, 44)
ORDER BY id DESC;
Шаг 2. Проверить, сколько процессов сканера запущено:

powershell
Get-CimInstance Win32_Process -Filter "name like 'python%'" |
  Where-Object { $_.CommandLine -match "run_scanner" } |
  Select-Object ProcessId, CreationDate, CommandLine |
  Format-Table -AutoSize -Wrap
Ожидание:

1 процесс → проблема в Manager (B/D).

2+ процессов → осиротевшие сканеры (A) → TEST-NOTE-5.5 подтверждён.

Шаг 3. Проверить логи сканера (если доступны):

powershell
# Файл лога сканера
Get-Content "scanner\logs\scanner.log" -Tail 100 |
  Select-String -Pattern "task|43|404|results" -Context 2,2
Шаг 4. Проверить endpoint в Manager:

powershell
Get-Content "manager\src\api\scanner.py" |
  Select-String -Pattern "tasks.*results|def.*results" -Context 3,10
Смотрим:

Какой HTTP-код возвращается при отсутствии task.

Логика scanner_id vs task_id.

Возможные фиксы (по результатам диагностики)
Если A (осиротевший сканер):

Фикс: в start_scanner.bat добавить kill старых процессов перед стартом:

batch
REM BUG-097: убить осиротевшие сканеры
wmic process where "name='python.exe' and commandline like '%%run_scanner%%'" delete
Или lock-файл:

python
# scanner/src/managed_scanner.py
LOCK_FILE = Path("scanner.lock")
if LOCK_FILE.exists():
    # проверить, жив ли PID
    ...
Оформить как TASK-066 (не в этом ТЗ, если требует много времени).

Если B/D (баг Manager):

Фикс: улучшить логирование — при 404 на /results писать task_id, scanner_id → в логи. TASK-067.

📊 Сводка задач
ID	Название	Оценка
TASK-064	BUG-096: фикс _m.User → AuthUser	30 мин
TASK-065	BUG-096b: обновить 2 устаревших E2E-теста	30 мин
TASK-066	BUG-097: диагностика 404 на /results (осиротевший сканер?)	30 мин
✅ Критерии приёмки
BUG-096
□ Live: FP > 0 → GET /api/findings/false-positives → 200 (не 500)
□ reviewed_by_username заполнен (auditor/admin)
□ pytest tests/unit/test_false_positives_v31325.py -v — passed
□ Все места _m.User исправлены (grep — 0)
BUG-096b
□ test_full_scan_cycle — passed
□ test_scanner_findings — passed
□ Полный E2E: 50 passed
BUG-097
□ Диагностика завершена — корень найден
□ Если осиротевшие сканеры — фикс (kill в start_scanner.bat или lock-файл)
□ Если баг Manager — фикс + улучшенное логирование
□ Обновлён docs/admin-guide/10-troubleshooting.md
Общее
□ pytest tests/unit -q — 245+ passed (242 + 3)
□ Manager /api/health → 3.13.25
□ Обновлены STATE.md, ROADMAP.md, CHANGELOG.md
📌 Контекст для разработчика
Что уже известно
BUG-096 — реальный, воспроизведён вручную (FP > 0).

BUG-096b — устаревшие тесты, не блокер.

BUG-097 — свежий сигнал из логов, требует диагностики.

Оставленные данные для проверки
Finding id=1523 — оставлен в статусе false_positive специально — для проверки фикса BUG-096. После фикса — GET /false-positives должен вернуть 1 запись с reviewed_by_username=auditor.

Связанные контексты
TEST-NOTE-5.5 (наш) — «Осиротевшие сканеры после обновления» — может быть корнем BUG-097.

BUG-081 (v3.13.20) — Ctrl+C graceful shutdown. Если сканер не завершается штатно — остаются призраки.

BUG-048b — middleware для machine-API — не связано.

🚀 После закрытия
BUG-096 → ✅ v3.13.25

BUG-096b → ✅

BUG-097 → ✅ или отдельная задача

Продолжаем Блок 5 → п.5 (PATCH status) — с уже существующим FP (id=1523).

📄 Формат ответа
В отчёте указать:

BUG-096: фикс (файл + строка), live-подтверждение (/false-positives с FP > 0 → 200).

BUG-096b: какие тесты обновлены, результаты E2E.

BUG-097: диагностика — корень найден; если фикс — какой.

Обновления: STATE/ROADMAP/CHANGELOG/troubleshooting.

Оставленные данные: FP id=1523 — можно удалить или оставить.

Автор ТЗ: архитектор
Дата: 27.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.25, BUG-096/096b/097 → ✅