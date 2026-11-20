from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import current_profile
from ..models import ActivityLog, Mistake, Profile
from ..services import progress

router = APIRouter(prefix="/api/grammar", tags=["grammar"])


def _public_exercise(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in ("answer", "explanation")}


@router.get("/topics")
def list_topics(level: str | None = None):
    return [
        {k: t[k] for k in ("id", "title", "level", "unit", "summary")} | {"exercise_count": len(t["exercises"])}
        for t in content.grammar_topics()
        if level is None or t["level"] == level
    ]


@router.get("/topics/{topic_id}")
def get_topic(topic_id: str):
    t = content.find_topic(topic_id)
    if not t:
        raise HTTPException(404, "Topic not found")
    return t | {"exercises": [_public_exercise(e) for e in t["exercises"]]}


class AnswerIn(BaseModel):
    exercise_id: str
    answer: str = Field(max_length=500)
    seconds: int = Field(0, ge=0, le=3600)


@router.post("/topics/{topic_id}/answer")
def answer(topic_id: str, body: AnswerIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    t = content.find_topic(topic_id)
    if not t:
        raise HTTPException(404, "Topic not found")
    ex = next((e for e in t["exercises"] if e["id"] == body.exercise_id), None)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    ok = content.check_answer(ex, body.answer)
    db.add(ActivityLog(profile_id=p.id, skill="grammar", item_id=f"{topic_id}:{ex['id']}", score=1.0 if ok else 0.0, seconds=body.seconds))
    if not ok:
        db.add(Mistake(profile_id=p.id, category="grammar", pattern=t["title"], original=body.answer,
                       corrected=ex["answer"] if isinstance(ex["answer"], str) else ex["answer"][0],
                       explanation=ex["explanation"], source="grammar_exercise"))
    db.commit()
    progress.after(db, p, "lesson", topic_id)
    accepted = ex["answer"] if isinstance(ex["answer"], list) else [ex["answer"]]
    return {"correct": ok, "accepted_answers": accepted, "explanation": ex["explanation"]}
