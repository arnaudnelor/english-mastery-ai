"""Pronunciation Lab.

Read-aloud check: learner audio -> Whisper -> word alignment against the target.
A word the recogniser could not match is flagged as *possibly unclear*. This is an
intelligibility proxy, not phoneme scoring (see docs/ARCHITECTURE.md).
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import current_profile, provider_errors
from ..models import ActivityLog, Mistake, Profile
from ..providers import pronunciation as azure
from ..providers.speech import fluency_metrics, transcribe_any
from ..services.alignment import align

router = APIRouter(prefix="/api/pronunciation", tags=["pronunciation"])


@router.get("/content")
def get_content():
    return content.pronunciation()


@router.post("/read-aloud")
@provider_errors
def read_aloud(
    audio: UploadFile = File(...),
    target: str = Form(..., min_length=1, max_length=500),
    item_id: str = Form("free"),
    transcript: str = Form(""),
    duration: float = Form(0),
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    data = audio.file.read()
    if not data and not transcript:
        raise HTTPException(400, "Empty recording")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Recording too long")
    t = transcribe_any(data, audio.filename or "speech.webm", transcript, duration)
    r = align(target, t.text)
    metrics = fluency_metrics(t)
    db.add(ActivityLog(profile_id=p.id, skill="pronunciation", item_id=item_id[:80], score=r["score"],
                       seconds=int(metrics["duration_sec"] or 5) + 10))
    for w in r["words"]:
        if w["status"] in ("wrong", "missed") and w["word"]:
            db.add(Mistake(profile_id=p.id, category="pronunciation", pattern=f"unclear: {w['word'].strip('.,;:!?').lower()}"[:120],
                           original=w.get("heard") or "(not recognised)", corrected=w["word"],
                           explanation="The speech recogniser did not match this word.", source="read_aloud"))
    db.commit()
    return r | {"heard": t.text, "metrics": metrics,
                "note": "Scores show how clearly a speech recogniser understood you. They are a useful guide, not a phoneme-level assessment."}


class PairResult(BaseModel):
    set_id: str
    correct: int = Field(ge=0, le=100)
    total: int = Field(ge=1, le=100)


@router.post("/minimal-pairs/result")
def pair_result(body: PairResult, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    if not any(s["id"] == body.set_id for s in content.pronunciation()["minimal_pairs"]):
        raise HTTPException(404, "Unknown set")
    score = min(1.0, body.correct / body.total)
    db.add(ActivityLog(profile_id=p.id, skill="pronunciation", item_id=f"pairs:{body.set_id}", score=score, seconds=body.total * 6))
    db.commit()
    return {"score": score}


@router.post("/assess")
@provider_errors
def assess(
    audio: UploadFile = File(..., description="16 kHz mono PCM WAV"),
    target: str = Form(..., min_length=1, max_length=500),
    item_id: str = Form("free"),
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    """Phoneme-level assessment via Azure Speech (optional provider)."""
    data = audio.file.read()
    if not data.startswith(b"RIFF"):
        raise HTTPException(400, "Expected a WAV recording")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Recording too long (max ~5 minutes)")
    r = azure.assess(data, target, p.accent_preference if p.accent_preference in ("en-US", "en-GB", "en-CA") else "en-US")
    score = (r["pronunciation_score"] or 0) / 100
    db.add(ActivityLog(profile_id=p.id, skill="pronunciation", item_id=f"azure:{item_id}"[:80], score=score, seconds=15))
    for w in r["words"]:
        if w["accuracy"] is not None and w["accuracy"] < 60:
            weak = [ph["phoneme"] for ph in w["phonemes"] if (ph["accuracy"] or 100) < 60]
            db.add(Mistake(profile_id=p.id, category="pronunciation",
                           pattern=(f"sound /{weak[0]}/" if weak else f"word: {w['word']}")[:120],
                           original=w["word"] or "", corrected=w["word"] or "",
                           explanation=f"Accuracy {w['accuracy']:.0f}/100" + (f"; weak sounds: {', '.join(weak)}" if weak else ""),
                           source="azure_assessment"))
    db.commit()
    return r
