"""Learning path, analytics, search and bookmarks."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import current_profile
from ..models import ActivityLog, Bookmark, Conversation, ExamAttempt, Mistake, Profile, VideoItem
from ..services import learning
from ..services.conversation import MODES

router = APIRouter(prefix="/api", tags=["insights"])
ORDER = ["B1", "B2", "C1", "C2"]


def _done_map(db, pid) -> dict[str, float]:
    rows = db.execute(select(ActivityLog.item_id, ActivityLog.score).where(ActivityLog.profile_id == pid)).all()
    agg: dict[str, list[float]] = defaultdict(list)
    for item, score in rows:
        agg[item.split(":")[0]].append(score)
    return {k: sum(v) / len(v) for k, v in agg.items()}


@router.get("/path")
def path(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    done = _done_map(db, p.id)
    lo, hi = ORDER.index(p.estimated_level if p.estimated_level in ORDER else "B2"), ORDER.index(p.target_level)
    levels = ORDER[max(1, lo): max(lo, hi) + 1] or ["B2"]
    weak = Counter(m.pattern for m in db.scalars(select(Mistake).where(Mistake.profile_id == p.id)))
    units = []
    for lv in levels:
        for t in content.grammar_topics():
            if t["level"] == lv:
                units.append({"kind": "grammar", "id": t["id"], "title": t["title"], "level": lv, "route": f"/grammar/{t['id']}",
                              "done": done.get(t["id"], 0) >= 0.7, "priority": weak.get(t["title"], 0)})
        for t in content.reading_texts():
            if t["level"] == lv:
                units.append({"kind": "reading", "id": t["id"], "title": t["title"], "level": lv, "route": f"/reading/{t['id']}",
                              "done": t["id"] in done, "priority": 0})
        for it in content.listening_items():
            if it["level"] == lv:
                units.append({"kind": "listening", "id": it["id"], "title": it["title"], "level": lv, "route": f"/listening/{it['id']}",
                              "done": it["id"] in done, "priority": 0})
    # Recurring-mistake topics first, then by level; done items sink within their week
    units.sort(key=lambda u: (-min(u["priority"], 1), ORDER.index(u["level"])))
    speaking = ["business", "academic", "debate", "job_interview", "presentation", "negotiation", "finance", "ielts", "mba", "university"]
    weeks = []
    for i in range(0, len(units), 4):
        chunk = units[i:i + 4]
        mode = speaking[(i // 4) % len(speaking)]
        chunk.append({"kind": "speaking", "id": mode, "title": MODES[mode]["title"], "level": chunk[0]["level"],
                      "route": f"/conversation?mode={mode}", "done": False, "priority": 0})
        weeks.append({"week": i // 4 + 1, "units": chunk})
    total = sum(1 for u in units)
    completed = sum(1 for u in units if u["done"])
    return {"levels": levels, "weeks": weeks, "completed": completed, "total": total,
            "placement_done": p.placement_done_at is not None}


@router.get("/analytics")
def analytics(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    since = now - timedelta(weeks=12)
    acts = db.scalars(select(ActivityLog).where(ActivityLog.profile_id == p.id, ActivityLog.created_at >= since)).all()
    week_start = lambda d: (d - timedelta(days=d.weekday())).date()  # noqa: E731
    weeks = [week_start(now - timedelta(weeks=k)) for k in range(11, -1, -1)]
    minutes = defaultdict(int)
    skill_week: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    for a in acts:
        w = week_start(a.created_at)
        minutes[w] += a.seconds
        skill_week[a.skill][w].append(a.score)
    mistakes = db.scalars(select(Mistake).where(Mistake.profile_id == p.id)).all()
    by_cat = Counter(m.category for m in mistakes)
    mistakes_week = defaultdict(int)
    for m in mistakes:
        if m.created_at >= since:
            mistakes_week[week_start(m.created_at)] += 1
    recent = db.scalars(select(ActivityLog).where(ActivityLog.profile_id == p.id).order_by(ActivityLog.id.desc()).limit(40)).all()
    exams = db.scalars(select(ExamAttempt).where(ExamAttempt.profile_id == p.id, ExamAttempt.overall_band.is_not(None)).order_by(ExamAttempt.id)).all()
    total_secs = db.scalar(select(func.coalesce(func.sum(ActivityLog.seconds), 0)).where(ActivityLog.profile_id == p.id)) or 0
    n_acts = db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.profile_id == p.id)) or 0
    n_conv = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.profile_id == p.id)) or 0
    return {
        "weeks": [w.isoformat() for w in weeks],
        "minutes_per_week": [round(minutes[w] / 60) for w in weeks],
        "skills_per_week": {s: [round(sum(v[w]) / len(v[w]), 3) if v[w] else None for w in weeks] for s, v in skill_week.items()},
        "mistakes_by_category": dict(by_cat),
        "mistakes_per_week": [mistakes_week[w] for w in weeks],
        "top_mistakes": learning.top_weaknesses(db, p.id, 10),
        "vocabulary": learning.vocab_stats(db, p.id),
        "exams": [{"date": e.started_at.date().isoformat(), "overall": e.overall_band, "bands": (e.results or {}).get("summary", {}).get("bands")} for e in exams],
        "totals": {"hours": round(total_secs / 3600, 1), "activities": n_acts, "conversations": n_conv, "streak": learning.streak(db, p.id)},
        "skills_now": learning.skill_scores(db, p.id),
        "estimated_cefr": learning.estimated_level(db, p.id, p.estimated_level),
        "history": [{"when": a.created_at.isoformat(), "skill": a.skill, "item": a.item_id, "score": round(a.score, 2), "minutes": round(a.seconds / 60, 1)} for a in recent],
    }


@router.get("/search")
def search(q: str, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    q = q.strip().lower()
    if len(q) < 2:
        return []
    hits = []
    has = lambda *parts: q in " ".join(x for x in parts if x).lower()  # noqa: E731
    for t in content.grammar_topics():
        if has(t["title"], t["summary"], t["unit"], t["explanation"]):
            hits.append({"kind": "Grammar", "title": t["title"], "level": t["level"], "route": f"/grammar/{t['id']}"})
    for w in content.vocabulary():
        if has(w["word"], w["definition"], w["french"]):
            hits.append({"kind": "Vocabulary", "title": f"{w['word']}: {w['definition']}", "level": w["level"], "route": f"/vocabulary?domain={w['domain']}"})
    for t in content.reading_texts():
        if has(t["title"], t["genre"], t["body"]):
            hits.append({"kind": "Reading", "title": t["title"], "level": t["level"], "route": f"/reading/{t['id']}"})
    for it in content.listening_items():
        if has(it["title"], it["kind"], " ".join(ln["t"] for ln in it["lines"])):
            hits.append({"kind": "Listening", "title": it["title"], "level": it["level"], "route": f"/listening/{it['id']}"})
    for mid, m in MODES.items():
        if has(m["title"], m["brief"]):
            hits.append({"kind": "Conversation", "title": m["title"], "level": "", "route": f"/conversation?mode={mid}"})
    for v in db.scalars(select(VideoItem).where(VideoItem.profile_id == p.id)):
        if has(v.title, " ".join(c["text"] for c in (v.cues or []))):
            hits.append({"kind": "Video", "title": v.title, "level": v.level, "route": f"/video/{v.id}"})
    return hits[:40]


class BookmarkIn(BaseModel):
    kind: str = Field(max_length=20)
    item_id: str = Field(max_length=80)
    title: str = Field(max_length=200)
    route: str = Field(pattern=r"^/[A-Za-z0-9/_\-?=&%.]*$", max_length=200)


@router.get("/bookmarks")
def bookmarks(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    rows = db.scalars(select(Bookmark).where(Bookmark.profile_id == p.id).order_by(Bookmark.id.desc())).all()
    return [{"id": b.id, "kind": b.kind, "item_id": b.item_id, "title": b.title or b.item_id, "route": b.route or "/"} for b in rows]


@router.post("/bookmarks")
def add_bookmark(body: BookmarkIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    existing = db.scalar(select(Bookmark).where(Bookmark.profile_id == p.id, Bookmark.kind == body.kind, Bookmark.item_id == body.item_id))
    if existing:
        return {"id": existing.id}
    b = Bookmark(profile_id=p.id, **body.model_dump())
    db.add(b)
    db.commit()
    return {"id": b.id}


@router.delete("/bookmarks/{bid}")
def del_bookmark(bid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    b = db.get(Bookmark, bid)
    if not b or b.profile_id != p.id:
        raise HTTPException(404, "Bookmark not found")
    db.delete(b)
    db.commit()
    return {"deleted": True}


@router.get("/mistakes")
def mistakes(limit: int = 100, category: str | None = None, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    """Every recorded mistake, newest first, for review."""
    q = select(Mistake).where(Mistake.profile_id == p.id)
    if category:
        q = q.where(Mistake.category == category)
    rows = db.scalars(q.order_by(Mistake.id.desc()).limit(max(1, min(limit, 500)))).all()
    return [{"when": m.created_at.isoformat(), "category": m.category, "pattern": m.pattern, "original": m.original,
             "corrected": m.corrected, "explanation": m.explanation, "source": m.source} for m in rows]
