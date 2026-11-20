@echo off
rem Starts English Mastery AI automatically when you log in to Windows (no browser window).
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\English Mastery AI.lnk'); $s.TargetPath='%~dp0start.bat'; $s.Arguments='nobrowser'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo  Auto-start enabled. After you log in, open http://localhost:8765 (or the desktop shortcut).
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\English Mastery AI.lnk'); $s.TargetPath='%~dp0start.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo  Desktop shortcut created.
pause
