"""Speech-to-text and text-to-speech providers.

STT uses Whisper (OpenAI API) with word timestamps so we can measure
real fluency signals: speaking rate, long pauses, filler words.
Pronunciation *scoring* is intentionally limited to what these signals
support; we do not claim phoneme-level accuracy (see docs/ARCHITECTURE.md).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from ..config import get_secret, settings
from .llm import MissingAPIKey, ProviderError

FILLERS = {"um", "uh", "erm", "er", "hmm", "like", "euh"}


@dataclass
class Word:
    word: str
    start: float
    end: float


@dataclass
class Transcript:
    text: str
    words: list[Word] = field(default_factory=list)
    duration: float = 0.0


def fluency_metrics(t: Transcript, long_pause: float = 0.8) -> dict:
    """Objective fluency measures from word timings (pauses need word timings, i.e. Whisper)."""
    words = t.words
    n = len(words) or len(t.text.split())
    duration = t.duration or (words[-1].end - words[0].start if words else 0.0)
    pauses = [
        round(b.start - a.end, 2)
        for a, b in zip(words, words[1:])
        if b.start - a.end >= long_pause
    ]
    tokens = [re.sub(r"[^a-z']", "", w.word.lower()) for w in words] or re.findall(
        r"[a-z']+", t.text.lower()
    )
    fillers = sum(1 for tok in tokens if tok in FILLERS)
    wpm = round(n / duration * 60, 1) if duration > 0 else None
    return {
        "pauses_measured": bool(words),
        "word_count": n,
        "duration_sec": round(duration, 2),
        "words_per_minute": wpm,
        "long_pauses": len(pauses),
        "longest_pause_sec": max(pauses) if pauses else 0.0,
        "filler_words": fillers,
    }


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes, filename: str, language: str = "en") -> Transcript:
        ...


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> tuple[bytes, str]:
        """Return (audio_bytes, mime_type)."""


class OpenAIWhisperSTT(STTProvider):
    def __init__(self, model: str):
        self.model = model
        self.key = get_secret("openai")
        if not self.key:
            raise MissingAPIKey("openai")

    def transcribe(self, audio, filename, language="en") -> Transcript:
        try:
            r = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.key}"},
                data={
                    "model": self.model,
                    "language": language,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "word",
                    # Ask Whisper to keep disfluencies instead of cleaning them up
                    "prompt": "Umm, let me think, uh... I mean, like, hmm.",
                },
                files={"file": (filename, audio)},
                timeout=120,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Network error during transcription: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"Transcription error {r.status_code}: {r.text[:300]}")
        body = r.json()
        words = [Word(w["word"], w["start"], w["end"]) for w in body.get("words", [])]
        return Transcript(text=body.get("text", "").strip(), words=words, duration=body.get("duration", 0.0))


class OpenAITTS(TTSProvider):
    def __init__(self, model: str, voice: str):
        self.model, self.voice = model, voice
        self.key = get_secret("openai")
        if not self.key:
            raise MissingAPIKey("openai")

    def synthesize(self, text, voice=None):
        try:
            r = httpx.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self.key}"},
                json={"model": self.model, "voice": voice or self.voice, "input": text[:4000], "format": "mp3"},
                timeout=60,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Network error during speech synthesis: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"TTS error {r.status_code}: {r.text[:300]}")
        return r.content, "audio/mpeg"


def transcribe_any(audio: bytes, filename: str, transcript: str | None = None, duration: float | None = None) -> Transcript:
    """Whisper when an OpenAI key is configured (word timings, pauses); otherwise the transcript
    produced by the browser's built-in speech recognition (free; no pause data)."""
    if _stt_override is not None or get_secret("openai"):
        if audio:
            return get_stt().transcribe(audio, filename)
    if transcript and transcript.strip():
        return Transcript(text=transcript.strip(), words=[], duration=float(duration or 0))
    if not get_secret("openai"):
        raise MissingAPIKey("openai")
    return Transcript(text="", words=[], duration=0.0)


_stt_override: STTProvider | None = None
_tts_override: TTSProvider | None = None


def set_speech_overrides(stt: STTProvider | None = None, tts: TTSProvider | None = None):
    global _stt_override, _tts_override
    _stt_override, _tts_override = stt, tts


def get_stt() -> STTProvider:
    return _stt_override or OpenAIWhisperSTT(settings.stt_model)


def get_tts() -> TTSProvider:
    return _tts_override or OpenAITTS(settings.tts_model, settings.tts_voice)
