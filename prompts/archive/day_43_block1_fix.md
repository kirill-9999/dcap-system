# 🔧 ТЗ на фикс Блока 1 — DCAP v3.13.2

**Приоритет:** 🔴 критично (баги блокируют Блок 2+)
**Оценка:** ~3 рабочих дня
**Ветка:** `fix/block_1_issues`

---

## 🔴 Приоритет 1 — Deploy / Config (день 1)

### BUG-001: `/api/health` — version=3.7.0

**Файл:** `manager/src/main.py`
**Проблема:** версия хардкодом `"3.7.0"` вместо чтения из `VERSION` env / `manager/config/config.json`.
**Фикс:**
```python
import os
from pathlib import Path

def get_version():
    v = os.getenv("VERSION")
    if v:
        return v.strip()
    # fallback: из config.json
    try:
        import json
        cfg = Path(__file__).parent.parent / "config" / "config.json"
        return json.loads(cfg.read_text(encoding="utf-8")).get("version", "unknown")
    except Exception:
        return "unknown"

@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": get_version()}
Проверка: Invoke-RestMethod http://localhost:8000/api/health → version: 3.13.2.

BUG-002/007: Deploy не готов из коробки
Файлы: .env.example, docker-compose.yml, deploy.sh, docs/deployment.md

Проблемы:

.env.example: VERSION=3.5.0 (устарело).

docker-compose.yml: ${VERSION:-3.5.0} (default устарел).

Нет инструкции «скопируй .env.example в .env».

Фикс:

.env.example: VERSION=3.13.2.

docker-compose.yml: заменить все ${VERSION:-3.5.0} на ${VERSION:-3.13.2}.

deploy.sh: fail-fast, если .env отсутствует:

bash
if [ ! -f .env ]; then
  echo "[ERROR] .env not found. Copy .env.example to .env and configure."
  exit 1
fi
docs/deployment.md: добавить шаг «cp .env.example .env».

Проверка: на fresh-клоне cp .env.example .env && docker compose up -d → все контейнеры healthy.

BUG-017/019: postgres_exporter вне dcap-network
Файл: docker-compose.yml:292-311
Проблема: у postgres_exporter нет networks: [dcap-network] → Prometheus не резолвит.
Фикс:

yaml
postgres_exporter:
  image: prometheuscommunity/postgres-exporter
  networks:
    - dcap-network
Аналогично для redis_exporter, celery_exporter.

Проверка: docker compose down --remove-orphans && docker compose up -d → Prometheus target postgres_exporter = UP.

BUG-036: Emoji во всей кодовой базе
Файлы: вся кодовая база Python
Проблема: emoji в print() / logger.*() → UnicodeEncodeError на cp1251.

Фикс:

Прогнать rg "[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" --type py → список файлов.

Заменить emoji на ASCII:

Emoji	Замена
✅	[OK]
❌	[ERROR]
⚠️	[WARN]
🔴	[CRIT]
🟢	[INFO]
🚀	[START]
⏹️	[STOP]
📁	[DIR]
📌	[PIN]
🆔	[ID]
⏱️	[TIME]
📊	[STATS]
🔍	[SCAN]
🔄	[SYNC]
🐛	[BUG]
Защита: в run_scanner.py и run_manager.py:

python
import sys, io
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
Проверка: python run_scanner.py ... 2>&1 | Tee-Object file.log — без ошибок.

🔴 Приоритет 2 — Findings / Scanner (день 2)
BUG-022: Утечка PII через line_text / context_*
Файл: scanner/src/encryption.py
Проблема: mask_line(line, [(start, end, cat)]) маскирует только свою категорию. Остальные PII в строке остаются открытыми.

Фикс:

При сканировании файла — собрать все находки в строке.

При сериализации — маскировать все PII в строке, а не только свою.

Пример для _serialize_finding:

python
def _serialize_finding(self, finding, resource_path, all_findings_in_line=None):
    # all_findings_in_line — список всех находок в той же строке
    positions = [(f.start_pos, f.end_pos, f.category) for f in all_findings_in_line or [finding]]
    d["line_text_masked"] = mask_line(line_text, positions)
    d["context_before_masked"] = mask_context(ctx_before, positions)
    d["context_after_masked"] = mask_context(ctx_after, positions)
Проверка: у находки person (id=9) в line_text телефон должен быть маскирован: Иван Иванов, тел +7***123-45-67.

BUG-027: Progress-рассинхрон
Файл: manager/src/api/scanner.py
Проблемы:

.1: progress.total = files_scanned, percent: 100 при 70%.

.2: top-level files_scanned ≠ progress.files_scanned.

.3: status: assigned при живой задаче.

.4: progress пустой при completed (linewise).

Фикс:

progress.total — брать из heartbeat (передаётся сканером) или из task.total_files (при создании задачи).

progress.percent = files_scanned / total * 100 — только если total > 0.

Top-level files_scanned — синхронизировать с progress.files_scanned.

status: сканер при старте шлёт heartbeat(status="busy", task_id=...) → Manager → status: running.

Linewise-путь: вызывать heartbeat.set_progress(scanned, total) при каждом файле (уже делается, но Manager не сохраняет — исправить приём).

Проверка: Task 4 в API: status: completed, progress.total: 3, progress.percent: 100, files_scanned: 3.

BUG-034: Manager не закрывает прерванную задачу
Файл: manager/src/api/scanner.py
Проблема: Task 2 висел 2 дня в assigned после остановки сканера.
Фикс:

В _mark_stale_scanners — если сканер не шлёт heartbeat > N минут и у него есть assigned задача → status: failed, completed_at: NOW().

Endpoint POST /api/tasks/{id}/cancel — для ручной отмены.

Проверка: остановить сканер, подождать N минут → Task 2 автоматически → failed.

BUG-035: Нет батчинга findings
Файл: scanner/src/managed_scanner.py (метод submit_results)
Проблема: один POST с миллионами findings.
Фикс:

Разбить на батчи по 500-1000 findings.

POST /api/scanner/tasks/{id}/results?batch=N&total=M.

Manager собирает батчи в БД.

Проверка: Task с 22 500 файлов → findings идут батчами → БД получает все.

🔴 Приоритет 3 — WebUI (день 3)
W-54: /findings/{id} — нет кнопок действий
Файлы: webui/templates/finding_detail.html, webui/static/js/finding_detail.js
Проблема: нет кнопок Reveal / PATCH / Fragment.
Фикс:

Кнопка «Reveal» (для Auditor+) → POST /api/findings/{id}/reveal.

Кнопка «Изменить статус» → PATCH /api/findings/{id}.

Кнопка «Показать фрагмент» → GET /api/findings/{id}/fragment.

Кнопка «Назад» → /findings.

Проверка: на /findings/6 — все кнопки видны, Reveal работает.

W-42: Dashboard — 9 находок вместо 13
Файл: webui/templates/dashboard.html (или JS)
Проблема: Dashboard использует другой счётчик (не /api/findings/count).
Фикс: использовать GET /api/findings/count → {count: 13}.

Проверка: Dashboard показывает 13.

W-60: Catalog tree — E: — 0/0, is_folder: false
Файл: manager/src/api/catalog.py (endpoint /api/catalog/tree)
Проблема: корневой узел не агрегирует детей.
Фикс:

is_folder: true для узлов-папок.

total_findings, file_count — сумма по детям (рекурсивно).

has_findings: true, если узел или дети имеют находки.

Проверка: /api/catalog/tree → E: → {is_folder: true, total_findings: 13, file_count: 2, has_findings: true}.

W-66: FP-страница — файл —
Файл: manager/src/api/findings.py (endpoint /api/findings/false-positives)
Проблема: endpoint не возвращает file_path.
Фикс: добавить file_path (JOIN с resources) в response.

Проверка: /api/findings/false-positives → каждая запись содержит file_path: "E:\test_smoke\pii.txt".

W-70: Нет кнопки «Снять FP»
Файл: webui/templates/false_positives.html
Проблема: FP-находки — только просмотр.
Фикс: кнопка «Восстановить» → PATCH /api/findings/{id} со {status: "new"}.

Проверка: клик на «Снять FP» → находка возвращается в /findings с status: new.

W-43: Footer v3.0.0
Файл: webui/templates/base.html
Фикс: брать версию из /api/health или из VERSION env.

W-55: Нет has_encrypted / can_reveal в UI
Файл: webui/templates/finding_detail.html
Фикс: добавить блок «Шифрование»:

has_encrypted: true/false

can_reveal: true/false

encryption_key_id

W-57: Нет last_seen_at / reviewed_by / reviewed_at
Файл: webui/templates/finding_detail.html
Фикс: добавить поля в блок метаданных.

W-62: Нет ссылок /findings/{id} из каталога
Файл: webui/templates/catalog.html
Фикс: :N 12***900 PII new → ссылка <a href="/findings/{id}">.

W-67: FP — помечено: 1 (user_id)
Файл: manager/src/api/findings.py (endpoint /api/findings/false-positives)
Фикс: JOIN с users → возвращать reviewed_by_username + reviewed_by_id.

Проверка: /api/findings/false-positives → reviewed_by: "admin" вместо 1.

W-72/W-73: Catalog metadata
Файл: manager/src/api/catalog.py
Фикс:

W-72: last_scanned — обновлять при каждом скане папки.

W-73: classifiers — сериализовать как JSON-объект (не PowerShell-хеш).

📋 Порядок работы
День 1 — Deploy/Config
BUG-001 (health version)

BUG-002/007 (deploy)

BUG-017/019 (networks)

BUG-036 (emoji)

День 2 — Findings/Scanner
BUG-022 (утечка PII) — приоритет

BUG-027.1-4 (progress)

BUG-034 (Manager не закрывает)

BUG-035 (батчинг)

День 3 — WebUI
W-54 (кнопки Reveal/PATCH/Fragment) — приоритет

W-42 (Dashboard count)

W-60 (Catalog tree)

W-66 (FP file_path)

W-70 (снять FP)

W-43, W-55, W-57, W-62, W-67, W-72, W-73

✅ Критерии приёмки
Все критичные баги (BUG-001, 017/019, 022, 027.1-4, 034, 035, W-42, W-54, W-60, W-66) — закрыты.

Smoke-тест Блока 1 — проходит без регрессий.

Тест дедупа (13 → 13) — работает.

Reveal — работает через UI, пишет в audit_logs.

Emoji — отсутствуют в print()/logger.*().

📎 Ссылки
STATE_TEST_SESSION.md — детали багов.

STATE.md — текущий статус проекта.

ARCHITECTURE.md — модель Findings, шифрование.

Конец TZ_BLOCK_1_FIX.md

text

---

## 🎯 Что делать сейчас

1. **Сохрани** `STATE_TEST_SESSION.md` (из этого сообщения) в:
E:\projects\dcap-system\prompts\test\STATE_TEST_SESSION.md

text

2. **Сохрани** `TZ_BLOCK_1_FIX.md` в:
E:\projects\dcap-system\prompts\tz\TZ_BLOCK_1_FIX.md

text

3. **Передай ТЗ разработчику** (кодеру / OpenCode / Big Pickle).

4. **Открой новую беседу**, приложи:
- `STATE_TEST_SESSION.md`
- `STATE.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`

5. **Триггер:**