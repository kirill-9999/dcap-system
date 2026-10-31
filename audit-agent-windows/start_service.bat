@echo off
chcp 65001 >nul
echo Запуск службы DCAP Audit Agent...
cd /d "%~dp0"
python service.py start
pause
