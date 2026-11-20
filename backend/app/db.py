from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def init_engine(url: str | None = None):
    global _engine, _SessionLocal
    url = url or settings.resolved_database_url()
    if url.startswith("postgres://"):  # Neon / Heroku style URLs
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("sqlite"):
        _engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    else:  # serverless Postgres closes idle connections: verify before use and recycle
        _engine = create_engine(url, future=True, pool_pre_ping=True, pool_recycle=280, pool_size=5, max_overflow=5)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    from . import models, models_platform  # noqa: F401  (register tables)

    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)
    from .services import platform

    with _SessionLocal() as db:
        platform.seed(db)
        from . import content

        content.load_overlay(db)
    if settings.mode == "server":
        platform.install_secret_lookup()
        with _SessionLocal() as db:
            saved = platform.get_setting(db, "ai_provider")
            if isinstance(saved, dict):
                settings.llm_provider = saved.get("llm_provider", settings.llm_provider)
                settings.llm_model = saved.get("llm_model", settings.llm_model)
                settings.azure_speech_region = saved.get("azure_speech_region", settings.azure_speech_region)
    return _engine


def _add_missing_columns(engine):
    """Tiny forward-only migration: add new nullable columns to existing tables.

    Keeps databases created by earlier versions working after an upgrade.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    ddl_type = col.type.compile(dialect=engine.dialect)
                    default = ""
                    if col.default is not None and getattr(col.default, "is_scalar", False):
                        v = col.default.arg
                        default = f" DEFAULT {int(v) if isinstance(v, bool) else repr(v)}"
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{default}'))


def get_engine():
    if _engine is None:
        init_engine()
    return _engine


def get_db() -> Iterator[Session]:
    if _SessionLocal is None:
        init_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
