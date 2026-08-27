@echo off
REM Shim. The installer itself is install.py in the repository root -- one
REM cross-platform file instead of a .bat and a .sh that drift apart.
cd /d "%~dp0.."
python install.py %*
if errorlevel 1 pause
