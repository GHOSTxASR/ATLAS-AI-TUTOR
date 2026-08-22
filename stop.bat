@echo off
setlocal enabledelayedexpansion
title LearningOS - Stopping Services
cd /d "%~dp0"

call scripts\load-env.bat
if "%LEARNINGOS_PORT%"=="" set LEARNINGOS_PORT=8000

echo [LearningOS] Stopping services...

for %%P in (%LEARNINGOS_PORT% 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P"') do (
    if not "%%A"=="0" (
      echo Killing process on port %%P, PID %%A...
      taskkill /F /PID %%A >nul 2>&1
    )
  )
)

echo [LearningOS] Services stopped.
exit /b 0
