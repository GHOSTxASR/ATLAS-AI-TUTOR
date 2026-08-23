@echo off
setlocal

cd /d "%~dp0"

call scripts\load-env.bat

if not exist "backend\.venv" (
  echo Backend virtual environment not found. Run setup.bat first.
  exit /b 1
)

if "%ATLAS_PORT%"=="" set ATLAS_PORT=8000

echo [Atlas] Starting backend and frontend development servers...
start "Atlas Backend" cmd /k "cd /d %CD%\backend && call .venv\Scripts\activate.bat && set PYTHONPATH=%CD%\backend && set ATLAS_ENV=development && set ATLAS_PORT=%ATLAS_PORT% && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port %ATLAS_PORT%"
start "Atlas Frontend" cmd /k "cd /d %CD%\frontend && set ATLAS_PORT=%ATLAS_PORT% && npm run dev -- --host 127.0.0.1"
start http://127.0.0.1:5173
