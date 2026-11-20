# English Mastery AI — Your Personal Intelligent English Academy

A Windows 11 desktop app that takes you from B2 to C1/C2. At its centre is an AI professor you can talk to hands-free, who corrects you with explanations and tracks your recurring mistakes. Around it: grammar, vocabulary with spaced repetition, reading, a multi-accent listening lab, a pronunciation lab with optional phoneme scoring, a Video Academy, an AI writing tutor, a full IELTS Academic mock exam, a business and finance track, a placement test, a personal learning path and progress analytics.

**Version 1.1:** all nine development phases are complete, plus original TOEFL iBT (2026 format) and Cambridge C1/C2 practice papers, a built-in **Test my setup** check, expanded content, and a browser preview. See `docs/ROADMAP.md` for ideas beyond 1.0. Every screen marked “Soon” in the app is labelled as planned, with no inactive buttons.

## Run it (Windows)

Double-click `start.bat`, then open http://localhost:8765. See `docs/DEPLOYMENT.md` for phone access, auto-start and troubleshooting.

## Development

```powershell
# 1. Engine
cd backend
python -m venv .venv; .\.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest            # 43 tests
python -m app.main          # http://127.0.0.1:8765  (API docs at /docs)

# 2. UI (new terminal)
cd frontend
npm install
npm run dev                 # browser at http://localhost:5173
# or as a desktop window:
npm run electron:dev        # starts the engine itself
```

Then open **Settings → AI providers** and add an OpenAI key (needed for voice) and/or an Anthropic key.

## Build the Windows installer

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```
Runs the test suite, freezes the engine with PyInstaller, builds the UI and produces `frontend\release\English Mastery AI Setup 1.1.0.exe` (NSIS: choose folder, desktop shortcut, clean uninstall; your progress in `%APPDATA%\EnglishMasteryAI` is kept on uninstall).

## Browser preview
`preview/` contains the hosted preview: the same engine runs inside the browser with Pyodide (official CDN), using two small self-written stand-ins (`preview/shims/`) for python-multipart and pydantic-settings. To rebuild it: `cd frontend && VITE_PREVIEW=1 npx vite build --outDir ../preview-site`, then `python preview/build_preview.py preview-site`.

## Documentation

- `docs/ARCHITECTURE.md`: design, correction pipeline, security, folder structure
- `docs/API_CONFIG.md`: which features need keys or internet, and running costs
- `docs/ROADMAP.md`: phase status and next steps
- `docs/USER_GUIDE.md`: how to use the app
- `docs/DEPLOYMENT.md`: start/stop scripts, phone access, auto-start, troubleshooting

## Your data

Everything is local: `%APPDATA%\EnglishMasteryAI\` holds the database, logs and backups. To restore a backup, close the app and copy the backup file over `english_mastery.db`.
