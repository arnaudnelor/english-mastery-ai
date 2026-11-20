"""Password hashing, opaque tokens, secret encryption and a small in-memory rate limiter."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


def password_problems(pw: str, email: str = "") -> list[str]:
    problems = []
    if len(pw) < 10:
        problems.append("at least 10 characters")
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        problems.append("letters and at least one number")
    if email and email.split("@")[0].lower() in pw.lower() and len(email.split("@")[0]) >= 4:
        problems.append("not containing your email name")
    if pw.lower() in {"password123", "englishmastery1", "1234567890a"}:
        problems.append("not a common password")
    return problems


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------------------------ secret encryption (Fernet)
def _fernet(secret_key: str):
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(("ema-secrets:" + secret_key).encode()).digest())
    return Fernet(key)


def encrypt(secret_key: str, plaintext: str) -> str:
    return _fernet(secret_key).encrypt(plaintext.encode()).decode()


def decrypt(secret_key: str, ciphertext: str) -> str:
    return _fernet(secret_key).decrypt(ciphertext.encode()).decode()


# ------------------------------------------------------------------ rate limiting
class RateLimiter:
    """Sliding-window limiter keyed by (bucket, client). Single-instance deployment; swap for Redis when scaling out."""

    def __init__(self):
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str, client: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[(bucket, client)]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
