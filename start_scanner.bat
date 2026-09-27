@echo off
REM ============================================================
REM  DCAP Scanner launcher (v3.13.13+)
REM  Загружает ENV-ключи Findings из secrets\ и запускает сканер.
REM  Использование: двойной клик или .\start_scanner.bat
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo [X] DCAP Scanner launcher
echo ============================================================

REM --- 1. Проверка файлов секретов ---
if not exist "secrets\findings_encryption_key" (
    echo [ERROR] Missing file: secrets\findings_encryption_key
    echo         Generate keys: python scripts\generate_findings_keys.py
    pause
    exit /b 1
)
if not exist "secrets\findings_hmac_key" (
    echo [ERROR] Missing file: secrets\findings_hmac_key
    pause
    exit /b 1
)
if not exist "secrets\findings_key_id" (
    echo [ERROR] Missing file: secrets\findings_key_id
    pause
    exit /b 1
)

REM --- 2. Загрузка ENV из файлов ---
set FINDINGS_ENCRYPTION_KEY=
set FINDINGS_HMAC_KEY=
set FINDINGS_KEY_ID=

for /f "usebackq delims=" %%i in ("secrets\findings_encryption_key") do set FINDINGS_ENCRYPTION_KEY=%%i
for /f "usebackq delims=" %%i in ("secrets\findings_hmac_key") do set FINDINGS_HMAC_KEY=%%i
for /f "usebackq delims=" %%i in ("secrets\findings_key_id") do set FINDINGS_KEY_ID=%%i

echo [OK] ENV loaded:
echo      FINDINGS_ENCRYPTION_KEY: !FINDINGS_ENCRYPTION_KEY:~0,12!...
echo      FINDINGS_HMAC_KEY:       !FINDINGS_HMAC_KEY:~0,12!...
echo      FINDINGS_KEY_ID:         !FINDINGS_KEY_ID!

REM --- 3. Проверка конфига сканера ---
if not exist "scanner\config\scanner_config.json" (
    echo [ERROR] Config not found: scanner\config\scanner_config.json
    pause
    exit /b 1
)

REM --- 4. Проверка Manager (warning, не критично) ---
powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://localhost:8000/api/health' -TimeoutSec 3; Write-Host ('[OK] Manager: ' + $h.status + ', version ' + $h.version) -ForegroundColor Green } catch { Write-Host '[WARN] Manager not responding at http://localhost:8000/api/health' -ForegroundColor Yellow }"

echo ============================================================
echo Starting scanner: scanner\config\scanner_config.json
echo To stop: Ctrl+C
echo ============================================================
echo.

REM --- 5. Запуск сканера ---
python -X utf8 run_scanner.py scanner\config\scanner_config.json

REM --- 6. Пауза после завершения, чтобы увидеть ошибки ---
echo.
echo [X] Scanner stopped.
pause