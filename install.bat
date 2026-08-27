@echo off
REM Shim. The installer itself is install.py -- one cross-platform file
REM instead of a .bat and a .sh that drift apart. See install.py.
cd /d "%~dp0"
python install.py %*
if errorlevel 1 pause
