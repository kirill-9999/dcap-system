@echo off
chcp 65001 >nul
echo Остановка службы DCAP Audit Agent...
cd /d "%~dp0"
python service.py stop
pause
