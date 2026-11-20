# Running English Mastery AI on Windows

## Requirements
- Windows 10/11
- Python 3.10 or newer (Anaconda works). Node.js is **not** needed: the interface ships pre-built in `frontend\dist`.
- Internet for the first setup (installs Python packages, about 1–2 minutes) and for AI features.

## Start (this computer only — recommended)
Double-click **start.bat**. The first run creates `backend\.venv` and installs dependencies; later starts take a few seconds. Your browser opens **http://localhost:8765**. A minimised window titled *English Mastery AI – engine* is the server: leave it open.

| Script | What it does |
|---|---|
| `start.bat` | Starts the app for this PC only and opens the browser |
| `stop.bat` | Stops all app services (frees port 8765) |
| `restart.bat` | Stop + start |
| `start-lan.bat` | Starts for this PC **and** phones/tablets on your Wi-Fi (HTTPS + PIN) |
| `firewall-allow.bat` / `firewall-remove.bat` | Adds/removes a Windows Firewall rule for port 8765 on *private* networks (asks for admin) |
| `install-autostart.bat` / `remove-autostart.bat` | Start automatically at Windows login, plus a desktop shortcut |
| `install-reminder.bat` / `remove-reminder.bat` | Open the app every day at a chosen time (Task Scheduler) |

The database (`english_mastery.db`), logs (`app.log`), LAN certificate and PIN live in `%APPDATA%\EnglishMasteryAI`. They survive reinstalls.

## After restarting Windows
Either double-click **start.bat** (or the desktop shortcut), or run **install-autostart.bat** once so the engine starts at login; then just open http://localhost:8765.

## Phone / tablet on the same Wi-Fi
1. Run **firewall-allow.bat** once (approve the admin prompt). Your Wi-Fi must be set to *Private network*.
2. Run **start-lan.bat**. It shows the phone address, e.g. `https://192.168.1.23:8765`, and a 6-digit PIN.
3. On the phone, open that address, accept the certificate warning (Advanced → Proceed), and enter the PIN.

Why HTTPS: phone browsers only allow the microphone on secure pages. The certificate is self-signed for your own machine, so browsers warn once.
Security: other devices need the PIN for every API call; API keys, provider settings and backups can only be changed on the PC itself; the firewall rule is limited to private networks. Without `start-lan.bat`, the app only listens on 127.0.0.1 and nothing on the network can reach it. To return to PC-only mode, run `stop.bat` then `start.bat`.

## Troubleshooting
- **"Python 3.10 or newer was not found"**: install from python.org with "Add python.exe to PATH" ticked.
- **Engine did not start**: check `%APPDATA%\EnglishMasteryAI\app.log`, or that nothing else uses port 8765 (`stop.bat` frees it).
- **Microphone blocked**: Windows Settings → Privacy & security → Microphone → allow desktop apps and your browser.
- **AI features say a key is needed**: Settings → AI providers (only from the PC).

## Desktop window instead of a browser tab (optional)
Requires Node.js 20+: `cd frontend`, `npm install`, `npm run electron:dev`.

## Building the installer
`powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1` (needs Python + Node.js). Output: `frontend\release\English Mastery AI Setup 1.0.0.exe`.
