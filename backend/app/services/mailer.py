"""Email delivery: Brevo HTTP API (free tier) or SMTP. With neither configured, emails are recorded as
'not_configured' and the admin portal offers the equivalent manual action (e.g. copy a reset link)."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from ..config import get_secret, settings
from ..models_platform import EmailOutbox

log = logging.getLogger(__name__)


def provider() -> str | None:
    if get_secret("brevo") and settings.mail_from:
        return "brevo"
    if settings.smtp_host and get_secret("smtp") and settings.mail_from:
        return "smtp"
    return None


def configured() -> bool:
    return provider() is not None


def send_email(db: Session, to: str, subject: str, text: str, kind: str) -> bool:
    p = provider()
    status, error = "not_configured", None
    if p:
        try:
            if p == "brevo":
                r = httpx.post("https://api.brevo.com/v3/smtp/email", timeout=20,
                               headers={"api-key": get_secret("brevo"), "accept": "application/json"},
                               json={"sender": {"email": settings.mail_from, "name": settings.mail_from_name},
                                     "to": [{"email": to}], "subject": subject, "textContent": text})
                if r.status_code >= 300:
                    raise RuntimeError(f"Brevo {r.status_code}: {r.text[:200]}")
            else:
                msg = EmailMessage()
                msg["From"], msg["To"], msg["Subject"] = f"{settings.mail_from_name} <{settings.mail_from}>", to, subject
                msg.set_content(text)
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
                    s.starttls()
                    s.login(settings.smtp_user or settings.mail_from, get_secret("smtp"))
                    s.send_message(msg)
            status = "sent"
        except Exception as e:  # network / provider error: recorded, never crashes the request
            status, error = "failed", str(e)[:500]
            log.warning("Email to %s failed: %s", to, e)
    db.add(EmailOutbox(to_email=to, subject=subject[:200], kind=kind, status=status, error=error))
    return status == "sent"
