from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Profile


def current_user(request: Request, db: Session = Depends(get_db)):
    """Server mode: the user authenticated by the auth middleware (bearer session token)."""
    from .models_platform import User

    uid = getattr(request.state, "user_id", None)
    if settings.mode != "server" or uid is None:
        raise HTTPException(401, "Please sign in.")
    u = db.get(User, uid)
    if not u or u.status != "active":
        raise HTTPException(401, "Please sign in.")
    return u


def current_profile(request: Request, db: Session = Depends(get_db)) -> Profile:
    """Local app: the first profile is the learner. Hosted academy: the signed-in user's own profile only."""
    if settings.mode == "server":
        u = current_user(request, db)
        p = db.scalar(select(Profile).where(Profile.user_id == u.id))
        if p is None:  # e.g. an administrator who opens the learner area
            p = Profile(user_id=u.id, name=u.first_name, estimated_level="A1")
            db.add(p)
            db.commit()
        return p
    p = db.scalar(select(Profile).order_by(Profile.id))
    if p is None:
        raise HTTPException(409, "No profile yet. Complete onboarding first.")
    return p


def require(perm: str):
    """Dependency factory: the signed-in user must hold `perm` (super_admin holds all)."""

    def dep(request: Request, db: Session = Depends(get_db)):
        from .services.platform import has_permission

        u = current_user(request, db)
        if u.role not in ("super_admin", "admin", "teacher") or not has_permission(db, u, perm):
            raise HTTPException(403, "You don't have permission for this action.")
        return u

    return dep


def provider_errors(fn):
    """Translate AI-provider failures into clear HTTP errors for the UI."""
    import functools

    from .providers.llm import MissingAPIKey, ProviderError

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except MissingAPIKey as e:
            if settings.mode == "server":
                raise HTTPException(412, "The AI professor isn't switched on yet. The academy administrator needs to add an AI key in the admin portal.") from e
            raise HTTPException(412, str(e)) from e
        except ProviderError as e:
            raise HTTPException(502, str(e)) from e

    return wrapper
