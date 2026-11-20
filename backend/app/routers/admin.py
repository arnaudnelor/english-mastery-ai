"""Administrator portal API. Every endpoint checks a permission; the auth middleware already
restricts /api/admin/* to administrator roles. All figures come from database records."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from .. import content
from ..config import get_secret, settings
from ..db import get_db
from ..deps import require
from ..models import ActivityLog, AssessmentResult, Profile
from ..models_platform import (AuditLog, AuthSession, Classroom, ContentDocument, ContentLesson, EmailOutbox, Invoice,
                               LearnerGroup, LessonProgress, MediaAsset, Organization, Payment, Permission, Role,
                               RolePermission, StudyTime, Subscription, SubscriptionPlan, TeacherProfile, User)
from ..services import mailer, platform, reports
from .auth import client_ip, reset_link_for, user_out

router = APIRouter(prefix="/api/admin", tags=["admin"])
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def _learners(db: Session):
    return select(User).where(User.role == "learner")


# ------------------------------------------------------------------ overview
@router.get("/overview")
def overview(u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    inactive_days = int(platform.get_setting(db, "inactive_after_days") or 14)
    learners = db.scalars(_learners(db)).all()
    ids = [x.id for x in learners]
    active = [x for x in learners if x.last_seen_at and x.last_seen_at >= _since(inactive_days)]
    profiles = {p.user_id: p for p in db.scalars(select(Profile).where(Profile.user_id.in_(ids)))} if ids else {}
    pids = [p.id for p in profiles.values()]
    dist = Counter((p.estimated_level if (p.level_confirmed or p.placement_done_at) else "Not placed") for p in profiles.values())
    completed = db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.profile_id.in_(pids), LessonProgress.status == "completed")) if pids else 0
    secs = db.scalar(select(func.coalesce(func.sum(StudyTime.seconds), 0)).where(StudyTime.profile_id.in_(pids))) if pids else 0
    avg = db.scalar(select(func.avg(ActivityLog.score)).where(ActivityLog.profile_id.in_(pids), ActivityLog.created_at >= _since(30))) if pids else None
    biz = db.scalar(select(func.count(func.distinct(LessonProgress.profile_id))).where(LessonProgress.profile_id.in_(pids), LessonProgress.level == "business")) if pids else 0
    placements = db.scalars(select(AssessmentResult).where(AssessmentResult.kind == "placement", AssessmentResult.profile_id.in_(pids))).all() if pids else []
    recent = db.execute(select(ActivityLog, Profile).join(Profile, Profile.id == ActivityLog.profile_id)
                        .where(Profile.user_id.in_(ids)).order_by(ActivityLog.id.desc()).limit(15)).all() if ids else []
    return {
        "learners": {"total": len(learners), "active": len(active), "inactive": len(learners) - len(active),
                     "new_7d": sum(1 for x in learners if x.created_at >= _since(7)), "new_30d": sum(1 for x in learners if x.created_at >= _since(30)),
                     "suspended": sum(1 for x in learners if x.status == "suspended"), "unverified": sum(1 for x in learners if not x.email_verified_at)},
        "lessons_completed": completed or 0, "learning_hours": round((secs or 0) / 3600, 1),
        "average_performance_30d": round(float(avg), 3) if avg is not None else None,
        "cefr_distribution": {lv: dist.get(lv, 0) for lv in LEVELS + ["Not placed"]},
        "business_enrolments": biz or 0,
        "placement": {"taken": len(placements), "learners_placed": len({r.profile_id for r in placements}),
                      "distribution": dict(Counter(r.level for r in placements))},
        "recent": [{"learner": p.name, "user_id": p.user_id, "skill": a.skill, "item": a.item_id, "score": round(a.score, 2),
                    "date": a.created_at.isoformat()} for a, p in recent],
        "attention": attention(db, learners, profiles, inactive_days),
        "inactive_after_days": inactive_days,
        "email_enabled": mailer.configured(),
        "ai_enabled": any(get_secret(k) for k in ("gemini", "openai", "anthropic")),
    }


def attention(db: Session, learners, profiles, inactive_days: int) -> list[dict]:
    out = []
    for x in learners:
        if x.status != "active":
            continue
        p = profiles.get(x.id)
        reasons = []
        if not x.last_seen_at or x.last_seen_at < _since(inactive_days):
            reasons.append(f"No activity for {inactive_days}+ days")
        if p and not (p.placement_done_at or p.level_confirmed) and x.created_at < _since(3):
            reasons.append("Registered 3+ days ago without taking the placement test")
        if p:
            fails = db.scalars(select(AssessmentResult).where(AssessmentResult.profile_id == p.id, AssessmentResult.kind == "level_test")
                               .order_by(AssessmentResult.id.desc()).limit(2)).all()
            if len(fails) == 2 and not any(f.passed for f in fails):
                reasons.append(f"Failed the {fails[0].level} level test twice in a row")
            avg = db.scalar(select(func.avg(ActivityLog.score)).where(ActivityLog.profile_id == p.id, ActivityLog.created_at >= _since(14)))
            n = db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.profile_id == p.id, ActivityLog.created_at >= _since(14)))
            if avg is not None and n >= 10 and avg < 0.5:
                reasons.append(f"Low recent accuracy ({round(avg * 100)}%)")
        if reasons:
            out.append({"user_id": x.id, "name": f"{x.first_name} {x.last_name}", "email": x.email, "reasons": reasons})
    return out[:50]


# ------------------------------------------------------------------ learners
@router.get("/learners")
def learners(q: str = "", level: str = "", status: str = "", role: str = "learner", page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200),
             u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    stmt = select(User)
    if role in ("learner", "admin", "super_admin", "teacher"):
        stmt = stmt.where(User.role == role)
    elif role == "staff":
        stmt = stmt.where(User.role.in_(["admin", "super_admin", "teacher"]))
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.first_name).like(like),
                              func.lower(User.last_name).like(like), func.lower(User.first_name + " " + User.last_name).like(like)))
    if status in ("active", "inactive", "suspended"):
        stmt = stmt.where(User.status == status)
    if level in LEVELS:
        stmt = stmt.join(Profile, Profile.user_id == User.id).where(Profile.estimated_level == level,
                                                                    or_(Profile.level_confirmed == 1, Profile.placement_done_at.is_not(None)))
    elif level == "none":
        stmt = stmt.join(Profile, Profile.user_id == User.id).where(Profile.level_confirmed == 0, Profile.placement_done_at.is_(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": [reports.learner_stats(db, x) for x in rows]}


def _user(db: Session, uid: int) -> User:
    x = db.get(User, uid)
    if not x:
        raise HTTPException(404, "User not found")
    return x


@router.get("/learners/{uid}")
def learner(uid: int, u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    x = _user(db, uid)
    return reports.learner_detail(db, x) | {"sessions": db.scalar(select(func.count()).select_from(AuthSession).where(
        AuthSession.user_id == x.id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.utcnow()))}


class StatusIn(BaseModel):
    status: str = Field(pattern=r"^(active|inactive|suspended)$")
    reason: str = Field("", max_length=300)


def _guard_target(actor: User, target: User):
    if target.id == actor.id:
        raise HTTPException(400, "You can't change your own account here.")
    if target.role == "super_admin" and actor.role != "super_admin":
        raise HTTPException(403, "Only a Super Administrator can change another Super Administrator.")


@router.post("/learners/{uid}/status")
def set_status(uid: int, body: StatusIn, request: Request, u: User = Depends(require("learners.manage")), db: Session = Depends(get_db)):
    x = _user(db, uid)
    _guard_target(u, x)
    old, x.status = x.status, body.status
    if body.status != "active":  # sign the account out everywhere
        db.query(AuthSession).filter(AuthSession.user_id == x.id, AuthSession.revoked_at.is_(None)).update({"revoked_at": datetime.utcnow()})
    platform.audit(db, u.id, f"learner.{body.status}", "user", x.id, {"from": old, "reason": body.reason}, client_ip(request))
    db.commit()
    return reports.learner_stats(db, x)


@router.post("/learners/{uid}/verify")
def verify(uid: int, request: Request, u: User = Depends(require("learners.manage")), db: Session = Depends(get_db)):
    x = _user(db, uid)
    x.email_verified_at = x.email_verified_at or datetime.utcnow()
    platform.audit(db, u.id, "learner.email_verified_manually", "user", x.id, ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.post("/learners/{uid}/reset-link")
def reset_link(uid: int, request: Request, u: User = Depends(require("learners.manage")), db: Session = Depends(get_db)):
    """Secure, single-use reset link (valid 72 h). Emailed when email is configured; always shown to the admin to pass on."""
    x = _user(db, uid)
    _guard_target(u, x)
    link = reset_link_for(db, x, created_by=u.id)
    sent = mailer.send_email(db, x.email, "Reset your password — English Mastery AI",
                             f"Hello {x.first_name},\n\nAn administrator started a password reset for your account. Choose a new password here "
                             f"(valid 72 hours):\n{link}", "admin_reset")
    platform.audit(db, u.id, "learner.reset_link", "user", x.id, {"emailed": sent}, client_ip(request))
    db.commit()
    return {"link": link, "emailed": sent, "expires_hours": 72}


class RoleIn(BaseModel):
    role: str = Field(pattern=r"^(learner|admin|super_admin)$")


@router.post("/learners/{uid}/role")
def set_role(uid: int, body: RoleIn, request: Request, u: User = Depends(require("users.roles")), db: Session = Depends(get_db)):
    x = _user(db, uid)
    _guard_target(u, x)
    if body.role == "super_admin" and u.role != "super_admin":
        raise HTTPException(403, "Only a Super Administrator can create another one.")
    old, x.role = x.role, body.role
    platform.audit(db, u.id, "user.role_changed", "user", x.id, {"from": old, "to": body.role}, client_ip(request))
    db.commit()
    return reports.learner_stats(db, x)


class InviteIn(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    role: str = Field(pattern=r"^(admin|super_admin)$")


@router.post("/staff")
def invite_staff(body: InviteIn, request: Request, u: User = Depends(require("users.roles")), db: Session = Depends(get_db)):
    """Create an administrator account; the new admin sets their own password through a single-use link."""
    from ..services import security

    if body.role == "super_admin" and u.role != "super_admin":
        raise HTTPException(403, "Only a Super Administrator can create another one.")
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "This email already has an account. Change its role from the learner page instead.")
    x = User(email=email, password_hash=security.hash_password(security.new_token()), first_name=body.first_name, last_name=body.last_name,
             role=body.role, email_verified_at=datetime.utcnow())
    db.add(x)
    db.flush()
    link = reset_link_for(db, x, created_by=u.id)
    sent = mailer.send_email(db, x.email, "You've been invited to administer English Mastery AI",
                             f"Hello {x.first_name},\n\nChoose your password to activate your administrator account (valid 72 hours):\n{link}", "admin_invite")
    platform.audit(db, u.id, "staff.invited", "user", x.id, {"role": body.role, "emailed": sent}, client_ip(request))
    db.commit()
    return {"user_id": x.id, "link": link, "emailed": sent}


@router.get("/learners/{uid}/report.pdf")
def learner_pdf(uid: int, request: Request, u: User = Depends(require("learners.export")), db: Session = Depends(get_db)):
    x = _user(db, uid)
    platform.audit(db, u.id, "report.learner_pdf", "user", x.id, ip=client_ip(request))
    db.commit()
    return Response(reports.learner_report_pdf(db, x), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="learner-{x.id}-report.pdf"'})


# ------------------------------------------------------------------ reports
REPORTS = {
    "learners": "Learner list", "usage_weekly": "Weekly platform usage", "usage_monthly": "Monthly platform usage",
    "completion": "Course completion", "cefr": "CEFR distribution", "assessments": "Assessment results",
}


def _date(s: str, default: datetime) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d") if s else default
    except ValueError:
        raise HTTPException(422, "Dates must be YYYY-MM-DD")


@router.get("/reports")
def report_list(u: User = Depends(require("reports.view"))):
    return REPORTS


@router.get("/reports/{kind}")
def report(kind: str, request: Request, format: str = Query("json", pattern=r"^(json|csv|xlsx|pdf)$"), date_from: str = "", date_to: str = "",
           level: str = "", course: str = "", learner: int | None = None,
           u: User = Depends(require("reports.view")), db: Session = Depends(get_db)):
    if kind not in REPORTS:
        raise HTTPException(404, "Unknown report")
    d0, d1 = _date(date_from, datetime(2000, 1, 1)), _date(date_to, datetime.utcnow()) + timedelta(days=1)
    users = db.scalars(_learners(db)).all()
    if learner:
        users = [x for x in users if x.id == learner]
    profiles = {p.user_id: p for p in db.scalars(select(Profile).where(Profile.user_id.in_([x.id for x in users])))} if users else {}
    if level in LEVELS:
        users = [x for x in users if profiles.get(x.id) and profiles[x.id].estimated_level == level]
    pids = {profiles[x.id].id: x for x in users if x.id in profiles}
    if kind == "learners":
        cols = ["Name", "Email", "Country", "Status", "Level", "Registered", "Last login", "Completed", "Hours", "Average"]
        rows = []
        for x in users:
            s = reports.learner_stats(db, x)
            if not (d0 <= x.created_at < d1):
                continue
            rows.append([s["name"], s["email"], s["country"], s["status"], s["level"] or "Not placed", s["registered"][:10],
                         (s["last_login"] or "")[:10], s["completed"], s["hours"], f"{round(s['average'] * 100)}%" if s["average"] is not None else ""])
    elif kind in ("usage_weekly", "usage_monthly"):
        buckets: dict[str, dict] = {}
        acts = db.scalars(select(ActivityLog).where(ActivityLog.profile_id.in_(pids.keys()), ActivityLog.created_at >= d0, ActivityLog.created_at < d1)).all() if pids else []
        for a in acts:
            k = (a.created_at - timedelta(days=a.created_at.weekday())).strftime("%Y-%m-%d") if kind == "usage_weekly" else a.created_at.strftime("%Y-%m")
            b = buckets.setdefault(k, {"acts": 0, "learners": set(), "scores": []})
            b["acts"] += 1
            b["learners"].add(a.profile_id)
            b["scores"].append(a.score)
        study = db.scalars(select(StudyTime).where(StudyTime.profile_id.in_(pids.keys()), StudyTime.day >= d0.strftime("%Y-%m-%d"),
                                                   StudyTime.day < d1.strftime("%Y-%m-%d"))).all() if pids else []
        mins: Counter = Counter()
        for s in study:
            day = datetime.strptime(s.day, "%Y-%m-%d")
            k = (day - timedelta(days=day.weekday())).strftime("%Y-%m-%d") if kind == "usage_weekly" else s.day[:7]
            mins[k] += s.seconds // 60
            buckets.setdefault(k, {"acts": 0, "learners": set(), "scores": []})
        regs = Counter(((x.created_at - timedelta(days=x.created_at.weekday())).strftime("%Y-%m-%d") if kind == "usage_weekly" else x.created_at.strftime("%Y-%m"))
                       for x in users if d0 <= x.created_at < d1)
        for k in regs:
            buckets.setdefault(k, {"acts": 0, "learners": set(), "scores": []})
        cols = ["Period", "Active learners", "Activities", "Study minutes", "Average score", "New registrations"]
        rows = [[k, len(b["learners"]), b["acts"], mins.get(k, 0), f"{round(sum(b['scores']) / len(b['scores']) * 100)}%" if b["scores"] else "", regs.get(k, 0)]
                for k, b in sorted(buckets.items())]
    elif kind == "completion":
        cur = content.curriculum()
        courses = [(lv["code"], f"General English {lv['code']} — {lv['name']}", sum(len(un["items"]) for un in lv["units"])) for lv in cur["levels"]]
        courses.append(("business", "Business English Academy", sum(len(c["items"]) for c in cur["business"])))
        if course:
            courses = [c for c in courses if c[0] == course]
        cols = ["Course", "Activities", "Learners started", "Activities completed", "Learners ≥50% complete", "Learners 100% complete"]
        rows = []
        for code, name, n in courses:
            prog = db.scalars(select(LessonProgress).where(LessonProgress.profile_id.in_(pids.keys()), LessonProgress.level == code,
                                                           LessonProgress.updated_at >= d0, LessonProgress.updated_at < d1)).all() if pids else []
            per = Counter(r.profile_id for r in prog if r.status == "completed")
            rows.append([name, n, len({r.profile_id for r in prog}), sum(per.values()), sum(1 for v in per.values() if v >= n / 2),
                         sum(1 for v in per.values() if v >= n)])
    elif kind == "cefr":
        dist = Counter(p.estimated_level if (p.level_confirmed or p.placement_done_at) else "Not placed" for uid, p in profiles.items()
                       if uid in {x.id for x in users})
        total = sum(dist.values()) or 1
        cols = ["Level", "Learners", "Share"]
        rows = [[f"{lv} — {reports.LEVEL_NAMES.get(lv, '')}".strip(" —"), dist.get(lv, 0), f"{round(dist.get(lv, 0) / total * 100)}%"] for lv in LEVELS + ["Not placed"]]
    else:  # assessments
        res = db.scalars(select(AssessmentResult).where(AssessmentResult.profile_id.in_(pids.keys()), AssessmentResult.created_at >= d0,
                                                        AssessmentResult.created_at < d1).order_by(AssessmentResult.id.desc())).all() if pids else []
        cols = ["Date", "Learner", "Email", "Assessment", "Level", "Score", "Passed"]
        rows = [[r.created_at.strftime("%Y-%m-%d"), f"{pids[r.profile_id].first_name} {pids[r.profile_id].last_name}", pids[r.profile_id].email,
                 {"placement": "Placement test", "level_test": "Level test", "business": "Business assessment"}.get(r.kind, r.kind), r.level,
                 f"{round(r.score * 100)}%", "yes" if r.passed else "no"] for r in res]
    if format == "json":
        return {"title": REPORTS[kind], "columns": cols, "rows": rows}
    body, mime, ext = reports.export_table(REPORTS[kind], cols, rows, format)
    platform.audit(db, u.id, "report.exported", "report", kind, {"format": format, "filters": {"from": date_from, "to": date_to, "level": level, "course": course, "learner": learner}}, client_ip(request))
    db.commit()
    return Response(body, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{kind}-{datetime.utcnow():%Y%m%d}.{ext}"'})


# ------------------------------------------------------------------ placement & assessments
@router.get("/assessments")
def assessments(kind: str = "", level: str = "", u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    stmt = select(AssessmentResult, Profile).join(Profile, Profile.id == AssessmentResult.profile_id).where(Profile.user_id.is_not(None))
    if kind:
        stmt = stmt.where(AssessmentResult.kind == kind)
    if level:
        stmt = stmt.where(AssessmentResult.level == level)
    rows = db.execute(stmt.order_by(AssessmentResult.id.desc()).limit(500)).all()
    return [{"id": r.id, "user_id": p.user_id, "learner": p.name, "kind": r.kind, "level": r.level, "score": round(r.score, 3), "passed": bool(r.passed),
             "details": r.details, "date": r.created_at.isoformat()} for r, p in rows]


@router.get("/placement")
def placement_config(u: User = Depends(require("assessments.manage")), db: Session = Depends(get_db)):
    return {"document": content.placement(), "customised": db.get(ContentDocument, "placement") is not None,
            "thresholds": {"placement_level_threshold": platform.get_setting(db, "placement_level_threshold"),
                           "level_test_pass_mark": platform.get_setting(db, "level_test_pass_mark")},
            "reading_options": [t["id"] for t in content.reading_texts()], "listening_options": [i["id"] for i in content.listening_items()]}


class PlacementQ(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,30}$")
    level: str = Field(pattern=r"^(A1|A2|B1|B2|C1|C2)$")
    skill: str = Field("grammar", pattern=r"^(grammar|vocabulary|construction)$")
    prompt: str = Field(min_length=3, max_length=400)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: str = Field(min_length=1, max_length=200)


class PlacementDocIn(BaseModel):
    grammar_vocab: list[PlacementQ] = Field(min_length=6, max_length=120)
    reading_text: str
    listening_items: list[str] = Field(min_length=1, max_length=4)
    writing_prompt: str = Field(min_length=10, max_length=1000)
    speaking_prompt: str = Field(min_length=10, max_length=1000)
    placement_level_threshold: float = Field(0.6, ge=0.3, le=0.95)
    level_test_pass_mark: float = Field(0.7, ge=0.4, le=0.95)


@router.put("/placement")
def save_placement(body: PlacementDocIn, request: Request, u: User = Depends(require("assessments.manage")), db: Session = Depends(get_db)):
    ids = [q.id for q in body.grammar_vocab]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Question ids must be unique.")
    for q in body.grammar_vocab:
        if q.answer not in q.options:
            raise HTTPException(422, f"Question {q.id}: the answer must be one of the options.")
    levels = Counter(q.level for q in body.grammar_vocab)
    missing = [lv for lv in LEVELS if levels.get(lv, 0) < 1]
    if missing:
        raise HTTPException(422, f"Each level needs at least one question (missing: {', '.join(missing)}).")
    if not content.by_id(content.reading_texts(), body.reading_text.split(":")[-1]):
        raise HTTPException(422, "Unknown reading text.")
    for iid in body.listening_items:
        if not content.by_id(content.listening_items(), iid):
            raise HTTPException(422, f"Unknown listening item {iid}.")
    doc = {"grammar_vocab": [q.model_dump() for q in body.grammar_vocab], "reading_text": "reading:" + body.reading_text.split(":")[-1],
           "listening_items": body.listening_items, "writing_prompt": body.writing_prompt, "speaking_prompt": body.speaking_prompt}
    _save_doc(db, "placement", doc, u.id)
    platform.set_setting(db, "placement_level_threshold", body.placement_level_threshold, u.id)
    platform.set_setting(db, "level_test_pass_mark", body.level_test_pass_mark, u.id)
    platform.audit(db, u.id, "placement.updated", "content", "placement", {"questions": len(ids)}, client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"saved": True}


@router.delete("/placement")
def reset_placement(request: Request, u: User = Depends(require("assessments.manage")), db: Session = Depends(get_db)):
    row = db.get(ContentDocument, "placement")
    if row:
        db.delete(row)
    platform.audit(db, u.id, "placement.reset", "content", "placement", ip=client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"reset": True}


def _save_doc(db: Session, key: str, data: dict, uid: int):
    row = db.get(ContentDocument, key) or ContentDocument(key=key, version=0)
    row.data, row.version, row.updated_at, row.updated_by = data, (row.version or 0) + 1, datetime.utcnow(), uid
    db.add(row)


# ------------------------------------------------------------------ content: lessons
LESSON_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,58}$")


class ExerciseIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,40}$")
    type: str = Field(pattern=r"^(mcq|gap|correct|translate)$")
    prompt: str = Field(min_length=2, max_length=600)
    options: list[str] | None = Field(None, max_length=8)
    answer: list[str] | str
    explanation: str = Field("", max_length=1000)


class LessonIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    level: str = Field(pattern=r"^(A1|A2|B1|B2|C1|C2)$")
    unit: str = Field(min_length=2, max_length=80)
    summary: str = Field(min_length=3, max_length=400)
    explanation: str = Field(min_length=10, max_length=12000)
    explanation_fr: str = Field("", max_length=4000)
    examples: list[dict] = Field(default_factory=list, max_length=20)
    exercises: list[ExerciseIn] = Field(min_length=1, max_length=40)
    collection: str = Field("lessons", pattern=r"^(grammar|lessons|business)$")
    published: bool = True


def _lesson_row_out(t: dict, row: ContentLesson | None, builtin: bool) -> dict:
    return {"id": t["id"], "title": t["title"], "level": t["level"], "unit": t["unit"], "summary": t.get("summary", ""),
            "exercises": len(t.get("exercises", [])), "builtin": builtin, "customised": bool(row) and builtin,
            "published": row.published if row else True, "deleted": bool(row and row.deleted)}


@router.get("/content/lessons")
def list_lessons(collection: str = "", q: str = "", u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    rows = {r.id: r for r in db.scalars(select(ContentLesson))}
    builtin = content.builtin_ids()
    out = []
    for coll, fn in (("grammar", content.grammar_topics), ("lessons", content.lessons), ("business", content.business_lessons)):
        if collection and collection != coll:
            continue
        for t in fn(include_unpublished=True):
            if q and q.lower() not in (t["title"] + " " + t.get("summary", "")).lower():
                continue
            out.append(_lesson_row_out(t, rows.get(t["id"]), t["id"] in builtin) | {"collection": coll})
    for r in rows.values():  # deleted built-ins stay listed so they can be restored
        if r.deleted and r.id in builtin:
            base = next((t for c in ("grammar", "lessons", "business") for t in content._base(c) if t["id"] == r.id), None)
            if base and (not collection or r.collection == collection):
                out.append(_lesson_row_out(base, r, True) | {"collection": r.collection})
    return out


@router.get("/content/lessons/{lid}")
def get_lesson(lid: str, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    t = content.find_topic(lid, include_unpublished=True)
    if not t:
        raise HTTPException(404, "Lesson not found")
    row = db.get(ContentLesson, lid)
    coll = row.collection if row else next(c for c in ("grammar", "lessons", "business") if any(x["id"] == lid for x in content._base(c)))
    return t | {"collection": coll, "published": row.published if row else True, "builtin": lid in content.builtin_ids()}


@router.put("/content/lessons/{lid}")
def save_lesson(lid: str, body: LessonIn, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    if not LESSON_ID.match(lid):
        raise HTTPException(422, "Lesson id: lowercase letters, digits and dashes (3–60 characters).")
    ex_ids = [e.id for e in body.exercises]
    if len(set(ex_ids)) != len(ex_ids):
        raise HTTPException(422, "Exercise ids must be unique within the lesson.")
    for e in body.exercises:
        ans = e.answer if isinstance(e.answer, list) else [e.answer]
        if not ans or not all(a.strip() for a in ans):
            raise HTTPException(422, f"Exercise {e.id} needs an answer.")
        if e.type == "mcq" and (not e.options or ans[0] not in e.options):
            raise HTTPException(422, f"Exercise {e.id}: a multiple-choice answer must be one of the options.")
    builtin = lid in content.builtin_ids()
    row = db.get(ContentLesson, lid)
    if builtin:
        coll = next(c for c in ("grammar", "lessons", "business") if any(x["id"] == lid for x in content._base(c)))
    else:
        coll = body.collection
    data = body.model_dump(exclude={"collection", "published"})
    data["examples"] = [{"en": str(x.get("en", ""))[:400], "note": str(x.get("note", ""))[:400]} for x in body.examples if x.get("en")]
    data["exercises"] = [{k: v for k, v in e.model_dump().items() if v is not None} | {"answer": e.answer if isinstance(e.answer, list) else e.answer}
                         for e in body.exercises]
    if coll == "business":
        data["unit"] = "Business English"
    row = row or ContentLesson(id=lid)
    row.collection, row.data, row.published, row.deleted, row.updated_at, row.updated_by = coll, data, body.published, False, datetime.utcnow(), u.id
    db.add(row)
    platform.audit(db, u.id, "content.lesson_saved", "lesson", lid, {"builtin": builtin, "published": body.published}, client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"saved": True, "id": lid}


class PublishIn(BaseModel):
    published: bool


@router.post("/content/lessons/{lid}/publish")
def publish(lid: str, body: PublishIn, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    t = content.find_topic(lid, include_unpublished=True)
    if not t:
        raise HTTPException(404, "Lesson not found")
    row = db.get(ContentLesson, lid)
    if row is None:
        coll = next(c for c in ("grammar", "lessons", "business") if any(x["id"] == lid for x in content._base(c)))
        row = ContentLesson(id=lid, collection=coll, data={k: v for k, v in t.items() if k not in ("id", "published", "custom")})
        db.add(row)
    row.published, row.updated_at, row.updated_by = body.published, datetime.utcnow(), u.id
    platform.audit(db, u.id, "content.published" if body.published else "content.unpublished", "lesson", lid, ip=client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"published": body.published}


@router.delete("/content/lessons/{lid}")
def delete_lesson(lid: str, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    row = db.get(ContentLesson, lid)
    builtin = lid in content.builtin_ids()
    if builtin:  # built-ins are hidden (restorable), never destroyed
        if row is None:
            t = content.find_topic(lid, include_unpublished=True)
            if not t:
                raise HTTPException(404, "Lesson not found")
            coll = next(c for c in ("grammar", "lessons", "business") if any(x["id"] == lid for x in content._base(c)))
            row = ContentLesson(id=lid, collection=coll, data={k: v for k, v in t.items() if k not in ("id", "published", "custom")})
            db.add(row)
        row.deleted, row.updated_at, row.updated_by = True, datetime.utcnow(), u.id
    elif row:
        db.delete(row)
    else:
        raise HTTPException(404, "Lesson not found")
    platform.audit(db, u.id, "content.lesson_deleted", "lesson", lid, {"builtin": builtin}, client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"deleted": True}


@router.post("/content/lessons/{lid}/restore")
def restore_lesson(lid: str, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    """Built-in lesson: discard admin edits/deletion and go back to the original."""
    row = db.get(ContentLesson, lid)
    if not row or lid not in content.builtin_ids():
        raise HTTPException(404, "Nothing to restore")
    db.delete(row)
    platform.audit(db, u.id, "content.lesson_restored", "lesson", lid, ip=client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"restored": True}


# ------------------------------------------------------------------ content: curriculum (levels, units, categories)
@router.get("/content/curriculum")
def get_curriculum(u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    from ..models_platform import ContentDocument as CD
    from ..services.conversation import MODES
    from .writing import GENRES

    media = [{"id": m.id, "title": m.title, "kind": m.kind, "level": m.level} for m in db.scalars(select(MediaAsset).order_by(MediaAsset.id.desc()))]
    lessons = [{"id": t["id"], "title": t["title"], "level": t["level"], "unit": t["unit"], "published": t.get("published", True)}
               for t in content.all_lessons(include_unpublished=True)]
    return {"curriculum": content.curriculum(), "customised": db.get(CD, "curriculum") is not None, "lessons": lessons, "media": media,
            "readings": [{"id": t["id"], "title": t["title"], "level": t["level"]} for t in content.reading_texts()],
            "listening": [{"id": t["id"], "title": t["title"], "level": t["level"]} for t in content.listening_items()],
            "modes": [{"id": k, "title": v["title"]} for k, v in MODES.items()],
            "writing_genres": list(GENRES)}


ITEM_KINDS = {"lesson", "reading", "listening", "vocab", "conversation", "writing", "pronunciation", "media", "soon"}


def _validate_curriculum(doc: dict) -> None:
    from ..services.conversation import MODES

    if [lv.get("code") for lv in doc.get("levels", [])] != LEVELS:
        raise HTTPException(422, "The six levels A1–C2 must stay in order.")
    if not isinstance(doc.get("business"), list) or not doc["business"]:
        raise HTTPException(422, "The Business English Academy needs at least one category.")
    keys = set()

    def check(it: dict, where: str):
        k = it.get("kind")
        if k not in ITEM_KINDS:
            raise HTTPException(422, f"{where}: unknown activity type {k!r}")
        ref = str(it.get("ref", ""))
        if k == "lesson" and not content.find_topic(ref, include_unpublished=True):
            raise HTTPException(422, f"{where}: lesson {ref!r} doesn't exist")
        if k == "reading" and not content.by_id(content.reading_texts(), ref):
            raise HTTPException(422, f"{where}: reading {ref!r} doesn't exist")
        if k == "listening" and not content.by_id(content.listening_items(), ref):
            raise HTTPException(422, f"{where}: listening {ref!r} doesn't exist")
        if k == "conversation" and ref not in MODES:
            raise HTTPException(422, f"{where}: conversation mode {ref!r} doesn't exist")
        if k == "writing" and (not it.get("genre") or not it.get("task")):
            raise HTTPException(422, f"{where}: writing tasks need a genre and a task")
        if k == "vocab" and not re.match(r"^(level|domain):.+$", ref):
            raise HTTPException(422, f"{where}: vocabulary sets use level:XX or domain:name")
        if k in ("lesson", "reading", "listening", "writing", "media"):
            if (k, ref) in keys:
                raise HTTPException(422, f"{where}: {k} {ref!r} is used twice — every activity belongs to exactly one place")
            keys.add((k, ref))

    for lv in doc["levels"]:
        if not lv.get("units"):
            raise HTTPException(422, f"{lv['code']}: needs at least one unit")
        for un in lv["units"]:
            if not str(un.get("title", "")).strip():
                raise HTTPException(422, f"{lv['code']}: every unit needs a title")
            for it in un.get("items", []):
                check(it, f"{lv['code']} / {un['title']}")
                if it["kind"] == "lesson" and content.find_topic(it["ref"], include_unpublished=True)["level"] != lv["code"]:
                    raise HTTPException(422, f"{lv['code']} / {un['title']}: lesson {it['ref']!r} belongs to level "
                                             f"{content.find_topic(it['ref'], include_unpublished=True)['level']} — lessons are never mixed between levels")
    for c in doc["business"]:
        if not re.match(r"^[a-z0-9-]{2,40}$", str(c.get("id", ""))) or not c.get("title"):
            raise HTTPException(422, "Business categories need an id (lowercase-dashes) and a title")
        for it in c.get("items", []):
            check(it, f"Business / {c['title']}")


@router.put("/content/curriculum")
def save_curriculum(doc: dict, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    _validate_curriculum(doc)
    _save_doc(db, "curriculum", {"levels": doc["levels"], "business": doc["business"]}, u.id)
    platform.audit(db, u.id, "content.curriculum_saved", "content", "curriculum", ip=client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"saved": True}


@router.delete("/content/curriculum")
def reset_curriculum(request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    row = db.get(ContentDocument, "curriculum")
    if row:
        db.delete(row)
    platform.audit(db, u.id, "content.curriculum_reset", "content", "curriculum", ip=client_ip(request))
    db.commit()
    content.load_overlay(db)
    return {"reset": True}


# ------------------------------------------------------------------ media
MEDIA_MIME = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg", ".mp4": "video/mp4", ".webm": "video/webm",
              ".pdf": "application/pdf"}
MAX_MEDIA = 25 * 1024 * 1024
YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def _media_out(m: MediaAsset) -> dict:
    return {"id": m.id, "title": m.title, "kind": m.kind, "level": m.level, "category": m.category, "description": m.description,
            "mime": m.mime, "size": m.size, "youtube_id": m.youtube_id, "external_url": m.external_url, "has_file": m.size > 0,
            "subtitles": len(m.subtitles or []), "questions": m.questions or [], "transcript": m.transcript or "", "published": m.published,
            "created_at": m.created_at.isoformat()}


@router.get("/media")
def media_list(u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    return [_media_out(m) for m in db.scalars(select(MediaAsset).order_by(MediaAsset.id.desc()))]


def _parse_questions(raw: str) -> list | None:
    if not raw.strip():
        return None
    try:
        qs = json.loads(raw)
        assert isinstance(qs, list)
        out = []
        for i, q in enumerate(qs[:20]):
            assert q["answer"] in q["options"] and q["prompt"]
            out.append({"id": f"q{i + 1}", "prompt": str(q["prompt"])[:400], "options": [str(o)[:200] for o in q["options"][:6]],
                        "answer": str(q["answer"]), "explanation": str(q.get("explanation", ""))[:400]})
        return out
    except Exception:
        raise HTTPException(422, 'Questions must be JSON: [{"prompt": "...", "options": ["a","b"], "answer": "a", "explanation": "..."}]')


@router.post("/media")
def media_add(request: Request, title: str = Form(..., min_length=2, max_length=200), kind: str = Form(..., pattern=r"^(audio|video|document)$"),
              level: str = Form("", pattern=r"^(|A1|A2|B1|B2|C1|C2)$"), category: str = Form("", max_length=40), description: str = Form("", max_length=4000),
              youtube_url: str = Form(""), external_url: str = Form("", max_length=500), transcript: str = Form("", max_length=100000),
              questions: str = Form("", max_length=50000), file: UploadFile | None = File(None), subtitles_file: UploadFile | None = File(None),
              u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    from ..services import subtitles

    m = MediaAsset(title=title.strip(), kind=kind, level=level or None, category=category or None, description=description, created_by=u.id)
    if youtube_url.strip():
        mt = YT.search(youtube_url)
        if not mt:
            raise HTTPException(422, "That doesn't look like a YouTube link.")
        m.youtube_id = mt.group(1)
    elif file is not None and file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in MEDIA_MIME:
            raise HTTPException(415, "Allowed files: mp3, m4a, wav, ogg, mp4, webm, pdf.")
        data = file.file.read(MAX_MEDIA + 1)
        if len(data) > MAX_MEDIA:
            raise HTTPException(413, "Files are limited to 25 MB on the hosted plan. For longer videos, upload to YouTube and paste the link.")
        sig = data[:12]
        if ext == ".pdf" and not sig.startswith(b"%PDF"):
            raise HTTPException(415, "This file is not a valid PDF.")
        m.data, m.size, m.mime = data, len(data), MEDIA_MIME[ext]
    elif external_url.strip():
        if not external_url.startswith("https://"):
            raise HTTPException(422, "Links must start with https://")
        m.external_url = external_url.strip()
    else:
        raise HTTPException(422, "Upload a file, or add a YouTube or https link.")
    if subtitles_file is not None and subtitles_file.filename:
        raw = subtitles_file.file.read(2_000_000)
        cues = subtitles.parse(raw.decode("utf-8", errors="replace"))
        if not cues:
            raise HTTPException(422, "Could not read the subtitles (.srt or .vtt).")
        m.subtitles = cues
    elif transcript.strip() and "-->" in transcript:
        m.subtitles = subtitles.parse(transcript)
    m.transcript = transcript or None
    m.questions = _parse_questions(questions)
    db.add(m)
    db.flush()
    platform.audit(db, u.id, "content.media_added", "media", m.id, {"kind": kind, "size": m.size}, client_ip(request))
    db.commit()
    return _media_out(m)


class MediaPatch(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    level: str | None = Field(None, pattern=r"^(|A1|A2|B1|B2|C1|C2)$")
    description: str | None = Field(None, max_length=4000)
    transcript: str | None = Field(None, max_length=100000)
    questions: list[dict] | None = None
    published: bool | None = None


@router.put("/media/{mid}")
def media_update(mid: int, body: MediaPatch, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    m = db.get(MediaAsset, mid)
    if not m:
        raise HTTPException(404, "Not found")
    for k in ("title", "description", "transcript", "published"):
        v = getattr(body, k)
        if v is not None:
            setattr(m, k, v)
    if body.level is not None:
        m.level = body.level or None
    if body.questions is not None:
        m.questions = _parse_questions(json.dumps(body.questions))
    platform.audit(db, u.id, "content.media_updated", "media", m.id, ip=client_ip(request))
    db.commit()
    return _media_out(m)


@router.delete("/media/{mid}")
def media_delete(mid: int, request: Request, u: User = Depends(require("content.manage")), db: Session = Depends(get_db)):
    m = db.get(MediaAsset, mid)
    if not m:
        raise HTTPException(404, "Not found")
    db.delete(m)
    platform.audit(db, u.id, "content.media_deleted", "media", mid, ip=client_ip(request))
    db.commit()
    return {"deleted": True}


# ------------------------------------------------------------------ settings, status, audit, backups
class SettingsIn(BaseModel):
    platform_name: str = Field(min_length=2, max_length=80)
    registration_open: bool
    require_email_verification: bool | str
    session_days: int = Field(ge=1, le=90)
    lockout_after_failed_logins: int = Field(ge=3, le=20)
    inactive_after_days: int = Field(ge=3, le=120)
    notifications: dict[str, bool]


@router.get("/settings")
def get_settings(u: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    return platform.all_settings(db)


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, u: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    if body.require_email_verification not in (True, False, "auto"):
        raise HTTPException(422, "require_email_verification must be true, false or 'auto'")
    for k, v in body.model_dump().items():
        if k == "notifications":
            v = {kk: bool(vv) for kk, vv in v.items() if kk in platform.DEFAULT_SETTINGS["notifications"]}
        platform.set_setting(db, k, v, u.id)
    platform.audit(db, u.id, "settings.updated", "settings", None, body.model_dump(), client_ip(request))
    db.commit()
    return platform.all_settings(db)


@router.get("/status")
def status(u: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    url = str(db.get_bind().url)
    dialect = db.get_bind().dialect.name
    t0 = datetime.utcnow()
    db.execute(text("SELECT 1"))
    latency = (datetime.utcnow() - t0).total_seconds() * 1000
    size = None
    if dialect == "postgresql":
        size = db.scalar(text("SELECT pg_database_size(current_database())"))
    media = db.scalar(select(func.coalesce(func.sum(MediaAsset.size), 0))) or 0
    emails = db.execute(select(EmailOutbox.status, func.count()).group_by(EmailOutbox.status)).all()
    return {
        "database": {"engine": dialect, "host": url.split("@")[-1].split("/")[0] if "@" in url else "local file", "latency_ms": round(latency, 1),
                     "size_bytes": size, "users": db.scalar(select(func.count()).select_from(User))},
        "storage": {"media_bytes": int(media), "media_files": db.scalar(select(func.count()).select_from(MediaAsset)), "limit_note": "Files are stored in the database (25 MB each)."},
        "ai": {"provider": settings.llm_provider, "model": settings.llm_model,
               "keys": {k: bool(get_secret(k)) for k in ("gemini", "openai", "anthropic", "azure_speech")}},
        "email": {"provider": mailer.provider(), "from": settings.mail_from or None, "brevo_key": bool(get_secret("brevo")),
                  "outbox": dict(emails)},
        "payments": {"stripe_key": bool(get_secret("stripe")), "paypal_key": bool(get_secret("paypal")), "active": False},
        "security": {"https": True, "session_days": platform.get_setting(db, "session_days"), "secret_key_set": bool(settings.secret_key),
                     "rate_limiting": True, "password_hashing": "scrypt"},
        "mode": settings.mode, "server_time": datetime.utcnow().isoformat(),
    }


@router.get("/audit")
def audit_log(action: str = "", user_id: int | None = None, page: int = Query(1, ge=1), u: User = Depends(require("audit.view")), db: Session = Depends(get_db)):
    stmt = select(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if user_id:
        stmt = stmt.where(or_(AuditLog.actor_user_id == user_id, AuditLog.target_id == str(user_id)))
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * 100).limit(100)).all()
    return [{"id": a.id, "date": a.created_at.isoformat(), "actor": x.email if x else None, "action": a.action, "target": f"{a.target_type or ''}:{a.target_id or ''}",
             "details": a.details, "ip": a.ip} for a, x in rows]


@router.get("/backup")
def backup(request: Request, u: User = Depends(require("backups.run")), db: Session = Depends(get_db)):
    """Full JSON export of every table (password hashes and encrypted keys excluded). Neon also keeps point-in-time history."""
    from ..db import Base

    dump = {"exported_at": datetime.utcnow().isoformat(), "tables": {}}
    skip_cols = {("users", "password_hash"), ("platform_secrets", "ciphertext"), ("auth_sessions", "token_hash"),
                 ("account_tokens", "token_hash"), ("media_assets", "data")}
    for table in Base.metadata.sorted_tables:
        cols = [c.name for c in table.columns if (table.name, c.name) not in skip_cols]
        rows = db.execute(select(*[table.c[c] for c in cols])).all()
        dump["tables"][table.name] = [{c: (v.isoformat() if isinstance(v, datetime) else v) for c, v in zip(cols, r)} for r in rows]
    platform.audit(db, u.id, "backup.downloaded", None, None, ip=client_ip(request))
    db.commit()
    return Response(json.dumps(dump, ensure_ascii=False, default=str).encode(), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="english-mastery-backup-{datetime.utcnow():%Y%m%d-%H%M}.json"'})


# ------------------------------------------------------------------ roles & permissions
@router.get("/roles")
def roles(u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    perms = {p.code: p.description for p in db.scalars(select(Permission))}
    out = []
    for r in db.scalars(select(Role)):
        out.append({"name": r.name, "label": r.label, "description": r.description, "active": r.active,
                    "permissions": sorted(platform.permissions_for(db, r.name)) if r.name != "super_admin" else sorted(perms),
                    "users": db.scalar(select(func.count()).select_from(User).where(User.role == r.name))})
    return {"roles": out, "permissions": perms}


class RolePermsIn(BaseModel):
    permissions: list[str]


@router.put("/roles/{role}")
def set_role_perms(role: str, body: RolePermsIn, request: Request, u: User = Depends(require("users.roles")), db: Session = Depends(get_db)):
    if role == "super_admin":
        raise HTTPException(400, "The Super Administrator always has every permission.")
    if not db.get(Role, role):
        raise HTTPException(404, "Unknown role")
    valid = {p.code for p in db.scalars(select(Permission))}
    wanted = set(body.permissions) & valid
    if role == "learner" and wanted:
        raise HTTPException(400, "Learners can't hold administrative permissions.")
    db.query(RolePermission).filter(RolePermission.role == role).delete()
    for p in sorted(wanted):
        db.add(RolePermission(role=role, permission=p))
    platform.audit(db, u.id, "roles.updated", "role", role, {"permissions": sorted(wanted)}, client_ip(request))
    db.commit()
    return {"role": role, "permissions": sorted(wanted)}


# ------------------------------------------------------------------ commercial & expansion (foundations, inactive)
class PlanIn(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=100)
    description: str = Field("", max_length=1000)
    price_monthly_cents: int | None = Field(None, ge=0, le=10_000_000)
    price_annual_cents: int | None = Field(None, ge=0, le=100_000_000)
    currency: str = Field("CAD", pattern=r"^[A-Z]{3}$")
    trial_days: int = Field(0, ge=0, le=90)
    features: list[str] = Field(default_factory=list)
    limits: dict = Field(default_factory=dict)
    for_organizations: bool = False
    active: bool = True


@router.get("/plans")
def plans(u: User = Depends(require("plans.manage")), db: Session = Depends(get_db)):
    feat = platform.get_setting(db, "features") or {}
    return {"status": feat.get("subscriptions"), "plans": [
        {c.name: getattr(p, c.name) for c in SubscriptionPlan.__table__.columns} for p in db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.sort))]}


@router.put("/plans/{code}")
def save_plan(code: str, body: PlanIn, request: Request, u: User = Depends(require("plans.manage")), db: Session = Depends(get_db)):
    p = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == code)) or SubscriptionPlan(code=body.code)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.add(p)
    platform.audit(db, u.id, "plans.saved", "plan", body.code, body.model_dump(), client_ip(request))
    db.commit()
    return {"saved": True}


@router.get("/commerce")
def commerce(u: User = Depends(require("plans.manage")), db: Session = Depends(get_db)):
    succeeded = db.scalars(select(Payment).where(Payment.status == "succeeded")).all()
    by_plan: Counter = Counter()
    for pay in succeeded:
        sub = db.get(Subscription, pay.subscription_id) if pay.subscription_id else None
        plan = db.get(SubscriptionPlan, sub.plan_id) if sub else None
        by_plan[plan.name if plan else "One-time"] += pay.amount_cents
    return {"payments_active": False,
            "note": "Payments are not activated. No payment provider account is connected, and card data is never stored here.",
            "total_revenue_cents": sum(p.amount_cents for p in succeeded),
            "active_subscriptions": db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status.in_(["active", "trialing"]))),
            "cancelled_subscriptions": db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status == "cancelled")),
            "pending_payments": db.scalar(select(func.count()).select_from(Payment).where(Payment.status == "pending")),
            "failed_transactions": db.scalar(select(func.count()).select_from(Payment).where(Payment.status == "failed")),
            "invoices": db.scalar(select(func.count()).select_from(Invoice)),
            "revenue_by_plan_cents": dict(by_plan)}


@router.get("/expansion")
def expansion(u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    feat = platform.get_setting(db, "features") or {}
    count = lambda m: db.scalar(select(func.count()).select_from(m))  # noqa: E731
    return {"features": feat, "records": {"organizations": count(Organization), "teachers": count(TeacherProfile), "classes": count(Classroom),
                                         "groups": count(LearnerGroup), "subscriptions": count(Subscription), "payments": count(Payment)}}


@router.get("/me")
def admin_me(request: Request, u: User = Depends(require("learners.view")), db: Session = Depends(get_db)):
    return user_out(db, u)
