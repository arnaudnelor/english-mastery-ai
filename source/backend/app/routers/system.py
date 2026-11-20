"""Settings, provider status, backup/restore, and the feature registry."""
from __future__ import annotations

import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import delete_secret, get_secret, set_secret, settings
from ..db import get_engine

router = APIRouter(prefix="/api/system", tags=["system"])

# Honest registry of what works, what needs a key/internet, what's planned.
FEATURES = [
    {"id": "dashboard", "name": "Dashboard & daily plan", "status": "available", "needs": []},
    {"id": "grammar", "name": "Grammar Academy", "status": "available", "needs": [], "offline": True},
    {"id": "vocabulary", "name": "Vocabulary + spaced repetition", "status": "available", "needs": [], "offline": True},
    {"id": "pronounce_word", "name": "Hear words & examples (system voice)", "status": "available", "needs": [], "offline": True},
    {"id": "conversation_text", "name": "AI Conversation (typed)", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "conversation_voice", "name": "AI Conversation (voice, hands-free)", "status": "available", "needs": ["llm_key", "internet", "microphone"]},
    {"id": "ai_voice", "name": "Natural AI voices (optional; device voices otherwise)", "status": "available", "needs": ["openai_key", "internet"]},
    {"id": "writing", "name": "Writing tutor", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "reading", "name": "Advanced Reading (texts, questions, speed)", "status": "available", "needs": [], "offline": True},
    {"id": "reading_ai", "name": "Reading: click-to-define any word, summary feedback", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "listening", "name": "Listening Lab with device voices", "status": "available", "needs": [], "offline": True},
    {"id": "listening_ai", "name": "Listening Lab natural multi-voice audio (cached after first play)", "status": "available", "needs": ["openai_key", "internet"]},
    {"id": "pron_offline", "name": "Pronunciation: sounds, minimal pairs, word stress, record & compare", "status": "available", "needs": ["microphone"], "offline": True},
    {"id": "pron_check", "name": "Pronunciation: read-aloud clarity check", "status": "available", "needs": ["internet", "microphone"]},
    {"id": "pron_phoneme", "name": "Pronunciation: phoneme-level scoring (Azure Speech)", "status": "available", "needs": ["azure_key", "internet", "microphone"]},
    {"id": "video_scenes", "name": "Video Academy: animated scenes with synced subtitles", "status": "available", "needs": [], "offline": True},
    {"id": "video_library", "name": "Video Academy: your own videos / YouTube embeds + subtitles", "status": "available", "needs": []},
    {"id": "video_study", "name": "Video Academy: AI study pack (vocabulary, idioms, grammar, questions)", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "exam_objective", "name": "IELTS Academic mock: timed Listening & Reading with band estimates", "status": "available", "needs": [], "offline": True},
    {"id": "exam_ai", "name": "IELTS Academic mock: Writing & Speaking assessment", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "toefl_cambridge_objective", "name": "TOEFL iBT (2026 format), Cambridge C1 & C2 mocks: reading, use of English, listening", "status": "available", "needs": [], "offline": True},
    {"id": "toefl_cambridge_ai", "name": "TOEFL & Cambridge mocks: writing and speaking assessment", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "business", "name": "Business, Finance & Academic English track", "status": "available", "needs": []},
    {"id": "placement", "name": "Placement test (grammar, vocabulary, reading, listening)", "status": "available", "needs": [], "offline": True},
    {"id": "placement_ai", "name": "Placement test: writing & speaking levels", "status": "available", "needs": ["llm_key", "internet"]},
    {"id": "weekly", "name": "Weekly progress check", "status": "available", "needs": [], "offline": True},
    {"id": "path", "name": "Personal learning path", "status": "available", "needs": [], "offline": True},
    {"id": "analytics", "name": "Progress analytics & learning history", "status": "available", "needs": [], "offline": True},
    {"id": "search", "name": "Search & bookmarks", "status": "available", "needs": [], "offline": True},
    {"id": "reminders", "name": "Daily study reminders", "status": "available", "needs": []},
]


@router.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}


class PinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=32)


@router.post("/unlock")
def unlock(body: PinIn, request: Request, response: Response):
    import hmac
    import time

    time.sleep(0.5)  # slow down guessing
    if not settings.lan_pin or not hmac.compare_digest(body.pin, settings.lan_pin):
        raise HTTPException(401, "Wrong PIN")
    response.set_cookie("ema_pin", body.pin, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", max_age=60 * 60 * 24 * 30)
    return {"ok": True}


@router.get("/whoami")
def whoami(request: Request):
    host = request.client.host if request.client else ""
    return {"local": host in {"127.0.0.1", "::1", "localhost", "testclient"}, "lan_mode": bool(settings.lan_pin)}


@router.get("/features")
def features():
    return FEATURES


@router.get("/providers")
def providers():
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "stt": f"{settings.stt_provider}:{settings.stt_model}",
        "tts": f"{settings.tts_provider}:{settings.tts_model}:{settings.tts_voice}",
        "keys": {name: bool(get_secret(name)) for name in ("gemini", "openai", "anthropic", "azure_speech")},
        "azure_speech_region": settings.azure_speech_region,
    }


class KeyIn(BaseModel):
    provider: str = Field(pattern=r"^(gemini|openai|anthropic|azure_speech)$")
    api_key: str = Field(min_length=10, max_length=300)


@router.post("/keys")
def save_key(body: KeyIn):
    if not set_secret(body.provider, body.api_key.strip()):
        raise HTTPException(
            500,
            "Could not access the Windows Credential Manager. Set the key as an environment "
            f"variable {body.provider.upper()}_API_KEY instead.",
        )
    return {"saved": True}


@router.delete("/keys/{provider}")
def remove_key(provider: str):
    delete_secret(provider)
    return {"deleted": True}


class ProviderIn(BaseModel):
    llm_provider: str = Field(pattern=r"^(gemini|openai|anthropic)$")
    llm_model: str = Field(min_length=2, max_length=80)
    azure_speech_region: str = Field("", pattern=r"^[a-z0-9]{0,30}$")


@router.put("/providers")
def set_provider(body: ProviderIn):
    """Runtime switch (persist by also writing EMA_LLM_PROVIDER/EMA_LLM_MODEL to .env)."""
    settings.llm_provider = body.llm_provider
    settings.llm_model = body.llm_model
    settings.azure_speech_region = body.azure_speech_region
    env = settings.data_dir / ".env"
    env.parent.mkdir(parents=True, exist_ok=True)
    env.write_text(f"EMA_LLM_PROVIDER={body.llm_provider}\nEMA_LLM_MODEL={body.llm_model}\n"
                   f"EMA_AZURE_SPEECH_REGION={body.azure_speech_region}\n", encoding="utf-8")
    return providers()


@router.post("/backup")
def backup():
    url = settings.resolved_database_url()
    if not url.startswith("sqlite:///"):
        raise HTTPException(400, "Backup is only supported for the local SQLite database")
    src = url.removeprefix("sqlite:///")
    get_engine().dispose()
    dest_dir = settings.data_dir / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"english_mastery_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(src, dest)
    return FileResponse(dest, filename=dest.name, media_type="application/octet-stream")


@router.post("/selftest")
def selftest():
    """Live checks of every external dependency. Each check is independent and reports ok / fail / skipped."""
    import platform
    import sys
    import time

    import httpx

    from ..db import get_engine
    from ..providers.llm import ChatMessage, MissingAPIKey, get_llm
    from ..providers.speech import get_stt, get_tts
    from ..services.alignment import align
    from ..services.correction import analyse_utterance

    results = []

    def check(name, fn):
        t0 = time.perf_counter()
        try:
            detail = fn()
            results.append({"name": name, "status": "ok", "detail": detail, "ms": round((time.perf_counter() - t0) * 1000)})
        except MissingAPIKey as e:
            results.append({"name": name, "status": "skipped", "detail": str(e)})
        except Exception as e:  # noqa: BLE001 - report every failure to the user
            results.append({"name": name, "status": "fail", "detail": f"{type(e).__name__}: {e}"[:400]})

    def system():
        from sqlalchemy import text
        with get_engine().connect() as c:
            c.execute(text("select 1"))
        probe = settings.data_dir / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return f"Python {sys.version.split()[0]} on {platform.system()} {platform.release()}; database and data folder OK ({settings.data_dir})"

    def llm():
        r = get_llm().chat_json([ChatMessage("system", 'Reply with strict JSON {"ok": true}.'), ChatMessage("user", "ping")], max_tokens=20)
        if r.get("ok") is not True:
            raise RuntimeError(f"unexpected reply {r}")
        p = get_llm()
        return f"{p.name} / {getattr(p, 'model', '?')} answered correctly"

    def correction():
        fb = analyse_utterance(get_llm(), "I am agree with this decision.")
        if not fb.issues:
            raise RuntimeError("the correction engine did not detect the planted error 'I am agree'")
        return f"Detected: '{fb.issues[0].original}' → '{fb.issues[0].corrected}'"

    audio = {}

    def tts():
        data, mime = get_tts().synthesize("The quick brown fox jumps over the lazy dog.")
        if len(data) < 1000:
            raise RuntimeError("audio too short")
        audio["mp3"] = data
        return f"{len(data) // 1024} KB of {mime} generated"

    def stt():
        if "mp3" not in audio:
            raise MissingAPIKey("openai")
        t = get_stt().transcribe(audio["mp3"], "selftest.mp3")
        score = align("The quick brown fox jumps over the lazy dog.", t.text)["score"]
        if score < 0.8:
            raise RuntimeError(f"recognised '{t.text}' ({score:.0%} match)")
        return f"Recognised the test sentence ({score:.0%} match), {len(t.words)} word timestamps"

    def azure():
        key, region = get_secret("azure_speech"), settings.azure_speech_region
        if not key or not region:
            raise MissingAPIKey("azure_speech")
        r = httpx.post(f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
                       headers={"Ocp-Apim-Subscription-Key": key}, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Azure answered {r.status_code}: check key and region")
        return f"Key accepted in region {region}"

    def tts_opt():
        if not get_secret("openai"):
            raise MissingAPIKey("openai — optional: without it the app uses your device's free voices")
        return tts()

    def stt_opt():
        if not get_secret("openai"):
            raise MissingAPIKey("openai — optional: without it the app uses Chrome's free speech recognition")
        return stt()

    for name, fn in (("App & database", system), ("AI professor (conversation, corrections, marking)", llm), ("Correction engine", correction),
                     ("Natural AI voices (optional, OpenAI)", tts_opt), ("Whisper speech analysis (optional, OpenAI)", stt_opt), ("Azure phoneme scoring (optional)", azure)):
        check(name, fn)
    return {"results": results, "ran_at": datetime.utcnow().isoformat()}
