@echo off
setlocal enabledelayedexpansion

title Atlas Setup
cd /d "%~dp0"

echo [Atlas] Forwarding to install.bat...
call "%~dp0install.bat"
exit /b %errorlevel%
