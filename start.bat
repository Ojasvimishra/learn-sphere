@echo off
title LearnSphere Platform
echo ===================================================
echo Starting LearnSphere Platform (Django + MongoDB)
echo ===================================================

REM Check if MongoDB is running on port 27017
netstat -ano | findstr 27017 >nul
if %errorlevel% neq 0 (
    echo [INFO] Starting MongoDB daemon...
    start /B "" "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --dbpath "%~dp0mongodb_data" --port 27017 --bind_ip 127.0.0.1
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] MongoDB is already running on port 27017.
)

echo [INFO] Starting Django Server at http://127.0.0.1:8000/ ...
start http://127.0.0.1:8000/
"%~dp0.venv\Scripts\python.exe" "%~dp0manage.py" runserver 127.0.0.1:8000
pause
