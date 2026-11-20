from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import progress as _progress
from ..deps import current_profile
from ..models import ActivityLog, Mistake, Profile
from ..providers.llm import ChatMessage, MissingAPIKey, ProviderError, get_llm

router = APIRouter(prefix="/api/writing", tags=["writing"])

GENRES = {
    "short_text": "Short text (A1–A2): about me, a postcard, a simple email",
    "paragraph": "Structured paragraph (B1)",
    "email": "Professional email",
    "essay": "Academic / opinion essay",
    "ielts_task2": "IELTS Academic Writing Task 2",
    "report": "Business report or executive summary",
    "cover_letter": "Cover letter",
    "minutes": "Meeting minutes",
    "summary": "Summary of a video, talk or article",
    "ielts_task1": "IELTS Academic Writing Task 1 (describe a chart)",
    "proposal": "Business proposal",
}

PROMPT = """You are a demanding but kind writing tutor (Cambridge C2 examiner level) for a French-speaking learner.
Genre: {genre}. Target level: {target}. Learner's current level: {level} — judge the text against what is realistic for that level, and keep explanations simple for A1–B1.
Return strict JSON:
{{"improved_text": str,
  "issues": [{{"category": "grammar"|"vocabulary"|"naturalness"|"coherence"|"repetition"|"register"|"punctuation",
              "original": str, "corrected": str, "explanation": str, "pattern": str}}],
  "repeated_words": [str],
  "scores": {{"task_achievement": float, "coherence_cohesion": float, "lexical_resource": float, "grammar_accuracy": float}},
  "overall": float,
  "practice_band_estimate": float|null,
  "advanced_expressions": [{{"instead_of": str, "try": str}}],
  "next_exercise": str}}
Scores are 0..1. practice_band_estimate only for IELTS genres (else null).
Keep the learner's meaning and voice in improved_text; fix, don't rewrite from scratch."""


class WritingIn(BaseModel):
    genre: str = "essay"
    text: str = Field(min_length=20, max_length=12000)
    task: str | None = Field(None, max_length=2000)
    lesson_id: str | None = Field(None, max_length=60)


@router.get("/genres")
def genres():
    return GENRES


@router.post("/evaluate")
def evaluate(body: WritingIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    if body.genre not in GENRES:
        raise HTTPException(400, "Unknown genre")
    user = (f"Task: {body.task}\n\n" if body.task else "") + f"Learner text:\n\"\"\"{body.text}\"\"\""
    try:
        result = get_llm().chat_json(
            [ChatMessage("system", PROMPT.format(genre=GENRES[body.genre], target=p.target_level, level=p.estimated_level)), ChatMessage("user", user)],
            max_tokens=3000,
        )
    except MissingAPIKey as e:
        raise HTTPException(412, str(e)) from e
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e
    for i in result.get("issues", [])[:30]:
        db.add(Mistake(profile_id=p.id, category=i.get("category", "grammar")[:20], pattern=(i.get("pattern") or "")[:120],
                       original=i.get("original", ""), corrected=i.get("corrected", ""), explanation=i.get("explanation", ""), source="writing"))
    overall = float(result.get("overall") or 0)
    db.add(ActivityLog(profile_id=p.id, skill="writing", item_id=body.genre, score=max(0.0, min(1.0, overall)),
                       seconds=len(body.text.split()) * 3))
    if body.lesson_id:
        db.add(ActivityLog(profile_id=p.id, skill="writing", item_id=f"lesson:{body.lesson_id}", score=max(0.0, min(1.0, overall)), seconds=0))
    db.commit()
    if body.lesson_id:
        _progress.after(db, p, "writing", body.lesson_id)
    if result.get("practice_band_estimate") is not None:
        result["disclaimer"] = "Practice estimate only — not an official IELTS score."
    result["original_text"] = body.text
    return result
