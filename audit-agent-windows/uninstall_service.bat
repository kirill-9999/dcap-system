@echo off
chcp 65001 >nul
echo Остановка и удаление службы DCAP Audit Agent...
cd /d "%~dp0"
python service.py stop
python service.py remove
echo Служба удалена.
pause
