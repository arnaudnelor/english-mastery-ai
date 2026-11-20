"""Placement test (4 skills) and weekly progress checks."""
from __future__ import annotations

import random
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import current_profile, provider_errors
from ..models import ActivityLog, AssessmentResult, Mistake, Profile, VocabCard
from ..providers.llm import ChatMessage, MissingAPIKey, ProviderError, get_llm
from ..providers.speech import fluency_metrics, transcribe_any

router = APIRouter(prefix="/api/assess", tags=["assessment"])
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_PROMPT = """You are a CEFR-certified assessor. Rate the learner's {skill} sample on the CEFR scale. \
Return strict JSON: {{"level": "A1"|"A2"|"B1"|"B2"|"C1"|"C2", "justification": str, "strengths": [str], "priorities": [str]}}. \
Be calibrated and conservative; quote the learner where useful."""


def accuracy_level(pct: float) -> str:
    """Placement reading/listening mix an A2 item with B2–C1 items, so low scores map below B1."""
    for cut, lv in ((0.2, "A1"), (0.4, "A2"), (0.55, "B1"), (0.7, "B2"), (0.85, "C1")):
        if pct < cut:
            return lv
    return "C2"


def grammar_level(by_level: dict[str, tuple[int, int]], threshold: float = 0.6) -> str:
    """Highest level such that it and every lower level are >= threshold correct (A1 is the floor)."""
    result = "A1"
    for lv in LEVELS:
        if lv not in by_level:
            continue
        c, t = by_level[lv]
        if c / t >= threshold:
            result = lv
        else:
            break
    return result


def median_level(levels: list[str]) -> str:
    order = LEVELS
    idx = sorted(order.index(lv) for lv in levels)
    return order[idx[(len(idx) - 1) // 2]]  # lower median: conservative


@router.get("/placement")
def placement():
    pl = content.placement()
    rt = content.by_id(content.reading_texts(), pl["reading_text"].split(":")[1])
    strip = lambda q: {k: v for k, v in q.items() if k not in ("answer", "explanation")}  # noqa: E731
    listening = []
    for iid in pl["listening_items"]:
        it = content.by_id(content.listening_items(), iid)
        listening.append({"id": iid, "title": it["title"], "speakers": it["speakers"], "lines": it["lines"],
                          "questions": [strip(q) | {"key": f"{iid}:{q['id']}"} for q in it["questions"]]})
    return {
        "grammar_vocab": [strip(q) for q in pl["grammar_vocab"]],
        "reading": {"title": rt["title"], "body": rt["body"], "questions": [strip(q) | {"key": f"{rt['id']}:{q['id']}"} for q in rt["questions"]]},
        "listening": listening,
        "writing_prompt": pl["writing_prompt"],
        "speaking_prompt": pl["speaking_prompt"],
    }


@router.post("/placement/speaking")
@provider_errors
def placement_speaking(audio: UploadFile = File(...), transcript: str = Form(""), duration: float = Form(0),
                       p: Profile = Depends(current_profile)):
    data = audio.file.read()
    if not data and not transcript:
        raise HTTPException(400, "Empty recording")
    t = transcribe_any(data, audio.filename or "speech.webm", transcript, duration)
    if not t.text:
        raise HTTPException(422, "No speech recognised")
    m = fluency_metrics(t)
    r = get_llm().chat_json([ChatMessage("system", CEFR_PROMPT.format(skill="spoken (transcribed) English; metrics: " + str(m))),
                             ChatMessage("user", f"Prompt: {content.placement()['speaking_prompt']}\nTranscript: {t.text}")], max_tokens=600)
    return r | {"transcript": t.text, "metrics": m}


class PlacementIn(BaseModel):
    answers: dict[str, str]
    writing: str = Field("", max_length=5000)
    speaking_level: str | None = Field(None, pattern=r"^(A1|A2|B1|B2|C1|C2)$")
    seconds: int = Field(0, ge=0, le=14400)


@router.post("/placement/submit")
def placement_submit(body: PlacementIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    pl = content.placement()
    by_level: dict[str, list[int]] = {}
    for q in pl["grammar_vocab"]:
        ok = content.normalise(body.answers.get(q["id"], "")) == content.normalise(q["answer"])
        c = by_level.setdefault(q["level"], [0, 0])
        c[0] += ok
        c[1] += 1
    from ..services.platform import get_setting

    try:
        threshold = float(get_setting(db, "placement_level_threshold") or 0.6)
    except (TypeError, ValueError):
        threshold = 0.6
    g_level = grammar_level({k: (v[0], v[1]) for k, v in by_level.items()}, threshold)
    g_score = sum(v[0] for v in by_level.values()) / sum(v[1] for v in by_level.values())

    def objective(keys_questions):
        right = sum(content.normalise(body.answers.get(k, "")) == content.normalise(q["answer"]) for k, q in keys_questions)
        return right / max(1, len(keys_questions))

    rt = content.by_id(content.reading_texts(), pl["reading_text"].split(":")[1])
    r_score = objective([(f"{rt['id']}:{q['id']}", q) for q in rt["questions"]])
    l_pairs = [(f"{iid}:{q['id']}", q) for iid in pl["listening_items"] for q in content.by_id(content.listening_items(), iid)["questions"]]
    l_score = objective(l_pairs)

    skills = {"grammar_vocabulary": g_level, "reading": accuracy_level(r_score), "listening": accuracy_level(l_score)}
    notes = []
    writing_result = None
    if len(body.writing.split()) >= 40:
        try:
            writing_result = get_llm().chat_json([ChatMessage("system", CEFR_PROMPT.format(skill="written")),
                                                  ChatMessage("user", f"Prompt: {pl['writing_prompt']}\nText: {body.writing}")], max_tokens=600)
            if writing_result.get("level") in LEVELS:
                skills["writing"] = writing_result["level"]
        except (MissingAPIKey, ProviderError) as e:
            notes.append(f"Writing not assessed: {e}")
    else:
        notes.append("Writing skipped (fewer than 40 words).")
    if body.speaking_level:
        skills["speaking"] = body.speaking_level
    else:
        notes.append("Speaking skipped.")

    overall = median_level(list(skills.values()))
    p.estimated_level = overall
    p.level_confirmed = 1
    p.placement_done_at = datetime.utcnow()
    construction = [q for q in pl["grammar_vocab"] if q.get("skill") == "construction"]
    c_score = sum(content.normalise(body.answers.get(q["id"], "")) == content.normalise(q["answer"]) for q in construction) / max(1, len(construction))
    db.add(AssessmentResult(profile_id=p.id, kind="placement", level=overall, score=g_score, passed=1,
                            details={"skills": skills, "scores": {"grammar_vocabulary": round(g_score, 2), "sentence_construction": round(c_score, 2),
                                                                  "reading": round(r_score, 2), "listening": round(l_score, 2)}}))
    for skill, score in (("grammar", g_score), ("reading", r_score), ("listening", l_score)):
        db.add(ActivityLog(profile_id=p.id, skill=skill, item_id="placement", score=score, seconds=body.seconds // 4))
    db.commit()
    order = LEVELS.index(overall)
    labels = {"grammar_vocabulary": "Grammar and vocabulary", "reading": "Reading", "listening": "Listening", "writing": "Writing", "speaking": "Speaking"}
    strengths = [f"{labels[k]} ({v})" for k, v in skills.items() if LEVELS.index(v) > order]
    weaknesses = [f"{labels[k]} ({v})" for k, v in skills.items() if LEVELS.index(v) < order]
    if c_score < 0.5:
        weaknesses.append(f"Sentence construction ({round(c_score * 100)}%)")
    elif c_score >= 0.85:
        strengths.append(f"Sentence construction ({round(c_score * 100)}%)")
    if not strengths:
        strengths = ["Balanced profile: your skills are at a similar level"]
    lv_def = next(x for x in content.curriculum()["levels"] if x["code"] == overall)
    pathway = [f"Start the {overall} programme: {u['title']}" for u in lv_def["units"][:3]]
    pathway += [f"Extra practice: {labels[k].lower()}" for k, v in skills.items() if LEVELS.index(v) < order][:2]
    pathway.append(f"Take the {overall} level test when your units are done (pass mark {round(float(get_setting(db, 'level_test_pass_mark') or 0.7) * 100)}%)")
    last = db.scalars(select(AssessmentResult).where(AssessmentResult.profile_id == p.id, AssessmentResult.kind == "placement")
                      .order_by(AssessmentResult.id.desc())).first()
    if last is not None:
        last.details = (last.details or {}) | {"strengths": strengths, "weaknesses": weaknesses, "pathway": pathway}
    if p.user_id:
        from ..services import platform

        platform.notify(db, p.user_id, "assessment", f"Placement result: {overall}", "Your programme is ready.", f"/level/{overall}", email=True)
        platform.notify_admins(db, "assessment", f"{p.name} completed the placement test: {overall}", "", f"/admin/learners/{p.user_id}",
                               setting="admin_assessment")
    db.commit()
    names = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate", "C1": "Advanced", "C2": "Proficiency"}
    return {"overall": overall, "overall_name": names[overall], "skills": skills,
            "scores": {"grammar_vocabulary": round(g_score, 2), "sentence_construction": round(c_score, 2), "reading": round(r_score, 2), "listening": round(l_score, 2)},
            "writing": writing_result, "notes": notes, "strengths": strengths, "weaknesses": weaknesses, "pathway": pathway,
            "disclaimer": "Placement estimate for planning your study, not a certified CEFR result."}


# ---------------------------------------------------------------- weekly check
def _weekly_pool(db: Session, p: Profile) -> list[dict]:
    target_levels = {p.estimated_level, p.target_level}
    weak_topics = {m.pattern for m in db.scalars(select(Mistake).where(Mistake.profile_id == p.id, Mistake.source == "grammar_exercise"))}
    pool = content.grammar_topics() + content.lessons()
    topics = [t for t in pool if t["title"] in weak_topics] + \
             [t for t in pool if t["level"] in target_levels and t["title"] not in weak_topics]
    items = []
    for t in topics:
        for e in t["exercises"]:
            if e["type"] in ("mcq", "gap"):
                items.append({"key": f"g:{t['id']}:{e['id']}", "kind": "grammar", "topic": t["title"], "type": e["type"],
                              "prompt": e["prompt"], "options": e.get("options")})
    deck = [c.word_id for c in db.scalars(select(VocabCard).where(VocabCard.profile_id == p.id))]
    words = [w for w in content.vocabulary() if w["id"] in deck] or [w for w in content.vocabulary() if w["level"] in target_levels]
    return items, words


@router.get("/weekly")
def weekly(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    items, words = _weekly_pool(db, p)
    rng = random.Random(f"{p.id}-{datetime.utcnow().isocalendar()[:2]}")  # stable within a week
    grammar = items[:4] + rng.sample(items[4:], min(4, max(0, len(items) - 4)))
    vocab = []
    all_words = content.vocabulary()
    for w in rng.sample(words, min(4, len(words))):
        distractors = rng.sample([x["word"] for x in all_words if x["id"] != w["id"]], 3)
        opts = distractors + [w["word"]]
        rng.shuffle(opts)
        vocab.append({"key": f"v:{w['id']}", "kind": "vocabulary", "type": "mcq", "prompt": f"Which word means: “{w['definition']}”", "options": opts})
    return {"items": grammar + vocab}


class WeeklyIn(BaseModel):
    answers: dict[str, str]


@router.post("/weekly/submit")
def weekly_submit(body: WeeklyIn, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    review = []
    for key, given in body.answers.items():
        parts = key.split(":")
        if parts[0] == "g" and len(parts) == 3:
            t = content.find_topic(parts[1])
            e = next((x for x in (t or {}).get("exercises", []) if x["id"] == parts[2]), None)
            if not e:
                continue
            ok = content.check_answer(e, given)
            ans = e["answer"] if isinstance(e["answer"], str) else e["answer"][0]
            review.append({"key": key, "correct": ok, "answer": ans, "explanation": e["explanation"]})
            db.add(ActivityLog(profile_id=p.id, skill="grammar", item_id=f"weekly:{parts[1]}", score=float(ok), seconds=40))
        elif parts[0] == "v" and len(parts) == 2:
            w = content.find_word(parts[1])
            if not w:
                continue
            ok = content.normalise(given) == content.normalise(w["word"])
            review.append({"key": key, "correct": ok, "answer": w["word"], "explanation": w["examples"][0]})
            db.add(ActivityLog(profile_id=p.id, skill="vocabulary", item_id=f"weekly:{w['id']}", score=float(ok), seconds=20))
    if not review:
        raise HTTPException(400, "No valid answers")
    score = sum(r["correct"] for r in review) / len(review)
    db.add(ActivityLog(profile_id=p.id, skill="grammar", item_id="weekly_check", score=score, seconds=0))
    db.commit()
    return {"score": round(score, 3), "review": review}
