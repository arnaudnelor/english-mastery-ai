from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..services import progress as _progress
from ..deps import current_profile, provider_errors
from ..models import ActivityLog, Mistake, Profile
from ..providers.llm import ChatMessage, get_llm

router = APIRouter(prefix="/api/reading", tags=["reading"])


def _text(tid: str) -> dict:
    t = content.by_id(content.reading_texts(), tid)
    if not t:
        raise HTTPException(404, "Text not found")
    return t


@router.get("/texts")
def list_texts():
    return [
        {k: t[k] for k in ("id", "title", "level", "genre", "domain")}
        | {"word_count": len(t["body"].split()), "question_count": len(t["questions"])}
        for t in content.reading_texts()
    ]


@router.get("/texts/{tid}")
def get_text(tid: str):
    t = _text(tid)
    return t | {"questions": [{k: v for k, v in q.items() if k not in ("answer", "explanation")} for q in t["questions"]],
                "word_count": len(t["body"].split())}


class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(max_length=500)


@router.post("/texts/{tid}/answer")
def answer(tid: str, body: AnswerIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    t = _text(tid)
    q = next((q for q in t["questions"] if q["id"] == body.question_id), None)
    if not q:
        raise HTTPException(404, "Question not found")
    ok = content.normalise(body.answer) == content.normalise(q["answer"])
    db.add(ActivityLog(profile_id=p.id, skill="reading", item_id=f"{tid}:{q['id']}", score=float(ok), seconds=0))
    db.commit()
    _progress.after(db, p, "reading", tid)
    return {"correct": ok, "answer": q["answer"], "explanation": q["explanation"], "type": q["type"]}


class FinishIn(BaseModel):
    seconds: int = Field(ge=1, le=7200)


@router.post("/texts/{tid}/finish")
def finish(tid: str, body: FinishIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    """Record reading time and return reading speed."""
    t = _text(tid)
    words = len(t["body"].split())
    wpm = round(words / body.seconds * 60)
    db.add(ActivityLog(profile_id=p.id, skill="reading", item_id=f"{tid}:time", score=min(1.0, wpm / 250), seconds=body.seconds))
    db.commit()
    benchmark = {"B2": 180, "C1": 220, "C2": 250}[t["level"]]
    return {"words": words, "wpm": wpm, "benchmark_wpm": benchmark,
            "note": "Typical comfortable speed for confident readers at this level is around "
                    f"{benchmark} words per minute with good comprehension."}


class DefineIn(BaseModel):
    word: str = Field(min_length=1, max_length=60)
    sentence: str = Field(max_length=1000)


@router.post("/define")
@provider_errors
def define(body: DefineIn, p: Profile = Depends(current_profile)):
    """Contextual explanation of any clicked word (AI). Glossary words are served offline by the UI."""
    fr = "Add a short French translation in 'french'." if p.french_explanations else "Set 'french' to null."
    return get_llm().chat_json([
        ChatMessage("system", "You are a concise English lexicographer for an advanced learner. Return strict JSON: "
                    '{"word": str, "ipa": str, "part_of_speech": str, "meaning_in_context": str, '
                    '"other_common_meaning": str|null, "example": str, "french": str|null}. ' + fr),
        ChatMessage("user", f"Word: {body.word}\nSentence: {body.sentence}"),
    ], max_tokens=400)


class SummaryIn(BaseModel):
    summary: str = Field(min_length=20, max_length=3000)


SUMMARY_PROMPT = """You assess a learner's summary of a text (target {level}). Return strict JSON:
{{"content_score": float, "language_score": float, "captured_main_idea": bool,
  "missing_points": [str], "inaccuracies": [str], "copied_phrases": [str],
  "corrections": [{{"original": str, "corrected": str, "explanation": str, "category": str}}],
  "model_summary": str, "comment": str}}
Scores 0..1. copied_phrases = long chunks copied verbatim from the text (summaries should paraphrase)."""


@router.post("/texts/{tid}/summary")
@provider_errors
def summary(tid: str, body: SummaryIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    t = _text(tid)
    r = get_llm().chat_json([
        ChatMessage("system", SUMMARY_PROMPT.format(level=t["level"])),
        ChatMessage("user", f"TEXT:\n{t['body']}\n\nLEARNER SUMMARY:\n{body.summary}"),
    ], max_tokens=1500)
    score = (float(r.get("content_score") or 0) + float(r.get("language_score") or 0)) / 2
    db.add(ActivityLog(profile_id=p.id, skill="writing", item_id=f"summary:{tid}", score=max(0.0, min(1.0, score)),
                       seconds=len(body.summary.split()) * 4))
    for c in (r.get("corrections") or [])[:15]:
        db.add(Mistake(profile_id=p.id, category=(c.get("category") or "grammar")[:20], pattern=(c.get("original") or "")[:60],
                       original=c.get("original", ""), corrected=c.get("corrected", ""), explanation=c.get("explanation", ""),
                       source="reading_summary"))
    db.commit()
    return r
