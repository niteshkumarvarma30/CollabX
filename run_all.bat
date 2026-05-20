@echo off
setlocal
cd /d "%~dp0"

echo Starting Instagram Insights Dashboard...
echo.

start "Instagram Insights Backend" "%~dp0start_backend.bat"
start "Instagram Insights Frontend" "%~dp0start_frontend.bat"

echo Backend:  http://127.0.0.1:8000/health
echo Frontend: http://127.0.0.1:5173/
echo.
echo Two command windows should stay open. If either window shows an error,
echo send me that text and I will fix it.
echo.
pause
