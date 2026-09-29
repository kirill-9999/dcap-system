📄 ТЗ: Фикс-спринт BUG-098…101
Файл: TZ_FIX_SPRINT_BUG098-101.md
Версия: v3.13.25 → v3.13.26
Оценка: ~3 ч
Дата: 29.09.2026
Контекст: Блок 5 (WebUI), п.5 (PATCH status) + п.6 (Bulk) + п.8 (False positives)

🎯 Цель
Устранить 4 бага, найденных в Блоке 5. Все — в manager/src/api/findings.py. Один фикс-спринт.

ID	Название	Приоритет
BUG-101	PATCH + bulk не пишутся в audit_logs	🔴 critical
BUG-100	PATCH new не очищает reviewed_by/reviewed_at	🟡 medium
BUG-099	/false-positives → limit/offset → 500 (нет _clamp_int)	🟡 medium
BUG-098	/false-positives → file_path = resource.path (директория)	🟡 medium
🐛 BUG-101 (🔴) — PATCH + bulk не пишутся в audit_logs
Файлы
manager/src/api/findings.py:~690 — update_finding (PATCH)

manager/src/api/findings.py:~739 — bulk_update (POST /bulk)

Доказательство (v3.13.25, 29.09.2026)
За 30 минут: 0 записей finding_confirmed / finding_false_positive / finding_updated — только auth_login (3).

Сделано 10+ запросов:

PATCH 1521, 1522, 1519, 1520 (new→confirmed, new→fp, confirmed→fp, fp→new, new→archived)

bulk confirmed (4 findings) × 2

bulk fp (4 findings) × 1

Ни одной записи. 🐛

Сравнение (что работает)
Эндпоинт	event_type	Пишется?
POST /{id}/reveal	finding_reveal	✅
GET /{id}/fragment	fragment_accessed	✅
GET /findings/export	findings_exported	✅
POST /auth/login	auth_login	✅
PATCH /{id}	—	🐛 нет
POST /bulk	—	🐛 нет
Требование
Добавить запись в audit_logs для каждого успешного изменения статуса.

Event types (по ARCHITECTURE.md):

Новый статус	event_type
confirmed	finding_confirmed
false_positive	finding_false_positive
archived	finding_archived
new (сброс)	finding_reset
Хелпер (общий):

python
def _log_finding_status_change(db, user, finding, old_status, new_status,
                                request, comment=None, via="patch"):
    """BUG-101 (v3.13.26): аудит смены статуса finding.

    via: 'patch' | 'bulk' — для различения источника в metadata.
    """
    try:
        from manager.src.db.models import AuditLog
        event_map = {
            "confirmed":      "finding_confirmed",
            "false_positive": "finding_false_positive",
            "archived":       "finding_archived",
            "new":            "finding_reset",
        }
        log = AuditLog(
            event_type=event_map.get(new_status, "finding_updated"),
            event_source="api",
            user=user.username if user else None,
            file_path=finding.fragment_path or f"finding:{finding.id}",
            source_host=request.client.host if request and request.client else None,
            metadata_json={
                "action": "status_changed",
                "finding_id": finding.id,
                "category": finding.category,
                "finding_type": finding.finding_type,
                "old_status": old_status,
                "new_status": new_status,
                "comment": comment,
                "via": via,
            },
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log status change for finding %s: %s",
                       finding.id, e)
        db.rollback()
В update_finding (PATCH):

python
old_status = finding.status
# ... обновление статуса ...
_log_finding_status_change(db, user, finding, old_status, body.status,
                            request, comment=body.comment, via="patch")
db.commit()
В bulk_update (POST /bulk):

Вариант A — по одной записи на каждый обновлённый finding:

python
for f in updated_findings:
    _log_finding_status_change(db, user, f, old_status_map[f.id],
                                body.status, request, comment=body.comment,
                                via="bulk")
db.commit()  # один commit
Вариант B — одна запись на batch с finding_ids[]:

python
AuditLog(
    event_type=f"finding_bulk_{body.status}",
    metadata_json={"finding_ids": [...], "count": N, ...}
)
Рекомендация: A — каждая finding = отдельная запись (лучше для SIEM, поиска по finding_id).

Тесты
Unit tests/unit/test_audit_status_change_v31326.py:

python
class TestAuditStatusChange:
    def test_patch_confirmed_writes_audit(self): ...
    def test_patch_false_positive_writes_audit(self): ...
    def test_patch_archived_writes_audit(self): ...
    def test_patch_new_reset_writes_audit(self): ...
    def test_bulk_confirmed_writes_audit_per_finding(self): ...
    def test_bulk_false_positive_writes_audit(self): ...
    def test_audit_metadata_has_old_new_status(self): ...
    def test_audit_metadata_via_patch_vs_bulk(self): ...
    def test_audit_user_is_current_user(self): ...
🐛 BUG-100 (🟡) — PATCH new не очищает review-поля
Файл
manager/src/api/findings.py:~690 — update_finding

Доказательство
text
PATCH /findings/1521 {status: false_positive} → reviewed_by=35, reviewed_at=18:57:17
PATCH /findings/1521 {status: new}            → status=new, НО reviewed_by=35, reviewed_at=18:58:05
Требование
При status=new — очистить reviewed_by, reviewed_at, comment.

python
if body.status == "new":
    finding.status = "new"
    finding.reviewed_by = None
    finding.reviewed_at = None
    finding.comment = body.comment  # или None
elif body.status in ("confirmed", "false_positive", "archived"):
    finding.status = body.status
    finding.reviewed_by = user.id
    finding.reviewed_at = datetime.utcnow()
    finding.comment = body.comment
Вопрос: comment при reset — body.comment (если передан) или None? Рекомендация: body.comment.

Тесты
Unit tests/unit/test_patch_reset_clears_review_v31326.py:

python
def test_patch_new_clears_reviewed_by(self): ...
def test_patch_new_clears_reviewed_at(self): ...
def test_patch_new_sets_comment_from_body(self): ...
def test_patch_new_from_fp_clears_all(self): ...
def test_patch_new_from_confirmed_clears_all(self): ...
🐛 BUG-099 (🟡) — /false-positives → limit/offset → 500
Файл
manager/src/api/findings.py:~228-229 — list_false_positives

Доказательство
text
GET /api/findings/false-positives?offset=-1 → 500  🐛
GET /api/findings/false-positives?limit=-5  → 500  🐛
Сравнение: /api/findings?offset=-1 → 200 (clamp из BUG-084).

Причина
В list_false_positives — старые:

python
limit: int = Query(100, le=1000),
offset: int = 0,
Не применён _clamp_int / OptInt из BUG-084 fix.

Требование
Скопировать логику из list_findings:

python
def list_false_positives(
    limit: OptInt = Query(100, le=1000),
    offset: OptInt = Query(0),
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    limit_val = _clamp_int(limit, default=100, lo=1, hi=1000)
    offset_val = _clamp_int(offset, default=0, lo=0, hi=10**9)
    ...
    .offset(offset_val).limit(limit_val).all()
Дополнительно: проверить другие эндпоинты с limit/offset:

powershell
Get-ChildItem -Path "manager\src\api" -Recurse -Filter *.py |
  Select-String -Pattern "offset:\s*int\s*=\s*0|limit:\s*int\s*=\s*Query" |
  Select-Object Path, LineNumber, Line |
  Format-Table -AutoSize
Если есть ещё без _clamp_int — исправить.

Тесты
Unit tests/unit/test_fp_pagination_v31326.py:

python
def test_fp_offset_negative_200(self): ...
def test_fp_limit_negative_200(self): ...
def test_fp_limit_zero_200(self): ...
def test_fp_limit_too_large_200(self): ...
def test_fp_valid_pagination(self): ...
🐛 BUG-098 (🟡) — /false-positives → file_path = директория
Файл
manager/src/api/findings.py:~256 — list_false_positives

Доказательство
Один и тот же finding (id=1523):

text
GET /api/findings?task_id=41&status=false_positive → file_path = C:\test\scanner_clean\pii\phones_clean.txt  ✅
GET /api/findings/false-positives                  → file_path = C:\test\scanner_clean  🐛 (директория)
Причина
python
# Строка 256:
"file_path": res_map.get(f.resource_id) or f.fragment_path,
Приоритет отдан res_map (путь ресурса = директория), а fragment_path (путь файла) — fallback.

Сравнение с рабочим списком (_finding_to_dict, строка 91):

python
"file_path": finding.fragment_path,  # ✅
Требование
Изменить приоритет — fragment_path первым:

python
# Было:
"file_path": res_map.get(f.resource_id) or f.fragment_path,

# Стало:
"file_path": f.fragment_path or res_map.get(f.resource_id),
Или (проще — как в list_findings):

python
"file_path": f.fragment_path,
Дополнительно: проверить другие эндпоинты — res_map.get может быть ещё где-то:

powershell
Select-String -Path "manager\src\api\findings.py" -Pattern "res_map" -Context 2,2
Тесты
Unit tests/unit/test_fp_file_path_v31326.py:

python
def test_fp_file_path_is_fragment_path(self): ...
def test_fp_file_path_not_resource_dir(self): ...
def test_fp_file_path_matches_main_list(self): ...
📝 Сводка правок
#	Файл	Действие	Задача
1	manager/src/api/findings.py	Хелпер _log_finding_status_change	BUG-101
2	manager/src/api/findings.py:~690	Вызов хелпера в update_finding	BUG-101
3	manager/src/api/findings.py:~739	Вызов хелпера в bulk_update (для каждого)	BUG-101
4	manager/src/api/findings.py:~690	Очистка reviewed_by/reviewed_at/comment при new	BUG-100
5	manager/src/api/findings.py:~228-229	OptInt + _clamp_int в list_false_positives	BUG-099
6	manager/src/api/findings.py:~256	file_path = fragment_path первым	BUG-098
7	tests/unit/test_audit_status_change_v31326.py	Создать (9 тестов)	BUG-101
8	tests/unit/test_patch_reset_clears_review_v31326.py	Создать (5 тестов)	BUG-100
9	tests/unit/test_fp_pagination_v31326.py	Создать (5 тестов)	BUG-099
10	tests/unit/test_fp_file_path_v31326.py	Создать (3 теста)	BUG-098
11	docker-compose.yml	VERSION → 3.13.26	релиз
12	STATE.md, ROADMAP.md, CHANGELOG.md	BUG-098…101 → ✅	док
✅ Критерии приёмки
BUG-101
□ PATCH → audit_logs: finding_confirmed / finding_false_positive / finding_archived / finding_reset
□ bulk → audit_logs: N записей (по одной на finding)
□ metadata: old_status, new_status, via (patch/bulk)
□ user = текущий пользователь
□ 9 unit-тестов passed
BUG-100
□ PATCH status=new → reviewed_by=NULL, reviewed_at=NULL
□ comment = body.comment
□ 5 unit-тестов passed
BUG-099
□ offset=-1 / limit=-5 → 200 (clamp)
□ Проверены другие эндпоинты — все с _clamp_int
□ 5 unit-тестов passed
BUG-098
□ file_path = fragment_path (файл, не директория)
□ Совпадает с GET /findings?status=false_positive
□ 3 unit-теста passed
Общее
□ pytest tests/unit -q — 278+ passed (264 + 22)
□ Manager /api/health → 3.13.26
□ Live: PATCH → audit_logs: записи появились
□ Live: /false-positives → file_path = файл
□ Live: offset=-1 → 200
□ Live: PATCH new → reviewed_by = NULL
📊 Live-проверка (после фикса)
powershell
# 1. PATCH → confirmed
$body = @{ status = "confirmed"; comment = "live test" } | ConvertTo-Json
Invoke-RestMethod -Method PATCH "${base}/1521" `
  -Headers @{ Authorization = "Bearer $auditorToken" } `
  -ContentType "application/json" -Body $body | Out-Null

# 2. PATCH → new (reset)
$body2 = @{ status = "new" } | ConvertTo-Json
Invoke-RestMethod -Method PATCH "${base}/1521" `
  -Headers @{ Authorization = "Bearer $auditorToken" } `
  -ContentType "application/json" -Body $body2 | Out-Null

# 3. bulk
$body3 = @{ finding_ids = @(1521, 1516); status = "confirmed" } | ConvertTo-Json
Invoke-RestMethod -Method POST "${base}/bulk" `
  -Headers @{ Authorization = "Bearer $auditorToken" } `
  -ContentType "application/json" -Body $body3 | Out-Null

# 4. FP-эндпоинт с offset=-1
Invoke-RestMethod "${base}/false-positives?offset=-1" `
  -Headers @{ Authorization = "Bearer $auditorToken" } | Select-Object -First 1
SQL:

sql
-- BUG-101: audit пишется
SELECT id, created_at, event_type, "user", metadata::text
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '5 minutes'
  AND event_type LIKE 'finding_%'
ORDER BY created_at DESC;

-- BUG-100: reviewed_by = NULL после reset
SELECT id, status, reviewed_by, reviewed_at FROM findings WHERE id = 1521;

-- BUG-098: file_path = файл
SELECT id, status FROM findings WHERE id = 1523;
API:

powershell
# BUG-098: file_path
(Invoke-RestMethod "${base}/false-positives" `
  -Headers @{ Authorization = "Bearer $auditorToken" })[0].file_path
# ожид. C:\test\scanner_clean\pii\phones_clean.txt
🚀 После закрытия
BUG-098…101 → ✅ v3.13.26

Продолжаем Блок 5 → п.7 (Stats) → п.13 (count) → п.14 (WebUI) → п.15 (Регрессия).

📌 Открытые вопросы к архитектору
BUG-101 — bulk audit: одна запись на finding (Вариант A) или одна на batch (Вариант B)? Рекомендация: A.

BUG-100 — comment при reset: body.comment или None? Рекомендация: body.comment.

BUG-101 — что с DELETE findings? Тоже не пишется? Проверить в ходе фикса.

Event type для reset: finding_reset или finding_new? Рекомендация: finding_reset.

Автор ТЗ: архитектор
Дата: 29.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.26, BUG-098…101 → ✅