@echo off
rem First-time setup: finds Python 3.10+, creates a virtual environment, installs dependencies.
setlocal
cd /d "%~dp0"
echo.
echo  English Mastery AI - first-time setup
echo  -------------------------------------
set "CHECK=import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
set "PYEXE="
set "PYARGS="
py -3 -c "%CHECK%" >nul 2>&1 && set "PYEXE=py" && set "PYARGS=-3"
if not defined PYEXE python -c "%CHECK%" >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE if exist "%USERPROFILE%\anaconda3\python.exe" "%USERPROFILE%\anaconda3\python.exe" -c "%CHECK%" >nul 2>&1 && set "PYEXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PYEXE if exist "%ProgramData%\anaconda3\python.exe" set "PYEXE=%ProgramData%\anaconda3\python.exe"
if not defined PYEXE (
  echo  Python 3.10 or newer was not found.
  echo  Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run start.bat again.
  pause
  exit /b 1
)
echo  Using Python: %PYEXE% %PYARGS%
"%PYEXE%" %PYARGS% -m venv "backend\.venv" || goto :fail
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt" --quiet --disable-pip-version-check || goto :fail
echo  Setup complete.
exit /b 0
:fail
echo  Setup failed. See the messages above.
if exist "backend\.venv" rmdir /s /q "backend\.venv"
pause
exit /b 1
