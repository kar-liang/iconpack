@echo off
REM ============================================================
REM  One-click icon pack update. Pure ASCII on purpose:
REM  this machine runs code page 936, and chcp 65001 breaks
REM  the batch parser. All Chinese config lives in
REM  iconpack.conf.json, read by publish.py
REM
REM  Flow: edit apps.txt -> download icons -> build -> push
REM ============================================================
setlocal
cd /d "%~dp0"

set "PY=C:\Users\YuanL\.workbuddy\binaries\python\versions\3.13.12\python.exe"

if not exist "%PY%" goto nopy
if not exist "apps.txt" goto noapps
if not exist "iconpack.conf.json" goto noconf

if "%~1"=="check" goto mode_check
if "%~1"=="nopush" goto mode_nopush

echo ============================================================
echo   STEP 1 / 4   Edit the app list
echo ============================================================
echo.
echo   Notepad will open apps.txt.
echo   Add app names, one per line, then save and close it.
echo.
echo   Same-name app  --->  Name = 123456789
echo   Overseas only  --->  Name = 123456789@us
echo   (see the header comment inside apps.txt)
echo.
notepad.exe "apps.txt"

echo.
echo ============================================================
echo   STEP 2 / 4   Download icons from Apple
echo ============================================================
echo.
"%PY%" fetch_ios_icon.py --list apps.txt --out icons/apps
if errorlevel 1 goto dlerr

echo.
echo ============================================================
echo   STEP 3 / 4   Build and push
echo ============================================================
echo.
"%PY%" publish.py
if errorlevel 1 goto builderr

echo.
echo All done.
pause
exit /b 0

:mode_check
"%PY%" publish.py --check
goto theend

:mode_nopush
echo Building only. Nothing will be pushed.
echo.
"%PY%" publish.py --no-push
goto theend

:dlerr
echo.
echo [FAILED] Download step failed. See the messages above.
goto theend

:builderr
echo.
echo [FAILED] Build or push step failed. Nothing was lost.
echo   Local files are saved. Fix the problem and run this again.
goto theend

:nopy
echo.
echo [ERROR] Python not found:
echo   %PY%
echo   Ask me to fix it.
goto theend

:noapps
echo.
echo [ERROR] apps.txt not found next to this file.
goto theend

:noconf
echo.
echo [ERROR] iconpack.conf.json not found next to this file.
echo   Pack name / GitHub repo / base URL are configured there.
goto theend

:theend
echo.
pause
exit /b 1