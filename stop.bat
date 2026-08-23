@echo off
setlocal enabledelayedexpansion
title Atlas - Stopping Services
cd /d "%~dp0"

call scripts\load-env.bat
if "%ATLAS_PORT%"=="" set ATLAS_PORT=8000

echo [Atlas] Stopping services...

for %%P in (%ATLAS_PORT% 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P"') do (
    if not "%%A"=="0" (
      echo Killing process on port %%P, PID %%A...
      taskkill /F /PID %%A >nul 2>&1
    )
  )
)

echo [Atlas] Services stopped.
exit /b 0
