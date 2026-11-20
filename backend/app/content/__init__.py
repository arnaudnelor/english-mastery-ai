"""Curriculum loader. Content is plain JSON so it can be extended without code."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent


# ------------------------------------------------------------------ admin overlays (hosted academy)
# Built-in content ships as JSON. Administrators can add lessons, edit or unpublish built-in ones, and
# edit the curriculum / placement documents; those changes live in the database and are overlaid here.
_OVERLAY: dict = {"version": 0, "lessons": {}, "docs": {}}


def set_overlay(lessons: dict[str, dict], docs: dict[str, dict]) -> None:
    """lessons: id -> {"collection", "data", "published", "deleted"}; docs: key -> data."""
    _OVERLAY.update(version=_OVERLAY["version"] + 1, lessons=lessons, docs=docs)
    _merged.cache_clear()


def load_overlay(db) -> None:
    from sqlalchemy import select

    from ..models_platform import ContentDocument, ContentLesson

    lessons = {r.id: {"collection": r.collection, "data": r.data, "published": r.published, "deleted": r.deleted}
               for r in db.scalars(select(ContentLesson))}
    docs = {r.key: r.data for r in db.scalars(select(ContentDocument))}
    set_overlay(lessons, docs)


@lru_cache
def _base(collection: str) -> list[dict]:
    if collection == "grammar":
        return json.loads((DIR / "grammar.json").read_text(encoding="utf-8"))["topics"]
    return _lessons_file()[collection]


def builtin_ids() -> set[str]:
    return {t["id"] for c in ("grammar", "lessons", "business") for t in _base(c)}


@lru_cache
def _merged(collection: str, include_unpublished: bool) -> tuple:
    out = []
    ov = _OVERLAY["lessons"]
    for t in _base(collection):
        o = ov.get(t["id"])
        if o:
            if o["deleted"] or (not o["published"] and not include_unpublished):
                continue
            t = o["data"] | {"id": t["id"], "published": o["published"]}
        out.append(t)
    for lid, o in ov.items():  # admin-created lessons
        if o["collection"] == collection and lid not in {t["id"] for t in _base(collection)} and not o["deleted"]:
            if o["published"] or include_unpublished:
                out.append(o["data"] | {"id": lid, "published": o["published"], "custom": True})
    return tuple(out)


def grammar_topics(include_unpublished: bool = False) -> list[dict]:
    return list(_merged("grammar", include_unpublished))


@lru_cache
def vocabulary() -> list[dict]:
    return json.loads((DIR / "vocabulary.json").read_text(encoding="utf-8"))["words"]


@lru_cache
def _lessons_file() -> dict:
    return json.loads((DIR / "lessons.json").read_text(encoding="utf-8"))


def lessons(include_unpublished: bool = False) -> list[dict]:
    """Communicative lessons attached to a CEFR level (same schema as grammar topics)."""
    return list(_merged("lessons", include_unpublished))


def business_lessons(include_unpublished: bool = False) -> list[dict]:
    return list(_merged("business", include_unpublished))


def all_lessons(include_unpublished: bool = False) -> list[dict]:
    return grammar_topics(include_unpublished) + lessons(include_unpublished) + business_lessons(include_unpublished)


@lru_cache
def _base_curriculum() -> dict:
    return json.loads((DIR / "curriculum.json").read_text(encoding="utf-8"))


def curriculum() -> dict:
    return _OVERLAY["docs"].get("curriculum") or _base_curriculum()


def find_topic(topic_id: str, include_unpublished: bool = False) -> dict | None:
    return next((t for t in all_lessons(include_unpublished) if t["id"] == topic_id), None)


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
def _base_placement() -> dict:
    return json.loads((DIR / "placement.json").read_text(encoding="utf-8"))


def placement() -> dict:
    return _OVERLAY["docs"].get("placement") or _base_placement()


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
