@echo off
rem Starts English Mastery AI for this PC AND other devices on your Wi-Fi (phone, tablet).
rem Uses HTTPS (needed for the microphone on phones) and a PIN for other devices.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (call "%~dp0setup.bat" || exit /b 1)
call "%~dp0stop.bat" quiet
set "i=0"
for /f "usebackq delims=" %%L in (`"backend\.venv\Scripts\python.exe" scripts\make_cert.py`) do (
  set /a i+=1
  if !i!==1 set "PIN=%%L"
  if !i!==2 set "IPS=%%L"
  if !i!==3 set "DATA=%%L"
)
if not defined PIN (echo  Could not create the certificate. & pause & exit /b 1)
set "EMA_HOST=0.0.0.0"
set "EMA_LAN_PIN=%PIN%"
set "EMA_SSL_CERTFILE=%DATA%\lan_cert.pem"
set "EMA_SSL_KEYFILE=%DATA%\lan_key.pem"
set "EMA_STATIC_DIR=%~dp0frontend\dist"
set "SCHEME=https"
start "English Mastery AI - engine LAN mode (do not close)" /min /d "%~dp0backend" "%~dp0backend\.venv\Scripts\python.exe" -m app.main

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
echo  =====================================================================
echo   English Mastery AI is running in LAN mode
echo.
echo   On this PC:        https://localhost:8765
for %%A in (%IPS:,= %) do echo   On your phone:     https://%%A:8765
echo.
echo   PIN for other devices:  %PIN%
echo.
echo   Your browser will warn that the certificate is not trusted: this is
echo   expected for a private, self-signed certificate. Choose "Advanced" then
echo   "Continue" / "Proceed". The phone must be on the same Wi-Fi network.
echo   If the phone cannot connect, run firewall-allow.bat once (as admin).
echo  =====================================================================
start "" "https://localhost:8765"
pause
