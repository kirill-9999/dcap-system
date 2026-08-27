@echo off
chcp 65001 >nul
echo Установка службы DCAP Audit Agent...
cd /d "%~dp0"
python service.py install
echo Служба установлена.
echo Для запуска выполните: python service.py start
pause
