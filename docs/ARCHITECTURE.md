# English Mastery AI — Architecture

## 1. Overview

```
┌──────────────────────── Windows 11 desktop app (Electron) ────────────────────────┐
│  React + TypeScript + Tailwind UI          (renderer, sandboxed, no Node access)  │
│    Dashboard · Conversation · Grammar · Vocabulary · Writing · Settings · …       │
│    MediaRecorder (microphone) · <audio> playback · Windows SpeechSynthesis        │
└──────────────────────────────▲─────────────────────────────────────────────────────┘
                               │ HTTP on 127.0.0.1:8765 only
┌──────────────────────────────┴─── Local learning engine (Python / FastAPI) ───────┐
│ routers/      profile · grammar · vocabulary · conversation · writing · reading ·  │
│               listening · pronunciation · video · exam · assess · insights · system│
│ services/     correction engine · conversation modes · SM-2 SRS · learning engine  │
│ providers/    LLMProvider (OpenAI | Anthropic) · STT (Whisper) · TTS (OpenAI)      │
│ content/      curriculum JSON: grammar, vocabulary, reading, listening, pronunciation│
│ db            SQLAlchemy → SQLite  (%APPDATA%\EnglishMasteryAI\english_mastery.db) │
└──────────────────────────────┬─────────────────────────────────────────────────────┘
                               │ HTTPS, only for AI features
                     OpenAI / Anthropic APIs
```

**Why this shape.** The Python engine keeps all AI, speech and data logic in one testable place and gives direct access to the Python speech-analysis ecosystem we'll need in Phase 4 (forced alignment, phoneme models). Electron gives a native Windows window, microphone permissions and an NSIS installer. The UI talks to the engine only over localhost, so the same engine could later back a web or mobile client.

## 2. Technology choices

| Layer | Choice | Reason |
|---|---|---|
| Desktop shell | **Electron** | Mature Windows installer (NSIS), Chromium's MediaRecorder for reliable mic capture, simple process management for the Python engine. Tauri is lighter but its WebView2 audio-capture and sidecar story is more fragile today. |
| UI | React 18, TypeScript, Tailwind 3, Vite | As requested; strict TS catches API-shape errors at build time. |
| Engine | Python 3.11+, FastAPI, Pydantic v2 | Typed request validation, auto OpenAPI docs at `/docs`, Python speech/ML ecosystem. |
| Database | SQLite via SQLAlchemy 2 | Zero-config local file. Switching to PostgreSQL = set `EMA_DATABASE_URL`. |
| LLM | `LLMProvider` interface; OpenAI and Anthropic implementations | Swap provider/model in Settings without rebuilding. New providers = one class. |
| Speech-to-text | OpenAI Whisper API with **word timestamps** | Timestamps give objective fluency metrics (pace, pauses, fillers). |
| Text-to-speech | OpenAI TTS; Windows SpeechSynthesis fallback | Natural voice online; built-in voices work offline for word pronunciation. |
| Secrets | `keyring` → Windows Credential Manager; env var fallback | Keys are never in code, config files or the database. |

## 3. The AI correction pipeline (Module 4)

1. **Capture** — the UI records with MediaRecorder (webm/opus, echo cancellation on).
2. **Transcribe** — `/voice-turn` sends audio to Whisper (`verbose_json`, word timestamps). The prompt asks Whisper to keep disfluencies (“um”, “uh”) rather than tidying them.
3. **Measure** — `fluency_metrics()` computes words/minute, pauses ≥ 0.8 s, longest pause and filler count from the timings. These are real measurements, not LLM guesses.
4. **Analyse** — `analyse_utterance()` sends the utterance, recent context, the learner's level and the metrics to the LLM with a strict JSON schema. Output is validated by Pydantic: corrected sentence, categorised issues (grammar / vocabulary / naturalness / pronunciation / fluency), explanation (+ French if enabled), an advanced alternative, and a repeat prompt.
5. **Reply** — a separate teacher call generates the in-role conversational reply (mode, persona, accent). In *Immediate* mode the teacher also recasts errors inline.
6. **Track** — every issue is stored in `mistakes` with a reusable `pattern` label; the dashboard ranks recurring patterns and the daily plan targets them.
7. **Speak** — the reply is voiced via TTS.
8. **Summarise** — `/end` produces an examiner-style session report (strengths, recurring issues, vocabulary, CEFR estimate; IELTS band *practice* estimate only in IELTS mode, clearly labelled).

**Correction modes**: feedback is always computed and tracked; the mode only controls when it is shown (immediately, after each response, at the end, or strict).

**Honest limits on pronunciation.** Whisper tells us what was *recognised*, not how each phoneme was produced. The Pronunciation Lab's read-aloud check therefore aligns the target sentence with Whisper's transcript word by word (`services/alignment.py`) and reports a *clarity* score: words the recogniser missed or misheard are flagged as possibly unclear and tracked as pronunciation weaknesses. That is a real, useful intelligibility measure, but it is not phoneme scoring, and the UI says so. Phase 4 adds a dedicated scoring engine (Azure Pronunciation Assessment or an open-source wav2vec2 phoneme model with forced alignment) for phoneme-level scores.

## 4. Learning engine

- **Spaced repetition**: SM-2 (Anki's algorithm) with four grades; statuses *new / learning / mastered (≥21-day interval) / often forgotten (≥3 lapses)*.
- **Skill scores**: rolling 30-day averages per skill from `activity_log`.
- **CEFR estimate**: averages over 60 days mapped relative to the stated level (needs ≥3 skills with data; otherwise keeps the self-assessed level). The Phase 8 placement test replaces this heuristic with calibrated items.
- **Daily plan**: base weights favour speaking (25%) and listening (20%); skills scoring under 70% are boosted by up to 50%; reasons reference due flashcards and recurring grammar patterns.

## 5. Data model

`profiles` · `conversations` · `messages` (with feedback + speech metrics JSON) · `mistakes` · `vocab_cards` (SRS state) · `activity_log` · `bookmarks`.

## 6. Security

- Engine binds to 127.0.0.1 only; CORS limited to the app and the dev server.
- Electron renderer: `contextIsolation`, `sandbox`, no Node integration; microphone permission granted only to the local origin; external links open in the system browser.
- API keys live in Windows Credential Manager; the API only reports *whether* a key is set.
- All inputs validated by Pydantic (lengths, enums, ranges); audio capped at 25 MB.
- Errors are logged to `%APPDATA%\EnglishMasteryAI\app.log` (rotating, 3 × 2 MB); users see clean messages.

## 7. Project structure

```
english-mastery-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app, logging, static UI serving
│   │   ├── config.py            settings + secure key storage
│   │   ├── db.py, models.py     SQLAlchemy engine and tables
│   │   ├── deps.py              active-profile dependency
│   │   ├── providers/llm.py     LLMProvider, OpenAI, Anthropic
│   │   ├── providers/speech.py  Whisper STT, TTS, fluency metrics
│   │   ├── services/            correction, conversation, srs, learning
│   │   ├── routers/             HTTP endpoints per module
│   │   └── content/             grammar.json, vocabulary.json
│   ├── tests/                   pytest suite (17 tests)
│   ├── run_backend.py           PyInstaller entry point
│   └── requirements.txt
├── frontend/
│   ├── electron/main.cjs        desktop shell, engine lifecycle, mic permission
│   ├── src/                     React app (pages/, components/, lib/)
│   └── package.json             incl. electron-builder NSIS config
├── scripts/build-windows.ps1    one-command Windows installer build
└── docs/                        this file, ROADMAP, API_CONFIG, USER_GUIDE
```

## 8. Listening audio pipeline (v0.2)

Listening scripts are original and stored as text with a voice and accent per speaker. On first play, each line is synthesised by the TTS provider in that speaker's voice and cached in `%APPDATA%\EnglishMasteryAI\audio_cache` (the file name includes a hash of voice + text, so edited lines regenerate automatically). After that the lesson plays offline. Without an API key the player falls back to installed Windows voices matched to each speaker's accent (en-CA / en-US / en-GB), so the module never stops working. Playback speed uses the browser's pitch-preserving `playbackRate`.

Dictation answers are scored with the same word alignment as the read-aloud check, so learners see missed, misheard and extra words.

## 9. Version 1.0 additions

**Hands-free conversation (Phase 5).** `frontend/src/lib/vad.ts` performs voice-activity detection in the browser: it calibrates the room's noise floor for one second, detects speech onset (≥250 ms above threshold) and ends an utterance after 1.2 s of silence. Each utterance is sent through the same Whisper → correction → reply pipeline. Speech onset immediately stops the AI voice (barge-in), and capture pauses while the server is thinking. Browser echo cancellation keeps the AI's own voice out of the microphone.

**Phoneme scoring (Phase 4).** `providers/pronunciation.py` calls Azure AI Speech Pronunciation Assessment (reference text, phoneme granularity, miscue and prosody). The browser converts the recording to 16 kHz mono PCM WAV (`lib/wav.ts`). Scores of 60 or below are stored as pronunciation weaknesses labelled by sound (e.g. "sound /θ/"). This feature is optional; without Azure, the Whisper clarity check remains.

**Video Academy (Phase 6).** Legal by design: the app never downloads third-party media. Local files are streamed with HTTP Range support for seeking, and YouTube plays through the official IFrame API on youtube-nocookie.com. `services/subtitles.py` parses SRT, WebVTT (tags stripped, rolling duplicates merged) and plain transcripts. Study packs are generated once from the transcript and cached in the database. Animated scenes reuse the original listening scripts with synced speakers and subtitles.

**Exams (Phase 7).** `routers/exam.py` and `services/ielts.py`: Listening and Reading are scored objectively and scaled to a 40-question raw score, then converted with an approximate public band table. Writing uses an examiner prompt over the four public criteria, with Task 2 weighted double. Speaking uses Whisper transcripts plus timing metrics; pronunciation is explicitly marked as an estimate. Overall bands use IELTS rounding (.25 rounds up to .5, .75 rounds up to the next band). Every result carries a practice-estimate disclaimer.

**Personalisation (Phase 8).** The placement test (`routers/assess.py`) combines a 24-item grammar and vocabulary ladder (highest level with ≥60% at that level and all levels below), reading and listening accuracy, and optional AI-rated writing and speaking. The overall result is the lower median of the skills, which is deliberately conservative. The learning path orders units from the current to the target level and puts topics behind recurring mistakes first. Analytics aggregate `activity_log` and `mistakes` by week.

**Database migrations.** `db._add_missing_columns()` adds new nullable columns to existing SQLite tables at start-up, so data from earlier versions is kept.

**Testing.** 37 backend tests (pytest) cover every router, the band maths, subtitle parsing, LAN security and migrations. A Playwright end-to-end script drives the production build in Chrome: onboarding, grammar, bookmarks, flashcards, reading, dictation, weekly check, mock exam, video library, every route, and conversation error handling, with zero console errors.
