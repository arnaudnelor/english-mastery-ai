"""The academy: six CEFR levels, the Business English Academy, level tests and assessment history."""
from __future__ import annotations

import math
import random
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import current_profile
from ..models import ActivityLog, AssessmentResult, Conversation, Message, Profile

router = APIRouter(prefix="/api/academy", tags=["academy"])
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
PASS_MARK = 0.7
FULL_NAMES = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate", "C1": "Advanced", "C2": "Proficiency"}


# ------------------------------------------------------------------ progress facts
class Facts:
    """Everything needed to decide which curriculum items are done, loaded once per request."""

    def __init__(self, db: Session, pid: int):
        rows = db.execute(select(ActivityLog.skill, ActivityLog.item_id, ActivityLog.score)
                          .where(ActivityLog.profile_id == pid).order_by(ActivityLog.id)).all()
        self.latest: dict[tuple[str, str], float] = {}
        self.vocab_reviewed: set[str] = set()
        self.pron_count = 0
        for skill, item, score in rows:
            self.latest[(skill, item)] = score
            if skill == "vocabulary":
                self.vocab_reviewed.add(item)
            if skill == "pronunciation":
                self.pron_count += 1
        conv = db.execute(select(Conversation.mode, func.count(Message.id))
                          .join(Message, Message.conversation_id == Conversation.id)
                          .where(Conversation.profile_id == pid, Message.role == "user")
                          .group_by(Conversation.id, Conversation.mode)).all()
        self.conv_turns: dict[str, int] = {}
        for mode, n in conv:
            self.conv_turns[mode] = max(self.conv_turns.get(mode, 0), n)

    def answered(self, skill: str, prefix: str, ids: list[str]) -> tuple[int, int]:
        got = [self.latest.get((skill, f"{prefix}:{i}")) for i in ids]
        return sum(g is not None for g in got), sum(1 for g in got if g is not None and g >= 0.999)


def _vocab_set(ref: str) -> list[dict]:
    kind, _, val = ref.partition(":")
    return [w for w in content.vocabulary() if (w["level"] if kind == "level" else w["domain"]) == val]


def resolve(item: dict, f: Facts) -> dict:
    """Turn a curriculum entry into {key, kind, title, route, available, done, score, detail}."""
    k, ref = item["kind"], item["ref"]
    out = {"kind": k, "ref": ref, "title": item.get("title"), "available": True, "done": False, "score": None, "detail": ""}
    if k == "lesson":
        t = content.find_topic(ref)
        if not t:
            return out | {"available": False, "title": out["title"] or ref, "route": None, "key": ref}
        ids = [e["id"] for e in t["exercises"]]
        n_ans, n_ok = f.answered("grammar", ref, ids)
        out |= {"key": ref, "title": t["title"], "route": f"/lesson/{ref}", "detail": f"{len(ids)} exercises",
                "done": n_ans >= math.ceil(0.8 * len(ids)), "score": round(n_ok / len(ids), 2) if n_ans else None,
                "summary": t["summary"]}
    elif k in ("reading", "listening"):
        src = content.reading_texts() if k == "reading" else content.listening_items()
        t = content.by_id(src, ref)
        if not t:
            return out | {"available": False, "route": None, "key": ref}
        ids = [q["id"] for q in t["questions"]]
        n_ans, n_ok = f.answered(k, ref, ids)
        out |= {"key": ref, "title": t["title"], "route": f"/{k}/{ref}", "detail": f"{len(ids)} questions",
                "done": n_ans >= math.ceil(0.75 * len(ids)), "score": round(n_ok / len(ids), 2) if n_ans else None}
    elif k == "vocab":
        words = _vocab_set(ref)
        seen = sum(1 for w in words if w["id"] in f.vocab_reviewed)
        need = min(10, math.ceil(0.6 * len(words))) if words else 1
        kind, _, val = ref.partition(":")
        out |= {"key": f"vocab-{ref}", "route": f"/vocabulary?{kind}={quote(val)}", "detail": f"{len(words)} words · {seen} reviewed",
                "done": bool(words) and seen >= need, "score": round(seen / len(words), 2) if words else None, "available": bool(words)}
    elif k == "conversation":
        turns = f.conv_turns.get(ref, 0)
        out |= {"key": f"conv-{ref}", "route": f"/conversation?mode={ref}", "detail": "AI conversation · at least 3 turns",
                "done": turns >= 3, "score": None}
    elif k == "writing":
        s = f.latest.get(("writing", f"lesson:{ref}"))
        out |= {"key": ref, "route": f"/writing?genre={item['genre']}&lesson={ref}&task={quote(item['task'])}",
                "detail": item["task"], "done": s is not None, "score": round(s, 2) if s is not None else None}
    elif k == "pronunciation":
        out |= {"key": f"pron-{item['title'][:20]}", "route": "/pronunciation", "detail": "5 recorded pronunciation exercises",
                "done": f.pron_count >= 5, "score": None}
    else:  # "soon"
        out |= {"key": f"soon-{item['title'][:30]}", "route": None, "available": False, "detail": "Coming soon"}
    return out


def _level_def(code: str) -> dict:
    lv = next((x for x in content.curriculum()["levels"] if x["code"] == code), None)
    if not lv:
        raise HTTPException(404, "Unknown level")
    return lv


def _tests(db: Session, pid: int, kind: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in db.scalars(select(AssessmentResult).where(AssessmentResult.profile_id == pid, AssessmentResult.kind == kind)):
        o = out.setdefault(r.level, {"attempts": 0, "best": 0.0, "passed": False, "last_at": None})
        o["attempts"] += 1
        o["best"] = max(o["best"], r.score)
        o["passed"] = o["passed"] or bool(r.passed)
        o["last_at"] = r.created_at.isoformat()
    return out


def confirmed(p: Profile) -> bool:
    return bool(p.level_confirmed) or p.placement_done_at is not None


def level_status(code: str, p: Profile, tests: dict) -> str:
    if not confirmed(p):
        return "available" if code == "A1" else "locked"
    cur = LEVELS.index(p.estimated_level) if p.estimated_level in LEVELS else 0
    i = LEVELS.index(code)
    if i < cur:
        return "completed"
    if i == cur:
        return "completed" if tests.get(code, {}).get("passed") and code == "C2" else "current"
    return "locked"


def _summarise_level(lv: dict, f: Facts, p: Profile, tests: dict) -> dict:
    items = [resolve(it, f) for u in lv["units"] for it in u["items"]]
    avail = [i for i in items if i["available"]]
    done = sum(i["done"] for i in avail)
    nxt = next((i for i in avail if not i["done"]), None)
    return {"code": lv["code"], "name": lv["name"], "full_name": f"{lv['code']} — {lv['name'].upper()}", "description": lv["description"],
            "lesson_count": len(avail), "coming_soon": len(items) - len(avail), "done": done,
            "percent": round(100 * done / len(avail)) if avail else 0, "status": level_status(lv["code"], p, tests),
            "test": tests.get(lv["code"]), "next": nxt and {"title": nxt["title"], "route": nxt["route"]}}


def _business_summary(f: Facts, tests: dict) -> dict:
    cats = content.curriculum()["business"]
    total = done = 0
    for c in cats:
        for it in c["items"]:
            r = resolve(it, f)
            if r["available"]:
                total += 1
                done += r["done"]
    return {"categories": len(cats), "lesson_count": total, "done": done, "percent": round(100 * done / total) if total else 0,
            "test": tests.get("business")}


# ------------------------------------------------------------------ endpoints
@router.get("/overview")
def overview(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    f = Facts(db, p.id)
    tests = _tests(db, p.id, "level_test")
    levels = [_summarise_level(lv, f, p, tests) for lv in content.curriculum()["levels"]]
    last_pl = db.scalar(select(AssessmentResult).where(AssessmentResult.profile_id == p.id, AssessmentResult.kind == "placement")
                        .order_by(AssessmentResult.id.desc()))
    cur = next((lv for lv in levels if lv["status"] == "current"), None)
    return {
        "level_confirmed": confirmed(p),
        "current_level": p.estimated_level if confirmed(p) else None,
        "current_level_name": FULL_NAMES.get(p.estimated_level) if confirmed(p) else None,
        "levels": levels,
        "business": _business_summary(f, _tests(db, p.id, "business")),
        "placement": {"done": p.placement_done_at is not None,
                      "date": p.placement_done_at.isoformat() if p.placement_done_at else None,
                      "last": last_pl and {"level": last_pl.level, "details": last_pl.details, "date": last_pl.created_at.isoformat()}},
        "next": cur and cur["next"],
    }


@router.get("/level/{code}")
def level_detail(code: str, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    lv = _level_def(code)
    f = Facts(db, p.id)
    tests = _tests(db, p.id, "level_test")
    summary = _summarise_level(lv, f, p, tests)
    units = [{"title": u["title"], "items": [resolve(it, f) for it in u["items"]]} for u in lv["units"]]
    i = LEVELS.index(code)
    return summary | {"units": units, "pass_mark": PASS_MARK,
                      "next_level": LEVELS[i + 1] if i + 1 < len(LEVELS) else None,
                      "can_take_test": summary["status"] in ("current", "completed", "available")}


class ChooseIn(BaseModel):
    level: str = Field(pattern=r"^(A1|A2|B1|B2|C1|C2)$")


@router.post("/choose-level")
def choose_level(body: ChooseIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    """Manual choice when the learner skips the placement test. They can take it at any time later."""
    p.estimated_level = body.level
    p.level_confirmed = 1
    db.commit()
    return {"current_level": p.estimated_level}


def _exercise_pool(topics: list[dict]) -> list[dict]:
    return [{"key": f"g:{t['id']}:{e['id']}", "type": e["type"], "prompt": e["prompt"], "options": e.get("options"), "topic": t["title"]}
            for t in topics for e in t["exercises"] if e["type"] in ("mcq", "gap")]


def _vocab_items(words: list[dict], rng: random.Random, n: int) -> list[dict]:
    pool = content.vocabulary()
    out = []
    for w in rng.sample(words, min(n, len(words))):
        same = [x["word"] for x in pool if x["id"] != w["id"] and x["level"] == w["level"]] or [x["word"] for x in pool if x["id"] != w["id"]]
        opts = rng.sample(same, 3) + [w["word"]]
        rng.shuffle(opts)
        out.append({"key": f"v:{w['id']}", "type": "mcq", "prompt": f"Which word or expression means: “{w['definition']}”", "options": opts, "topic": "Vocabulary"})
    return out


def _build_test(topics: list[dict], words: list[dict], n_ex: int, n_voc: int) -> list[dict]:
    rng = random.Random()
    pool = _exercise_pool(topics)
    # spread across topics: one per topic first, then fill
    by_topic: dict[str, list[dict]] = {}
    for it in pool:
        by_topic.setdefault(it["topic"], []).append(it)
    picked = [rng.choice(v) for v in by_topic.values()]
    rng.shuffle(picked)
    picked = picked[:n_ex]
    rest = [x for x in pool if x not in picked]
    picked += rng.sample(rest, max(0, min(len(rest), n_ex - len(picked))))
    return picked + _vocab_items(words, rng, n_voc)


def _grade(answers: dict[str, str]) -> tuple[float, list[dict]]:
    review = []
    for key, given in answers.items():
        parts = key.split(":")
        if parts[0] == "g" and len(parts) == 3:
            t = content.find_topic(parts[1])
            e = next((x for x in (t or {}).get("exercises", []) if x["id"] == parts[2]), None)
            if not e:
                continue
            ok = content.check_answer(e, given)
            ans = e["answer"] if isinstance(e["answer"], str) else e["answer"][0]
            review.append({"key": key, "correct": ok, "given": given, "answer": ans, "explanation": e["explanation"], "topic": t["title"]})
        elif parts[0] == "v" and len(parts) == 2:
            w = content.find_word(parts[1])
            if not w:
                continue
            ok = content.normalise(given) == content.normalise(w["word"])
            review.append({"key": key, "correct": ok, "given": given, "answer": w["word"], "explanation": w["examples"][0], "topic": "Vocabulary"})
    if not review:
        raise HTTPException(400, "No valid answers")
    return sum(r["correct"] for r in review) / len(review), review


def _level_topics(code: str) -> list[dict]:
    lv = _level_def(code)
    refs = [it["ref"] for u in lv["units"] for it in u["items"] if it["kind"] == "lesson"]
    return [t for t in (content.find_topic(r) for r in refs) if t]


@router.get("/level/{code}/test")
def level_test(code: str, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    status = level_status(code, p, _tests(db, p.id, "level_test"))
    if status == "locked":
        raise HTTPException(403, "This level is locked. Take the placement test or pass the previous level's test first.")
    words = [w for w in content.vocabulary() if w["level"] == code]
    return {"level": code, "pass_mark": PASS_MARK, "items": _build_test(_level_topics(code), words, 15, 5)}


class TestIn(BaseModel):
    answers: dict[str, str]
    seconds: int = Field(0, ge=0, le=14400)


def _weak_topics(review: list[dict]) -> list[str]:
    from collections import Counter
    c = Counter(r["topic"] for r in review if not r["correct"])
    return [t for t, _ in c.most_common(4)]


@router.post("/level/{code}/test")
def submit_level_test(code: str, body: TestIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    status = level_status(code, p, _tests(db, p.id, "level_test"))
    if status == "locked":
        raise HTTPException(403, "This level is locked.")
    score, review = _grade(body.answers)
    passed = score >= PASS_MARK
    promoted_to = None
    i = LEVELS.index(code)
    if passed and status in ("current", "available") and i + 1 < len(LEVELS):
        promoted_to = LEVELS[i + 1]
        p.estimated_level = promoted_to
        p.level_confirmed = 1
    elif passed and status == "available":
        p.estimated_level, p.level_confirmed = code, 1
    weak = _weak_topics(review)
    db.add(AssessmentResult(profile_id=p.id, kind="level_test", level=code, score=score, passed=int(passed),
                            details={"weak_topics": weak, "promoted_to": promoted_to, "n": len(review)}))
    db.add(ActivityLog(profile_id=p.id, skill="grammar", item_id=f"level_test:{code}", score=score, seconds=body.seconds))
    db.commit()
    return {"score": round(score, 3), "passed": passed, "pass_mark": PASS_MARK, "promoted_to": promoted_to,
            "promoted_name": promoted_to and FULL_NAMES[promoted_to], "weak_topics": weak, "review": review}


# ------------------------------------------------------------------ business academy
@router.get("/business")
def business(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    f = Facts(db, p.id)
    cats = []
    for c in content.curriculum()["business"]:
        items = [resolve(it, f) for it in c["items"]]
        avail = [i for i in items if i["available"]]
        done = sum(i["done"] for i in avail)
        cats.append({k: c[k] for k in ("id", "title", "icon", "level")} | {
            "items": items, "lesson_count": len(avail), "done": done, "percent": round(100 * done / len(avail)) if avail else 0,
            "summary": (content.find_topic(c["items"][0]["ref"]) or {}).get("summary", "")})
    return {"categories": cats, "summary": _business_summary(f, _tests(db, p.id, "business")), "pass_mark": PASS_MARK}


@router.get("/business/test")
def business_test(p: Profile = Depends(current_profile)):
    words = [w for w in content.vocabulary() if w["domain"] in ("business", "finance", "banking", "economics", "investment", "management", "leadership", "project management", "risk management")]
    return {"pass_mark": PASS_MARK, "items": _build_test(content.business_lessons(), words, 18, 6)}


@router.post("/business/test")
def submit_business_test(body: TestIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    score, review = _grade(body.answers)
    passed = score >= PASS_MARK
    weak = _weak_topics(review)
    db.add(AssessmentResult(profile_id=p.id, kind="business", level="business", score=score, passed=int(passed), details={"weak_topics": weak, "n": len(review)}))
    db.add(ActivityLog(profile_id=p.id, skill="vocabulary", item_id="business_test", score=score, seconds=body.seconds))
    db.commit()
    return {"score": round(score, 3), "passed": passed, "pass_mark": PASS_MARK, "weak_topics": weak, "review": review}


@router.get("/assessments")
def assessments(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    rows = db.scalars(select(AssessmentResult).where(AssessmentResult.profile_id == p.id).order_by(AssessmentResult.id.desc())).all()
    return [{"id": r.id, "kind": r.kind, "level": r.level, "score": round(r.score, 3), "passed": bool(r.passed),
             "details": r.details, "date": r.created_at.isoformat()} for r in rows]
