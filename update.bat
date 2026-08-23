@echo off
setlocal

cd /d "%~dp0"

echo [Atlas] Updating dependencies and rebuilding...
if exist "backend\.venv" (
  call backend\.venv\Scripts\activate.bat
  pip install -r backend\requirements.txt
)

if exist "frontend\package.json" (
  pushd frontend
  npm install
  npm run build
  popd
)

echo [Atlas] Update complete.
exit /b 0

