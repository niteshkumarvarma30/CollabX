@echo off
setlocal
cd /d "%~dp0backend"

set "PYTHON_EXE=C:\Users\varni\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Python runtime not found:
  echo %PYTHON_EXE%
  pause
  exit /b 1
)

echo Installing backend dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt

echo Starting backend on http://0.0.0.0:8000
"%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000

echo.
echo Backend stopped.
pause
