# LearningOS PowerShell One-Click Installer
$ErrorActionPreference = "Stop"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "          LearningOS Installer (PowerShell)        " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# 1. Check or Create .env
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "[LearningOS] Creating .env from .env.example..." -ForegroundColor Green
        Copy-Item ".env.example" ".env"
    } else {
        Write-Host "[LearningOS] Creating default .env configuration..." -ForegroundColor Green
        @"
LEARNINGOS_ENV=production
LEARNINGOS_PORT=8000
LEARNINGOS_HOST=127.0.0.1
LEARNINGOS_DATA_DIR=data
AI_PROVIDER=offline
"@ | Out-File -FilePath ".env" -Encoding utf8
    }
}

# 2. Check Python
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Found $pythonVersion" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Python 3.11+ is required. Please install from https://www.python.org" -ForegroundColor Red
    exit 1
}

# 3. Virtual Environment
Write-Host "[2/5] Setting up Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "backend\.venv")) {
    python -m venv backend\.venv
}

Write-Host "[3/5] Installing backend dependencies..." -ForegroundColor Yellow
& "$Root\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$Root\backend\.venv\Scripts\pip.exe" install -r "$Root\backend\requirements.txt" --quiet

# 4. Node.js & Frontend Build
Write-Host "[4/5] Checking Node.js and building frontend..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  Found Node.js $nodeVersion" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Node.js 18+ is required. Please install from https://nodejs.org" -ForegroundColor Red
    exit 1
}

Push-Location "$Root\frontend"
try {
    Write-Host "  Installing npm packages..." -ForegroundColor Gray
    npm install --quiet
    Write-Host "  Building production frontend bundle..." -ForegroundColor Gray
    npm run build
} finally {
    Pop-Location
}

# 5. Initialize Data Directories
Write-Host "[5/5] Initializing local database and directories..." -ForegroundColor Yellow
$env:PYTHONPATH = "$Root\backend"
& "$Root\backend\.venv\Scripts\python.exe" -m app.config --init-data

Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "      LearningOS Installation Complete!            " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host "To start: .\start.bat or .\start.ps1" -ForegroundColor Cyan
Write-Host "To stop:  .\stop.bat or .\stop.ps1" -ForegroundColor Cyan
Write-Host ""
