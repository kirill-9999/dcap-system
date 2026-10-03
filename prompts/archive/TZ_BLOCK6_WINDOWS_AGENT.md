📋 ТЗ — БЛОК 6.1 + 6.4: WINDOWS-АГЕНТ + AUDIT POLICY
Файл: prompts/tz/TZ_BLOCK6_WINDOWS_AGENT.md
Дата: 03.10.2026
Версия: v3.13.28 (без bump — инфраструктура)
Статус: ✏️ Готово к разработке
Оценка: ~40 мин
Приоритет: 🟡 важно (Блок 6 — Агенты)

🎯 ЦЕЛЬ
Развернуть Windows-агент аудита как службу, проверить сквозной поток
(Security Log → агент → Manager → audit_logs).

Проверить, что события Windows Audit (4663 и др.) корректно собираются
и отправляются в Manager.

📌 ПРЕДУСЛОВИЯ (уже выполнены)
- ✅ Python 3.13.5 (Anaconda) — E:\Dev\Anaconda3\python.exe
- ✅ pywin32 + requests установлены
- ✅ PowerShell работает от администратора
- ✅ Audit Policy: File System = Success + Failure
- ✅ SACL на E:\test_audit (Everyone, FullControl, Success+Failure)
- ✅ События 4663 генерируются (проверено)
- ✅ config.json обновлён:
    manager_url=http://localhost:8000
    hostname=DESKTOP-9TI677N
    paths=["E:\\test_audit"]
- ✅ Manager работает на http://localhost:8000
- ❌ Служба DCAPAuditAgent НЕ установлена

📁 ФАЙЛЫ
Windows-агент: audit-agent-windows/
- main.py              (11 KB)  — точка входа
- collector.py         (9.9 KB) — чтение Security Log через wevtutil
- sender.py            (3.6 KB) — отправка в Manager
- buffer.py            (3.3 KB) — SQLite-буфер
- service.py           (6.3 KB) — Windows-служба (pywin32)
- config.json          (696 B)  — конфигурация
- requirements.txt     (30 B)   — requests, pywin32
- install_service.bat           — установка службы
- start_service.bat / stop_service.bat / restart_service.bat
- uninstall_service.bat
- README.md (9.6 KB) — инструкция (⚠️ содержит ошибку про SACL, см. BUG-121)

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-085 — Проверка предусловий

Проверить Python, pywin32, requests:
```powershell
python --version
python -c "import win32serviceutil; print('pywin32 OK')"
python -c "import requests; print('requests OK', requests.__version__)"
Проверить, что текущая PowerShell — от админа:

powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Ожидание: True.

Проверить конфиг:

powershell
Get-Content E:\projects\dcap-system\audit-agent-windows\config.json
Ожидание: hostname=DESKTOP-9TI677N, paths=["E:\test_audit"].

Проверить, что события 4663 генерируются:

powershell
"test" | Out-File E:\test_audit\pre_check.txt -Encoding UTF8
Get-Content E:\test_audit\pre_check.txt
Remove-Item E:\test_audit\pre_check.txt
Start-Sleep 3
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4663} -MaxEvents 3 |
    Select-Object TimeCreated, Id, @{n='Target';e={$_.Properties[6].Value}}
Ожидание: минимум 1 событие с Target=E:\test_audit\pre_check.txt.

TASK-086 — Первый запуск агента вручную (проверка регистрации)

⚠️ PowerShell ОТ АДМИНИСТРАТОРА (для чтения Security Log).

powershell
cd E:\projects\dcap-system\audit-agent-windows
python main.py
Что ожидаем в консоли:

[INFO] Audit Agent v... starting

[INFO] Reading config: config.json

[INFO] Registering agent: audit-agent-01

[INFO] Registered with id=N

[INFO] Agent started, entering main loop

Оставить окно открытым.

Проверить в Manager (второе окно):

powershell
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Method GET http://127.0.0.1:8000/api/audit/agents -Headers $headers |
    ConvertTo-Json -Depth 5
Ожидание: агент audit-agent-01 в списке, status=online.

TASK-087 — Проверка сквозного потока (событие → Manager)

В окне агента (TASK-086) продолжает работать main loop.

Создать событие (третье окно):

powershell
"test content 2" | Out-File E:\test_audit\file2.txt -Encoding UTF8
Get-Content E:\test_audit\file2.txt
Remove-Item E:\test_audit\file2.txt
Подождать 60–90 секунд (read_interval=60 в config.json).

В окне агента должны появиться:

[INFO] Found X events matching filters

[INFO] Sending X events to Manager

[INFO] Sent X events

Проверить в Manager:

powershell
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=windows_agent&limit=10" -Headers $headers |
    ConvertTo-Json -Depth 5
Ожидание: события от windows_agent, > 0.

Проверка в БД:

powershell
$sql = @'
SELECT id, created_at, event_type, "user", file_path, source_host
FROM audit_logs
WHERE event_source = 'windows_agent'
ORDER BY created_at DESC
LIMIT 10;
'@
$sql | docker exec -i dcap-postgres psql -U dcap -d dcap
Ожидание: записи с user=DESKTOP-9TI677N\User, file_path=E:\test_audit\file2.txt.

Остановить агент: Ctrl+C в окне TASK-086.

TASK-088 — Установка как службы

⚠️ PowerShell ОТ АДМИНИСТРАТОРА.

powershell
cd E:\projects\dcap-system\audit-agent-windows

# Установить
python service.py install

# Запустить
python service.py start

# Проверить
Get-Service DCAPAuditAgent
Ожидание:

Status: Running

DisplayName: DCAP Audit Agent

Проверить логи службы:

powershell
Get-Content E:\projects\dcap-system\audit-agent-windows\logs\audit_agent.log -Tail 30
Ожидание: [INFO] Registered with id=N, [INFO] Reading Security Log.

Проверить в Manager, что агент активен:

powershell
Invoke-RestMethod -Method GET http://127.0.0.1:8000/api/audit/agents -Headers $headers |
    ConvertTo-Json -Depth 5 | Select-String "audit-agent-01" -Context 2,10
TASK-089 — Финальный тест: событие через службу

powershell
# Создать событие
"final test" | Out-File E:\test_audit\file3.txt -Encoding UTF8
Get-Content E:\test_audit\file3.txt
Remove-Item E:\test_audit\file3.txt

# Подождать 60-90 сек
Start-Sleep 90

# Проверить в Manager
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=windows_agent&limit=5" -Headers $headers |
    ConvertTo-Json -Depth 5
Ожидание: событие с file_path=file3.txt в списке.

🧪 КРИТЕРИИ ПРИЁМКИ
□ python service.py install → успех
□ Get-Service DCAPAuditAgent → Running
□ Агент зарегистрирован в Manager (audit-agent-01, online)
□ Событие 4663 → отправлено в Manager → появилось в audit_logs
□ Логи службы: logs/audit_agent.log содержит [INFO] Sent N events
□ При перезагрузке служба запускается автоматически
□ config.json не требует ручных правок

📊 LIVE-ПРОВЕРКА (полный сквозной поток)

powershell
# 1. Проверка службы
Get-Service DCAPAuditAgent

# 2. Проверка в Manager
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Method GET http://127.0.0.1:8000/api/audit/agents -Headers $headers

# 3. Создать событие
"live test" | Out-File E:\test_audit\live.txt -Encoding UTF8
Get-Content E:\test_audit\live.txt
Start-Sleep 90

# 4. Проверка
Invoke-RestMethod -Method GET "http://127.0.0.1:8000/api/audit?event_source=windows_agent&limit=10" -Headers $headers
📝 СВОДКА ПРАВОК

#	Файл	Действие	Задача
1	audit-agent-windows/config.json	Обновлён (hostname, paths)	TASK-085
2	Система	Audit Policy + SACL настроены	TASK-085
3	Служба DCAPAuditAgent	Установлена и запущена	TASK-088
🐛 BUG-121 (найден в этой сессии) — ошибка в README

Файл: audit-agent-windows/README.md, раздел «Настройка аудита Windows».

Проблемы:

README предлагает icacls ... /grant ... — устанавливает DACL, не SACL.

icacls вообще НЕ поддерживает параметр /audit — такого параметра нет!

Everyone не резолвится на русской Windows — нужен SID S-1-1-0.

Правильная команда (заменена в сессии):

powershell
# Включить аудит
auditpol /set /subcategory:"{0CCE921D-69AE-11D9-BED3-505054503030}" /success:enable /failure:enable

# Установить SACL (через PowerShell с SID)
$path = "E:\test_audit"
$ACL = Get-Acl $path
$AuditUser = New-Object System.Security.Principal.SecurityIdentifier("S-1-1-0")
$AccessRule = New-Object System.Security.AccessControl.FileSystemAuditRule($AuditUser,"FullControl","ContainerInherit,ObjectInherit","None","Success,Failure")
$ACL.SetAuditRule($AccessRule)
$ACL | Set-Acl $path
Действие: обновить README.md (отдельная задача для v3.1.0 или в этой же сессии).

📋 ОТКРЫТЫЕ ВОПРОСЫ

Нужно ли маскировать E:\test_audit в примерах? (нет, dev-стенд)

Что делать, если агент не видит события 4663? → диагностика: Get-Acl, auditpol /get

Служба не запускается? → проверить права администратора, pywin32

⚠️ ЧТО НЕ ДЕЛАЕМ

Не фиксим BUG-121 в README (отдельная задача).

Не проверяем события 4656 (Windows пишет их не всегда).

Не настраиваем permissions_interval (сбор прав AD) — отдельная задача Блок 6.5.

Автор ТЗ: архитектор
Дата: 03.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: Windows-агент работает как служба, события идут в Manager