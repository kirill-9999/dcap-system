@echo off
title DCAP Load Test - E:\much_of_test_files

echo ======================================================================
echo   DCAP LOAD TEST - 22,500 FILES
echo   Source: E:\much_of_test_files
echo ======================================================================
echo.

echo [1/5] Cleaning old data...
cd /d E:\projects\dcap-system
python 01_cleanup.py

echo.
echo [2/5] Starting Manager in separate window...
start "DCAP Manager" cmd /k "cd /d E:\projects\dcap-system && python -m manager.src.main"

echo    Waiting for Manager initialization...
timeout /t 5 /nobreak > nul

echo    Checking Manager health...
curl -s http://localhost:8000/health > nul 2>&1
if errorlevel 1 (
    echo    [!] Manager not responding yet, waiting...
    timeout /t 5 /nobreak > nul
) else (
    echo    [OK] Manager is running
)

echo.
echo [3/5] Creating resource and task for E:\much_of_test_files...
cd /d E:\projects\dcap-system
python test_large_scan\create_resource_large.py

echo.
echo [4/5] Starting load test...
cd /d E:\projects\dcap-system
python test_large_scan\run_large_scan.py

echo.
echo [5/5] Analyzing results...
cd /d E:\projects\dcap-system
python test_large_scan\analyze_results.py

echo.
echo ======================================================================
echo   TEST COMPLETED!
echo   Results saved in database and state_large.json
echo ======================================================================
echo.
pause