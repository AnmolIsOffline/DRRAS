@echo off
setlocal EnableExtensions
 title DRRAS - Relief Command
cd /d "%~dp0"

 echo ========================================================
 echo  DRRAS - Disaster Relief Resource Allocation System
 echo  Local demo server: http://127.0.0.1:5055
 echo ========================================================
 echo.

if not exist "requirements.txt" (
  echo [ERROR] requirements.txt is missing from this project folder.
  goto :fail
)
if not exist "app.py" (
  echo [ERROR] app.py is missing from this project folder.
  goto :fail
)

set "PYTHON_EXE="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=py -3"
  py -3 --version >nul 2>nul
  if errorlevel 1 set "PYTHON_EXE="
)
if not defined PYTHON_EXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
  echo [ERROR] Python 3 was not found. Install Python 3.10 or newer and enable PATH.
  goto :fail
)
%PYTHON_EXE% --version
if errorlevel 1 (
  echo [ERROR] Python could not start.
  goto :fail
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [1/5] Creating project-local virtual environment...
  %PYTHON_EXE% -m venv --system-site-packages ".venv"
  if errorlevel 1 (
    echo [ERROR] Virtual environment creation failed.
    goto :fail
  )
)
if not exist "%VENV_PY%" (
  echo [ERROR] Virtual environment Python is missing: %VENV_PY%
  goto :fail
)

echo [2/5] Installing/checking project dependencies...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Dependency installation failed. Check your internet connection and requirements.txt.
  goto :fail
)

set "PORT=5055"
set "DRRAS_ENV=local"
set "FLASK_ENV=development"
set "FLASK_DEBUG=False"

echo [3/5] Checking local port 5055...
"%VENV_PY%" -c "import socket,sys;s=socket.socket();s.settimeout(1);r=s.connect_ex(('127.0.0.1',5055));s.close();sys.exit(0 if r==0 else 1)" >nul 2>nul
if not errorlevel 1 (
  echo [ERROR] Port 5055 is already in use. Stop the other DRRAS/server process, or close the program using port 5055, then retry.
  echo If DRRAS is already running, open http://127.0.0.1:5055 directly.
  goto :fail
)

echo [4/5] Applying safe schema initialization and idempotent demo seed...
"%VENV_PY%" seed_demo.py
if errorlevel 1 (
  echo [ERROR] Database initialization/seed failed. Existing database was not reset.
  goto :fail
)

echo [5/5] Starting Flask...
echo The server console stays open. Press Ctrl+C to stop DRRAS.
start "DRRAS browser readiness check" /min "%VENV_PY%" "%~dp0open_browser_when_ready.py" 5055
"%VENV_PY%" app.py
set "APP_EXIT=%errorlevel%"
if not "%APP_EXIT%"=="0" echo [ERROR] DRRAS exited with code %APP_EXIT%. Review the server logs above.
echo.
echo DRRAS has stopped. Press any key to close this window.
pause >nul
exit /b %APP_EXIT%

:fail
echo.
echo Startup stopped. No database reset was performed.
echo Press any key to close this window.
pause >nul
exit /b 1
