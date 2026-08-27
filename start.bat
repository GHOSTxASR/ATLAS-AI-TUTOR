@echo off
REM Shim. The launcher itself is start.py. See start.py.
cd /d "%~dp0"
python start.py %*
if errorlevel 1 pause
