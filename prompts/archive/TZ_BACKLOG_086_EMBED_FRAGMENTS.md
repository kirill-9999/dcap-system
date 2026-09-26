📄 ТЗ: BACKLOG-086 — Встраивание OCR-фрагментов в БД (ФИНАЛ)
Файл: TZ_BACKLOG_086_EMBED_FRAGMENTS.md
Версия: v3.13.18 → v3.13.19
Оценка: ~3 ч
Дата: 26.09.2026
Контекст: после BUG-077 (Manager в Docker не видит хостовые пути сканера). Файл может быть удалён/изменён после сканирования — нужны неизменяемые доказательства.

🎯 Цель
Встраивать OCR-фрагменты (весь PNG) в БД при создании finding, чтобы Manager/WebUI/аудит имели неизменяемое доказательство даже если исходный файл удалён или Manager не видит хостовый путь.

Ключевое преимущество: «Файл удалили — доказательство осталось».

📌 Ответы архитектора (зафиксировано)
#	Вопрос	Ответ
1	Хранить в БД или S3?	БД (проще, единый бэкап)
2	Дедупликация фрагментов?	Сейчас дубли, дедупликация → BACKLOG-087 (v3.1.0)
3	Доступ к /fragment	Только Auditor+ (ужесточить с Viewer+)
4	Максимальный размер	Настраиваемый, по умолчанию 2 МБ
5.1	OCR при bbox=None	A + C: весь PNG, дубли пока (дедуп → BACKLOG-087)
5.2	text_line — встраивать?	A: не встраивать (данные уже в line_text_encrypted)
5.3	byte_range	A: отложить до v3.1.0
5.4	Размер batch'а	B: батчинг POST'ов (отдельная задача TASK-050)
5.5	N findings / 1 файл	Дубли (BACKLOG-087)
🏗️ Архитектура решения
Поток данных
text
Scanner (host)
  ├─ OCR находит PII в image.png
  ├─ fragment_type = image_region, bbox = None (BUG-077)
  ├─ Читает весь PNG (≤ MAX_FRAGMENT_EMBED_SIZE)
  ├─ base64 + SHA-256
  └─ Отправляет в Manager: { finding, fragment_base64, fragment_mime, fragment_hash, fragment_size }

Manager (Docker)
  ├─ Декодирует base64
  ├─ Сохраняет fragment_data (LargeBinary) прямо в findings
  ├─ fragment_hash (SHA-256) для целостности
  └─ GET /api/findings/{id}/fragment → из БД
Для text_line: ничего не встраиваем (данные уже в line_text_encrypted).
Для byte_range: отложено до v3.1.0.

🔧 Задача
TASK-045 — Расширить модель Finding (Manager)
Файл: manager/src/db/models.py (модель Finding)

Добавить поля:

python
# BACKLOG-086 (TASK-045, v3.13.19): встроенный фрагмент (доказательная база).
# Только для image_region. text_line — данные в line_text_encrypted.
# byte_range — отложено до v3.1.0.
fragment_data = Column(LargeBinary, nullable=True)      # base64-decoded bytes
fragment_mime = Column(String(50), nullable=True)       # image/png, image/jpeg
fragment_hash = Column(String(64), nullable=True)       # SHA-256 (целостность)
fragment_size = Column(Integer, nullable=True)          # bytes
fragment_embedded_at = Column(DateTime, nullable=True)  # когда встроен
TASK-046 — Scanner: встраивать фрагмент в payload
Файл: scanner/src/managed_scanner.py (отправка результатов, ~строка 673)

Логика:

Только для image_region (OCR).

Только если файл ≤ MAX_FRAGMENT_EMBED_SIZE (настраиваемый ENV, default 2 МБ).

Base64 + SHA-256.

Иначе — fragment_base64 = None, остаётся только fragment_path.

Скелет:

python
import base64, hashlib, os

MAX_FRAGMENT_EMBED_SIZE = int(os.environ.get("MAX_FRAGMENT_EMBED_SIZE", 2 * 1024 * 1024))

def _embed_fragment(finding) -> dict:
    """BACKLOG-086 (TASK-046): встроить OCR-фрагмент в payload."""
    if finding.fragment_type != "image_region":
        return {}  # text_line/byte_range — не встраиваем
    if not finding.fragment_path or not os.path.exists(finding.fragment_path):
        return {}
    size = os.path.getsize(finding.fragment_path)
    if size > MAX_FRAGMENT_EMBED_SIZE:
        return {}  # слишком большой — оставляем только fragment_path
    with open(finding.fragment_path, "rb") as f:
        data = f.read()
    return {
        "fragment_base64": base64.b64encode(data).decode("ascii"),
        "fragment_mime": "image/png",  # или по расширению
        "fragment_hash": hashlib.sha256(data).hexdigest(),
        "fragment_size": len(data),
    }
В payload (строка ~673):

python
{
    "line_number": finding.line_number,
    "category": finding.category,
    # ... существующие поля
    "bounding_box": finding.bounding_box,
    **_embed_fragment(finding),  # ← добавить
}
ENV:

MAX_FRAGMENT_EMBED_SIZE (default 2097152 = 2 МБ) — настраиваемый.

TASK-047 — Manager: сохранять фрагмент
Файл: manager/src/api/scanner.py, endpoint /api/scanner/tasks/{id}/results (~строка 490)

Обработка payload:

python
# BACKLOG-086 (TASK-047): встроенный фрагмент
fragment_b64 = finding_data.get("fragment_base64")
fragment_data = None
if fragment_b64:
    try:
        fragment_data = base64.b64decode(fragment_b64)
    except Exception as e:
        logger.warning(f"Failed to decode fragment: {e}")

finding = Finding(
    # ... существующие поля
    bounding_box=finding_data.get("bounding_box"),  # TASK-044 (BUG-077)
    fragment_data=fragment_data,
    fragment_mime=finding_data.get("fragment_mime"),
    fragment_hash=finding_data.get("fragment_hash"),
    fragment_size=len(fragment_data) if fragment_data else None,
    fragment_embedded_at=datetime.utcnow() if fragment_data else None,
)
TASK-048 — Manager: обновить /fragment + новый /fragment/hash
Файл: manager/src/api/findings.py, роут _get_image_fragment (~строка 464)

Новая логика (приоритеты):

Если fragment_data IS NOT NULL — отдать из БД:

Content-Type: fragment_mime

X-Fragment-Mode: embedded

X-Fragment-Hash: <sha256>

Content-Length: fragment_size

Иначе если bounding_box IS NOT NULL — резать по bbox (существующая логика).

Иначе если bounding_box IS NULL и fragment_path существует на хосте Manager — отдать файл (X-Fragment-Mode: full-image).

Иначе — 404.

⚠️ RBAC — ужесточить до Auditor+:

python
@router.get("/{finding_id}/fragment")
async def get_fragment(
    finding_id: int,
    current_user: User = Depends(require_role("auditor", "admin")),  # BACKLOG-086
    db: Session = Depends(get_db),
):
Новый endpoint — /fragment/hash:

python
@router.get("/{finding_id}/fragment/hash")
async def get_fragment_hash(
    finding_id: int,
    current_user: User = Depends(require_role("auditor", "admin")),
    db: Session = Depends(get_db),
):
    """BACKLOG-086: метаданные встроенного фрагмента (для аудита)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    if not finding.fragment_data:
        raise HTTPException(404, "No embedded fragment")
    return {
        "finding_id": finding.id,
        "hash": finding.fragment_hash,
        "size": finding.fragment_size,
        "mime": finding.fragment_mime,
        "embedded_at": finding.fragment_embedded_at,
    }
Аудит доступа — каждый GET /fragment и /fragment/hash логируется:

python
audit_log(
    action="fragment_accessed",
    user=current_user,
    finding_id=finding.id,
    metadata={"mode": "embedded|full-image"},
)
TASK-049 — Alembic-миграция
Файл: manager/src/db/migrations/versions/00X_add_fragment_columns.py

python
def upgrade():
    op.add_column('findings', sa.Column('fragment_data', sa.LargeBinary(), nullable=True))
    op.add_column('findings', sa.Column('fragment_mime', sa.String(50), nullable=True))
    op.add_column('findings', sa.Column('fragment_hash', sa.String(64), nullable=True))
    op.add_column('findings', sa.Column('fragment_size', sa.Integer(), nullable=True))
    op.add_column('findings', sa.Column('fragment_embedded_at', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('findings', 'fragment_embedded_at')
    op.drop_column('findings', 'fragment_size')
    op.drop_column('findings', 'fragment_hash')
    op.drop_column('findings', 'fragment_mime')
    op.drop_column('findings', 'fragment_data')
TASK-050 — Батчинг POST'ов (вынесено отдельно)
Проблема: 100 findings × 2 МБ base64 = ~200 МБ в одном POST. Memory/timeout риск.

Требование: проверить, есть ли батчинг в managed_scanner.py. Если нет — разбивать POST на чанки по общему размеру:

python
MAX_BATCH_SIZE_BYTES = 20 * 1024 * 1024  # 20 МБ на POST (настраиваемый)

# Разбить findings на батчи по размеру
batches = _split_by_size(findings, MAX_BATCH_SIZE_BYTES)
for batch in batches:
    POST /api/scanner/tasks/{id}/results
ENV: MAX_BATCH_SIZE_BYTES (default 20971520 = 20 МБ).

⚠️ Уточнить у архитектора: делать ли TASK-050 в рамках BACKLOG-086 или отдельным ТЗ. В этом ТЗ — отдельная задача TASK-050, если батчинга ещё нет.

🧪 Тесты
Unit — Manager — tests/unit/test_fragment_embed_v31319.py
python
"""BACKLOG-086 (TASK-045..049, v3.13.19): встроенные фрагменты."""

import base64
import hashlib


class TestFragmentEmbed:
    def test_fragment_saved_from_payload(self):
        """fragment_base64 → findings.fragment_data (decoded)."""
        # mock POST /api/scanner/tasks/{id}/results с payload + fragment_base64
        # assert finding.fragment_data == decoded bytes
        # assert finding.fragment_hash == sha256
        # assert finding.fragment_size == len(data)
        pass

    def test_text_line_fragment_not_embedded(self):
        """text_line findings — fragment_data = None (не встраиваем)."""
        pass

    def test_fragment_endpoint_returns_embedded(self):
        """GET /fragment → из БД с X-Fragment-Mode: embedded."""
        pass

    def test_fragment_endpoint_falls_back_to_path(self):
        """fragment_data IS NULL + fragment_path есть → full-image."""
        pass

    def test_fragment_endpoint_404_when_nothing(self):
        """fragment_data NULL + fragment_path отсутствует → 404."""
        pass

    def test_fragment_endpoint_requires_auditor(self):
        """GET /fragment: viewer → 403, auditor → 200."""
        pass

    def test_fragment_hash_endpoint(self):
        """GET /fragment/hash → hash, size, mime, embedded_at."""
        pass

    def test_fragment_access_audited(self):
        """GET /fragment → запись в audit_logs (action=fragment_accessed)."""
        pass
Ожидание: 8 passed.

Unit — Scanner — tests/unit/test_scanner_fragment_embed.py
python
class TestScannerEmbedsFragment:
    def test_small_image_embedded(self):
        """PNG < 2 МБ → fragment_base64 в payload."""
        pass

    def test_large_image_not_embedded(self):
        """PNG > 2 МБ → fragment_base64 = None, fragment_path сохраняется."""
        pass

    def test_text_line_not_embedded(self):
        """text_line → fragment_base64 = None."""
        pass

    def test_hash_matches_data(self):
        """fragment_hash == sha256(b64decode(fragment_base64))."""
        pass

    def test_custom_max_size_env(self):
        """MAX_FRAGMENT_EMBED_SIZE=1024 → файл 2 КБ не встраивается."""
        pass
Ожидание: 5 passed.

E2E — tests/e2e/test_fragment_e2e.py
python
class TestFragmentE2E:
    def test_fragment_survives_source_deletion(self):
        """
        1. Сканировать C:\\test\\scanner_clean → task N
        2. Найти OCR-finding
        3. GET /fragment → 200, X-Fragment-Mode: embedded
        4. УДАЛИТЬ исходный PNG
        5. GET /fragment → 200, X-Fragment-Mode: embedded ✅
        6. GET /fragment/hash → hash совпадает
        """
        pass
📊 Live-проверка (task 39)
1. Подготовка
powershell
$env:VERSION="3.13.19"
docker compose build manager webui celery_worker celery_beat
docker compose up -d manager webui celery_worker celery_beat
curl http://127.0.0.1:8000/api/health
# → 3.13.19
Перезапустить сканер (Ctrl+C → start_scanner.bat).

sql
DELETE FROM findings WHERE task_id IN (36, 37, 38);
2. Task 39
powershell
$body = @{
  resource_path = "C:\test\scanner_clean"
  name          = "scanner_clean_v3.13.19_fragments"
} | ConvertTo-Json

$task = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/tasks/create `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body
$task.id
Дождаться completed, findings_count=29.

3. SQL
sql
-- OCR-finding'и — есть fragment_data
SELECT id, category, fragment_type, detector,
       fragment_size, fragment_mime,
       fragment_hash IS NOT NULL AS has_hash,
       fragment_embedded_at IS NOT NULL AS has_embedded_at,
       octet_length(fragment_data) AS data_bytes
FROM findings
WHERE task_id = 39 AND fragment_type = 'image_region';
-- ожидание: 2 строки, data_bytes > 0, mime=image/png, has_hash=t, has_embedded_at=t

-- text_line — fragment_data = NULL
SELECT COUNT(*) FROM findings
WHERE task_id = 39 AND fragment_type = 'text_line' AND fragment_data IS NOT NULL;
-- ожидание: 0
4. API — Auditor
powershell
$auditorLogin = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" `
  -Body '{"username":"auditor","password":"auditor123"}'
$auditorToken = $auditorLogin.access_token

$r = Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/findings?task_id=39" `
  -Headers @{ Authorization = "Bearer $auditorToken" }
$ocr = $r | Where-Object { $_.fragment_type -eq 'image_region' } | Select-Object -First 1

# 4.1. GET /fragment — из БД (embedded)
$frag = Invoke-WebRequest -Method GET "http://127.0.0.1:8000/api/findings/$($ocr.id)/fragment" `
  -Headers @{ Authorization = "Bearer $auditorToken" }
Write-Host "Status:          $($frag.StatusCode)"
Write-Host "Content-Type:    $($frag.Headers['Content-Type'])"
Write-Host "X-Fragment-Mode: $($frag.Headers['X-Fragment-Mode'])"
Write-Host "X-Fragment-Hash: $($frag.Headers['X-Fragment-Hash'])"
Write-Host "Content-Length:  $($frag.Headers['Content-Length'])"

# 4.2. Hash-endpoint
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/findings/$($ocr.id)/fragment/hash" `
  -Headers @{ Authorization = "Bearer $auditorToken" } | ConvertTo-Json -Depth 5

# 4.3. Сохранить и открыть
Invoke-WebRequest -Method GET "http://127.0.0.1:8000/api/findings/$($ocr.id)/fragment" `
  -Headers @{ Authorization = "Bearer $auditorToken" } -OutFile ocr_embedded.png
Start-Process ocr_embedded.png
Ожидание:

X-Fragment-Mode: embedded

X-Fragment-Hash — SHA-256 hex

PNG открывается

5. RBAC — Viewer должен получить 403
powershell
$viewerLogin = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" `
  -Body '{"username":"viewer","password":"viewer123"}'
$viewerToken = $viewerLogin.access_token

try {
  Invoke-WebRequest -Method GET "http://127.0.0.1:8000/api/findings/$($ocr.id)/fragment" `
    -Headers @{ Authorization = "Bearer $viewerToken" }
  Write-Host "FAIL: viewer получил доступ"
} catch {
  Write-Host "Status: $($_.Exception.Response.StatusCode.value__) (ожидание 403)"
}
6. Ключевой тест — удалить исходник
powershell
# На хосте удалить PNG
Remove-Item C:\test\scanner_clean\images\screenshot_clean.png

# Фрагмент всё ещё доступен
$frag = Invoke-WebRequest -Method GET "http://127.0.0.1:8000/api/findings/$($ocr.id)/fragment" `
  -Headers @{ Authorization = "Bearer $auditorToken" }
Write-Host "After source deleted — Status: $($frag.StatusCode)"
Write-Host "X-Fragment-Mode: $($frag.Headers['X-Fragment-Mode'])"
Ожидание: 200 OK, X-Fragment-Mode: embedded. ✅ Доказательство сохранено!

7. Audit log
sql
SELECT id, action, finding_id, user_id, timestamp, metadata
FROM audit_logs
WHERE action = 'fragment_accessed'
ORDER BY timestamp DESC LIMIT 5;
Ожидание: записи о доступе к фрагменту.

📝 Сводка правок
#	Файл	Действие	Задача
1	manager/src/db/models.py	+5 колонок fragment_*	TASK-045
2	scanner/src/managed_scanner.py	base64 + SHA-256 для image_region	TASK-046
3	manager/src/api/scanner.py	Сохранять fragment_base64	TASK-047
4	manager/src/api/findings.py	/fragment (embedded first), /fragment/hash, RBAC Auditor+	TASK-048
5	manager/src/db/migrations/versions/00X_add_fragment_columns.py	Alembic	TASK-049
6	scanner/src/managed_scanner.py	Батчинг POST'ов (если нет)	TASK-050
7	tests/unit/test_fragment_embed_v31319.py	8 тестов	TASK-045..049
8	tests/unit/test_scanner_fragment_embed.py	5 тестов	TASK-046
9	tests/e2e/test_fragment_e2e.py	E2E с удалением исходника	TASK-048
10	docker-compose.yml	VERSION → 3.13.19, ENV: MAX_FRAGMENT_EMBED_SIZE, MAX_BATCH_SIZE_BYTES	релиз
11	.env.example	+ MAX_FRAGMENT_EMBED_SIZE, MAX_BATCH_SIZE_BYTES	релиз
12	STATE.md, ROADMAP.md, ARCHITECTURE.md, CHANGELOG.md, STATE_TEST_SESSION.md	BACKLOG-086 → ✅	док
13	docs/admin-guide/05-security.md	Раздел «Неизменяемые доказательства»	док
14	docs/admin-guide/09-retention.md	Учесть fragment_data в политиках	док
✅ Критерии закрытия ТЗ
□ py_compile всех изменённых .py — OK
□ Alembic-миграция применена без ошибок
□ pytest tests/unit/test_fragment_embed_v31319.py -v — 8 passed
□ pytest tests/unit/test_scanner_fragment_embed.py -v — 5 passed
□ pytest tests/unit/ -q — 159 passed (146 + 13)
□ pytest tests/e2e/test_fragment_e2e.py -v — passed
□ Manager /api/health → 3.13.19
□ Task 39: fragment_data сохранён для OCR-finding'ов (2 шт)
□ text_line findings: fragment_data = NULL
□ GET /fragment (auditor) → X-Fragment-Mode: embedded, X-Fragment-Hash
□ GET /fragment (viewer) → 403 ✅ (RBAC ужесточён)
□ GET /fragment/hash → SHA-256, size, mime, embedded_at
□ После удаления исходного PNG — GET /fragment всё ещё 200 ✅
□ audit_logs: action=fragment_accessed
□ Батчинг POST'ов работает (TASK-050 — или вынести в отдельное ТЗ)
□ Обновлены: STATE.md, ROADMAP.md, ARCHITECTURE.md, CHANGELOG.md, STATE_TEST_SESSION.md, docs/admin-guide/05-security.md, docs/admin-guide/09-retention.md
🔒 Безопасность и приватность
Фрагменты содержат PII (email/phone видны на картинке).

Аспект	Решение
RBAC	/fragment и /fragment/hash — только Auditor+
Аудит	Каждый доступ → audit_logs (action=fragment_accessed)
Ретенция	Фрагменты удаляются вместе с findings (политики retention)
Шифрование	Опционально в v3.1.0 (AES-256-GCM, как match_text_encrypted)
Размер	MAX_FRAGMENT_EMBED_SIZE (default 2 МБ) — ограничивает объём
Батчинг	MAX_BATCH_SIZE_BYTES (default 20 МБ) — защита от больших POST'ов
⚠️ Важное: fragment_data — не шифруется в v3.13.19. Если это критично для комплаенса — зашифровать (AES-256-GCM) в отдельной задаче. Пока — RBAC + аудит + ограничение размера.

🚀 После закрытия
BACKLOG-086 → ✅ (v3.13.19)

BACKLOG-085 (OCR bbox) → 📋 v3.1.0

BACKLOG-087 (дедупликация фрагментов) → 📋 v3.1.0

BACKLOG-088 (шифрование фрагментов, если нужно) → 📋 v3.1.0

BUG-079 (доступ к /fragment для Viewer) → исправлено (TASK-048 → Auditor+)

TASK-050 (батчинг POST'ов) → в рамках этого ТЗ или отдельно

Продолжить Блок 5 → п.2.3 (фильтры)

📌 Открытые вопросы к архитектору
TASK-050 (батчинг POST'ов) — делать в рамках BACKLOG-086 или отдельным ТЗ? В этом ТЗ — включено, но с оговоркой.

Шифрование fragment_data — сейчас нет, в бэклог (BACKLOG-088) или сразу делать?

Retention для fragment_data — при архивации findings удалять fragment_data или архивировать? Уточнить в docs/admin-guide/09-retention.md.

Автор ТЗ: архитектор
Дата: 26.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.19, BACKLOG-086 → ✅