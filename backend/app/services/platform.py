"""Platform services: role/permission seeding, settings, encrypted secrets, audit log, notifications."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..config import settings
from ..models_platform import (AuditLog, Notification, Permission, PlatformSecret, PlatformSetting, Role,
                               RolePermission, SubscriptionPlan, User)
from . import security

log = logging.getLogger(__name__)

ROLES = [
    ("super_admin", "Super Administrator", "Full control, including administrators, permissions, secrets and backups.", True),
    ("admin", "Administrator", "Manages learners, content, assessments and reports.", True),
    ("teacher", "Teacher", "Future teacher portal: classes, homework, feedback (inactive until activated).", False),
    ("learner", "Learner", "Studies in the academy and sees only their own records.", True),
]

PERMISSIONS = {
    "learners.view": "View learners and their progress",
    "learners.manage": "Activate, deactivate, suspend learners and reset passwords",
    "learners.export": "Export learner reports",
    "content.manage": "Create, edit, publish and unpublish lessons, units and media",
    "assessments.manage": "Configure placement questions and thresholds",
    "reports.view": "View and export platform reports",
    "settings.manage": "Change platform settings and notification settings",
    "secrets.manage": "Add or remove AI / email / payment API keys",
    "users.roles": "Change user roles and role permissions",
    "audit.view": "View the audit log",
    "backups.run": "Download database backups",
    "plans.manage": "Configure subscription plans (commercial features)",
    "classes.manage": "Manage classes, groups and enrolments (future)",
    "teachers.manage": "Create and approve teachers (future)",
}

DEFAULT_ROLE_PERMS = {
    "super_admin": list(PERMISSIONS),
    "admin": ["learners.view", "learners.manage", "learners.export", "content.manage", "assessments.manage",
              "reports.view", "settings.manage", "audit.view", "plans.manage", "classes.manage", "teachers.manage"],
    "teacher": ["learners.view", "classes.manage"],
    "learner": [],
}

DEFAULT_SETTINGS = {
    "platform_name": "English Mastery AI",
    "registration_open": True,
    "require_email_verification": "auto",  # auto = required only when an email service is configured
    "level_test_pass_mark": 0.7,
    "placement_level_threshold": 0.6,
    "session_days": 30,
    "lockout_after_failed_logins": 8,
    "inactive_after_days": 14,
    "notifications": {
        "learner_welcome": True, "learner_assessment": True, "learner_milestone": True, "learner_reminders": True,
        "admin_new_registration": True, "admin_assessment": True, "admin_inactive": True, "admin_security": True,
        "admin_errors": True,
    },
    "features": {  # clearly distinguish operational / configured-inactive / future
        "teacher_portal": "future", "classes": "future", "groups": "future", "organizations": "future",
        "subscriptions": "configured_inactive", "payments": "configured_inactive",
    },
}

DEFAULT_PLANS = [
    ("free", "Free", "Limited lessons and exercises, basic placement test.", 0, 0, ["placement_basic", "lessons_limited"], {"lessons_per_week": 5}, False),
    ("basic", "Basic", "General English courses: grammar, vocabulary, reading, listening.", 1500, 15000, ["general_english", "grammar", "vocabulary", "reading", "listening"], {}, False),
    ("premium", "Premium", "Full A1–C2 curriculum, AI professor, voice conversations, pronunciation lab, advanced assessments.", 2900, 29000, ["general_english", "ai_professor", "voice", "pronunciation", "advanced_assessments"], {}, False),
    ("business", "Business", "Business English Academy, simulations, finance vocabulary, business assessments.", 3900, 39000, ["business_academy", "simulations", "business_assessments", "ai_professor"], {}, False),
    ("institutional", "Institutional", "Multiple learners, teacher accounts, classes, group monitoring, reporting.", None, None, ["all", "teachers", "classes", "groups", "org_reporting"], {"seats": 50}, True),
]


def seed(db: Session) -> None:
    """Idempotent: create roles, permissions, default role permissions, settings and draft plans."""
    have_roles = {r.name for r in db.scalars(select(Role))}
    for name, label, desc, active in ROLES:
        if name not in have_roles:
            db.add(Role(name=name, label=label, description=desc, active=active))
    have_perms = {p.code for p in db.scalars(select(Permission))}
    for code, desc in PERMISSIONS.items():
        if code not in have_perms:
            db.add(Permission(code=code, description=desc))
    db.flush()
    if not db.scalar(select(RolePermission).limit(1)):
        for role, perms in DEFAULT_ROLE_PERMS.items():
            for p in perms:
                db.add(RolePermission(role=role, permission=p))
    else:  # super admin always holds every permission, including newly added ones
        have = {rp.permission for rp in db.scalars(select(RolePermission).where(RolePermission.role == "super_admin"))}
        for p in PERMISSIONS:
            if p not in have:
                db.add(RolePermission(role="super_admin", permission=p))
    if not db.scalar(select(SubscriptionPlan).limit(1)):
        for i, (code, name, desc, m, y, feats, limits, org) in enumerate(DEFAULT_PLANS):
            db.add(SubscriptionPlan(code=code, name=name, description=desc, price_monthly_cents=m, price_annual_cents=y,
                                    features=feats, limits=limits, for_organizations=org, sort=i, trial_days=7 if code == "premium" else 0))
    db.commit()


# ------------------------------------------------------------------ settings
def get_setting(db: Session, key: str):
    row = db.get(PlatformSetting, key)
    if row is None:
        return DEFAULT_SETTINGS.get(key)
    if isinstance(DEFAULT_SETTINGS.get(key), dict) and isinstance(row.value, dict):
        return DEFAULT_SETTINGS[key] | row.value
    return row.value


def all_settings(db: Session) -> dict:
    return {k: get_setting(db, k) for k in DEFAULT_SETTINGS}


def set_setting(db: Session, key: str, value, user_id: int | None) -> None:
    row = db.get(PlatformSetting, key) or PlatformSetting(key=key)
    row.value, row.updated_at, row.updated_by = value, datetime.utcnow(), user_id
    db.add(row)


# ------------------------------------------------------------------ permissions
def permissions_for(db: Session, role: str) -> set[str]:
    return {rp.permission for rp in db.scalars(select(RolePermission).where(RolePermission.role == role))}


def has_permission(db: Session, user: User, perm: str) -> bool:
    return user.role == "super_admin" or perm in permissions_for(db, user.role)


# ------------------------------------------------------------------ secrets (admin portal)
def _secret_key() -> str:
    if not settings.secret_key:
        raise RuntimeError("EMA_SECRET_KEY is not set")
    return settings.secret_key


def save_secret(db: Session, name: str, value: str) -> None:
    row = db.get(PlatformSecret, name) or PlatformSecret(name=name)
    row.ciphertext, row.updated_at = security.encrypt(_secret_key(), value), datetime.utcnow()
    db.add(row)


def delete_secret(db: Session, name: str) -> None:
    row = db.get(PlatformSecret, name)
    if row:
        db.delete(row)


def install_secret_lookup() -> None:
    from ..db import get_db

    def lookup(name: str) -> str | None:
        gen = get_db()
        db = next(gen)
        try:
            row = db.get(PlatformSecret, name)
            return security.decrypt(_secret_key(), row.ciphertext) if row else None
        except Exception as e:  # wrong secret key or corrupt value
            log.warning("Could not read secret %s: %s", name, e)
            return None
        finally:
            gen.close()

    config._server_secret_lookup = lookup


# ------------------------------------------------------------------ audit & notifications
def audit(db: Session, actor: int | None, action: str, target_type: str | None = None, target_id=None,
          details: dict | None = None, ip: str | None = None) -> None:
    db.add(AuditLog(actor_user_id=actor, action=action, target_type=target_type,
                    target_id=str(target_id) if target_id is not None else None, details=details, ip=ip))


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "", route: str | None = None,
           email: bool = False) -> None:
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, route=route))
    if email:
        u = db.get(User, user_id)
        prefs = (u.notification_prefs or {}) if u else {}
        if u and prefs.get("email", True):
            from .mailer import send_email
            send_email(db, u.email, title, body + (f"\n\nOpen: {link(route)}" if route else ""), kind)


def notify_admins(db: Session, kind: str, title: str, body: str = "", route: str | None = None, setting: str | None = None) -> None:
    if setting and not (get_setting(db, "notifications") or {}).get(setting, True):
        return
    for u in db.scalars(select(User).where(User.role.in_(["super_admin", "admin"]), User.status == "active")):
        db.add(Notification(user_id=u.id, kind=kind, title=title, body=body, route=route))


def link(route: str | None) -> str:
    base = (settings.public_app_url or "").rstrip("/")
    return f"{base}/#{route}" if route else base
