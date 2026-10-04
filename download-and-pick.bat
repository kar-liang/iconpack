@echo off
cd /d "%~dp0"
set "PY=C:\Users\YuanL\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)
REM Proxy is auto-detected. Pass one as argument 1 to override:
REM   download-and-pick.bat http:\192.168.2.100:7890
set "PROXYARG="
if not "%~1"=="" set "PROXYARG=--proxy %1"
echo Downloading the community icon pack (proxy auto-detect) ...
echo.
"%PY%" fetch_source.py Emby-Icon.json %PROXYARG% --workers 10
if errorlevel 1 (
    echo.
    echo [ERROR] Download failed. Try passing a proxy explicitly, e.g.
    echo   download-and-pick.bat http:\192.168.2.100:7890
    pause
    exit /b 1
)
echo.
"%PY%" picker.py
echo.
echo Pick your icons in the browser, then click the export button.
echo Then run  collect.bat
echo.
pause
