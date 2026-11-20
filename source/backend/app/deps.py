from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Profile


def current_profile(db: Session = Depends(get_db)) -> Profile:
    """Single-user local app: the first profile is the active one."""
    p = db.scalar(select(Profile).order_by(Profile.id))
    if p is None:
        raise HTTPException(409, "No profile yet. Complete onboarding first.")
    return p


def provider_errors(fn):
    """Translate AI-provider failures into clear HTTP errors for the UI."""
    import functools

    from .providers.llm import MissingAPIKey, ProviderError

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except MissingAPIKey as e:
            raise HTTPException(412, str(e)) from e
        except ProviderError as e:
            raise HTTPException(502, str(e)) from e

    return wrapper
