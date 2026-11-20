@echo off
rem Opens English Mastery AI every day at the time you choose (Windows Task Scheduler).
setlocal
set /p T=Daily study time (24h HH:MM, e.g. 19:00): 
schtasks /create /f /sc daily /st %T% /tn "English Mastery AI - daily session" /tr "\"%~dp0start.bat\"" >nul && (
  echo  Done. Every day at %T% the app will start and open in your browser.
) || echo  Could not create the task. Check the time format (HH:MM).
pause
