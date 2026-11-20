"""Learner statistics, exports (CSV / Excel / PDF), personal data export and deletion."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..models import (ActivityLog, AssessmentResult, Bookmark, Conversation, ExamAttempt, Message, Mistake, Profile,
                      VideoItem, VocabCard)
from ..models_platform import (AccountToken, AuditLog, AuthSession, Enrolment, LessonProgress, Notification, StudyTime, User)
from . import learning

LEVEL_NAMES = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate", "C1": "Advanced", "C2": "Proficiency"}


# ------------------------------------------------------------------ per-learner statistics
def profile_of(db: Session, u: User) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == u.id))


def study_hours(db: Session, profile_id: int) -> float:
    secs = db.scalar(select(func.coalesce(func.sum(StudyTime.seconds), 0)).where(StudyTime.profile_id == profile_id)) or 0
    if not secs:  # before heartbeats existed: time spent on recorded activities
        secs = db.scalar(select(func.coalesce(func.sum(ActivityLog.seconds), 0)).where(ActivityLog.profile_id == profile_id)) or 0
    return round(secs / 3600, 2)


def learner_stats(db: Session, u: User) -> dict:
    p = profile_of(db, u)
    base = {"user_id": u.id, "name": f"{u.first_name} {u.last_name}", "email": u.email, "country": u.country, "status": u.status,
            "role": u.role, "email_verified": u.email_verified_at is not None, "registered": u.created_at.isoformat(),
            "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
            "last_seen": u.last_seen_at.isoformat() if u.last_seen_at else None}
    if not p:
        return base | {"level": None, "completed": 0, "in_progress": 0, "hours": 0.0, "placement_done": False, "skills": {}, "average": None}
    completed = db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.profile_id == p.id, LessonProgress.status == "completed")) or 0
    in_prog = db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.profile_id == p.id, LessonProgress.status == "in_progress")) or 0
    skills = learning.skill_scores(db, p.id, 3650)
    vals = [v for v in skills.values() if v is not None]
    confirmed = bool(p.level_confirmed) or p.placement_done_at is not None
    return base | {"profile_id": p.id, "level": p.estimated_level if confirmed else None, "placement_done": p.placement_done_at is not None,
                   "completed": completed, "in_progress": in_prog, "hours": study_hours(db, p.id), "skills": skills,
                   "average": round(sum(vals) / len(vals), 3) if vals else None,
                   "business_progress": db.scalar(select(func.count()).select_from(LessonProgress).where(
                       LessonProgress.profile_id == p.id, LessonProgress.level == "business", LessonProgress.status == "completed")) or 0}


def learner_detail(db: Session, u: User) -> dict:
    d = learner_stats(db, u)
    p = profile_of(db, u)
    d |= {"first_name": u.first_name, "last_name": u.last_name, "preferred_language": u.preferred_language, "objectives": u.objectives or []}
    if not p:
        return d | {"assessments": [], "recent": [], "weaknesses": [], "weekly": [], "lessons": []}
    tests = db.scalars(select(AssessmentResult).where(AssessmentResult.profile_id == p.id).order_by(AssessmentResult.id.desc())).all()
    recent = db.scalars(select(ActivityLog).where(ActivityLog.profile_id == p.id).order_by(ActivityLog.id.desc()).limit(30)).all()
    lessons = db.scalars(select(LessonProgress).where(LessonProgress.profile_id == p.id).order_by(LessonProgress.updated_at.desc())).all()
    weekly = []
    now = datetime.utcnow()
    for k in range(11, -1, -1):
        start = (now - timedelta(days=now.weekday(), weeks=k)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        rows = db.execute(select(func.count(ActivityLog.id), func.avg(ActivityLog.score))
                          .where(ActivityLog.profile_id == p.id, ActivityLog.created_at >= start, ActivityLog.created_at < end)).one()
        secs = db.scalar(select(func.coalesce(func.sum(StudyTime.seconds), 0)).where(
            StudyTime.profile_id == p.id, StudyTime.day >= start.strftime("%Y-%m-%d"), StudyTime.day < end.strftime("%Y-%m-%d"))) or 0
        weekly.append({"week": start.strftime("%Y-%m-%d"), "activities": rows[0], "average": round(float(rows[1]), 3) if rows[1] is not None else None,
                       "minutes": int(secs) // 60})
    return d | {
        "target_level": p.target_level,
        "assessments": [{"kind": t.kind, "level": t.level, "score": round(t.score, 3), "passed": bool(t.passed), "details": t.details,
                         "date": t.created_at.isoformat()} for t in tests],
        "recent": [{"skill": a.skill, "item": a.item_id, "score": round(a.score, 2), "date": a.created_at.isoformat()} for a in recent],
        "weaknesses": learning.top_weaknesses(db, p.id, 8),
        "weekly": weekly,
        "lessons": [{"title": r.title, "kind": r.kind, "level": r.level, "status": r.status, "score": r.score,
                     "date": (r.completed_at or r.updated_at).isoformat()} for r in lessons[:100]],
        "vocabulary": learning.vocab_stats(db, p.id),
        "streak": learning.streak(db, p.id),
    }


# ------------------------------------------------------------------ table export
def export_table(title: str, columns: list[str], rows: list[list], fmt: str) -> tuple[bytes, str, str]:
    """Returns (bytes, media_type, extension)."""
    safe = [["" if v is None else v for v in r] for r in rows]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(columns)
        for r in safe:
            w.writerow([_csv_safe(v) for v in r])
        return ("﻿" + buf.getvalue()).encode("utf-8"), "text/csv; charset=utf-8", "csv"
    if fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = title[:31] or "Report"
        ws.append(columns)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in safe:
            ws.append([_csv_safe(v) if isinstance(v, str) else v for v in r])
        for i, col in enumerate(columns, 1):
            width = max([len(str(col))] + [len(str(r[i - 1])) for r in safe[:200]]) + 2
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(50, width)
        ws.freeze_panes = "A2"
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    if fmt == "pdf":
        return _pdf(title, [(None, columns, safe)]), "application/pdf", "pdf"
    raise ValueError("format must be csv, xlsx or pdf")


def _csv_safe(v):
    """Prevent spreadsheet formula injection from learner-entered text."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _pdf(title: str, sections: list[tuple[str | None, list[str], list[list]]], intro: list[str] | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    wide = any(len(cols) > 6 for _, cols, _ in sections)
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4) if wide else A4, title=title, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    ss = getSampleStyleSheet()
    cell = ss["BodyText"].clone("cell", fontSize=8, leading=10)
    story = [Paragraph(title, ss["Title"]), Paragraph(f"Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC · English Mastery AI", ss["Italic"]), Spacer(1, 10)]
    for line in intro or []:
        story.append(Paragraph(line, ss["BodyText"]))
    for heading, cols, rows in sections:
        if heading:
            story += [Spacer(1, 8), Paragraph(heading, ss["Heading2"])]
        if not rows:
            story.append(Paragraph("No records.", ss["BodyText"]))
            continue
        data = [[Paragraph(f"<b>{_esc(c)}</b>", cell) for c in cols]] + [[Paragraph(_esc(str(v)), cell) for v in r] for r in rows[:2000]]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c7cfdd")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    doc.build(story)
    return out.getvalue()


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def learner_report_pdf(db: Session, u: User) -> bytes:
    d = learner_detail(db, u)
    lvl = d.get("level")
    intro = [f"<b>{_esc(d['name'])}</b> · {_esc(d['email'])}",
             f"Current level: <b>{lvl + ' — ' + LEVEL_NAMES[lvl] if lvl else 'not placed yet'}</b> · Study time: {d['hours']} h · "
             f"Completed activities: {d['completed']} · Streak: {d.get('streak', 0)} days"]
    skills = [[k.capitalize(), f"{round(v * 100)}%" if v is not None else "—"] for k, v in (d.get("skills") or {}).items()]
    tests = [[t["date"][:10], {"placement": "Placement test", "level_test": "Level test", "business": "Business assessment"}.get(t["kind"], t["kind"]),
              t["level"], f"{round(t['score'] * 100)}%", "yes" if t["passed"] else "no"] for t in d.get("assessments", [])]
    lessons = [[r["date"][:10], r["title"], r["level"] or "", r["status"].replace("_", " "), f"{round(r['score'] * 100)}%" if r["score"] is not None else ""]
               for r in d.get("lessons", [])]
    weak = [[w["category"], w["pattern"], w["count"]] for w in d.get("weaknesses", [])]
    return _pdf("Progress report", [("Skills (all time)", ["Skill", "Average score"], skills),
                                    ("Assessments", ["Date", "Assessment", "Level", "Score", "Passed"], tests),
                                    ("Lessons and activities", ["Date", "Activity", "Level", "Status", "Score"], lessons),
                                    ("Recurring mistakes", ["Type", "Pattern", "Times"], weak)], intro)


# ------------------------------------------------------------------ privacy
def learner_data_export(db: Session, u: User) -> dict:
    p = profile_of(db, u)
    out = {"account": {"email": u.email, "first_name": u.first_name, "last_name": u.last_name, "country": u.country,
                       "preferred_language": u.preferred_language, "objectives": u.objectives, "created_at": u.created_at.isoformat()}}
    if p:
        out["progress"] = learner_detail(db, u)
        out["conversations"] = [{"mode": c.mode, "started_at": c.started_at.isoformat(),
                                 "messages": [{"role": m.role, "content": m.content} for m in db.scalars(select(Message).where(Message.conversation_id == c.id))]}
                                for c in db.scalars(select(Conversation).where(Conversation.profile_id == p.id))]
        out["mistakes"] = [{"category": m.category, "original": m.original, "corrected": m.corrected, "date": m.created_at.isoformat()}
                           for m in db.scalars(select(Mistake).where(Mistake.profile_id == p.id))]
    return out


def delete_learner(db: Session, u: User) -> None:
    """Hard-delete a learner and all their learning records."""
    p = profile_of(db, u)
    if p:
        conv_ids = [c for c in db.scalars(select(Conversation.id).where(Conversation.profile_id == p.id))]
        if conv_ids:
            db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        for model in (Conversation, Mistake, VocabCard, ActivityLog, Bookmark, VideoItem, ExamAttempt, AssessmentResult, LessonProgress, StudyTime):
            db.execute(delete(model).where(model.profile_id == p.id))
        db.delete(p)
    db.execute(update(AuditLog).where(AuditLog.actor_user_id == u.id).values(actor_user_id=None))
    db.execute(update(AccountToken).where(AccountToken.created_by == u.id).values(created_by=None))
    for model in (AuthSession, AccountToken, Notification, Enrolment):
        db.execute(delete(model).where(model.user_id == u.id))
    db.delete(u)
