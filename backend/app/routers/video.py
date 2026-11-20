"""Video Academy: the learner's own videos (local files or YouTube embeds) with synced subtitles.

Legal by design: the app never downloads or redistributes third-party media.
Local files are the learner's own; YouTube videos play through YouTube's official embed player.
"""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_profile, provider_errors
from ..models import ActivityLog, Profile, VideoItem
from ..providers.llm import ChatMessage, get_llm
from ..services import subtitles

router = APIRouter(prefix="/api/video", tags=["video"])

VIDEO_EXT = {".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm"}
MAX_VIDEO = 4 * 1024**3
YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def video_dir() -> Path:
    d = settings.data_dir / "videos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(db, p, vid) -> VideoItem:
    v = db.get(VideoItem, vid)
    if not v or v.profile_id != p.id:
        raise HTTPException(404, "Video not found")
    return v


def _out(v: VideoItem, full=False) -> dict:
    d = {"id": v.id, "title": v.title, "level": v.level, "source": v.source, "youtube_id": v.youtube_id,
         "has_subtitles": bool(v.cues), "timed": bool(v.cues and v.cues[0]["start"] is not None),
         "has_study": v.study is not None, "created_at": v.created_at.isoformat()}
    if full:
        d |= {"cues": v.cues or [], "study": v.study}
    return d


def _read_subs(upload: UploadFile | None, transcript: str | None) -> list[dict] | None:
    if upload is not None and upload.filename:
        raw = upload.file.read(5 * 1024 * 1024)
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        cues = subtitles.parse(text)
        if not cues:
            raise HTTPException(422, "Could not read any subtitles from that file (.srt or .vtt expected).")
        return cues
    if transcript and transcript.strip():
        return subtitles.parse(transcript)
    return None


@router.get("/items")
def items(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    rows = db.scalars(select(VideoItem).where(VideoItem.profile_id == p.id).order_by(VideoItem.id.desc())).all()
    return [_out(v) for v in rows]


@router.post("/items")
def add(
    title: str = Form(..., min_length=1, max_length=200),
    level: str = Form("C1", pattern=r"^(A1|A2|B1|B2|C1|C2)$"),
    youtube_url: str = Form(""),
    transcript: str = Form("", max_length=200000),
    video: UploadFile | None = File(None),
    subtitles_file: UploadFile | None = File(None),
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    v = VideoItem(profile_id=p.id, title=title.strip(), level=level)
    if youtube_url.strip():
        m = YT.search(youtube_url)
        if not m:
            raise HTTPException(422, "That doesn't look like a YouTube video link.")
        v.source, v.youtube_id = "youtube", m.group(1)
    elif video is not None and video.filename:
        if settings.mode == "server":
            raise HTTPException(422, "In the online academy, add videos with a YouTube link (uploaded files can't be stored for each learner).")
        ext = Path(video.filename).suffix.lower()
        if ext not in VIDEO_EXT:
            raise HTTPException(415, "Use an .mp4, .m4v or .webm video (these play in the app).")
        name = f"{uuid.uuid4().hex}{ext}"
        dest = video_dir() / name
        size = 0
        with dest.open("wb") as f:
            while chunk := video.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO:
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, "Video larger than 4 GB")
                f.write(chunk)
        v.source, v.filename = "file", name
    else:
        raise HTTPException(422, "Add a video file or a YouTube link.")
    v.cues = _read_subs(subtitles_file, transcript)
    db.add(v)
    db.commit()
    return _out(v, full=True)


@router.get("/items/{vid}")
def get_item(vid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    return _out(_get(db, p, vid), full=True)


@router.get("/items/{vid}/file")
def file(vid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    v = _get(db, p, vid)
    if v.source != "file" or not v.filename:
        raise HTTPException(404, "No local file for this video")
    path = video_dir() / v.filename
    if not path.exists():
        raise HTTPException(410, "The video file is missing from the library folder.")
    return FileResponse(path, media_type=VIDEO_EXT[path.suffix])


@router.post("/items/{vid}/subtitles")
def set_subs(vid: int, transcript: str = Form("", max_length=200000), subtitles_file: UploadFile | None = File(None),
             p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    v = _get(db, p, vid)
    cues = _read_subs(subtitles_file, transcript)
    if not cues:
        raise HTTPException(422, "Provide a subtitle file or a transcript.")
    v.cues, v.study = cues, None
    db.commit()
    return _out(v, full=True)


@router.delete("/items/{vid}")
def delete(vid: int, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    v = _get(db, p, vid)
    if v.filename:
        (video_dir() / v.filename).unlink(missing_ok=True)
    db.delete(v)
    db.commit()
    return {"deleted": True}


STUDY_PROMPT = """You are an expert English teacher preparing a study pack from a video transcript for a \
French-speaking learner at about {level}. Return strict JSON:
{{"summary": str,
  "vocabulary": [{{"word": str, "meaning": str, "example": str, "french": str|null}}],
  "idioms": [{{"phrase": str, "meaning": str}}],
  "grammar": [{{"point": str, "example_from_video": str, "explanation": str}}],
  "questions": [{{"prompt": str, "options": [str, str, str, str], "answer": str, "explanation": str}}],
  "pronunciation_focus": [{{"phrase": str, "tip": str}}],
  "summary_task": str}}
8-12 vocabulary items at or above the level, all idioms/phrasal verbs actually used, 2-4 grammar points \
quoting the transcript, 5 comprehension questions (answer must be one of the options), 3 pronunciation tips \
on connected speech in phrases from the video. Use only what is in the transcript."""


@router.post("/items/{vid}/study")
@provider_errors
def study(vid: int, refresh: bool = False, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    v = _get(db, p, vid)
    if not v.cues:
        raise HTTPException(409, "Add subtitles or a transcript first: the study pack is built from them.")
    if v.study and not refresh:
        return v.study
    text = subtitles.transcript(v.cues)[:24000]
    pack = get_llm().chat_json([ChatMessage("system", STUDY_PROMPT.format(level=v.level)),
                                ChatMessage("user", f"Title: {v.title}\nTranscript:\n{text}")], max_tokens=3500)
    pack["questions"] = [q for q in pack.get("questions", []) if q.get("answer") in q.get("options", [])]
    v.study = pack
    db.commit()
    return pack


class ProgressIn(BaseModel):
    seconds: int = Field(ge=0, le=36000)
    score: float | None = Field(None, ge=0, le=1)
    item: str = Field("watch", max_length=40)


@router.post("/items/{vid}/progress")
def progress(vid: int, body: ProgressIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    _get(db, p, vid)
    db.add(ActivityLog(profile_id=p.id, skill="listening", item_id=f"video:{vid}:{body.item}",
                       score=body.score if body.score is not None else 0.7, seconds=body.seconds))
    db.commit()
    return {"ok": True}
