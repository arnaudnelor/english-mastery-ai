"""Parse SRT / WebVTT subtitles (or plain transcripts) into timed cues."""
from __future__ import annotations

import re

_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})")


def _sec(m: re.Match) -> float:
    h, mnt, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse(text: str) -> list[dict]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        ms = list(_TS.finditer(lines[idx]))
        if len(ms) < 2:
            continue
        body = " ".join(lines[idx + 1:])
        body = re.sub(r"<[^>]+>", "", body)  # strip VTT/HTML tags like <i>, <c.colour>, timestamps
        body = re.sub(r"\{\\[^}]*\}", "", body).strip()  # strip SSA tags
        if body:
            cues.append({"start": round(_sec(ms[0]), 3), "end": round(_sec(ms[1]), 3), "text": body})
    if cues:
        return _merge_duplicates(cues)
    # Plain transcript: one cue per sentence, no timing
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return [{"start": None, "end": None, "text": s} for s in sentences if s]


def _merge_duplicates(cues: list[dict]) -> list[dict]:
    """Auto-generated captions often repeat rolling lines; drop consecutive duplicates."""
    out: list[dict] = []
    for c in cues:
        if out and c["text"] == out[-1]["text"]:
            out[-1]["end"] = c["end"]
        else:
            out.append(c)
    return out


def transcript(cues: list[dict]) -> str:
    return " ".join(c["text"] for c in cues)
