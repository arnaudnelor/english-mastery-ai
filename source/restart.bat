@echo off
call "%~dp0stop.bat" quiet
ping -n 2 127.0.0.1 >nul
call "%~dp0start.bat" %*
