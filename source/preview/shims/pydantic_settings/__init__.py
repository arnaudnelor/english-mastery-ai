"""Minimal, self-written stand-in for `pydantic-settings`, used only by the browser preview.

Supports what English Mastery AI uses: a BaseSettings model whose fields can be
overridden by environment variables with a prefix (e.g. EMA_DATA_DIR).
"""
from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict

_PREFIX = {"value": ""}


def SettingsConfigDict(env_prefix: str = "", extra: str = "ignore", **_ignored) -> ConfigDict:  # noqa: N802
    _PREFIX["value"] = env_prefix
    return ConfigDict(extra=extra)


class BaseSettings(BaseModel):
    def __init__(self, **values):
        prefix = _PREFIX["value"]
        for name in type(self).model_fields:
            env = os.environ.get(f"{prefix}{name}".upper())
            if env is not None and name not in values:
                values[name] = env
        super().__init__(**values)
