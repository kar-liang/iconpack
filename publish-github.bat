@echo off
REM [DEPRECATED] Do not use for routine updates.
REM Use add-icons.bat instead - it does download+build+push in one go,
REM reads base URL and pack name from iconpack.conf.json, and uses
REM the master branch (this file still assumes main).
REM Kept only for reference / first-time setup.
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================
echo   Publish icon pack to GitHub
echo ============================================
echo.
echo Requires: git + gh (GitHub CLI), both logged in.
echo Repo will be created as PUBLIC - required, because
echo the phone app fetches raw URLs with no token.
echo.

where git >nul 2>&1 || (echo [ERROR] git not found. & pause & exit /b 1)
where gh   >nul 2>&1 || (echo [ERROR] gh not found. Install GitHub CLI. & pause & exit /b 1)

if not exist "icons\*.png" if not exist "icons\*.jpg" (
    echo [ERROR] No images found in icons\. Nothing to publish.
    pause
    exit /b 1
)

set /p REPO="Repo name (e.g. my-icons): "
if "%REPO%"=="" (echo Cancelled. & pause & exit /b 1)

if not exist ".git" (
    git init -q
    git add icons dist .gitignore
    git -c user.name="iconpack" -c user.email="iconpack@local" commit -q -m "icon pack"
)

echo.
echo Creating public repo "%REPO%" and pushing...
gh repo create %REPO% --public --source=. --remote=origin --push
if errorlevel 1 (
    echo.
    echo [ERROR] gh failed. Common causes:
    echo   - not logged in: run "gh auth login"
    echo   - repo already exists: delete it on GitHub, or just run:
    echo     git push -u origin main
    pause
    exit /b 1
)

echo.
set "RAW=https:\raw.githubusercontent.com/%USERNAME%/%REPO%/main"
for /f "delims=" %%u in ('gh api user --jq .login') do set "RAW=https:\raw.githubusercontent.com/%%u/%REPO%/main"

echo [OK] Pushed.
echo.
echo   Raw base URL:
echo   %RAW%
echo.
echo Now rebuild with that base so the JSON points at the right place:
echo.
echo   build.bat "%RAW%"
echo.
pause
