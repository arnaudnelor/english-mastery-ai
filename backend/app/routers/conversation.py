"""AI Speaking & Conversation Lab.

Flow for a spoken turn:
  microphone audio -> Whisper STT (word timestamps) -> objective fluency metrics
  -> LLM teacher reply  +  LLM correction analysis (categorised)
  -> mistakes stored for weakness tracking -> TTS of the reply on demand.
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import progress as _progress
from ..deps import current_profile
from ..models import ActivityLog, Conversation, Message, Mistake, Profile
from ..providers.llm import ChatMessage, MissingAPIKey, ProviderError, get_llm
from ..providers.speech import fluency_metrics, get_tts, transcribe_any
from ..services import conversation as conv
from ..services.correction import analyse_utterance

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # Whisper API limit


def provider_errors(fn):
    """Translate provider failures into clear HTTP errors for the UI."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except MissingAPIKey as e:
            raise HTTPException(412, str(e)) from e
        except ProviderError as e:
            raise HTTPException(502, str(e)) from e

    return wrapper


@router.get("/modes")
def modes():
    return {
        "modes": [{"id": k, "title": v["title"], "brief": v["brief"]} for k, v in conv.MODES.items()],
        "personas": list(conv.PERSONAS),
        "accents": conv.ACCENTS,
        "correction_modes": ["immediate", "after_response", "end_of_conversation", "strict"],
    }


class StartIn(BaseModel):
    mode: str = "free"
    correction_mode: str | None = Field(None, pattern=r"^(immediate|after_response|end_of_conversation|strict)$")


@router.post("/start")
def start(body: StartIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    if body.mode not in conv.MODES:
        raise HTTPException(400, "Unknown mode")
    c = Conversation(profile_id=p.id, mode=body.mode, correction_mode=body.correction_mode or p.correction_mode)
    db.add(c)
    db.flush()
    opener = conv.MODES[body.mode]["opener"]
    db.add(Message(conversation_id=c.id, role="assistant", content=opener))
    db.commit()
    return {"conversation_id": c.id, "opener": opener, "correction_mode": c.correction_mode}


def _history(db, cid) -> list[ChatMessage]:
    rows = db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id)).all()
    return [ChatMessage(m.role, m.content) for m in rows]


def learner_notes(db: Session, p: Profile) -> str:
    """Long-term memory for the AI professor: who the learner is and what they keep getting wrong."""
    from ..services.learning import top_weaknesses

    weak = top_weaknesses(db, p.id, 5)
    last = db.scalar(select(Conversation).where(Conversation.profile_id == p.id, Conversation.summary.is_not(None))
                     .order_by(Conversation.id.desc()))
    lines = [f"Learner: {p.name}, French speaker, about {p.estimated_level}, aiming for {p.target_level}."]
    if weak:
        lines.append("Recurring mistakes to watch for and gently target: " + "; ".join(f"{w['pattern']} (x{w['count']})" for w in weak) + ".")
    if last and last.summary:
        steps = last.summary.get("next_steps") or []
        if steps:
            lines.append("Agreed next steps from the last session: " + "; ".join(steps[:3]) + ".")
    return " ".join(lines)


def _turn(db: Session, p: Profile, c: Conversation, text: str, persona: str, metrics: dict | None):
    llm = get_llm()
    history = _history(db, c.id)
    history.append(ChatMessage("user", text))

    # Feedback is always computed (so mistakes are tracked); *display* depends on mode.
    feedback = analyse_utterance(
        llm, text, context=history[:-1], level=p.estimated_level, target=p.target_level,
        french=bool(p.french_explanations), speech_metrics=metrics,
    )
    inline = c.correction_mode == "immediate"
    msgs = conv.build_messages(c.mode, persona, p.accent_preference, p.estimated_level, inline, history)
    msgs[0] = ChatMessage("system", msgs[0].content + "\nWhat you remember about this learner: " + learner_notes(db, p))
    reply = llm.chat(msgs)

    db.add(Message(conversation_id=c.id, role="user", content=text, feedback=feedback.model_dump(), speech_metrics=metrics))
    db.add(Message(conversation_id=c.id, role="assistant", content=reply))
    for i in feedback.issues:
        db.add(Mistake(profile_id=p.id, category=i.category, pattern=i.pattern[:120] or i.category,
                       original=i.original, corrected=i.corrected, explanation=i.explanation))
    db.add(ActivityLog(profile_id=p.id, skill="speaking", item_id=f"conv:{c.id}", score=feedback.score,
                       seconds=int((metrics or {}).get("duration_sec") or 20) + 15))
    db.commit()
    _progress.after(db, p, "conversation", c.mode)

    show = c.correction_mode in ("immediate", "after_response", "strict")
    if c.correction_mode == "immediate" and feedback.is_correct:
        show = False  # don't interrupt when there's nothing to fix
    return {
        "transcript": text,
        "reply": reply,
        "feedback": feedback.model_dump() if show else None,
        "feedback_deferred": not show,
        "speech_metrics": metrics,
    }


class SpeechInfo(BaseModel):
    duration_sec: float = Field(ge=0, le=600)
    source: str = Field("browser", max_length=20)


class TurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    persona: str = "professor"
    speech: SpeechInfo | None = None  # set when the text came from the browser's speech recognition


@router.post("/{cid}/turn")
@provider_errors
def text_turn(cid: int, body: TurnIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.profile_id != p.id:
        raise HTTPException(404, "Conversation not found")
    metrics = None
    if body.speech:
        from ..providers.speech import Transcript
        metrics = fluency_metrics(Transcript(text=body.text, words=[], duration=body.speech.duration_sec))
    return _turn(db, p, c, body.text.strip(), body.persona, metrics)


@router.post("/{cid}/voice-turn")
@provider_errors
def voice_turn(
    cid: int,
    audio: UploadFile = File(...),
    persona: str = Form("professor"),
    transcript: str = Form(""),
    duration: float = Form(0),
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    c = db.get(Conversation, cid)
    if not c or c.profile_id != p.id:
        raise HTTPException(404, "Conversation not found")
    data = audio.file.read()
    if not data and not transcript:
        raise HTTPException(400, "Empty recording")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too long (max 25 MB)")
    t = transcribe_any(data, audio.filename or "speech.webm", transcript, duration)
    if not t.text:
        raise HTTPException(422, "I couldn't hear any speech. Check your microphone and try again.")
    return _turn(db, p, c, t.text, persona, fluency_metrics(t))


@router.post("/{cid}/end")
@provider_errors
def end(cid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.profile_id != p.id:
        raise HTTPException(404, "Conversation not found")
    msgs = db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id)).all()
    user_msgs = [m for m in msgs if m.role == "user"]
    if not user_msgs:
        raise HTTPException(400, "Nothing to review yet")
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in msgs)
    summary = get_llm().chat_json([
        ChatMessage("system", conv.SUMMARY_PROMPT + f"\nMode: {c.mode}."),
        ChatMessage("user", transcript),
    ])
    summary["corrections"] = [m.feedback for m in user_msgs if m.feedback and m.feedback.get("issues")]
    if c.mode in ("ielts", "toefl"):
        summary["disclaimer"] = "Practice estimate only — not an official examination score."
    c.summary = summary
    db.commit()
    return summary


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = None


@router.post("/tts")
@provider_errors
def tts(body: TTSIn):
    audio, mime = get_tts().synthesize(body.text, body.voice)
    return {"mime": mime, "audio_base64": base64.b64encode(audio).decode()}


@router.get("/history")
def history(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).where(Conversation.profile_id == p.id).order_by(Conversation.id.desc()).limit(50)).all()
    out = []
    for c in rows:
        n = db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == c.id, Message.role == "user")) or 0
        if n:
            out.append({"id": c.id, "mode": c.mode, "title": conv.MODES.get(c.mode, {}).get("title", c.mode),
                        "started_at": c.started_at.isoformat(), "turns": n, "has_summary": c.summary is not None,
                        "estimated_cefr": (c.summary or {}).get("estimated_cefr")})
    return out


@router.get("/{cid}")
def get_conversation(cid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.profile_id != p.id:
        raise HTTPException(404, "Conversation not found")
    msgs = db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id)).all()
    return {"id": c.id, "mode": c.mode, "title": conv.MODES.get(c.mode, {}).get("title", c.mode), "started_at": c.started_at.isoformat(),
            "summary": c.summary, "messages": [{"role": m.role, "content": m.content, "feedback": m.feedback, "speech_metrics": m.speech_metrics} for m in msgs]}


