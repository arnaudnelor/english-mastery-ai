# Builds the Windows 11 installer (EnglishMasteryAI-Setup-x.y.z.exe).
# Run from the repository root in PowerShell on Windows:
#   powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
# Prerequisites: Python 3.11+ and Node.js 20+ on PATH.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "1/4  Backend: installing dependencies and running tests" -ForegroundColor Cyan
Push-Location "$root\backend"
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt pyinstaller
.\.venv\Scripts\python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed - installer not built." }

Write-Host "2/4  Backend: freezing to ema-backend.exe" -ForegroundColor Cyan
.\.venv\Scripts\pyinstaller --noconfirm --clean --name ema-backend `
  --add-data "app\content\*.json;app\content" `
  --hidden-import keyring.backends.Windows `
  --collect-submodules uvicorn `
  run_backend.py
Pop-Location

Write-Host "3/4  Frontend: building UI" -ForegroundColor Cyan
Push-Location "$root\frontend"
npm ci
npm run build

Write-Host "4/4  Packaging NSIS installer" -ForegroundColor Cyan
npx electron-builder --win nsis
Pop-Location

Write-Host "Done. Installer is in frontend\release\" -ForegroundColor Green
