@echo off
cd /d "%~dp0"

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
  start "" http://127.0.0.1:5000
  exit /b 0
)

python -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias...
  pip install -r requirements.txt
)

start "PetFeeder" cmd /k "python app.py"
timeout /t 2 >nul
start "" http://127.0.0.1:5000
