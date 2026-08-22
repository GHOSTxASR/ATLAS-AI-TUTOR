@echo off
setlocal

cd /d "%~dp0"

call scripts\load-env.bat

if not exist "backend\.venv" (
  echo Backend virtual environment not found. Run setup.bat first.
  exit /b 1
)

if "%LEARNINGOS_PORT%"=="" set LEARNINGOS_PORT=8000

echo [LearningOS] Starting backend and frontend development servers...
start "LearningOS Backend" cmd /k "cd /d %CD%\backend && call .venv\Scripts\activate.bat && set PYTHONPATH=%CD%\backend && set LEARNINGOS_ENV=development && set LEARNINGOS_PORT=%LEARNINGOS_PORT% && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port %LEARNINGOS_PORT%"
start "LearningOS Frontend" cmd /k "cd /d %CD%\frontend && set LEARNINGOS_PORT=%LEARNINGOS_PORT% && npm run dev -- --host 127.0.0.1"
start http://127.0.0.1:5173
