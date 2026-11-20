from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import current_profile
from ..models import ActivityLog, Profile, VocabCard
from ..services import srs

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


def _cards(db, pid) -> dict[str, VocabCard]:
    return {c.word_id: c for c in db.scalars(select(VocabCard).where(VocabCard.profile_id == pid))}


@router.get("/words")
def list_words(q: str | None = None, domain: str | None = None, level: str | None = None,
               p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    cards = _cards(db, p.id)
    out = []
    for w in content.vocabulary():
        if domain and w["domain"] != domain:
            continue
        if level and w["level"] != level:
            continue
        if q and q.lower() not in (w["word"] + " " + w["definition"]).lower():
            continue
        c = cards.get(w["id"])
        out.append(w | {"status": srs.status(c) if c else "not_started", "in_deck": c is not None})
    return out


@router.post("/deck/{word_id}")
def add_to_deck(word_id: str, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    if not content.find_word(word_id):
        raise HTTPException(404, "Word not found")
    if word_id not in _cards(db, p.id):
        db.add(VocabCard(profile_id=p.id, word_id=word_id))
        db.commit()
    return {"ok": True}


@router.post("/deck-all")
def add_all(level: str | None = None, domain: str | None = None, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    have = _cards(db, p.id)
    n = 0
    for w in content.vocabulary():
        if w["id"] not in have and (level is None or w["level"] == level) and (domain is None or w["domain"] == domain):
            db.add(VocabCard(profile_id=p.id, word_id=w["id"]))
            n += 1
    db.commit()
    return {"added": n}


@router.get("/review")
def due_cards(limit: int = 20, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(VocabCard)
        .where(VocabCard.profile_id == p.id, VocabCard.due_at <= datetime.utcnow())
        .order_by(VocabCard.due_at)
        .limit(limit)
    ).all()
    return [{"card_id": c.id, "status": srs.status(c), "word": content.find_word(c.word_id)} for c in rows if content.find_word(c.word_id)]


class GradeIn(BaseModel):
    grade: int = Field(ge=0, le=3)


@router.post("/review/{card_id}")
def grade(card_id: int, body: GradeIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    c = db.get(VocabCard, card_id)
    if not c or c.profile_id != p.id:
        raise HTTPException(404, "Card not found")
    srs.review(c, body.grade)
    db.add(ActivityLog(profile_id=p.id, skill="vocabulary", item_id=c.word_id, score=body.grade / 3, seconds=8))
    db.commit()
    return {"next_due": c.due_at.isoformat(), "interval_days": c.interval_days, "status": srs.status(c)}
