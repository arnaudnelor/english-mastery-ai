"""Academy media (audio, video, documents added by administrators) for learners."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from .. import content
from ..db import get_db
from ..deps import current_profile
from ..models import ActivityLog, Profile
from ..models_platform import MediaAsset
from ..services import progress

router = APIRouter(prefix="/api/media", tags=["media"])


def _get(db: Session, mid: int) -> MediaAsset:
    m = db.get(MediaAsset, mid)
    if not m or not m.published:
        raise HTTPException(404, "Not found")
    return m


@router.get("")
def list_media(level: str = "", p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    stmt = select(MediaAsset).where(MediaAsset.published.is_(True))
    if level:
        stmt = stmt.where(MediaAsset.level == level)
    return [{"id": m.id, "title": m.title, "kind": m.kind, "level": m.level, "category": m.category, "description": m.description}
            for m in db.scalars(stmt.order_by(MediaAsset.id.desc()))]


@router.get("/{mid}")
def get_media(mid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    m = _get(db, mid)
    return {"id": m.id, "title": m.title, "kind": m.kind, "level": m.level, "description": m.description, "mime": m.mime,
            "has_file": m.size > 0, "youtube_id": m.youtube_id, "external_url": m.external_url, "cues": m.subtitles or [],
            "transcript": m.transcript or "", "questions": [{k: q[k] for k in ("id", "prompt", "options")} for q in (m.questions or [])]}


@router.get("/{mid}/file")
def media_file(mid: int, request: Request, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    m = db.scalar(select(MediaAsset).options(undefer(MediaAsset.data)).where(MediaAsset.id == mid))
    if not m or not m.published or not m.data:
        raise HTTPException(404, "No file")
    data = m.data
    rng = request.headers.get("range", "")
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}
    if rng.startswith("bytes="):  # seeking in audio/video players
        a, _, b = rng[6:].partition("-")
        start = int(a or 0)
        end = min(int(b) if b else len(data) - 1, len(data) - 1)
        if start > end:
            raise HTTPException(416, "Bad range")
        headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        return Response(data[start:end + 1], status_code=206, media_type=m.mime, headers=headers)
    return Response(data, media_type=m.mime, headers=headers)


class AnswersIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


@router.post("/{mid}/complete")
def complete(mid: int, body: AnswersIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    """Watched/listened: grade the comprehension questions (if any) and record the activity."""
    m = _get(db, mid)
    review = []
    for q in m.questions or []:
        ok = content.normalise(body.answers.get(q["id"], "")) == content.normalise(q["answer"])
        review.append({"id": q["id"], "correct": ok, "answer": q["answer"], "explanation": q.get("explanation", "")})
    score = sum(r["correct"] for r in review) / len(review) if review else 1.0
    db.add(ActivityLog(profile_id=p.id, skill="listening", item_id=f"media:{m.id}", score=score, seconds=60))
    db.commit()
    progress.after(db, p, "media", str(m.id))
    return {"score": round(score, 3), "review": review}
