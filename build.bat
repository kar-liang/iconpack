@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY=C:\Users\YuanL\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" (
    echo [ERROR] Python not found: %PY%
    echo Read README.md section 4, or ask me to fix it.
    pause
    exit /b 1
)

echo ============================================
echo   Icon Pack Builder
echo ============================================
echo.

if "%~1"=="" goto interactive

"%PY%" build.py --base "%~1" %2 %3 %4 %5
goto done

:interactive
echo Put your images in the "icons" folder first.
echo.
set /p BASE="Public base URL (https:\... no trailing slash): "
if "%BASE%"=="" (
    echo Empty URL, cancelled.
    goto done
)
echo.
"%PY%" build.py --base "%BASE%"
goto done

:done
echo.
if exist dist\icons.json (
    echo [DONE] Output is in the dist folder:
    echo        dist\icons.json             ^<- upload this
    echo        dist\manifest.txt           ^<- name / path / size list
    echo        dist\preview.html           ^<- open in browser to verify
    echo        dist\loon-import.html       ^<- open in browser, import to Loon
    echo        dist\senplayer-import.html  ^<- open in browser, import to SenPlayer
    echo.
    echo [NEXT] Upload both the icons folder and dist\icons.json to the web.
    echo        Then open dist\preview.html to confirm every icon loads.
    start "" "dist\preview.html"
) else (
    echo [FAILED] icons.json was not produced. See messages above.
)
echo.
pause
