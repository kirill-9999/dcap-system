@echo off
chcp 65001 >nul
echo Перезапуск службы DCAP Audit Agent...
cd /d "%~dp0"
python service.py stop
timeout /t 3
python service.py start
pause
