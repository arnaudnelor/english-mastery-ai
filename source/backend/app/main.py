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
from .routers import assess, conversation, exam, grammar, insights, papers, listening, profile, pronunciation, reading, system, video, vocabulary, writing


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


def create_app(static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="English Mastery AI", version="1.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://."],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (profile, grammar, vocabulary, conversation, writing, reading, listening, pronunciation, video, exam, papers, assess, insights, system):
        app.include_router(r.router)

    LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}
    OPEN_PATHS = ("/api/system/unlock", "/api/system/health", "/api/system/whoami")

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

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logging.getLogger("app").exception("Unhandled error on %s", request.url.path)
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
    if settings.host not in ("127.0.0.1", "localhost") and not settings.lan_pin:
        raise SystemExit("Refusing to listen on the network without EMA_LAN_PIN. Use start-lan.bat.")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info", **ssl)


if __name__ == "__main__":
    run()
