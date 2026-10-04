@echo off
cd /d "%~dp0"
set "PY=C:\Users\YuanL\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)
"%PY%" collect.py
echo.
echo Next: run  build.bat  and enter your public base URL.
echo.
pause
