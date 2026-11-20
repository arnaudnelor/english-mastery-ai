"""Listening Laboratory.

Audio for each line is synthesised once per speaker voice with the TTS provider
and cached on disk, so lessons replay offline afterwards. Without a key, the UI
falls back to Windows voices (per-speaker accent) so the module still works.
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import content
from ..config import settings
from ..db import get_db
from ..deps import current_profile, provider_errors
from ..models import ActivityLog, Mistake, Profile
from ..providers.speech import get_tts
from ..services.alignment import align

router = APIRouter(prefix="/api/listening", tags=["listening"])


def _item(iid: str) -> dict:
    it = content.by_id(content.listening_items(), iid)
    if not it:
        raise HTTPException(404, "Listening item not found")
    return it


def audio_cache_dir():
    d = settings.data_dir / "audio_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/items")
def items():
    return [
        {k: it[k] for k in ("id", "title", "level", "kind", "domain")}
        | {"accents": sorted({s["accent"] for s in it["speakers"].values()}), "lines": len(it["lines"])}
        for it in content.listening_items()
    ]


@router.get("/items/{iid}")
def item(iid: str):
    it = _item(iid)
    cached = [_cache_path(it, i).exists() for i in range(len(it["lines"]))]
    return it | {
        "questions": [{k: v for k, v in q.items() if k not in ("answer", "explanation")} for q in it["questions"]],
        "gaps": [{"line": g["line"], "count": len(g["words"]), "words": g["words"]} for g in it["gaps"]],
        "audio_cached": all(cached),
    }


def _cache_path(it: dict, idx: int):
    line = it["lines"][idx]
    voice = it["speakers"][line["s"]]["voice"]
    h = hashlib.sha1(f"{voice}|{line['t']}".encode()).hexdigest()[:16]
    return audio_cache_dir() / f"{it['id']}_{idx}_{h}.mp3"


@router.get("/items/{iid}/audio/{idx}")
@provider_errors
def audio(iid: str, idx: int):
    it = _item(iid)
    if not 0 <= idx < len(it["lines"]):
        raise HTTPException(404, "Line not found")
    path = _cache_path(it, idx)
    if not path.exists():
        line = it["lines"][idx]
        data, _ = get_tts().synthesize(line["t"], it["speakers"][line["s"]]["voice"])
        path.write_bytes(data)
    return FileResponse(path, media_type="audio/mpeg")


VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}


@router.get("/line")
@provider_errors
def line_audio(text: str, voice: str = "alloy"):
    """Natural-voice audio for any script line (modules, mock exams, papers), cached on disk."""
    text = text.strip()
    if not text or len(text) > 800:
        raise HTTPException(400, "Text must be 1–800 characters")
    if voice not in VOICES:
        raise HTTPException(400, "Unknown voice")
    path = audio_cache_dir() / f"line_{hashlib.sha1(f'{voice}|{text}'.encode()).hexdigest()[:20]}.mp3"
    if not path.exists():
        data, _ = get_tts().synthesize(text, voice)
        path.write_bytes(data)
    return FileResponse(path, media_type="audio/mpeg")


class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(max_length=500)


@router.post("/items/{iid}/answer")
def answer(iid: str, body: AnswerIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    it = _item(iid)
    q = next((q for q in it["questions"] if q["id"] == body.question_id), None)
    if not q:
        raise HTTPException(404, "Question not found")
    ok = content.normalise(body.answer) == content.normalise(q["answer"])
    db.add(ActivityLog(profile_id=p.id, skill="listening", item_id=f"{iid}:{q['id']}", score=float(ok), seconds=30))
    db.commit()
    return {"correct": ok, "answer": q["answer"], "explanation": q["explanation"]}


class DictationIn(BaseModel):
    line: int
    text: str = Field(max_length=1000)


@router.post("/items/{iid}/dictation")
def dictation(iid: str, body: DictationIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    it = _item(iid)
    if body.line not in it["dictation"]:
        raise HTTPException(400, "This line is not a dictation line")
    target = it["lines"][body.line]["t"]
    r = align(target, body.text)
    db.add(ActivityLog(profile_id=p.id, skill="listening", item_id=f"{iid}:dict{body.line}", score=r["score"], seconds=60))
    db.commit()
    return r | {"target": target}


class GapIn(BaseModel):
    line: int
    answers: list[str] = Field(max_length=10)


@router.post("/items/{iid}/gaps")
def gaps(iid: str, body: GapIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    it = _item(iid)
    g = next((g for g in it["gaps"] if g["line"] == body.line), None)
    if not g:
        raise HTTPException(404, "Gap line not found")
    results = [content.normalise(a) == content.normalise(w) for a, w in zip(body.answers + [""] * len(g["words"]), g["words"])]
    score = sum(results) / len(results)
    db.add(ActivityLog(profile_id=p.id, skill="listening", item_id=f"{iid}:gap{body.line}", score=score, seconds=30))
    for ok, w, a in zip(results, g["words"], body.answers + [""] * len(g["words"])):
        if not ok:
            db.add(Mistake(profile_id=p.id, category="vocabulary", pattern=f"heard: {w}"[:120], original=a or "(blank)",
                           corrected=w, explanation="Listening gap-fill", source="listening"))
    db.commit()
    return {"results": results, "words": g["words"], "score": score}
