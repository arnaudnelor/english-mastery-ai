"""Curriculum loader. Content is plain JSON so it can be extended without code."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent


@lru_cache
def grammar_topics() -> list[dict]:
    return json.loads((DIR / "grammar.json").read_text(encoding="utf-8"))["topics"]


@lru_cache
def vocabulary() -> list[dict]:
    return json.loads((DIR / "vocabulary.json").read_text(encoding="utf-8"))["words"]


def find_topic(topic_id: str) -> dict | None:
    return next((t for t in grammar_topics() if t["id"] == topic_id), None)


def find_word(word_id: str) -> dict | None:
    return next((w for w in vocabulary() if w["id"] == word_id), None)


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).strip().lower()
    s = s.replace("’", "'").replace("–", "-")
    s = re.sub(r"[.!?]+$", "", s)
    return re.sub(r"\s+", " ", s)


def check_answer(exercise: dict, given: str) -> bool:
    accepted = exercise["answer"]
    if isinstance(accepted, str):
        accepted = [accepted]
    return normalise(given) in {normalise(a) for a in accepted}


@lru_cache
def reading_texts() -> list[dict]:
    return json.loads((DIR / "reading.json").read_text(encoding="utf-8"))["texts"]


@lru_cache
def listening_items() -> list[dict]:
    return json.loads((DIR / "listening.json").read_text(encoding="utf-8"))["items"]


@lru_cache
def pronunciation() -> dict:
    return json.loads((DIR / "pronunciation.json").read_text(encoding="utf-8"))


def by_id(items: list[dict], item_id: str) -> dict | None:
    return next((x for x in items if x["id"] == item_id), None)


@lru_cache
def exams() -> list[dict]:
    return json.loads((DIR / "exams.json").read_text(encoding="utf-8"))["exams"]


@lru_cache
def placement() -> dict:
    return json.loads((DIR / "placement.json").read_text(encoding="utf-8"))


@lru_cache
def exam_ielts() -> dict:
    """Passages and recordings written only for the IELTS mock (never shown in the modules)."""
    return json.loads((DIR / "exam_ielts.json").read_text(encoding="utf-8"))


def exam_listening(iid: str) -> dict | None:
    return by_id(exam_ielts()["listening"], iid)


def exam_reading(tid: str) -> dict | None:
    return by_id(exam_ielts()["reading"], tid)


@lru_cache
def papers() -> list[dict]:
    return json.loads((DIR / "papers.json").read_text(encoding="utf-8"))["papers"]
