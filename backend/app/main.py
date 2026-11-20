from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import hmac

from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_engine
from .routers import academy, admin, auth, assess, media, conversation, exam, grammar, insights, papers, listening, profile, pronunciation, reading, system, video, vocabulary, writing


def setup_logging():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(settings.data_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_engine()
    yield


PUBLIC_API = {
    "/api/auth/config", "/api/auth/register", "/api/auth/login", "/api/auth/logout", "/api/auth/verify-email",
    "/api/auth/resend-verification", "/api/auth/forgot-password", "/api/auth/reset-password", "/api/auth/setup-admin",
    "/api/system/health",
}
ADMIN_ONLY = ("/api/admin/", "/api/system/keys", "/api/system/backup", "/api/system/selftest")


def _authenticate(token: str) -> tuple[int, str] | None:
    """Return (user_id, role) for a valid, unexpired, unrevoked session of an active user."""
    from datetime import datetime, timedelta

    from .db import get_db
    from .models_platform import AuthSession, User
    from .services.security import token_hash

    gen = get_db()
    db = next(gen)
    try:
        s = db.query(AuthSession).filter(AuthSession.token_hash == token_hash(token)).first()
        now = datetime.utcnow()
        if not s or s.revoked_at or s.expires_at < now:
            return None
        u = db.get(User, s.user_id)
        if not u or u.status != "active":
            return None
        if now - s.last_used_at > timedelta(minutes=5) or u.last_seen_at is None:  # throttle writes
            s.last_used_at = now
            u.last_seen_at = now
            db.commit()
        return u.id, u.role
    finally:
        gen.close()


def install_server_guards(app: FastAPI) -> None:
    """Hosted academy: every API call needs a valid session, except sign-up/sign-in/recovery endpoints.
    Administrator areas additionally need an administrator role (fine-grained permissions are checked per endpoint)."""
    from starlette.concurrency import run_in_threadpool

    from .services.security import limiter

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/"):  # versioned alias of the same API
            path = "/api/" + path[len("/api/v1/"):]
            request.scope["path"] = path
        if not path.startswith("/api/") or request.method == "OPTIONS" or path in PUBLIC_API:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        found = await run_in_threadpool(_authenticate, auth[7:].strip()) if auth.lower().startswith("bearer ") else None
        if not found:
            return JSONResponse({"detail": "Please sign in."}, status_code=401)
        uid, role = found
        if not limiter.allow("api", str(uid), 600, 60):
            return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429)
        admin_put = path == "/api/system/providers" and request.method != "GET"
        if (path.startswith(ADMIN_ONLY) or admin_put) and role not in ("super_admin", "admin"):
            return JSONResponse({"detail": "Administrators only."}, status_code=403)
        request.state.user_id, request.state.role = uid, role
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


_last_error_report = [0.0]


def report_error_to_admins(path: str, exc: Exception) -> None:
    import time

    if time.time() - _last_error_report[0] < 600:
        return
    _last_error_report[0] = time.time()
    try:
        from .db import get_db
        from .services import platform

        gen = get_db()
        db = next(gen)
        platform.notify_admins(db, "error", f"Technical error on {path}", f"{type(exc).__name__}: {str(exc)[:300]}",
                               "/admin/settings", setting="admin_errors")
        db.commit()
        gen.close()
    except Exception:
        pass


def create_app(static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="English Mastery AI", version="1.1.0", lifespan=lifespan)
    for r in (auth, admin, media, profile, academy, grammar, vocabulary, conversation, writing, reading, listening, pronunciation, video, exam, papers, assess, insights, system):
        app.include_router(r.router)

    LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}
    OPEN_PATHS = ("/api/system/unlock", "/api/system/health", "/api/system/whoami")

    if settings.mode != "server":  # the single-learner desktop app; the hosted academy uses accounts instead
        @app.middleware("http")
        async def lan_guard(request: Request, call_next):
            """Devices other than this PC need the LAN PIN for the API, and can never manage API keys."""
            host = request.client.host if request.client else ""
            path = request.url.path
            if host not in LOOPBACK and path.startswith("/api/"):
                if path.startswith("/api/system/keys") or path == "/api/system/providers" and request.method != "GET" \
                        or path == "/api/system/backup":
                    return JSONResponse({"detail": "For security, this can only be changed on the computer running the app."}, status_code=403)
                if path not in OPEN_PATHS:
                    pin = settings.lan_pin
                    if not pin or not hmac.compare_digest(request.cookies.get("ema_pin", ""), pin):
                        return JSONResponse({"detail": "PIN required"}, status_code=401)
            return await call_next(request)

    if settings.mode == "server":
        install_server_guards(app)
    origins = ["http://localhost:5173", "http://127.0.0.1:5173", "app://."] + [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logging.getLogger("app").exception("Unhandled error on %s", request.url.path)
        if settings.mode == "server":
            report_error_to_admins(request.url.path, exc)
        return JSONResponse({"detail": "Unexpected error. Details were written to the log file."}, status_code=500)

    # Serve the built frontend (production / installer build)
    static_dir = static_dir or os.environ.get("EMA_STATIC_DIR")
    if static_dir and Path(static_dir).is_dir():
        app.mount("/assets", StaticFiles(directory=Path(static_dir) / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            f = Path(static_dir) / path
            return FileResponse(f if f.is_file() else Path(static_dir) / "index.html")

    return app


app = create_app()


def run():
    import uvicorn

    ssl = {}
    if settings.ssl_certfile and settings.ssl_keyfile:
        ssl = {"ssl_certfile": settings.ssl_certfile, "ssl_keyfile": settings.ssl_keyfile}
    if settings.mode != "server" and settings.host not in ("127.0.0.1", "localhost") and not settings.lan_pin:
        raise SystemExit("Refusing to listen on the network without EMA_LAN_PIN. Use start-lan.bat.")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info", **ssl)


if __name__ == "__main__":
    run()
