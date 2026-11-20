"""Personalised learning engine: level estimate, weaknesses, daily plan."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ActivityLog, Mistake, VocabCard
from .srs import status

SKILLS = ("listening", "speaking", "reading", "writing", "grammar", "vocabulary", "pronunciation")
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def score_to_cefr(avg: float, item_level: str = "B2") -> str:
    """Map an average score on items of a given level onto a CEFR estimate."""
    idx = LEVELS.index(item_level) if item_level in LEVELS else 3
    if avg >= 0.85:
        idx += 1
    elif avg < 0.5:
        idx -= 1
    return LEVELS[max(0, min(len(LEVELS) - 1, idx))]


def skill_scores(db: Session, profile_id: int, days: int = 30) -> dict[str, float | None]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(ActivityLog.skill, func.avg(ActivityLog.score))
        .where(ActivityLog.profile_id == profile_id, ActivityLog.created_at >= since)
        .group_by(ActivityLog.skill)
    ).all()
    found = {s: round(float(a), 3) for s, a in rows}
    return {s: found.get(s) for s in SKILLS}


def top_weaknesses(db: Session, profile_id: int, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(Mistake.category, Mistake.pattern).where(Mistake.profile_id == profile_id)
    ).all()
    counts = Counter((c, p) for c, p in rows if p)
    return [
        {"category": c, "pattern": p, "count": n} for (c, p), n in counts.most_common(limit)
    ]


def vocab_stats(db: Session, profile_id: int) -> dict:
    cards = db.scalars(select(VocabCard).where(VocabCard.profile_id == profile_id)).all()
    c = Counter(status(card) for card in cards)
    due = sum(1 for card in cards if card.due_at <= datetime.utcnow())
    return {"total": len(cards), "due": due, **{k: c.get(k, 0) for k in ("new", "learning", "mastered", "often_forgotten")}}


def study_minutes(db: Session, profile_id: int, days: int) -> int:
    from ..models_platform import StudyTime

    since = datetime.utcnow() - timedelta(days=days)
    hb = db.scalar(select(func.coalesce(func.sum(StudyTime.seconds), 0)).where(
        StudyTime.profile_id == profile_id, StudyTime.day >= since.strftime("%Y-%m-%d")))
    if hb:  # real time with the app open (heartbeats)
        return int(hb) // 60
    s = db.scalar(
        select(func.coalesce(func.sum(ActivityLog.seconds), 0)).where(
            ActivityLog.profile_id == profile_id, ActivityLog.created_at >= since
        )
    )
    return int(s or 0) // 60


def streak(db: Session, profile_id: int) -> int:
    dates = {
        d.date()
        for d in db.scalars(select(ActivityLog.created_at).where(ActivityLog.profile_id == profile_id))
    }
    day, n = datetime.utcnow().date(), 0
    if day not in dates:
        day -= timedelta(days=1)
    while day in dates:
        n += 1
        day -= timedelta(days=1)
    return n


# Default share of a session, weighted toward speaking & listening as requested.
BASE_WEIGHTS = {
    "speaking": 0.25,
    "listening": 0.20,
    "pronunciation": 0.10,
    "vocabulary": 0.15,
    "grammar": 0.12,
    "reading": 0.09,
    "writing": 0.09,
}

ROUTES = {
    "speaking": "/conversation",
    "listening": "/listening",
    "pronunciation": "/pronunciation",
    "vocabulary": "/vocabulary",
    "grammar": "/grammar",
    "reading": "/reading",
    "writing": "/writing",
}


def daily_plan(db: Session, profile_id: int, minutes: int) -> list[dict]:
    scores = skill_scores(db, profile_id)
    weights = dict(BASE_WEIGHTS)
    # Boost weak skills (score < 0.7) by up to +50%
    for s, v in scores.items():
        if v is not None and v < 0.7:
            weights[s] *= 1 + (0.7 - v) / 0.7 * 0.5
    total = sum(weights.values())
    weak = top_weaknesses(db, profile_id, 3)
    vs = vocab_stats(db, profile_id)
    plan = []
    for skill, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        mins = max(5, round(minutes * w / total / 5) * 5)
        reason = "Core daily practice"
        if scores.get(skill) is not None and scores[skill] < 0.7:
            reason = f"Weak area (recent average {round(scores[skill] * 100)}%)"
        if skill == "vocabulary" and vs["due"]:
            reason = f"{vs['due']} flashcards due for review"
        if skill == "grammar" and any(x["category"] == "grammar" for x in weak):
            reason = "Targets your recurring mistake: " + next(
                x["pattern"] for x in weak if x["category"] == "grammar"
            )
        plan.append({"skill": skill, "minutes": mins, "reason": reason, "route": ROUTES[skill]})
    return plan


def estimated_level(db: Session, profile_id: int, fallback: str) -> str:
    scores = [v for v in skill_scores(db, profile_id, 60).values() if v is not None]
    if len(scores) < 3:
        return fallback
    return score_to_cefr(sum(scores) / len(scores), fallback)
