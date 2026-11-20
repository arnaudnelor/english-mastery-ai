from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_profile
from ..models import Profile
from ..services import learning

router = APIRouter(prefix="/api/profile", tags=["profile"])

LEVELS = r"^(A1|A2|B1|B2|C1|C2)$"
MODES = r"^(immediate|after_response|end_of_conversation|strict)$"


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    target_level: str = Field("C1", pattern=LEVELS)
    estimated_level: str = Field("B2", pattern=LEVELS)
    daily_minutes: int = Field(60, ge=15, le=480)
    accent_preference: str = Field("en-CA", pattern=r"^en-(CA|US|GB)$")
    correction_mode: str = Field("after_response", pattern=MODES)
    french_explanations: bool = False
    reminder_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


def _out(p: Profile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "target_level": p.target_level,
        "estimated_level": p.estimated_level,
        "daily_minutes": p.daily_minutes,
        "accent_preference": p.accent_preference,
        "correction_mode": p.correction_mode,
        "french_explanations": bool(p.french_explanations),
        "reminder_time": p.reminder_time,
        "placement_done": p.placement_done_at is not None,
        "level_confirmed": bool(p.level_confirmed) or p.placement_done_at is not None,
    }


@router.get("")
def get_profile(db: Session = Depends(get_db)):
    p = db.scalar(select(Profile).order_by(Profile.id))
    return _out(p) if p else None


@router.put("")
def upsert_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = db.scalar(select(Profile).order_by(Profile.id)) or Profile()
    for k, v in body.model_dump().items():
        setattr(p, k, int(v) if isinstance(v, bool) else v)
    db.add(p)
    db.commit()
    return _out(p)


@router.get("/dashboard")
def dashboard(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    est = learning.estimated_level(db, p.id, p.estimated_level)
    return {
        "profile": _out(p),
        "estimated_cefr": est,
        "skills": learning.skill_scores(db, p.id),
        "weaknesses": learning.top_weaknesses(db, p.id),
        "vocabulary": learning.vocab_stats(db, p.id),
        "minutes_week": learning.study_minutes(db, p.id, 7),
        "minutes_month": learning.study_minutes(db, p.id, 30),
        "streak_days": learning.streak(db, p.id),
        "daily_plan": learning.daily_plan(db, p.id, p.daily_minutes),
    }
