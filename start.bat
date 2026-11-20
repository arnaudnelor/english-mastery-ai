@echo off
rem Starts English Mastery AI on this computer only and opens it in your browser.
rem Usage: start.bat            (opens the browser)
rem        start.bat nobrowser  (used by auto-start at Windows login)
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (call "%~dp0setup.bat" || exit /b 1)
set "SCHEME=http"
curl.exe -s -o nul -m 2 "http://127.0.0.1:8765/api/system/health" && goto :ready
echo  Starting English Mastery AI...
set "EMA_HOST=127.0.0.1"
set "EMA_LAN_PIN="
set "EMA_SSL_CERTFILE="
set "EMA_SSL_KEYFILE="
set "EMA_STATIC_DIR=%~dp0frontend\dist"
start "English Mastery AI - engine (do not close)" /min /d "%~dp0backend" "%~dp0backend\.venv\Scripts\python.exe" -m app.main

set /a tries=0
:wait
curl.exe -sk -o nul -m 2 "%SCHEME%://127.0.0.1:8765/api/system/health" && goto :ready
set /a tries+=1
if %tries% geq 60 goto :fail
ping -n 2 127.0.0.1 >nul
goto :wait
:fail
echo  The engine did not start. Open "%APPDATA%\EnglishMasteryAI\app.log" or the minimised engine window for details.
pause
exit /b 1

:ready
echo.
echo  English Mastery AI is running:  http://localhost:8765
echo  To stop it, run stop.bat
if /i not "%~1"=="nobrowser" start "" "http://localhost:8765"
exit /b 0
