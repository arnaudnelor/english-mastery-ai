@echo off
rem Allows phones/tablets on your PRIVATE (home) Wi-Fi to reach the app on port 8765.
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
netsh advfirewall firewall delete rule name="English Mastery AI" >nul 2>&1
netsh advfirewall firewall add rule name="English Mastery AI" dir=in action=allow protocol=TCP localport=8765 profile=private
echo.
echo  Firewall rule added for private networks only (port 8765).
echo  Make sure your Wi-Fi is set to "Private network" in Windows Settings ^> Network ^& internet ^> Wi-Fi.
pause
