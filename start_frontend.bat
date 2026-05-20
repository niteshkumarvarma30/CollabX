@echo off
setlocal
cd /d "%~dp0frontend"

set "NODE_EXE=C:\Users\varni\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
set "VITE_JS=%~dp0frontend\node_modules\vite\bin\vite.js"

if not exist "%NODE_EXE%" (
  echo Node runtime not found:
  echo %NODE_EXE%
  pause
  exit /b 1
)

if not exist "%VITE_JS%" (
  echo Frontend dependencies are missing.
  echo Run this once:
  echo cd /d "%~dp0frontend"
  echo npm.cmd install
  pause
  exit /b 1
)

echo Starting frontend on http://127.0.0.1:5173
"%NODE_EXE%" "%VITE_JS%" --host 127.0.0.1 --port 5173

echo.
echo Frontend stopped.
pause
