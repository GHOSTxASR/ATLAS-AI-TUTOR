# LearningOS PowerShell Server Launcher
$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# Keep the production launcher on the same port and host as Vite and start-dev.bat.
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$Port = if ($env:LEARNINGOS_PORT) { $env:LEARNINGOS_PORT } else { "8000" }
$HostName = if ($env:LEARNINGOS_HOST) { $env:LEARNINGOS_HOST } else { "127.0.0.1" }

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "             Starting LearningOS Server            " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

if (-not (Test-Path "backend\.venv")) {
    Write-Host "[ERROR] Virtual environment not found. Please run .\install.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "[WARNING] Building frontend production bundle..." -ForegroundColor Yellow
    Push-Location "frontend"
    npm run build
    Pop-Location
}

# Stop any existing process on target port
$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping existing process on port $Port..." -ForegroundColor Yellow
    & "$Root\stop.bat" | Out-Null
    Start-Sleep -Seconds 2
}

$env:PYTHONPATH = "$Root\backend"
$env:LEARNINGOS_ENV = "production"
$env:LEARNINGOS_PORT = $Port
$env:LEARNINGOS_HOST = $HostName

Write-Host "Launching unified server on http://$HostName`:$Port..." -ForegroundColor Green

$procInfo = New-Object System.Diagnostics.ProcessStartInfo
$procInfo.FileName = "$Root\backend\.venv\Scripts\python.exe"
$procInfo.Arguments = "-m uvicorn app.main:app --host $HostName --port $Port"
$procInfo.WorkingDirectory = "$Root\backend"
$procInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
[System.Diagnostics.Process]::Start($procInfo) | Out-Null

$healthUrl = "http://$HostName`:$Port/api/v1/health"
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($ready) {
    Write-Host "LearningOS is healthy! Opening browser..." -ForegroundColor Green
    Start-Process "http://$HostName`:$Port"
    Write-Host ""
    Write-Host "Running at http://$HostName`:$Port. Run .\stop.bat to shut down." -ForegroundColor Cyan
} else {
    Write-Host "[ERROR] Server health check timed out. Check backend logs." -ForegroundColor Red
    exit 1
}
