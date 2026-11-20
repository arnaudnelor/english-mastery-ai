"""Learner and administrator accounts: registration, email verification, login, sessions,
password recovery, profile, notifications, privacy (export / delete)."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import Profile
from ..models_platform import AccountToken, AuthSession, Notification, User
from ..services import mailer, platform, security

router = APIRouter(prefix="/api/auth", tags=["auth"])
LANGS = r"^(fr|en|es|pt|ar|zh|de|it|other)$"


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else ""))[:64]


def _limit(request: Request, bucket: str, limit: int, window: int):
    if not security.limiter.allow(bucket, client_ip(request), limit, window):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")


def verification_required(db: Session) -> bool:
    v = platform.get_setting(db, "require_email_verification")
    return mailer.configured() if v == "auto" else bool(v)


def user_out(db: Session, u: User) -> dict:
    p = db.scalar(select(Profile).where(Profile.user_id == u.id))
    return {
        "id": u.id, "email": u.email, "first_name": u.first_name, "last_name": u.last_name, "country": u.country,
        "preferred_language": u.preferred_language, "objectives": u.objectives or [], "role": u.role, "status": u.status,
        "email_verified": u.email_verified_at is not None, "created_at": u.created_at.isoformat(),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "notification_prefs": {"email": True, "reminders": True, "milestones": True} | (u.notification_prefs or {}),
        "permissions": sorted(platform.permissions_for(db, u.role)) if u.role != "super_admin" else sorted(platform.PERMISSIONS),
        "is_admin": u.role in ("super_admin", "admin"),
        "level": p.estimated_level if p and (p.level_confirmed or p.placement_done_at) else None,
    }


def _new_session(db: Session, u: User, request: Request) -> str:
    token = security.new_token()
    days = int(platform.get_setting(db, "session_days") or settings.session_days)
    db.add(AuthSession(user_id=u.id, token_hash=security.token_hash(token), expires_at=datetime.utcnow() + timedelta(days=days),
                       ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300]))
    u.last_login_at = u.last_seen_at = datetime.utcnow()
    return token


def _issue_token(db: Session, u: User, purpose: str, hours: int, created_by: int | None = None) -> str:
    db.execute(update(AccountToken).where(AccountToken.user_id == u.id, AccountToken.purpose == purpose,
                                          AccountToken.used_at.is_(None)).values(used_at=datetime.utcnow()))
    token = security.new_token()
    db.add(AccountToken(user_id=u.id, purpose=purpose, token_hash=security.token_hash(token),
                        expires_at=datetime.utcnow() + timedelta(hours=hours), created_by=created_by))
    return token


def _consume(db: Session, token: str, purpose: str) -> AccountToken:
    t = db.scalar(select(AccountToken).where(AccountToken.token_hash == security.token_hash(token), AccountToken.purpose == purpose))
    if not t or t.used_at or t.expires_at < datetime.utcnow():
        raise HTTPException(400, "This link is invalid or has expired. Please request a new one.")
    t.used_at = datetime.utcnow()
    return t


def send_verification(db: Session, u: User) -> None:
    token = _issue_token(db, u, "verify_email", 48)
    mailer.send_email(db, u.email, "Confirm your email address — English Mastery AI",
                      f"Hello {u.first_name},\n\nWelcome to English Mastery AI. Please confirm your email address:\n"
                      f"{platform.link('/verify-email?token=' + token)}\n\nThis link is valid for 48 hours.", "verify_email")


def reset_link_for(db: Session, u: User, created_by: int | None = None) -> str:
    token = _issue_token(db, u, "reset_password", 2 if created_by is None else 72, created_by)
    return platform.link("/reset-password?token=" + token)


class Password(BaseModel):
    password: str = Field(min_length=10, max_length=128)
    password_confirm: str = Field(max_length=128)


class RegisterIn(Password):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    country: str = Field(min_length=2, max_length=80)
    preferred_language: str = Field("fr", pattern=LANGS)
    objectives: list[str] = Field(default_factory=list, max_length=12)
    accept_privacy: bool

    @field_validator("first_name", "last_name", "country")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v or any(c in v for c in "<>"):
            raise ValueError("invalid characters")
        return v


def _check_pw(body: Password, email: str):
    if body.password != body.password_confirm:
        raise HTTPException(422, "The two passwords don't match.")
    problems = security.password_problems(body.password, email)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems) + ".")


@router.get("/config")
def auth_config(db: Session = Depends(get_db)):
    has_super = db.scalar(select(User.id).where(User.role == "super_admin").limit(1)) is not None
    return {"mode": settings.mode, "registration_open": bool(platform.get_setting(db, "registration_open")),
            "email_enabled": mailer.configured(), "verification_required": verification_required(db),
            "setup_available": settings.mode == "server" and not has_super and bool(settings.admin_setup_code),
            "platform_name": platform.get_setting(db, "platform_name")}


def _create_user(db: Session, body: RegisterIn, role: str) -> User:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists. Try signing in or resetting your password.")
    u = User(email=email, password_hash=security.hash_password(body.password), first_name=body.first_name, last_name=body.last_name,
             country=body.country, preferred_language=body.preferred_language, objectives=[o[:120] for o in body.objectives], role=role)
    db.add(u)
    db.flush()
    db.add(Profile(user_id=u.id, name=body.first_name, french_explanations=int(body.preferred_language == "fr"),
                   target_level="C1", estimated_level="A1"))
    return u


@router.post("/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "register", 5, 600)
    if settings.mode != "server":
        raise HTTPException(404, "Accounts are only used in the hosted academy")
    if not platform.get_setting(db, "registration_open"):
        raise HTTPException(403, "Registration is currently closed.")
    if not body.accept_privacy:
        raise HTTPException(422, "Please accept the privacy notice to create an account.")
    _check_pw(body, body.email)
    u = _create_user(db, body, "learner")
    need_verify = verification_required(db)
    platform.audit(db, u.id, "auth.register", "user", u.id, ip=client_ip(request))
    platform.notify(db, u.id, "welcome", f"Welcome to English Mastery AI, {u.first_name}!",
                    "Start with the placement test so your programme begins at the right level.", "/tests?start=placement")
    platform.notify_admins(db, "new_registration", f"New learner: {u.first_name} {u.last_name}", u.email, f"/admin/learners/{u.id}",
                           setting="admin_new_registration")
    if need_verify:
        send_verification(db, u)
        db.commit()
        return {"verification_required": True, "email": u.email}
    db.flush()
    token = _new_session(db, u, request)
    db.commit()
    return {"verification_required": False, "token": token, "user": user_out(db, u)}


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "login", 10, 300)
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    generic = HTTPException(401, "Incorrect email or password.")
    if not u:
        security.verify_password(body.password, security.hash_password("timing-equaliser"))
        raise generic
    if u.locked_until and u.locked_until > datetime.utcnow():
        raise HTTPException(423, "Too many failed attempts. This account is locked for 15 minutes, or reset your password.")
    if not security.verify_password(body.password, u.password_hash):
        u.failed_logins += 1
        limit = int(platform.get_setting(db, "lockout_after_failed_logins") or 8)
        if u.failed_logins >= limit:
            u.locked_until, u.failed_logins = datetime.utcnow() + timedelta(minutes=15), 0
            platform.audit(db, u.id, "auth.locked", "user", u.id, ip=client_ip(request))
            platform.notify_admins(db, "security", f"Account locked after repeated failed logins: {u.email}", "",
                                   f"/admin/learners/{u.id}", setting="admin_security")
        db.commit()
        raise generic
    if u.status == "suspended":
        raise HTTPException(403, "This account is suspended. Please contact the academy.")
    if u.status == "inactive":
        raise HTTPException(403, "This account is deactivated. Please contact the academy.")
    if u.email_verified_at is None and verification_required(db) and u.role == "learner":
        raise HTTPException(403, "Please confirm your email address first. Check your inbox, or ask for a new link.")
    u.failed_logins = 0
    token = _new_session(db, u, request)
    platform.audit(db, u.id, "auth.login", "user", u.id, ip=client_ip(request))
    db.commit()
    return {"token": token, "user": user_out(db, u)}


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        db.execute(update(AuthSession).where(AuthSession.token_hash == security.token_hash(auth[7:].strip()))
                   .values(revoked_at=datetime.utcnow()))
        db.commit()
    return {"ok": True}


@router.post("/logout-all")
def logout_all(u: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(AuthSession).where(AuthSession.user_id == u.id, AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.utcnow()))
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_out(db, u)


class MeIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=2, max_length=80)
    preferred_language: str = Field(pattern=LANGS)
    objectives: list[str] = Field(default_factory=list, max_length=12)
    notification_prefs: dict[str, bool] = Field(default_factory=dict)


@router.put("/me")
def update_me(body: MeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.first_name, u.last_name, u.country = body.first_name.strip(), body.last_name.strip(), body.country.strip()
    u.preferred_language, u.objectives = body.preferred_language, [o[:120] for o in body.objectives]
    u.notification_prefs = {k: bool(v) for k, v in body.notification_prefs.items() if k in ("email", "reminders", "milestones")}
    p = db.scalar(select(Profile).where(Profile.user_id == u.id))
    if p:
        p.name = u.first_name
    db.commit()
    return user_out(db, u)


class ChangePwIn(Password):
    current_password: str = Field(max_length=128)


@router.post("/change-password")
def change_password(body: ChangePwIn, request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _limit(request, "changepw", 6, 600)
    if not security.verify_password(body.current_password, u.password_hash):
        raise HTTPException(400, "Your current password is incorrect.")
    _check_pw(body, u.email)
    u.password_hash = security.hash_password(body.password)
    # sign out every other device
    current = security.token_hash(request.headers.get("authorization", "")[7:].strip())
    db.execute(update(AuthSession).where(AuthSession.user_id == u.id, AuthSession.token_hash != current,
                                         AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.utcnow()))
    platform.audit(db, u.id, "auth.password_changed", "user", u.id, ip=client_ip(request))
    db.commit()
    return {"ok": True}


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


@router.post("/verify-email")
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "verify", 20, 600)
    t = _consume(db, body.token, "verify_email")
    u = db.get(User, t.user_id)
    u.email_verified_at = u.email_verified_at or datetime.utcnow()
    platform.audit(db, u.id, "auth.email_verified", "user", u.id)
    db.commit()
    return {"ok": True, "email": u.email}


class EmailIn(BaseModel):
    email: EmailStr


@router.post("/resend-verification")
def resend_verification(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "resend", 3, 600)
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and not u.email_verified_at:
        send_verification(db, u)
        db.commit()
    return {"ok": True, "email_enabled": mailer.configured()}


@router.post("/forgot-password")
def forgot_password(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "forgot", 5, 900)
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and u.status != "suspended":
        link = reset_link_for(db, u)
        mailer.send_email(db, u.email, "Reset your password — English Mastery AI",
                          f"Hello {u.first_name},\n\nUse this link to choose a new password (valid 2 hours):\n{link}\n\n"
                          "If you didn't ask for this, you can ignore this email.", "reset_password")
        platform.audit(db, u.id, "auth.reset_requested", "user", u.id, ip=client_ip(request))
        db.commit()
    # same answer whether or not the account exists
    return {"ok": True, "email_enabled": mailer.configured()}


class ResetIn(Password):
    token: str = Field(min_length=20, max_length=100)


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    _limit(request, "reset", 10, 900)
    t = _consume(db, body.token, "reset_password")
    u = db.get(User, t.user_id)
    _check_pw(body, u.email)
    u.password_hash, u.failed_logins, u.locked_until = security.hash_password(body.password), 0, None
    u.email_verified_at = u.email_verified_at or datetime.utcnow()  # they proved access to the mailbox / admin link
    db.execute(update(AuthSession).where(AuthSession.user_id == u.id, AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.utcnow()))
    platform.audit(db, u.id, "auth.password_reset", "user", u.id, ip=client_ip(request))
    db.commit()
    return {"ok": True}


class SetupIn(RegisterIn):
    setup_code: str = Field(min_length=8, max_length=100)


@router.post("/setup-admin")
def setup_admin(body: SetupIn, request: Request, db: Session = Depends(get_db)):
    """Creates the first Super Administrator with the one-time EMA_ADMIN_SETUP_CODE. Disabled afterwards."""
    import hmac

    _limit(request, "setup", 5, 900)
    if settings.mode != "server" or not settings.admin_setup_code:
        raise HTTPException(404, "Not available")
    if db.scalar(select(User.id).where(User.role == "super_admin").limit(1)):
        raise HTTPException(409, "The Super Administrator already exists. Sign in instead.")
    if not hmac.compare_digest(body.setup_code.strip(), settings.admin_setup_code):
        raise HTTPException(403, "Incorrect setup code.")
    _check_pw(body, body.email)
    u = _create_user(db, body, "super_admin")
    u.email_verified_at = datetime.utcnow()
    db.flush()
    platform.audit(db, u.id, "admin.setup", "user", u.id, ip=client_ip(request))
    token = _new_session(db, u, request)
    db.commit()
    return {"token": token, "user": user_out(db, u)}


# ------------------------------------------------------------------ notifications
@router.get("/notifications")
def notifications(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == u.id).order_by(Notification.id.desc()).limit(50)).all()
    return {"unread": sum(1 for n in rows if not n.read_at),
            "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "route": n.route, "read": n.read_at is not None,
                       "date": n.created_at.isoformat()} for n in rows]}


@router.post("/notifications/read")
def read_notifications(u: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == u.id, Notification.read_at.is_(None)).values(read_at=datetime.utcnow()))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ privacy
@router.get("/me/report.pdf")
def my_report(u: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..services.reports import learner_report_pdf

    return Response(learner_report_pdf(db, u), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="progress-report-{u.first_name}.pdf"'})


@router.get("/me/export.json")
def my_data(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Personal data export (privacy / PIPEDA access request)."""
    from ..services.reports import learner_data_export

    return learner_data_export(db, u)


class DeleteIn(BaseModel):
    password: str = Field(max_length=128)


@router.post("/me/delete")
def delete_me(body: DeleteIn, request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role == "super_admin":
        raise HTTPException(400, "The Super Administrator account can't delete itself.")
    if not security.verify_password(body.password, u.password_hash):
        raise HTTPException(400, "Incorrect password.")
    from ..services.reports import delete_learner

    platform.audit(db, None, "auth.account_deleted", "user", u.id, {"email_domain": u.email.split("@")[1]}, ip=client_ip(request))
    delete_learner(db, u)
    db.commit()
    return {"deleted": True}
