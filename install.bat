@echo off
setlocal enabledelayedexpansion

title Atlas One-Click Installer
cd /d "%~dp0"

echo ===================================================
echo           Atlas Installer (Production)
echo ===================================================
echo.

:: 1. Check Environment File (.env)
if not exist ".env" (
  if exist ".env.example" (
    echo [Atlas] Creating .env from .env.example...
    copy .env.example .env >nul
  ) else (
    echo [Atlas] Creating default .env configuration...
    (
      echo ATLAS_ENV=production
      echo ATLAS_PORT=8000
      echo ATLAS_HOST=127.0.0.1
      echo ATLAS_DATA_DIR=data
      echo AI_PROVIDER=offline
    ) > .env
  )
)

call scripts\load-env.bat

:: 2. Check Python Prerequisites
echo [1/5] Checking Python 3.11+ installation...
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python is not installed or not in system PATH.
  echo Please install Python 3.11 or newer from https://www.python.org/downloads/
  pause
  exit /b 1
)

:: 3. Setup Backend Virtual Environment
echo [2/5] Setting up Python virtual environment...
if not exist "backend\.venv" (
  echo Creating virtual environment in backend\.venv...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 2
  )
)

echo [3/5] Installing backend dependencies...
call backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r backend\requirements.txt --quiet
if errorlevel 1 (
  echo [ERROR] Failed to install backend dependencies.
  pause
  exit /b 2
)

:: 4. Check Node.js and Compile Frontend Production Build
echo [4/5] Checking Node.js and compiling frontend production build...
node --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js is not installed or not in PATH.
  echo Please install Node.js 18 LTS or newer from https://nodejs.org/
  pause
  exit /b 1
)

pushd frontend
echo Installing frontend npm packages...
call npm install --quiet
if errorlevel 1 (
  echo [ERROR] npm install failed.
  popd
  pause
  exit /b 3
)

echo Building production assets with Vite...
call npm run build
if errorlevel 1 (
  echo [ERROR] Frontend production build failed.
  popd
  pause
  exit /b 4
)
popd

:: 5. Initialize Data Directories and Optional Tools Check
echo [5/5] Initializing local database and storage...
set "PYTHONPATH=%CD%\backend"
python -m app.config --init-data
if errorlevel 1 (
  echo [ERROR] Failed to initialize local data directory.
  pause
  exit /b 5
)

echo.
echo Checking optional OCR and Local LLM tooling...
set "TESSERACT_FOUND="
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" set "TESSERACT_FOUND=%ProgramFiles%\Tesseract-OCR\tesseract.exe"
if not defined TESSERACT_FOUND (
  for /f "delims=" %%i in ('where tesseract 2^>nul') do if not defined TESSERACT_FOUND set "TESSERACT_FOUND=%%i"
)
if defined TESSERACT_FOUND (
  echo   [+] Tesseract OCR detected: %TESSERACT_FOUND%
) else (
  echo   [-] Tesseract OCR not found - optional, for scanned images/OCR.
)

echo.
echo ===================================================
echo       Atlas Installation Successful!
echo ===================================================
echo.
echo To launch Atlas:
echo   Double-click 'start.bat'
echo.
echo To stop Atlas:
echo   Double-click 'stop.bat'
echo.
echo Server will be accessible at: http://127.0.0.1:8000
echo.
pause
exit /b 0
