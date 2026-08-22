@echo off
setlocal enabledelayedexpansion

title LearningOS Setup
cd /d "%~dp0"

echo [LearningOS] Forwarding to install.bat...
call "%~dp0install.bat"
exit /b %errorlevel%
