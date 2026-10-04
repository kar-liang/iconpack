@echo off
cd /d "%~dp0"
set "PY=C:\Users\YuanL\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" goto nopy

if exist "apps.txt" goto listmode
if "%~1"=="" goto usage

REM No apps.txt, but app names given on the command line
echo Downloading iOS app icons from Apple server (no proxy needed) ...
echo.
"%PY%" fetch_ios_icon.py %* --out icons/apps
goto done

:listmode
if not "%~1"=="" goto withargs
REM Does apps.txt contain anything other than comments / blank lines?
"%PY%" -c "import sys;ls=[l.strip() for l in open('apps.txt',encoding='utf-8-sig') if l.strip() and not l.strip().startswith('#')];print(len(ls));sys.exit(0 if ls else 1)"
if errorlevel 1 goto usage

:withargs
echo Reading app list from  apps.txt  ...
echo.
"%PY%" fetch_ios_icon.py --list apps.txt %* --out icons/apps
goto done

:nopy
echo [ERROR] Python not found.
goto pause

:usage
echo [ERROR] Nothing to download.
echo.
echo Pick one:
echo.
echo   A) Fill in  apps.txt  (one app name per line), then run this file
echo      again - it reads apps.txt automatically.
echo.
echo   B) Or pass names directly:
echo      fetch-ios-icon.bat  WeChat  Alipay  NetEaseMusic
echo.
echo Tip: add --dry-run first to check every name resolves correctly.

:done
echo.
echo All done. Icons are in  icons\apps
echo Icons downloaded. Use add-icons.bat next time - it does the whole flow.

:pause
echo.
pause
