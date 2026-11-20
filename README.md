# English Mastery AI: web edition

**Open the app:** https://arnaudnelor.github.io/english-mastery-ai/

This repository hosts the built web edition of English Mastery AI. The app's Python engine (FastAPI + SQLite) runs entirely in your browser with Pyodide, inside a Web Worker. Your progress is stored in your browser on your device.

AI features (conversation, corrections, speech recognition, natural voices, writing and speaking assessment) call OpenAI directly from your browser using **your own API key**. You enter the key in Settings; it stays in your browser on your device and is sent only to OpenAI.
