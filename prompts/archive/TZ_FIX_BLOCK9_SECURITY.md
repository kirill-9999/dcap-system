📄 ТЗ: ФИКС-СПРИНТ — Блок 9 (Безопасность)
Файл: TZ_FIX_BLOCK9_SECURITY.md
Версия: v3.13.27 → v3.13.28
Оценка: ~10 ч (полный спринт) / ~5–6 ч (приоритет 🔴)
Дата: 03.10.2026
Приоритет: 🔴 critical (блокер v3.0.0 — mTLS/compliance/observability)
Обнаружено: 01–03.10.2026, мастер-сессия Блока 9

🎯 Проблема (сводно)
Мастер-сессия Блока 9 (Безопасность) выявила 10 BUG и 16 TEST-NOTE. Критичные из них:

mTLS не работает (BUG-105…108) — заявлен как production-feature в SECURITY.md / ARCHITECTURE.md.

MetricsMiddleware не видит защищённый трафик + кардинальность (BUG-103) — обсервабилити + алерты ломаются.

reveal при ошибке расшифровки: 500 вместо 409 + нет аудита (BUG-110) — нарушение 152-ФЗ / GDPR.

export findings: ломается на одном битом finding (BUG-111), нет source_host (BUG-114).

ротация ключей ломает fingerprint/дедупликацию (BUG-116).

📌 Доказательная база
BUG-103 — MetricsMiddleware
text
endpoint="/api/findings"        — list-запрос
endpoint="/api/findings/1594"   — ⚠️ серия на КАЖДЫЙ ID
endpoint="/api/findings/1595"   — ⚠️ серия на КАЖДЫЙ ID
При запросе без JWT (401 от AuthMiddleware) — endpoint не появляется.
Все защищённые эндпоинты невидимы → алерт HighErrorRate не сработает.

BUG-105 — mTLS volume
text
docker inspect dcap-manager:
  "Source": "E:\\projects\\dcap-system\\manager\\certs"
  "Destination": "/app/certs"

Get-ChildItem manager\certs   → ПУСТО
CertificateManager ожидает /app/certs/{ca,manager,crl}/... — не находит.

BUG-106 — _check_mtls мёртвый код
text
middleware.py:86  — def _check_mtls
middleware.py:176 — mtls_error = self._check_mtls(request)   ← единственный вызов

dispatch():
  1. if self._is_public(path): return call_next   ← machine-пути уходят сюда
  2. if self._is_machine_endpoint(path): ...      ← НЕДОСТИЖИМО
_is_public включает machine_prefixes → возвращает True раньше.

BUG-107 — CRL не проверяется
text
grep "is_revoked|verify_client_cert|_check_mtls":
  security.py:95  def verify_client_cert     ← объявлен, не вызывается
  security.py:117 def is_revoked             ← объявлен, не вызывается
  middleware.py:86,176 — _check_mtls (мёртвый, см. BUG-106)

В TLS-контексте (run_manager.py):
  НЕ установлен ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
BUG-108 — run_manager.py дублирует TLS
python
# run_manager.py — свой TLS, не вызывает CertificateManager:
if mtls_enabled and all(p.exists() for p in (cert_path, key_path, ca_path)):
    uvicorn_kwargs.update({
        "ssl_keyfile": ..., "ssl_certfile": ..., "ssl_ca_certs": ...,
        "ssl_cert_reqs": ssl.CERT_OPTIONAL,   # ← всегда OPTIONAL, даже в strict
    })
CertificateManager.get_server_ssl_context() не вызывается.

BUG-110 — reveal 500 + нет аудита
python
# manager/src/api/findings.py — reveal_finding
try:
    match_text = enc.decrypt(...) if ... else None
    line_text  = enc.decrypt(...) if ... else None
except ValueError:
    raise HTTPException(500, "Decryption failed")   # ← 500, не 409

revealed_at = datetime.utcnow()
_log_reveal(db, user, finding, revealed_at, request)   # ← не вызывается при ошибке
BUG-111 — export ломается
python
# _export_csv / _export_json
def _resolve_text(finding, field, reveal):
    if reveal:
        encrypted = getattr(finding, f"{field}_encrypted", None)
        if encrypted:
            return get_encryption().decrypt(encrypted)   # ← без try/except
Один битый finding → ValueError → FastAPI 500 → весь экспорт падает.

BUG-114 — _log_export без source_host
python
def _log_export(db, user, export_format, reveal, findings, filters):
    log = AuditLog(
        ...
        file_path="/",           # ← хардкод
        # source_host отсутствует
    )

# Эндпоинт export_findings тоже не принимает request.
Сравните с _log_reveal: принимает request, пишет source_host.

BUG-116 — ротация ломает fingerprint
python
# scripts/reencrypt_findings.py — docstring:
"Fingerprint НЕ пересчитывается (смена ключа сломает FP)."
FINDINGS_HMAC_KEY меняется вместе с FINDINGS_ENCRYPTION_KEY → fingerprint всех findings становится несовместим с новым ключом → при повторном сканировании — дубликаты.

🔧 Задача — фикс-спринт
Группа 1 — mTLS (BUG-105, 106, 107, 108) — ~3-4 ч
TASK-074 (BUG-105) — Починить volume
Файл: docker-compose.yml (секция manager: volumes:)

Было:

yaml
- ./manager/certs:/app/certs:ro
Стало:

yaml
- ./certs:/app/certs:ro
Проверка: после docker compose up -d manager → docker exec dcap-manager ls /app/certs/ca/ca.crt → существует.

TASK-075 (BUG-106) — Порядок в dispatch()
Файл: manager/src/auth/middleware.py — метод dispatch.

Было:

python
if self._is_public(path):
    return await call_next(request)

if self._is_machine_endpoint(path):
    mtls_error = self._check_mtls(request)
    if mtls_error is not None:
        return mtls_error
    ...
Стало:

python
# BUG-106: machine-эндпоинты ДО _is_public — иначе _check_mtls недостижим
if self._is_machine_endpoint(path):
    mtls_error = self._check_mtls(request)
    if mtls_error is not None:
        return mtls_error
    # ... JWT extraction (BUG-048b) ...
    return await call_next(request)

if self._is_public(path):
    return await call_next(request)
Тест-кейс (strict): POST /api/audit/events без клиентского сертификата → 401 (раньше — 200/422).

TASK-076 (BUG-107) — CRL verification
Файл: manager/src/core/security.py — get_server_ssl_context / get_client_ssl_context.

Было:

python
if self.crl_path.exists():
    ctx.load_verify_locations(cafile=str(self.crl_path))
Стало:

python
if self.crl_path.exists():
    ctx.load_verify_locations(cafile=str(self.crl_path))
    ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
Дополнительно — в _check_mtls (middleware) добавить явную проверку для строгого режима:

python
if self.cert_manager.strict and peer_cert:
    if self.cert_manager.is_revoked(peer_cert):   # требуется pem-encoding
        return JSONResponse(401, {"detail": "Client certificate revoked"})
Тест: отозвать scanner.crt (scripts/rotate_certs.py --revoke <serial>), добавить в crl.pem → POST /api/audit/events → 401.

TASK-077 (BUG-108) — Единый TLS-контекст
Файл: run_manager.py

Было:

python
if mtls_enabled and all(p.exists() for p in (cert_path, key_path, ca_path)):
    uvicorn_kwargs.update({
        "ssl_keyfile": str(key_path), ...
        "ssl_cert_reqs": ssl.CERT_OPTIONAL,
    })
Стало:

python
from manager.src.core.security import CertificateManager

security_cfg = data.get("security", {})
cert_manager = CertificateManager(security_cfg)
ssl_ctx = cert_manager.get_server_ssl_context()

if ssl_ctx is not None:
    # BUG-108: единый TLS-контекст, включая CRL и strict
    uvicorn_kwargs["ssl"] = ssl_ctx
    print(f"[run_manager] mTLS enabled: https://{host}:{port}")
else:
    print(f"[run_manager] plain HTTP: http://{host}:{port}")
ВАЖНО: убедиться, что CertificateManager.get_server_ssl_context() учитывает strict — в strict-mode ssl_cert_reqs должен быть CERT_REQUIRED, не CERT_OPTIONAL. Правка security.py:

python
ctx.verify_mode = ssl.CERT_REQUIRED if self.strict else ssl.CERT_OPTIONAL
Группа 2 — Compliance findings (BUG-110, 111, 114) — ~2 ч
TASK-078 (BUG-110) — reveal: 409 вместо 500 + аудит
Файл: manager/src/api/findings.py — reveal_finding.

Было:

python
try:
    match_text = enc.decrypt(finding.match_text_encrypted) if finding.match_text_encrypted else None
    line_text  = enc.decrypt(finding.line_text_encrypted)  if finding.line_text_encrypted  else None
except ValueError:
    raise HTTPException(500, "Decryption failed")

revealed_at = datetime.utcnow()
_log_reveal(db, user, finding, revealed_at, request)
Стало:

python
revealed_at = datetime.utcnow()

try:
    match_text = enc.decrypt(finding.match_text_encrypted) if finding.match_text_encrypted else None
    line_text  = enc.decrypt(finding.line_text_encrypted)  if finding.line_text_encrypted  else None
except ValueError as e:
    # BUG-110: аудит попытки (даже неудачной) + 409 вместо 500
    _log_reveal(
        db, user, finding, revealed_at, request,
        failed=True,
        reason=str(e),
        finding_key_id=finding.encryption_key_id,
        current_key_id=enc.key_id,
    )
    raise HTTPException(
        409,
        detail={
            "error": "Decryption failed",
            "reason": "encryption_key_id mismatch",
            "finding_key_id": finding.encryption_key_id,
            "current_key_id": enc.key_id,
        },
    )

_log_reveal(db, user, finding, revealed_at, request)
Правка _log_reveal — добавить параметры failed, reason, finding_key_id, current_key_id:

python
def _log_reveal(db, user, finding, revealed_at, request, failed=False, reason=None, **extra):
    try:
        metadata = {
            "finding_id": finding.id,
            "category": finding.category,
            "finding_type": finding.finding_type,
            "action": "finding_reveal_failed" if failed else "finding_revealed",
        }
        if failed:
            metadata.update({"reason": reason, **extra})
        log = AuditLog(event_type="finding_reveal", ...)
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning(...)
        db.rollback()
Тест: зашифровать finding ключом A, переключить ENV на ключ B → POST /{id}/reveal → 409 + запись в audit_logs.

TASK-079 (BUG-111) — export не падает на одном битом finding
Файл: manager/src/api/findings.py — _resolve_text, _export_csv, _export_json.

Было:

python
def _resolve_text(finding, field, reveal):
    if reveal:
        encrypted = getattr(finding, f"{field}_encrypted", None)
        if encrypted:
            return get_encryption().decrypt(encrypted)   # ← падает
    return getattr(finding, f"{field}_masked", "") or ""
Стало:

python
def _resolve_text(finding, field, reveal):
    if reveal:
        encrypted = getattr(finding, f"{field}_encrypted", None)
        if encrypted:
            try:
                return get_encryption().decrypt(encrypted)
            except ValueError:
                # BUG-111: не роняем весь экспорт из-за одного битого finding
                logger.warning(
                    "Decryption failed for finding %s field %s (key_id=%s)",
                    finding.id, field, finding.encryption_key_id,
                )
                return f"[decryption failed: key_id={finding.encryption_key_id}]"
    return getattr(finding, f"{field}_masked", "") or ""
Тест: один finding с encryption_key_id ≠ текущего + reveal=true → экспорт 200, в CSV — строка с маркером, остальные — расшифрованы.

TASK-080 (BUG-114) — _log_export с source_host и file_path
Файл: manager/src/api/findings.py — export_findings, _log_export.

Было:

python
async def export_findings(
    format: str = Query("csv", ...),
    ...
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor),
):
    ...
    _log_export(db, current_user, format, reveal, findings, {...})


def _log_export(db, user, export_format, reveal, findings, filters):
    log = AuditLog(
        event_type="findings_exported", ...,
        file_path="/",
        # source_host НЕ передаётся
    )
Стало:

python
async def export_findings(
    request: Request,                          # ← добавить
    format: str = Query("csv", ...),
    ...
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor),
):
    ...
    _log_export(db, current_user, format, reveal, findings, {...}, request)


def _log_export(db, user, export_format, reveal, findings, filters, request=None):
    log = AuditLog(
        event_type="findings_exported", ...,
        file_path=request.url.path if request else "/api/findings/export",
        source_host=request.client.host if request and request.client else None,
        ...
    )
Тест: GET /api/findings/export?reveal=false от admin → в audit_logs запись с file_path="/api/findings/export", source_host="172.19.0.1".

Группа 3 — Минорные (BUG-115) — ~10 мин
TASK-081 (BUG-115) — /api/findings/count с require_auth
Файл: manager/src/api/findings.py — get_findings_count_legacy.

Было:

python
@router.get("/count")
def get_findings_count_legacy(
    ...,
    db: Session = Depends(get_db),
):
Стало:

python
@router.get("/count")
def get_findings_count_legacy(
    ...,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),      # ← добавить
):
Группа 4 — Ротация ключей (BUG-116) — ~2–3 ч
TASK-082 (BUG-116) — Пересчёт fingerprint при ротации
Файл: scripts/reencrypt_findings.py

Изменение логики:

Расшифровать match_text_encrypted (для получения plaintext match).

Расшифровать line_text_encrypted (нужно для контекста — не обязательно).

Получить file_path (= finding.fragment_path), line_number, category.

Пересчитать fingerprint новым HMAC-ключом:

python
new_fp = hmac.new(new_hmac_key, f"{file_path}|{line}|{match}|{category}".encode(), hashlib.sha256).hexdigest()
Обновить finding.fingerprint = new_fp.

Проверить дедупликацию — если новый FP уже есть в БД → не создавать дубликат, объединить в одну запись.

Параметры (добавить):

--recompute-fingerprint (по умолчанию true).

--dedup (объединять дубликаты).

Дополнительно: в docstring добавить предупреждение:

text
⚠️ ВНИМАНИЕ: при ротации HMAC-ключа все fingerprints пересчитываются.
   Это может привести к коллизиям, если в БД уже есть finding с таким FP.
   Используйте --dedup для автоматического объединения.
Тест:

Скан → 10 findings с key_id A.

Ротация на key_id B (reencrypt_findings.py).

Повторный скан того же файла → 0 новых findings (дедупликация работает).

Группа 5 — MetricsMiddleware (BUG-103) — ~2–3 ч
TASK-083 (BUG-103) — Порядок middleware + нормализация endpoint
Файл: manager/src/main.py

Было (порядок add_middleware):

python
app.add_middleware(CORSMiddleware, ...)        # стр. 57
app.add_middleware(MetricsMiddleware)          # стр. 66
app.add_middleware(AuthMiddleware, ...)        # стр. 102
app.add_middleware(RateLimitMiddleware, ...)   # стр. 148
Стало — MetricsMiddleware СНАРУЖИ всех (добавить после RateLimitMiddleware):

python
app.add_middleware(CORSMiddleware, ...)        # внутренний
app.add_middleware(AuthMiddleware, ...)
app.add_middleware(RateLimitMiddleware, ...)
app.add_middleware(MetricsMiddleware)          # ← ПОСЛЕДНИМ = снаружи всех
Файл: manager/src/metrics.py — нормализация endpoint.

Было:

python
endpoint = request.url.path
Стало:

python
import re
# BUG-103: заменяем числовые ID на {id} для предотвращения кардинальности
endpoint = re.sub(r'/\d+', '/{id}', request.url.path)
Тест:

Запрос без JWT → dcap_http_requests_total{endpoint="/api/findings/{id}", status="401"} — есть.

Запросы /api/findings/1594, /api/findings/1595 → одна серия /api/findings/{id}, counter=2.

🧪 Тесты
Unit-тесты
Файл: tests/unit/test_block9_fixes_v31328.py — NEW (порядка 12–15 тестов):

python
"""Мастер-сессия Блока 9 (v3.13.28): регрессионные тесты."""

class TestMTLSFixes:
    def test_bug105_volume_certs_mounted(self): ...
    def test_bug106_machine_endpoint_check_mtls_called(self): ...
    def test_bug107_crl_verify_flags_set(self): ...
    def test_bug108_run_manager_uses_cert_manager(self): ...

class TestFindingsCompliance:
    def test_bug110_reveal_returns_409_on_decryption_error(self): ...
    def test_bug110_reveal_logs_audit_on_failure(self): ...
    def test_bug111_export_survives_one_broken_finding(self): ...
    def test_bug114_export_logs_source_host(self): ...

class TestRBACFix:
    def test_bug115_findings_count_requires_auth(self): ...

class TestKeyRotation:
    def test_bug116_reencrypt_recomputes_fingerprint(self): ...
    def test_bug116_dedup_after_rotation(self): ...

class TestMetricsMiddleware:
    def test_bug103_metrics_visible_for_protected(self): ...
    def test_bug103_endpoint_normalizes_ids(self): ...
E2E-тесты
Файл: tests/e2e/test_block9_fixes_e2e.py — NEW (порядка 3–4 теста):

python
def test_mtls_strict_machine_401(manager_url): ...
def test_reveal_key_mismatch_409(manager_url, admin_token): ...
def test_export_with_source_host(manager_url, admin_token): ...
def test_metrics_endpoint_normalized(manager_url): ...
Ожидание: +15 unit, +4 E2E. Итого unit: 317 + 15 = 332 passed. E2E: 47 + 4 = 51 passed (6 skipped).

🧪 Live-проверка
1. Пересборка
powershell
$env:VERSION="3.13.28"
docker compose build manager celery_worker celery_beat webui
docker compose up -d manager celery_worker celery_beat webui
Start-Sleep 20
(Invoke-RestMethod http://127.0.0.1:8000/api/health).version
# → 3.13.28
2. BUG-105 — PKI виден
powershell
docker exec dcap-manager ls /app/certs
# → ca/ manager/ scanner/ webui/ agents/ crl/
docker exec dcap-manager ls /app/certs/ca/ca.crt
# → ca.crt
3. BUG-103 — метрики видят защищённые эндпоинты
powershell
# Логин + 2 запроса
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod http://127.0.0.1:8000/api/findings/1594 -Headers $h
Invoke-RestMethod http://127.0.0.1:8000/api/findings/1595 -Headers $h

# Проверить метрики:
docker exec dcap-manager curl -s http://localhost:8000/metrics | Select-String "findings"
# Ожидаем: dcap_http_requests_total{endpoint="/api/findings/{id}", ...} 2.0
# И dcap_http_requests_total{endpoint="/api/auth/login", status="200"} 1.0
4. BUG-110 — reveal 409
Смоделировать key_id mismatch:

В БД найти finding, расшифровать его старым ключом.

Переключить FINDINGS_ENCRYPTION_KEY в .env на новый.

Перезапустить Manager.

POST /{id}/reveal → ожидаем 409 + запись в audit_logs.

5. BUG-114 — export с source_host
powershell
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/findings/export?format=json" -Headers $h

# Через 1 сек:
$sql = @'
SELECT id, created_at, file_path, source_host
FROM audit_logs WHERE event_type = 'findings_exported'
ORDER BY created_at DESC LIMIT 1;
'@
$sql | docker exec -i dcap-postgres psql -U dcap -d dcap
# Ожидаем: file_path="/api/findings/export", source_host="172.19.0.1"
6. BUG-105/106 — mTLS strict (после TASK-077)
powershell
# В .env установить:
MTLS_ENABLED=true
MTLS_STRICT=true

docker compose up -d manager
Start-Sleep 5

# Machine-эндпоинт без клиентского сертификата:
try {
    Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/audit/events `
        -Body '{}' -ContentType "application/json"
} catch {
    "HTTP $($_.Exception.Response.StatusCode.value__)"   # ожидаем 401
}
7. BUG-116 — ротация с FP
powershell
# dry-run ротации:
python scripts/reencrypt_findings.py `
    --old-key-file secrets/findings_encryption_key `
    --old-hmac-file secrets/findings_hmac_key `
    --new-key-file secrets/new/findings_encryption_key `
    --new-hmac-file secrets/new/findings_hmac_key `
    --new-key-id key-2026-10 `
    --recompute-fingerprint `
    --dry-run
# Ожидаем: все findings обработаны, FP пересчитаны, 0 ошибок
✅ Критерии приёмки
□ python -m py_compile для всех изменённых .py — OK
□ pytest tests/unit/test_block9_fixes_v31328.py -v — 15 passed
□ pytest tests/e2e/test_block9_fixes_e2e.py -v — 4 passed
□ Полный unit: 332+ passed (317 + 15)
□ Полный E2E: 51+ passed (47 + 4)
□ Manager /api/health → 3.13.28
□ Live: BUG-105 — /app/certs виден в контейнере
□ Live: BUG-106 — strict machine-endpoint без сертификата → 401
□ Live: BUG-107 — отозванный сертификат → 401
□ Live: BUG-108 — единый TLS, run_manager.py вызывает CertificateManager
□ Live: BUG-110 — reveal при key mismatch → 409 + запись в audit_logs
□ Live: BUG-111 — export не падает на битом finding
□ Live: BUG-114 — findings_exported.source_host заполнен
□ Live: BUG-115 — /findings/count с явным require_auth
□ Live: BUG-116 — ротация пересчитывает fingerprint (dry-run показывает 0 ошибок)
□ Live: BUG-103 — dcap_http_requests_total{endpoint="/api/findings/{id}"} присутствует
□ Не сломаны существующие тесты (317 unit + 47 E2E)
□ Обновлены STATE.md, ROADMAP.md, CHANGELOG.md, ARCHITECTURE.md, SECURITY.md
📝 Сводка правок
#	Файл	Действие	Задача
1	docker-compose.yml	./certs:/app/certs:ro вместо ./manager/certs	TASK-074 (BUG-105)
2	manager/src/auth/middleware.py	Порядок в dispatch() (machine до public)	TASK-075 (BUG-106)
3	manager/src/core/security.py	ctx.verify_flags |= VERIFY_CRL_CHECK_LEAF + strict CERT_REQUIRED	TASK-076 (BUG-107)
4	run_manager.py	Использовать CertificateManager.get_server_ssl_context()	TASK-077 (BUG-108)
5	manager/src/api/findings.py	reveal_finding — 409 + аудит при ошибке	TASK-078 (BUG-110)
6	manager/src/api/findings.py	_resolve_text — try/except	TASK-079 (BUG-111)
7	manager/src/api/findings.py	export_findings + _log_export — request	TASK-080 (BUG-114)
8	manager/src/api/findings.py	get_findings_count_legacy — require_auth	TASK-081 (BUG-115)
9	scripts/reencrypt_findings.py	Пересчёт fingerprint + dedup	TASK-082 (BUG-116)
10	manager/src/main.py + manager/src/metrics.py	Порядок MetricsMiddleware + regex ID	TASK-083 (BUG-103)
11	tests/unit/test_block9_fixes_v31328.py	NEW — 15 тестов	TASK-084
12	tests/e2e/test_block9_fixes_e2e.py	NEW — 4 теста	TASK-084
13	docker-compose.yml	VERSION=3.13.28	релиз
14	STATE.md, ROADMAP.md, CHANGELOG.md, ARCHITECTURE.md, SECURITY.md	Обновить BUG-103…116 → ✅	док
⚠️ Приоритизация (если полный спринт не влезает)
🔴 Блокеры v3.0.0 (фиксить обязательно):

TASK-074 (BUG-105) — 5 мин.

TASK-075 (BUG-106) — 30 мин.

TASK-076 (BUG-107) — 30 мин.

TASK-077 (BUG-108) — 1–2 ч.

TASK-078 (BUG-110) — 1 ч.

TASK-083 (BUG-103) — 2–3 ч.

Итого: ~5–6 ч.

🟡 Отложить в v3.1.0:

TASK-079 (BUG-111) — 30 мин.

TASK-080 (BUG-114) — 30 мин.

TASK-081 (BUG-115) — 5 мин.

TASK-082 (BUG-116) — 2–3 ч.

🚀 Команда коммита
bash
git checkout -b fix/block9_security_v31328
git add -A
git commit -m "fix: Блок 9 (Безопасность) — v3.13.28

🔴 Критичные фиксы (блокеры v3.0.0):
- BUG-105: docker-compose монтирует ./certs вместо ./manager/certs
- BUG-106: machine-эндпоинты проверяются ДО _is_public (mTLS strict enforce)
- BUG-107: CRL verification (VERIFY_CRL_CHECK_LEAF + middleware)
- BUG-108: run_manager.py использует CertificateManager (единый TLS)
- BUG-110: reveal → 409 + аудит при ошибке расшифровки (152-ФЗ)
- BUG-103: MetricsMiddleware снаружи всех + нормализация endpoint {id}

🟡 Средние:
- BUG-111: export не падает на одном битом finding
- BUG-114: findings_exported пишет source_host + file_path
- BUG-115: /api/findings/count с явным require_auth

🟠 Ротация:
- BUG-116: reencrypt_findings.py пересчитывает fingerprint + dedup

Тесты:
- tests/unit/test_block9_fixes_v31328.py (15)
- tests/e2e/test_block9_fixes_e2e.py (4)
- Итого: 332 unit, 51 E2E

Docs:
- STATE.md → v3.13.28, Блок 9 ✅
- ROADMAP.md: BUG-103…116 → ✅
- ARCHITECTURE.md, SECURITY.md — обновлены
- CHANGELOG.md"
📌 После закрытия
BUG-103, 105, 106, 107, 108, 110, 111, 114, 115, 116 → ✅ v3.13.28

BACKLOG-044 (/metrics защита) — отдельно, если решено закрывать в v3.0.0

Блок 9 (Безопасность) — ЗАКРЫТ

Следующий шаг — Блок 6 (Агенты) или GitHub-пакет (BACKLOG-028/046)

📋 Открытые вопросы к архитектору
BACKLOG-044 (/metrics auth) — включать в этот спринт или отдельно?

BUG-116 (ротация FP) — фиксить сейчас или отложить в v3.1.0 (multi-key)?

mTLS strict в production — разворачивать ли mtls_strict=true на dev-стенде после фикса?

_log_export action — привести к единому action=findings_exported или оставить findings_exported_revealed/_masked?

Тесты — 15 unit хватит или нужны ещё на каждый BUG отдельный файл?

Автор ТЗ: архитектор
Дата: 03.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.28, Блок 9 (Безопасность) → ✅