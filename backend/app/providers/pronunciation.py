"""Phoneme-level pronunciation assessment (optional).

Uses Azure AI Speech Pronunciation Assessment, which scores accuracy per
phoneme, word accuracy, fluency, completeness and prosody against a reference
text. Requires an Azure Speech key + region (Settings). Without it, the app
falls back to the Whisper-based clarity check.
"""
from __future__ import annotations

import base64
import json

import httpx

from ..config import get_secret, settings
from .llm import MissingAPIKey, ProviderError


def _pa(obj: dict) -> dict:
    """Scores live under 'PronunciationAssessment' in current API versions, at top level in older ones."""
    return obj.get("PronunciationAssessment") or obj


def parse_assessment(body: dict) -> dict:
    if body.get("RecognitionStatus") not in (None, "Success"):
        raise ProviderError(f"Azure could not recognise speech ({body.get('RecognitionStatus')}). Try again, closer to the microphone.")
    best = (body.get("NBest") or [{}])[0]
    s = _pa(best)
    words = []
    for w in best.get("Words", []):
        wp = _pa(w)
        words.append({
            "word": w.get("Word"),
            "accuracy": wp.get("AccuracyScore"),
            "error_type": wp.get("ErrorType", "None"),
            "phonemes": [{"phoneme": p.get("Phoneme"), "accuracy": _pa(p).get("AccuracyScore")} for p in w.get("Phonemes", [])],
        })
    return {
        "pronunciation_score": s.get("PronScore"),
        "accuracy": s.get("AccuracyScore"),
        "fluency": s.get("FluencyScore"),
        "completeness": s.get("CompletenessScore"),
        "prosody": s.get("ProsodyScore"),
        "recognised": best.get("Display", ""),
        "words": words,
    }


def assess(wav: bytes, reference: str, language: str = "en-US") -> dict:
    key = get_secret("azure_speech")
    region = settings.azure_speech_region
    if not key or not region:
        raise MissingAPIKey("azure_speech")
    cfg = {"ReferenceText": reference, "GradingSystem": "HundredMark", "Granularity": "Phoneme",
           "Dimension": "Comprehensive", "EnableMiscue": True, "EnableProsodyAssessment": True}
    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    try:
        r = httpx.post(url, params={"language": language, "format": "detailed"}, content=wav, timeout=60, headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
            "Pronunciation-Assessment": base64.b64encode(json.dumps(cfg).encode()).decode(),
        })
    except httpx.HTTPError as exc:
        raise ProviderError(f"Network error contacting Azure Speech: {exc}") from exc
    if r.status_code != 200:
        raise ProviderError(f"Azure Speech error {r.status_code}: {r.text[:300]}")
    return parse_assessment(r.json())
