@echo off
setlocal enabledelayedexpansion

title LearningOS Unified Production Server
cd /d "%~dp0"

call scripts\load-env.bat
if "%LEARNINGOS_PORT%"=="" set LEARNINGOS_PORT=8000
if "%LEARNINGOS_HOST%"=="" set LEARNINGOS_HOST=127.0.0.1

echo ===================================================
echo             Starting LearningOS
echo ===================================================
echo.

if not exist "backend\.venv" (
  echo [ERROR] Backend virtual environment not found.
  echo Please run install.bat first.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo [WARNING] Production frontend build not found in frontend\dist.
  echo Running 'npm run build' to generate production bundle...
  pushd frontend
  call npm run build
  popd
)

netstat -ano | findstr ":%LEARNINGOS_PORT%" >nul
if %errorlevel% equ 0 (
  echo [WARNING] Port %LEARNINGOS_PORT% is in use. Stopping existing instance...
  call stop.bat >nul 2>&1
  timeout /t 2 /nobreak >nul
)

set "PYTHONPATH=%CD%\backend"
set "LEARNINGOS_ENV=production"

echo [LearningOS] Launching production server on http://%LEARNINGOS_HOST%:%LEARNINGOS_PORT%...
start "LearningOS Backend" /MIN cmd /c "cd /d %CD%\backend && call .venv\Scripts\activate.bat && set PYTHONPATH=%CD%\backend && set LEARNINGOS_ENV=production && set LEARNINGOS_PORT=%LEARNINGOS_PORT% && set LEARNINGOS_HOST=%LEARNINGOS_HOST% && python -m uvicorn app.main:app --host %LEARNINGOS_HOST% --port %LEARNINGOS_PORT%"

set "HEALTH_URL=http://%LEARNINGOS_HOST%:%LEARNINGOS_PORT%/api/v1/health"
set "MAX_TRIES=60"
set "TRIES=0"

:HEALTH_CHECK
powershell -Command "try { $response = Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing; if ($response.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
  echo [LearningOS] Server is healthy and ready.
  goto :LAUNCH_BROWSER
)

set /a TRIES+=1
if !TRIES! geq !MAX_TRIES! (
  echo [ERROR] Health check timed out after 60 seconds.
  echo Check logs or run manually with: cd backend && .venv\Scripts\activate && uvicorn app.main:app
  pause
  exit /b 5
)

timeout /t 1 /nobreak >nul
goto :HEALTH_CHECK

:LAUNCH_BROWSER
echo [LearningOS] Opening web browser...
start http://%LEARNINGOS_HOST%:%LEARNINGOS_PORT%

echo.
echo ===================================================
echo    LearningOS is running at http://%LEARNINGOS_HOST%:%LEARNINGOS_PORT%
echo    To stop the application, run 'stop.bat'
echo ===================================================
echo.
exit /b 0
