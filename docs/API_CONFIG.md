# AI Configuration, Dependencies and Running Costs

## What needs what

| Feature | API key | Internet | Paid service |
|---|---|---|---|
| Dashboard, grammar, vocabulary + flashcards, progress | — | — | — |
| Word/sentence audio (speaker icons) | — | — | — (Windows built-in voices) |
| AI conversation — typed | OpenAI **or** Anthropic | ✓ | ✓ |
| AI conversation — voice input | OpenAI (Whisper) | ✓ | ✓ |
| Natural AI voice replies | OpenAI (TTS) | ✓ | ✓ (falls back to Windows voice if unavailable) |
| Writing tutor, reading summaries, video study packs, IELTS writing | OpenAI **or** Anthropic | ✓ | ✓ |
| IELTS speaking, placement speaking, hands-free conversation | OpenAI (Whisper) + LLM | ✓ | ✓ |
| Phoneme-level pronunciation scores | Azure Speech key + region (optional) | ✓ | ✓ (Azure free tier: 5 audio hours/month at the time of writing) |
| Listening Lab, Video Academy playback, placement test (objective parts), mock exam listening/reading, weekly checks, analytics | — | — (YouTube videos need internet) | — |

## Adding a key

Settings → AI providers → choose provider → paste key → **Save key**. It is stored in Windows Credential Manager (entry “EnglishMasteryAI”), never in a file. Alternative for developers: environment variables `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`.

Get keys at platform.openai.com and console.anthropic.com. Both require adding a payment method; set a monthly spending limit in each console.

## Azure Speech (optional)
In the Azure portal, create a *Speech* resource, then copy *Key 1* and the *Location/Region* (e.g. `canadacentral`). In the app, go to Settings → AI providers, choose "Azure Speech", paste the key and save, then enter the region and save. The Pronunciation Lab then shows the "Phoneme-level scoring (Azure)" button.

## Switching models

Settings → “Use for conversation”. Persisted to `%APPDATA%\EnglishMasteryAI\.env`. Any environment variable prefixed `EMA_` overrides defaults, e.g. `EMA_LLM_MODEL`, `EMA_TTS_VOICE` (alloy, echo, fable, onyx, nova, shimmer).

## Estimated cost

Prices change — check the providers' pricing pages. Rough order of magnitude with the defaults (gpt-4o-mini, whisper-1, tts-1) at late-2026 published rates:

- **One spoken turn** ≈ 15 s of audio + 2 LLM calls + ~40 words of TTS: well under one US cent.
- **A 30-minute speaking session** (~40 turns): typically **$0.15–$0.40**, dominated by Whisper and TTS.
- **One hour of mixed study per day**: roughly **$3–$8 per month**.
- Larger models (e.g. GPT-4o, Claude Sonnet) give sharper corrections and cost several times more per turn.

Cost controls: use typed mode or turn off “Read replies aloud” to cut speech costs; grammar and vocabulary practice cost nothing.
