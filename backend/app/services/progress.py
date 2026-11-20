"""Keeps lesson_progress (per learner, per curriculum item) in step with the learner's real activity,
records study time and the last opened activity, and raises milestone notifications."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import content
from ..models import Profile
from ..models_platform import LessonProgress, StudyTime

MILESTONES = (1, 10, 25, 50, 100, 200, 400)


def _items():
    """Yield (level_or_business, curriculum_item) for every curriculum entry."""
    cur = content.curriculum()
    for lv in cur["levels"]:
        for u in lv["units"]:
            for it in u["items"]:
                yield lv["code"], it
    for c in cur["business"]:
        for it in c["items"]:
            yield "business", it


def _matches(it: dict, kind: str | None, ref: str | None) -> bool:
    if kind is None:
        return True
    if kind == "vocab":
        return it["kind"] == "vocab"
    if kind == "conversation":
        return it["kind"] == "conversation" and it["ref"] == ref
    return it["kind"] == kind and str(it["ref"]) == str(ref)


def sync(db: Session, p: Profile, kind: str | None = None, ref: str | None = None) -> None:
    """Recompute matching items (all items when kind is None) and upsert their progress rows."""
    from ..routers.academy import Facts, resolve

    f = Facts(db, p.id)
    rows = {r.item_key: r for r in db.scalars(select(LessonProgress).where(LessonProgress.profile_id == p.id))}
    newly_completed = 0
    for level, it in _items():
        if not _matches(it, kind, ref):
            continue
        r = resolve(it, f)
        if not r["available"]:
            continue
        started = r["done"] or r["score"] is not None
        row = rows.get(r["key"])
        if not started and not row:
            continue
        if row is None:
            row = LessonProgress(profile_id=p.id, item_key=r["key"][:80], kind=r["kind"], level=level)
            db.add(row)
            rows[r["key"]] = row
        row.title, row.route, row.score, row.updated_at = (r["title"] or "")[:200], r["route"], r["score"], datetime.utcnow()
        if r["done"] and row.status != "completed":
            row.status, row.completed_at = "completed", datetime.utcnow()
            newly_completed += 1
        elif not r["done"] and row.status != "completed":
            row.status = "in_progress"
    db.flush()
    if newly_completed and p.user_id:
        total = db.scalar(select(func.count()).select_from(LessonProgress)
                          .where(LessonProgress.profile_id == p.id, LessonProgress.status == "completed")) or 0
        for m in MILESTONES:
            if total - newly_completed < m <= total:
                from . import platform

                platform.notify(db, p.user_id, "milestone", f"Milestone: {m} activit{'y' if m == 1 else 'ies'} completed 🎉",
                                "Keep going — every activity brings you closer to the next level.", "/")


def visit(db: Session, p: Profile, route: str, title: str) -> None:
    p.last_route, p.last_title, p.last_at = route[:300], title[:200], datetime.utcnow()
    from ..routers.academy import Facts, resolve

    f = None
    for level, it in _items():
        if it["kind"] in ("soon",):
            continue
        f = f or Facts(db, p.id)
        r = resolve(it, f)
        if r["route"] and r["route"].split("&task=")[0] == route.split("&task=")[0]:
            row = db.scalar(select(LessonProgress).where(LessonProgress.profile_id == p.id, LessonProgress.item_key == r["key"]))
            if row is None:
                db.add(LessonProgress(profile_id=p.id, item_key=r["key"][:80], kind=r["kind"], level=level, title=(r["title"] or "")[:200],
                                      route=r["route"], status="completed" if r["done"] else "in_progress", score=r["score"]))
            else:
                row.updated_at = datetime.utcnow()
            break


def add_study_time(db: Session, p: Profile, seconds: int) -> None:
    day = datetime.utcnow().strftime("%Y-%m-%d")
    row = db.scalar(select(StudyTime).where(StudyTime.profile_id == p.id, StudyTime.day == day))
    if row is None:
        row = StudyTime(profile_id=p.id, day=day, seconds=0)
        db.add(row)
    row.seconds = (row.seconds or 0) + max(0, min(seconds, 120))


def study_seconds(db: Session, profile_id: int, since_day: str | None = None) -> int:
    q = select(func.coalesce(func.sum(StudyTime.seconds), 0)).where(StudyTime.profile_id == profile_id)
    if since_day:
        q = q.where(StudyTime.day >= since_day)
    return int(db.scalar(q) or 0)


def after(db: Session, p: Profile, kind: str, ref: str | None = None) -> None:
    """Best-effort progress refresh after an activity was saved; never breaks the learner's request."""
    import logging

    try:
        sync(db, p, kind, ref)
        db.commit()
    except Exception:  # pragma: no cover
        db.rollback()
        logging.getLogger(__name__).exception("progress sync failed")
