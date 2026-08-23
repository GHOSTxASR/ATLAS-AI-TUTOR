@echo off
setlocal enabledelayedexpansion

title Atlas Unified Production Server
cd /d "%~dp0"

call scripts\load-env.bat
if "%ATLAS_PORT%"=="" set ATLAS_PORT=8000
if "%ATLAS_HOST%"=="" set ATLAS_HOST=127.0.0.1

echo ===================================================
echo             Starting Atlas
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

netstat -ano | findstr ":%ATLAS_PORT%" >nul
if %errorlevel% equ 0 (
  echo [WARNING] Port %ATLAS_PORT% is in use. Stopping existing instance...
  call stop.bat >nul 2>&1
  timeout /t 2 /nobreak >nul
)

set "PYTHONPATH=%CD%\backend"
set "ATLAS_ENV=production"

echo [Atlas] Launching production server on http://%ATLAS_HOST%:%ATLAS_PORT%...
start "Atlas Backend" /MIN cmd /c "cd /d %CD%\backend && call .venv\Scripts\activate.bat && set PYTHONPATH=%CD%\backend && set ATLAS_ENV=production && set ATLAS_PORT=%ATLAS_PORT% && set ATLAS_HOST=%ATLAS_HOST% && python -m uvicorn app.main:app --host %ATLAS_HOST% --port %ATLAS_PORT%"

set "HEALTH_URL=http://%ATLAS_HOST%:%ATLAS_PORT%/api/v1/health"
set "MAX_TRIES=60"
set "TRIES=0"

:HEALTH_CHECK
powershell -Command "try { $response = Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing; if ($response.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
  echo [Atlas] Server is healthy and ready.
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
echo [Atlas] Opening web browser...
start http://%ATLAS_HOST%:%ATLAS_PORT%

echo.
echo ===================================================
echo    Atlas is running at http://%ATLAS_HOST%:%ATLAS_PORT%
echo    To stop the application, run 'stop.bat'
echo ===================================================
echo.
exit /b 0
