"""Application configuration.

Non-secret settings come from environment variables / a .env file.
API keys are NEVER hardcoded: they are read from the OS credential store
(Windows Credential Manager via `keyring`) and fall back to environment
variables for development and CI.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

KEYRING_SERVICE = "EnglishMasteryAI"


def default_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "EnglishMasteryAI"


class Settings(BaseSettings):
    # Later files override earlier ones; the data-dir .env is written by Settings > AI Providers.
    model_config = SettingsConfigDict(
        env_prefix="EMA_", env_file=(".env", str(default_data_dir() / ".env")), extra="ignore"
    )

    data_dir: Path = default_data_dir()
    database_url: str = ""  # empty -> sqlite file in data_dir
    host: str = "127.0.0.1"  # 0.0.0.0 only in LAN mode (start-lan.bat)
    port: int = 8765
    lan_pin: str = ""  # required for any device other than this PC when set
    ssl_certfile: str = ""
    ssl_keyfile: str = ""

    # Provider selection (interchangeable without code changes)
    llm_provider: str = "gemini"  # gemini (free tier) | openai | anthropic
    llm_model: str = "gemini-2.5-flash"
    stt_provider: str = "openai"  # openai (Whisper API)
    stt_model: str = "whisper-1"
    tts_provider: str = "openai"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    azure_speech_region: str = ""  # e.g. canadacentral, eastus (optional phoneme scoring)

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'english_mastery.db'}"


settings = Settings()


def _keyring():
    try:
        import keyring  # noqa: WPS433

        return keyring
    except Exception:  # pragma: no cover - keyring optional on some systems
        return None


def get_secret(name: str) -> str | None:
    """Return an API key by logical name, e.g. 'openai' or 'anthropic'."""
    kr = _keyring()
    if kr is not None:
        try:
            value = kr.get_password(KEYRING_SERVICE, name)
            if value:
                return value
        except Exception as exc:  # no backend available (e.g. headless Linux)
            log.debug("keyring unavailable: %s", exc)
    return os.environ.get(f"{name.upper()}_API_KEY")


def set_secret(name: str, value: str) -> bool:
    """Store a key in the OS credential store. Returns False if unavailable."""
    kr = _keyring()
    if kr is None:
        return False
    try:
        kr.set_password(KEYRING_SERVICE, name, value)
        return True
    except Exception as exc:
        log.warning("Could not store secret in keyring: %s", exc)
        return False


def delete_secret(name: str) -> None:
    kr = _keyring()
    if kr is None:
        return
    try:
        kr.delete_password(KEYRING_SERVICE, name)
    except Exception:
        pass
