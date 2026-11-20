@echo off
rem Stops all English Mastery AI services.
powershell -NoProfile -Command "$p = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($id in $p) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }"
if /i not "%~1"=="quiet" echo  English Mastery AI has been stopped.
exit /b 0
